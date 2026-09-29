"""Telegram channel source (Telethon, user account).

Polling, not events: every cycle we ask ``iter_messages(min_id=last_seen_id)``. If the collector was
off for hours, the next poll simply returns everything it missed (in ``fetch_limit`` batches).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from loguru import logger
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl import types

from ayvona.sources.base import BaseSource, FetchResult, RawItem, SourceError, SourceRateLimited
from ayvona.timeutil import ensure_utc

if TYPE_CHECKING:
    from ayvona.config import Settings

_TME_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)/?$")


class TelegramConfigError(RuntimeError):
    """Missing API keys / session. Message is user-facing (Uzbek)."""


def normalize_identifier(identifier: str) -> str | int:
    """``t.me/kanal``, ``https://t.me/s/kanal``, ``kanal`` -> ``@kanal``; ``-100123`` -> int."""
    ident = identifier.strip()
    if re.fullmatch(r"-?\d+", ident):
        return int(ident)
    m = _TME_RE.match(ident)
    if m:
        return "@" + m.group(1)
    return ident if ident.startswith("@") else "@" + ident


def _media_type(msg: Any) -> str | None:
    """Kind of media we care about, or ``None`` (no media / only a link preview)."""
    media = getattr(msg, "media", None)
    if media is None or isinstance(media, types.MessageMediaWebPage):
        return None
    for attr in ("photo", "gif", "video", "voice", "audio", "sticker", "poll"):
        if getattr(msg, attr, None):
            return attr
    if getattr(msg, "document", None):
        return "document"
    return "other"


def _button_links(msg: Any) -> list[dict[str, str]]:
    """URL buttons under the post. Works across API layers (url on button or button.type)."""
    markup = getattr(msg, "reply_markup", None)
    out: list[dict[str, str]] = []
    for row in getattr(markup, "rows", None) or []:
        for btn in getattr(row, "buttons", None) or []:
            url = getattr(btn, "url", None) or getattr(getattr(btn, "type", None), "url", None)
            if url:
                out.append({"text": str(getattr(btn, "text", "")), "url": str(url)})
    return out


def _hidden_links(msg: Any) -> list[dict[str, Any]]:
    """Links hidden behind words ("HR bilan bog'lanish" -> t.me/hr) and mentions by user id."""
    if not getattr(msg, "entities", None):
        return []
    out: list[dict[str, Any]] = []
    for ent, text in msg.get_entities_text(
        (types.MessageEntityTextUrl, types.MessageEntityMentionName)
    ):
        if isinstance(ent, types.MessageEntityTextUrl):
            out.append({"text": text, "url": ent.url})
        else:
            out.append({"text": text, "user_id": ent.user_id})
    return out


def message_to_item(msg: Any) -> RawItem | None:
    """Convert a Telethon message; ``None`` for things we skip (service messages, empty posts)."""
    if isinstance(msg, types.MessageService) or getattr(msg, "action", None) is not None:
        return None
    text = getattr(msg, "message", None) or ""
    media_type = _media_type(msg)
    if not text.strip() and media_type is None:
        return None
    extra: dict[str, Any] = {}
    if links := _hidden_links(msg):
        extra["links"] = links
    if buttons := _button_links(msg):
        extra["buttons"] = buttons
    date = getattr(msg, "date", None)
    return RawItem(
        external_id=str(msg.id),
        text=text,
        has_media=media_type is not None,
        media_type=media_type,
        posted_at=ensure_utc(date) if date else None,
        grouped_id=getattr(msg, "grouped_id", None),
        extra=extra or None,
    )


class TelegramSource(BaseSource):
    """One Telegram channel. Several instances share one connected ``TelegramClient``."""

    type: ClassVar[str] = "telegram"

    def __init__(
        self,
        identifier: str,
        client: Any,
        *,
        initial_backfill: int = 0,
        fetch_limit: int = 200,
    ) -> None:
        super().__init__(identifier)
        self._client = client
        self._initial_backfill = initial_backfill
        self._fetch_limit = fetch_limit
        self._entity: Any = None

    async def _get_entity(self) -> Any:
        if self._entity is None:
            self._entity = await self._client.get_entity(normalize_identifier(self.identifier))
        return self._entity

    async def fetch_new(self, since: str | None) -> FetchResult:
        try:
            entity = await self._get_entity()
            if since is None:
                return await self._first_run(entity)
            messages = [
                m
                async for m in self._client.iter_messages(
                    entity, min_id=int(since), reverse=True, limit=self._fetch_limit
                )
            ]
        except FloodWaitError as e:
            raise SourceRateLimited(float(e.seconds)) from e
        except ValueError as e:  # unknown username / bad identifier
            raise SourceError(f"{self.identifier}: {e}") from e
        return _to_result(messages, since)

    async def _first_run(self, entity: Any) -> FetchResult:
        """First poll ever: take ``initial_backfill`` latest posts, or only remember the top id."""
        if self._initial_backfill > 0:
            messages = list(await self._client.get_messages(entity, limit=self._initial_backfill))
            return _to_result(messages, None)
        latest = list(await self._client.get_messages(entity, limit=1))
        top_id = latest[0].id if latest else 0
        logger.info(
            "{}: birinchi marta o'qilmoqda — eski postlar olinmaydi (oxirgi id={})",
            self.identifier,
            top_id,
        )
        return FetchResult(items=[], cursor=str(top_id))


def _to_result(messages: list[Any], since: str | None) -> FetchResult:
    messages = sorted(messages, key=lambda m: m.id)
    items = [it for m in messages if (it := message_to_item(m)) is not None]
    # Cursor = highest id seen, *including* skipped messages, so we never re-read them.
    cursor = str(messages[-1].id) if messages else None
    if since is not None and cursor is not None and int(cursor) <= int(since):
        cursor = None
    return FetchResult(items=items, cursor=cursor)


# ------------------------------------------------------------------ client
async def connect_client(settings: Settings) -> TelegramClient:
    """Create + connect the shared client. Never asks for phone/code (login_telethon.py does)."""
    env = settings.env
    if env.api_id is None or env.api_hash is None:
        raise TelegramConfigError(
            ".env faylida API_ID va API_HASH to'ldirilmagan (my.telegram.org dan oling)."
        )
    session_file = settings.session_file.with_name(settings.session_file.name + ".session")
    if not session_file.exists():
        raise TelegramConfigError(
            f"Telegram session topilmadi ({session_file}). "
            "Avval bir marta: uv run python scripts/login_telethon.py"
        )
    client = TelegramClient(str(settings.session_file), env.api_id, env.api_hash.get_secret_value())
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise TelegramConfigError(
            "Session eskirgan yoki bekor qilingan. Qayta: uv run python scripts/login_telethon.py"
        )
    return client
