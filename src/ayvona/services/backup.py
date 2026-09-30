"""Daily DB backup: SQLite online backup API -> ``data/backups/ayvona_YYYY-MM-DD.db``.

* Runs in the worker once a day at ``backup.hour:minute`` Asia/Tashkent (03:00). If the worker
  was off at that time, the backup is made as soon as it starts (``kv_store`` ``backup:last_date``).
* The SQLite backup API gives a consistent copy while collector / bot keep writing (WAL).
  The copy is written to ``*.tmp`` and renamed, so a half-written file never looks like a backup.
* Only the newest ``backup.keep`` (7) files named ``ayvona_YYYY-MM-DD.db`` directly in the backup
  folder are kept. Nothing else is touched — ``data/backups/deploy/`` belongs to scripts/deploy.sh.
* The file is also sent to the admin chat (if it is not bigger than ``max_send_mb``).
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.repositories import kv_repo
from ayvona.services.notifier import Notifier
from ayvona.timeutil import to_local, utcnow

LAST_DATE_KEY = "backup:last_date"
BACKUP_NAME_RE = re.compile(r"^ayvona_\d{4}-\d{2}-\d{2}\.db$")
SleepFn = Callable[[float], Awaitable[bool]]  # returns True if we should stop


def backup_name(day: date) -> str:
    return f"ayvona_{day.isoformat()}.db"


def make_backup(db_file: Path, backup_dir: Path, day: date, name: str | None = None) -> Path:
    """Consistent copy of ``db_file`` (blocking — run it in a thread).

    ``name``: another file name than the daily ``ayvona_YYYY-MM-DD.db`` (one-off backups)."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / (name or backup_name(day))
    tmp = target.with_suffix(".db.tmp")
    src = sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    tmp.replace(target)
    return target


def prune_backups(backup_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest ``keep`` daily backups. Only our own file names, top level only."""
    ours = sorted(p for p in backup_dir.iterdir() if p.is_file() and BACKUP_NAME_RE.match(p.name))
    removed = ours[:-keep] if len(ours) > keep else []
    for p in removed:
        p.unlink()
    return removed


def due(now_local: datetime, last_date: date | None, hour: int, minute: int) -> bool:
    """Today's backup time has passed and today's backup was not made yet."""
    at = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now_local >= at and last_date != now_local.date()


class BackupService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        notifier: Notifier | None = None,
    ) -> None:
        self.settings = settings
        self.cfg = settings.app.backup
        self.sf = session_factory
        self.notifier = notifier

    async def _last_date(self) -> date | None:
        async with self.sf() as s:
            raw = await kv_repo.get(s, LAST_DATE_KEY)
        return date.fromisoformat(raw) if raw else None

    async def run_backup(self, now: datetime | None = None) -> Path:
        """Make today's backup now, prune old ones, send it to the admin chat."""
        now = now or utcnow()
        day = to_local(now, self.settings.timezone).date()
        path = await asyncio.to_thread(
            make_backup, self.settings.db_file, self.settings.backup_dir, day
        )
        removed = await asyncio.to_thread(prune_backups, self.settings.backup_dir, self.cfg.keep)
        async with self.sf() as s, s.begin():
            await kv_repo.set_value(s, LAST_DATE_KEY, day.isoformat())
        size_mb = path.stat().st_size / 1024 / 1024
        logger.info(
            "Backup tayyor: {} ({:.1f} MB), eskilari o'chirildi: {}",
            path.name,
            size_mb,
            [p.name for p in removed] or "yo'q",
        )
        if self.notifier is not None and self.cfg.send_to_admin:
            if size_mb <= self.cfg.max_send_mb:
                await self.notifier.send_document(
                    path, f"💾 Kunlik backup: <code>{path.name}</code> ({size_mb:.1f} MB)"
                )
            else:
                await self.notifier.send(
                    f"💾 Backup tayyor, lekin katta ({size_mb:.0f} MB) — faqat serverda: "
                    f"<code>{path}</code>"
                )
        return path

    async def tick(self, now: datetime | None = None) -> Path | None:
        """Make the backup if it is due. Never raises (a failed backup is reported)."""
        now = now or utcnow()
        if not self.cfg.enabled:
            return None
        try:
            local = to_local(now, self.settings.timezone)
            if not due(local, await self._last_date(), self.cfg.hour, self.cfg.minute):
                return None
            return await self.run_backup(now)
        except Exception as e:
            logger.exception("Backup qilinmadi")
            if self.notifier is not None:
                await self.notifier.send(
                    f"❌ <b>Backup qilinmadi</b>: <code>{type(e).__name__}: {e}</code>",
                    key=f"backup_error:{type(e).__name__}",
                )
            return None

    async def run(self, sleep: SleepFn, interval: float = 60) -> None:
        """Check once a minute until ``sleep`` reports stop."""
        while True:
            await self.tick()
            if await sleep(interval):
                return


def next_run(now_local: datetime, hour: int, minute: int) -> datetime:
    """When the next daily backup happens (for /stats)."""
    at = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return at if at > now_local else at + timedelta(days=1)
