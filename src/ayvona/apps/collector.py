"""Collector process: reads new posts from every source and stores them *raw* in ``raw_posts``.

Reliability rules (docs/ARCHITECTURE.md §2):
* store first, process later — this process only writes raw posts;
* posts and the source cursor (``last_seen_id``) are committed in ONE transaction;
* one failing source never stops the others;
* heartbeat in ``kv_store`` every minute; Ctrl+C / SIGTERM stops cleanly.

Run:  uv run python -m ayvona.apps.collector          (forever)
      uv run python -m ayvona.apps.collector --once   (one cycle, then exit — for checking)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import CollectorConfig, Settings, get_settings
from ayvona.db.models import SourceType
from ayvona.db.repositories import kv_repo, raw_posts_repo, sources_repo
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.logging_setup import setup_logging
from ayvona.sources.base import BaseSource, SourceRateLimited
from ayvona.sources.registry import SourceDeps, create_source
from ayvona.sources.telegram_source import TelegramConfigError, connect_client
from ayvona.timeutil import utcnow

PROCESS_NAME = "collector"
LAST_CYCLE_KEY = "collector:last_cycle_at"

SessionFactory = async_sessionmaker[AsyncSession]
SleepFn = Callable[[float], Awaitable[bool]]  # returns True if we should stop


@dataclass(slots=True)
class PollOutcome:
    source_id: int
    identifier: str
    fetched: int = 0
    inserted: int = 0
    cursor: str | None = None
    error: str | None = None
    rate_limited_for: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(slots=True)
class ActiveSource:
    source_id: int
    source: BaseSource


# ------------------------------------------------------------------ helpers
def advance_cursor(old: str | None, new: str | None) -> str | None:
    """New ``last_seen_id`` to store (``None`` = keep). Numeric cursors never go backwards."""
    if new is None or new == old:
        return None
    if old is not None and old.isdigit() and new.isdigit() and int(new) < int(old):
        logger.warning("cursor would go backwards ({} -> {}), ignored", old, new)
        return None
    return new


async def _record_error(sf: SessionFactory, source_id: int, error: str) -> None:
    """Best effort: a broken DB must not crash the loop here."""
    try:
        async with sf() as s, s.begin():
            await sources_repo.mark_error(s, source_id, error, utcnow())
    except Exception:
        logger.exception("could not record error for source {}", source_id)


def stop_aware_sleep(stop: asyncio.Event) -> SleepFn:
    async def _sleep(seconds: float) -> bool:
        if seconds <= 0:
            return stop.is_set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        return stop.is_set()

    return _sleep


# ------------------------------------------------------------------ one source
async def poll_source(
    sf: SessionFactory, source_id: int, source: BaseSource, *, fetch_timeout: float
) -> PollOutcome:
    """Fetch new posts of one source and commit them together with the new cursor."""
    out = PollOutcome(source_id=source_id, identifier=source.identifier)

    try:
        async with sf() as s:
            row = await sources_repo.get(s, source_id)
            since = row.last_seen_id if row else None
    except Exception as e:  # e.g. DB locked longer than busy_timeout — try again next cycle
        out.error = f"db read: {type(e).__name__}: {e}"
        logger.opt(exception=e).error("{}: last_seen_id o'qilmadi", source.identifier)
        return out

    # 1) network — outside any DB transaction
    try:
        result = await asyncio.wait_for(source.fetch_new(since), timeout=fetch_timeout)
    except SourceRateLimited as e:
        out.error = f"rate limited: wait {e.seconds:.0f}s"
        out.rate_limited_for = e.seconds
        logger.warning("{}: Telegram kutishni so'radi — {:.0f} s", source.identifier, e.seconds)
        await _record_error(sf, source_id, out.error)
        return out
    except TimeoutError:
        out.error = f"timeout after {fetch_timeout:.0f}s"
        logger.warning("{}: javob kelmadi ({})", source.identifier, out.error)
        await _record_error(sf, source_id, out.error)
        return out
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
        logger.opt(exception=e).error("{}: o'qishda xato", source.identifier)
        await _record_error(sf, source_id, out.error)
        return out

    out.fetched = len(result.items)
    new_cursor = advance_cursor(since, result.cursor)

    # 2) ONE transaction: raw posts + cursor. Crash/exception here => neither is saved,
    #    the same posts are fetched again next cycle (and UNIQUE stops duplicates).
    try:
        async with sf() as s, s.begin():
            out.inserted = await raw_posts_repo.insert_ignore_duplicates(
                s, source_id, result.items, utcnow()
            )
            await sources_repo.mark_success(s, source_id, new_cursor, utcnow())
    except Exception as e:
        out.error = f"db: {type(e).__name__}: {e}"
        out.inserted = 0
        logger.opt(exception=e).error("{}: bazaga yozishda xato", source.identifier)
        await _record_error(sf, source_id, out.error)
        return out

    out.cursor = new_cursor or since
    if out.fetched or new_cursor:
        logger.info(
            "{}: {} ta yangi post (olingan {}), last_seen_id={}",
            source.identifier,
            out.inserted,
            out.fetched,
            out.cursor,
        )
    return out


# ------------------------------------------------------------------ one cycle
async def run_cycle(
    sf: SessionFactory,
    sources: Sequence[ActiveSource],
    cfg: CollectorConfig,
    sleep: SleepFn,
) -> list[PollOutcome]:
    outcomes: list[PollOutcome] = []
    for i, active in enumerate(sources):
        out = await poll_source(
            sf, active.source_id, active.source, fetch_timeout=cfg.fetch_timeout_seconds
        )
        outcomes.append(out)
        if out.rate_limited_for is not None:
            # Same Telegram account for every channel: wait as asked, then continue.
            if await sleep(out.rate_limited_for + 1):
                break
        elif i < len(sources) - 1 and await sleep(cfg.delay_between_sources_seconds):
            break
    try:
        async with sf() as s, s.begin():
            await kv_repo.set_value(s, LAST_CYCLE_KEY, utcnow().isoformat())
    except Exception:
        logger.exception("could not write {}", LAST_CYCLE_KEY)
    return outcomes


async def write_heartbeat(sf: SessionFactory) -> None:
    try:
        async with sf() as s, s.begin():
            await kv_repo.write_heartbeat(s, PROCESS_NAME)
    except Exception:
        logger.exception("heartbeat write failed")


async def heartbeat_loop(sf: SessionFactory, interval: float, stop: asyncio.Event) -> None:
    """Writes every ``interval`` s. The first beat is written by the caller before starting."""
    sleep = stop_aware_sleep(stop)
    while not await sleep(interval):
        await write_heartbeat(sf)


# ------------------------------------------------------------------ main loop
async def build_active_sources(
    sf: SessionFactory, settings: Settings, deps: SourceDeps
) -> list[ActiveSource]:
    """Sync settings.yaml -> ``sources`` table, then create a source object for each enabled row."""
    async with sf() as s, s.begin():
        rows = await sources_repo.sync_from_config(s, settings.app.sources)
    active: list[ActiveSource] = []
    for row in rows:
        try:
            active.append(ActiveSource(row.id, create_source(row, deps)))
        except Exception as e:
            logger.error("{}: manbani yaratib bo'lmadi: {}", row.identifier, e)
            await _record_error(sf, row.id, f"{type(e).__name__}: {e}")
    return active


async def run_collector(
    sf: SessionFactory,
    sources: Sequence[ActiveSource],
    cfg: CollectorConfig,
    stop: asyncio.Event,
    *,
    max_cycles: int | None = None,
) -> None:
    """Poll forever (or ``max_cycles`` times) until ``stop`` is set."""
    sleep = stop_aware_sleep(stop)
    await write_heartbeat(sf)  # immediately, so even a --once run leaves a heartbeat
    heartbeat = asyncio.create_task(heartbeat_loop(sf, cfg.heartbeat_interval_seconds, stop))
    if not sources:
        logger.warning(
            "Faol manba yo'q. config/settings.yaml dagi 'sources:' ga kanal qo'shing "
            "va qayta yoqing."
        )
    cycles = 0
    try:
        while not stop.is_set():
            outcomes = await run_cycle(sf, sources, cfg, sleep)
            cycles += 1
            failed = [o.identifier for o in outcomes if not o.ok]
            logger.debug(
                "sikl #{}: {} manba, {} yangi post, xato: {}",
                cycles,
                len(outcomes),
                sum(o.inserted for o in outcomes),
                failed or "yo'q",
            )
            if max_cycles is not None and cycles >= max_cycles:
                break
            if await sleep(cfg.poll_interval_seconds):
                break
    finally:
        stop.set()
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
        for active in sources:
            with contextlib.suppress(Exception):
                await active.source.close()


def _install_signal_handlers(stop: asyncio.Event) -> None:
    """SIGTERM (systemd stop) -> clean shutdown. Windows has only Ctrl+C (KeyboardInterrupt)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(sig, stop.set)


