"""Bot API setup shared by the worker (publisher, admin notices) and the bot process.

``BOT_TOKEN``, ``CHANNEL_ID`` and ``ADMIN_CHAT_ID`` may be missing (the owner has not created the
bot yet): nothing crashes, every caller gets ``None`` / a clear Uzbek message instead.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.utils.token import TokenValidationError

from ayvona.config import Settings

NO_TOKEN = (
    "BOT_TOKEN .env faylida yo'q. @BotFather -> /newbot bilan bot yarating va tokenni "
    ".env ga yozing: BOT_TOKEN=123456789:AAE... (docs/PROGRESS.md, 'Sardor uchun')."
)
BAD_TOKEN = (
    "BOT_TOKEN noto'g'ri ko'rinishda (to'g'risi: 123456789:AAE...). @BotFather bergan tokenni "
    "bo'sh joylarsiz, qo'shtirnoqsiz .env ga qayta yozing."
)
NO_CHANNEL = (
    "CHANNEL_ID .env faylida yo'q — kanalga joylash o'chirilgan, e'lonlar navbatda kutadi. "
    "Sinov uchun avval TEST kanal oching: CHANNEL_ID=@test_kanal yoki -100... "
    "(bot kanalda admin bo'lsin)."
)
NO_ADMIN_CHAT = (
    "ADMIN_CHAT_ID .env faylida yo'q — admin xabarlari faqat logga yoziladi. "
    "Yopiq guruh oching, botni qo'shing va guruh ID'sini (-100...) .env ga yozing."
)


class BotConfigError(Exception):
    """Missing or malformed bot settings; the message is for the owner (Uzbek)."""


def parse_chat_id(value: str | int | None) -> int | str | None:
    """``"-1001234"`` -> ``-1001234``; ``"kanal"`` / ``"t.me/kanal"`` / ... -> ``"@kanal"``."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    v = value.strip()
    if not v:
        return None
    if v.lstrip("-").isdigit():
        return int(v)
    for prefix in ("https://", "http://", "t.me/", "@"):
        v = v.removeprefix(prefix)
    return "@" + v.strip("/")


def create_bot(
    settings: Settings,
    session: BaseSession | None = None,
    default: DefaultBotProperties | None = None,
) -> Bot:
    """A Bot for ``BOT_TOKEN``. Raises :class:`BotConfigError` (Uzbek text) if it is missing/bad.

    No network request is made here (the token is only checked for its shape).
    """
    token = settings.env.bot_token
    if token is None:
        raise BotConfigError(NO_TOKEN)
    try:
        return Bot(token.get_secret_value().strip(), session=session, default=default)
    except TokenValidationError as e:
        raise BotConfigError(BAD_TOKEN) from e
