"""Messages to the admin chat: errors, failed posts, suspicious posts, silent processes, backups.

Rules:
* the same notice (same ``key``, default = the text) goes out at most once per
  ``throttle_seconds`` (10 min). The last-sent time lives in ``kv_store`` (``notify:<hash>``), so
  the limit holds across restarts and across the three processes;
* never raises: a broken Bot API or DB must not stop the pipeline / publisher;
* without ``BOT_TOKEN`` or ``ADMIN_CHAT_ID`` the notice only goes to the log.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.db.repositories import kv_repo
from ayvona.timeutil import utcnow

if TYPE_CHECKING:
    from aiogram import Bot

    from ayvona.litebot import LiteBot

THROTTLE_SECONDS = 600
KEY_PREFIX = "notify:"
MAX_MESSAGE_LEN = 4000  # Telegram: 4096
NO_LINK_PREVIEW: dict[str, Any] = {"is_disabled": True}


class Notifier:
    def __init__(
        self,
        bot: Bot | LiteBot | None,
        chat_id: int | str | None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        throttle_seconds: float = THROTTLE_SECONDS,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.sf = session_factory
        self.throttle = timedelta(seconds=throttle_seconds)
        self._sent: dict[str, datetime] = {}  # used when there is no DB

    @property
    def enabled(self) -> bool:
        return self.bot is not None and self.chat_id is not None

    @staticmethod
    def _kv_key(key: str) -> str:
        return KEY_PREFIX + hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]

    async def _last_sent(self, key: str) -> datetime | None:
        if self.sf is None:
            return self._sent.get(key)
        try:
            async with self.sf() as s:
                raw = await kv_repo.get(s, self._kv_key(key))
            return datetime.fromisoformat(raw) if raw else None
        except Exception:
            logger.exception("notifier: kv o'qilmadi")
            return None

    async def _remember(self, key: str, now: datetime) -> None:
        self._sent[key] = now
        if self.sf is None:
            return
        try:
            async with self.sf() as s, s.begin():
                await kv_repo.set_value(s, self._kv_key(key), now.isoformat())
        except Exception:
            logger.exception("notifier: kv yozilmadi")

    async def _throttled(self, key: str, now: datetime) -> bool:
        last = await self._last_sent(key)
        return last is not None and now - last < self.throttle

    async def send(
        self, text: str, *, key: str | None = None, chat_id: int | str | None = None
    ) -> bool:
        """Send an HTML notice (escape user text yourself). True if it reached Telegram.

        ``chat_id``: another chat than the admin chat (e.g. the admin who asked for something).
        """
        now = utcnow()
        key = key or text
        target = chat_id if chat_id is not None else self.chat_id
        if await self._throttled(key, now):
            logger.debug("notifier: takroriy xabar o'tkazib yuborildi ({})", key[:60])
            return False
        if self.bot is None or target is None:
            logger.warning("[admin'ga, yuborilmadi — bot/ADMIN_CHAT_ID yo'q] {}", text)
            return False
        try:
            # Plain values (no aiogram types): the collector sends these through LiteBot, and
            # aiogram would cost it ~130 MB of RAM just to be imported.
            await self.bot.send_message(
                target,
                text[:MAX_MESSAGE_LEN],
                parse_mode="HTML",
                link_preview_options=NO_LINK_PREVIEW,
            )
        except Exception as e:
            logger.error(
                "notifier: admin chatga yuborilmadi: {}: {} | {}", type(e).__name__, e, text
            )
            return False
        await self._remember(key, now)
        return True

    async def send_document(self, path: Path, caption: str = "") -> bool:
        """Send a file (DB backup). Not throttled. True if it reached Telegram."""
        if not self.enabled:
            logger.warning("[admin'ga, yuborilmadi — bot/ADMIN_CHAT_ID yo'q] fayl: {}", path)
            return False
        assert self.bot is not None and self.chat_id is not None
        from aiogram.enums import ParseMode
        from aiogram.types import FSInputFile

        try:
            await self.bot.send_document(
                self.chat_id,
                FSInputFile(path),
                caption=caption[:1000] or None,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("notifier: fayl yuborilmadi ({}): {}: {}", path.name, type(e).__name__, e)
            return False
        return True
