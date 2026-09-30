"""Users of the public bot (``users`` table). Shared by the bot and the future website.

No aiogram types here: the callers pass plain values (Telegram id, username, name).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import User

TRUST_NEW = 0
TRUST_TRUSTED = 1
TRUST_ADMIN = 2


async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    return await session.get(User, tg_id)


def needs_touch(
    user: User | None,
    username: str | None,
    full_name: str | None,
    now: datetime,
    interval: timedelta,
) -> bool:
    """Write the row? New user, changed name/username, or ``last_active_at`` older than
    ``interval`` (not on every message: one write per minute per user is plenty)."""
    if user is None:
        return True
    if user.username != username or user.full_name != full_name:
        return True
    return user.last_active_at is None or now - user.last_active_at >= interval


async def touch_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    full_name: str | None,
    now: datetime,
    *,
    is_admin: bool = False,
) -> User:
    """Create or update the user (name, username, ``last_active_at``). Admins get
    ``trust_level=2``. Does not commit."""
    user = await session.get(User, tg_id)
    if user is None:
        user = User(tg_id=tg_id, created_at=now, trust_level=TRUST_NEW)
        session.add(user)
    user.username = username
    user.full_name = full_name
    user.last_active_at = now
    if is_admin and user.trust_level < TRUST_ADMIN:
        user.trust_level = TRUST_ADMIN
    await session.flush()
    return user


async def set_banned(session: AsyncSession, tg_id: int, banned: bool, now: datetime) -> User:
    """Ban / unban (creates the row if the user never wrote to the bot). Does not commit."""
    user = await session.get(User, tg_id)
    if user is None:
        user = User(tg_id=tg_id, created_at=now)
        session.add(user)
    user.is_banned = banned
    await session.flush()
    return user


async def set_phone(session: AsyncSession, tg_id: int, phone: str) -> None:
    """The phone a user shared with the "📱 Raqamni yuborish" button. Does not commit."""
    user = await session.get(User, tg_id)
    if user is not None:
        user.phone = phone
