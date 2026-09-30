"""Monitoring: silent processes and silent / failing sources -> admin chat.

Runs every ``monitoring.check_interval_minutes`` (5) — in the worker (watches collector and bot)
and in the bot (watches the worker), so each process is watched by another one.

* a process whose ``heartbeat:<name>`` is older than ``heartbeat_stale_minutes`` (10);
  a process that never wrote a heartbeat (not deployed yet) is ignored;
* an enabled source without any post for ``source_silence_hours`` (24) — the channel may be
  deleted or has blocked our reader account. Only checked while the collector is reading
  (fresh heartbeat and a finished round): a stopped collector gives ONE "Collector jim"
  alert, not one "kanal jim" per channel;
* a source failing ``source_error_threshold`` (5) polls in a row.

One message when a problem starts and one "✅ ... tiklandi" when it ends (state in ``kv_store``
``monitor:<problem>``), not a message every 5 minutes.
"""

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.repositories import kv_repo, sources_repo
from ayvona.services.notifier import Notifier
from ayvona.timeutil import ensure_utc, to_local, utcnow

STATE_PREFIX = "monitor:"
PROCESS_TITLES = {"collector": "Collector", "worker": "Worker", "bot": "Bot"}
SleepFn = Callable[[float], Awaitable[bool]]


def _ago(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes < 120:
        return f"{minutes} daqiqa"
    hours = minutes // 60
    return f"{hours} soat" if hours < 48 else f"{hours // 24} kun"


class Monitor:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        notifier: Notifier | None,
        processes: Sequence[str],
        *,
        watch_sources: bool = True,
    ) -> None:
        self.settings = settings
        self.cfg = settings.app.monitoring
        self.sf = session_factory
        self.notifier = notifier
        self.processes = tuple(processes)
        self.watch_sources = watch_sources

    async def _flag(self, key: str) -> bool:
        async with self.sf() as s:
            return await kv_repo.get_bool(s, STATE_PREFIX + key)

    async def _set_flag(self, key: str, value: bool) -> None:
        async with self.sf() as s, s.begin():
            await kv_repo.set_bool(s, STATE_PREFIX + key, value)

    async def _transition(self, key: str, problem: bool, alert: str, recovered: str) -> str | None:
        """``alert`` when a problem starts, ``recovered`` when it ends; returns what was sent."""
        was = await self._flag(key)
        if problem == was:
            return None
        await self._set_flag(key, problem)
        text = alert if problem else recovered
        logger.warning("monitoring: {}", text)
        if self.notifier is not None:
            await self.notifier.send(text, key=f"monitor:{key}:{problem}")
        return text

    async def _collector_reading(self, now: datetime, stale_after: timedelta) -> bool:
        """The collector is alive (fresh heartbeat) AND finished a round over the sources
        recently (``collector:last_cycle_at``) — right after a restart the channels have not
        been read yet, so they would all still look silent."""
        async with self.sf() as s:
            beat = await kv_repo.read_heartbeat(s, "collector")
            cycle = await kv_repo.get_time(s, kv_repo.COLLECTOR_LAST_CYCLE)
        if beat is None or cycle is None:
            return False
        return now - ensure_utc(beat) <= stale_after and now - cycle <= stale_after

    async def check(self, now: datetime | None = None) -> list[str]:
        """One round of checks. Returns the messages sent (for tests / logs)."""
        now = now or utcnow()
        sent: list[str] = []
        stale_after = timedelta(minutes=self.cfg.heartbeat_stale_minutes)
        tz = self.settings.timezone
        for name in self.processes:
            async with self.sf() as s:
                beat = await kv_repo.read_heartbeat(s, name)
            if beat is None:
                continue  # never started (not deployed yet)
            age = now - ensure_utc(beat)
            title = PROCESS_TITLES.get(name, name)
            msg = await self._transition(
                f"stale:{name}",
                age > stale_after,
                f"🔴 <b>{title} jim</b>: oxirgi belgi {_ago(age)} oldin "
                f"({to_local(beat, tz):%d.%m %H:%M}). Jarayon to'xtagan bo'lishi mumkin.",
                f"✅ {title} yana ishlayapti.",
            )
            if msg:
                sent.append(msg)

        if not self.watch_sources:
            return sent
        # Silence only means something while the collector is reading: when it is down, every
        # channel looks silent — one "Collector jim" alert (above) instead of one per channel.
        # The silence flags are left as they are until the collector reads again.
        check_silence = await self._collector_reading(now, stale_after)
        silence = timedelta(hours=self.cfg.source_silence_hours)
        async with self.sf() as s:
            sources = await sources_repo.list_enabled(s)
            last_posts = await sources_repo.last_post_times(s)
        for src in sources:
            name = html.escape(src.identifier)
            if check_silence:
                last = last_posts.get(src.id) or ensure_utc(src.created_at)
                quiet = now - last
                msg = await self._transition(
                    f"silent:{src.id}",
                    quiet > silence,
                    f"🟡 <b>{name}</b> dan {_ago(quiet)} davomida birorta ham post kelmadi. "
                    "Kanal o'chirilgan yoki o'quvchi akkauntni bloklagan bo'lishi mumkin. "
                    "Kerak bo'lmasa: /sources → ⏸ Pauza.",
                    f"✅ {name} dan yana postlar kelyapti.",
                )
                if msg:
                    sent.append(msg)
            error = html.escape((src.last_error or "")[:300])
            msg = await self._transition(
                f"errors:{src.id}",
                src.error_count >= self.cfg.source_error_threshold,
                f"🔴 <b>{name}</b> ketma-ket {src.error_count} marta o'qilmadi.\n"
                f"<code>{error}</code>",
                f"✅ {name} yana o'qilyapti.",
            )
            if msg:
                sent.append(msg)
        return sent

    async def run(self, sleep: SleepFn) -> None:
        interval = self.cfg.check_interval_minutes * 60
        while True:
            try:
                await self.check()
            except Exception:
                logger.exception("monitoring: tekshirishda xato")
            if await sleep(interval):
                return
