"""Helpers shared by the three processes (collector, worker, bot): stop-aware sleep, clean
shutdown on SIGTERM / Ctrl+C, heartbeat in ``kv_store``."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Awaitable, Callable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.db.repositories import kv_repo

SessionFactory = async_sessionmaker[AsyncSession]
SleepFn = Callable[[float], Awaitable[bool]]  # returns True if we should stop


def stop_aware_sleep(stop: asyncio.Event) -> SleepFn:
    """``await sleep(s)`` waits ``s`` seconds or until ``stop`` is set; True = stop."""

    async def _sleep(seconds: float) -> bool:
        if seconds <= 0:
            return stop.is_set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        return stop.is_set()

    return _sleep


def install_signal_handlers(stop: asyncio.Event) -> None:
    """SIGTERM (systemd stop) -> clean shutdown. Windows has only Ctrl+C (KeyboardInterrupt)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(sig, stop.set)


async def write_heartbeat(sf: SessionFactory, process: str) -> None:
    try:
        async with sf() as s, s.begin():
            await kv_repo.write_heartbeat(s, process)
    except Exception:
        logger.exception("heartbeat write failed")


async def heartbeat_loop(
    sf: SessionFactory, process: str, interval: float, stop: asyncio.Event
) -> None:
    """Writes ``heartbeat:<process>`` now and then every ``interval`` s until ``stop``."""
    sleep = stop_aware_sleep(stop)
    await write_heartbeat(sf, process)
    while not await sleep(interval):
        await write_heartbeat(sf, process)
