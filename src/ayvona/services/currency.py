"""USD → so'm rate for the salary filter (``kv_store.usd_rate``), refreshed by the worker once a day
from the Central Bank's free open API (cbu.uz). Any error keeps the old rate (or the fallback in
settings.yaml) — search never depends on the network.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta

import aiohttp
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import KVStore
from ayvona.services.search import USD_RATE_KEY, set_usd_rate
from ayvona.timeutil import ensure_utc, utcnow

Fetch = Callable[[str], Awaitable[float]]
SleepFn = Callable[[float], Awaitable[bool]]
TIMEOUT_SECONDS = 20
RETRY_SECONDS = 3600


async def fetch_cbu_rate(url: str) -> float:
    """``[{"Ccy": "USD", "Rate": "12850.35", ...}]`` -> 12850.35."""
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as http, http.get(url) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    item = data[0] if isinstance(data, list) else data
    rate = float(str(item["Rate"]).replace(",", "."))
    if not 1_000 < rate < 100_000:
        raise ValueError(f"unexpected USD rate: {rate}")
    return rate


async def refresh_usd_rate(
    settings: Settings, sf: async_sessionmaker[AsyncSession], fetch: Fetch = fetch_cbu_rate
) -> float | None:
    """Fetch and store the rate. ``None`` on any error (the old value stays)."""
    try:
        rate = await fetch(settings.app.search.usd_rate_url)
    except Exception as e:
        logger.warning("USD kursi olinmadi ({}: {}) — eski qiymat qoladi", type(e).__name__, e)
        return None
    async with sf() as s, s.begin():
        await set_usd_rate(s, rate, utcnow())
    logger.info("USD kursi yangilandi: 1 $ = {} so'm", rate)
    return rate


async def rate_age_hours(sf: async_sessionmaker[AsyncSession]) -> float | None:
    """How old the stored rate is; ``None`` if there is none."""
    async with sf() as s:
        row = await s.get(KVStore, USD_RATE_KEY)
    if row is None or not row.value:
        return None
    return (utcnow() - ensure_utc(row.updated_at)) / timedelta(hours=1)


async def run_usd_rate(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
    sleep: SleepFn,
    fetch: Fetch = fetch_cbu_rate,
) -> None:
    """Worker task: refresh when the stored rate is older than ``usd_rate_refresh_hours``.
    An empty ``usd_rate_url`` turns it off (tests, offline use: the fallback rate is used)."""
    if not settings.app.search.usd_rate_url:
        return
    every = settings.app.search.usd_rate_refresh_hours
    while True:
        try:
            age = await rate_age_hours(sf)
            if age is None or age >= every:
                ok = await refresh_usd_rate(settings, sf, fetch)
                wait = every * 3600 if ok else RETRY_SECONDS
            else:
                wait = (every - age) * 3600
        except Exception:
            logger.exception("USD kursi: kutilmagan xato")
            wait = RETRY_SECONDS
        if await sleep(max(wait, 60)):
            return
