"""Middlewares of the bot (outer: they run before any filter, for every message / button).

``UserMiddleware`` — private chats only:
1. throttling: a user's updates closer than ``bot.throttle_seconds`` are dropped (a pressed button
   gets a short "⏳" answer so it stops spinning);
2. ``users`` row: created on the first update, name / username / ``last_active_at`` refreshed at
   most every ``bot.touch_interval_seconds`` (not a DB write per message);
3. ban: a banned user gets "🚫" (at most every 10 minutes) and nothing else.
Admins (``ADMIN_IDS``) are never throttled or banned. Group chats (the admin group) pass through
untouched. The handler gets the row as ``db_user``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject
from aiogram.types import User as TgUser
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.config import Settings
from ayvona.services import users as users_svc
from ayvona.timeutil import utcnow

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]
BAN_NOTICE_SECONDS = 600
_MAX_TRACKED = 20_000


class UserMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings, sf: async_sessionmaker[AsyncSession]) -> None:
        self.admin_ids = frozenset(settings.env.admin_ids)
        self.throttle = settings.app.bot.throttle_seconds
        self.touch_every = timedelta(seconds=settings.app.bot.touch_interval_seconds)
        self.sf = sf
        self._last_seen: dict[int, float] = {}
        self._ban_noticed: dict[int, float] = {}

    def _throttled(self, user_id: int) -> bool:
        now = time.monotonic()
        last = self._last_seen.get(user_id)
        if last is not None and now - last < self.throttle:
            return True
        if len(self._last_seen) > _MAX_TRACKED:  # forget idle users now and then
            cutoff = now - max(self.throttle, 1) * 10
            self._last_seen = {k: v for k, v in self._last_seen.items() if v > cutoff}
        self._last_seen[user_id] = now
        return False

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: TgUser | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if user is None or user.is_bot or (chat is not None and chat.type != "private"):
            return await handler(event, data)
        is_admin = user.id in self.admin_ids

        if not is_admin and self.throttle > 0 and self._throttled(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer(T.THROTTLED)
            return None

        now = utcnow()
        async with self.sf() as s:
            db_user = await users_svc.get_user(s, user.id)
        if users_svc.needs_touch(db_user, user.username, user.full_name, now, self.touch_every):
            try:
                async with self.sf() as s, s.begin():
                    db_user = await users_svc.touch_user(
                        s, user.id, user.username, user.full_name, now, is_admin=is_admin
                    )
            except Exception:  # DB busy: the handler still runs if the row exists
                logger.exception("users: {} yozilmadi", user.id)
                if db_user is None:
                    return None
        assert db_user is not None

        if db_user.is_banned and not is_admin:
            last = self._ban_noticed.get(user.id, 0.0)
            if time.monotonic() - last > BAN_NOTICE_SECONDS:
                self._ban_noticed[user.id] = time.monotonic()
                if isinstance(event, Message):
                    await event.answer(T.BANNED)
            if isinstance(event, CallbackQuery):
                await event.answer(T.BANNED, show_alert=True)
            return None

        data["db_user"] = db_user
        data["is_admin"] = is_admin
        return await handler(event, data)