async def main(once: bool = False) -> int:
    settings = get_settings()
    setup_logging(settings.env.log_level, settings.log_dir, PROCESS_NAME)
    logger.info("Collector ishga tushmoqda (baza: {})", settings.db_file)

    engine = create_engine(settings.db_url)
    client = None
    try:
        if not await schema_is_ready(engine):
            logger.error(
                "Baza tayyor emas. Avval shu buyruqni bajaring: uv run alembic upgrade head"
            )
            return 1
        sf = create_session_factory(engine)

        needs_telegram = any(
            s.enabled and SourceType.of(s.type) is SourceType.TELEGRAM for s in settings.app.sources
        )
        if needs_telegram:
            try:
                client = await connect_client(settings)
            except TelegramConfigError as e:
                logger.error(str(e))
                return 1
            me = await client.get_me()
            logger.info("Telegram'ga ulandi: {}", getattr(me, "username", None) or me.id)

        deps = SourceDeps(collector=settings.app.collector, telegram_client=client)
        sources = await build_active_sources(sf, settings, deps)
        logger.info("Faol manbalar: {}", [a.source.identifier for a in sources] or "yo'q")

        stop = asyncio.Event()
        _install_signal_handlers(stop)
        await run_collector(
            sf, sources, settings.app.collector, stop, max_cycles=1 if once else None
        )
        return 0
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                await client.disconnect()
        await engine.dispose()
        logger.info("Collector to'xtadi.")


def run() -> int:
    parser = argparse.ArgumentParser(description="Ayvona collector")
    parser.add_argument("--once", action="store_true", help="bitta sikl bajarib, chiqish")
    args = parser.parse_args()
    try:
        return asyncio.run(main(once=args.once))
    except KeyboardInterrupt:  # Ctrl+C on Windows
        logger.info("Ctrl+C — to'xtatildi.")
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
