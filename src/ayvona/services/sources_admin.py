"""Sources added from the bot (/addsource): parsing the admin's input and checking new channels.

Flow (ROADMAP Bosqich 8, 5): the bot writes a ``pending`` row -> the collector (it owns the
Telethon connection) checks it here every cycle: does the channel exist, can we read it; an
invite link makes our reader account join. Result: ``active`` (polled from the next cycle, no
restart) or ``rejected`` with the reason; the admin who asked gets a message either way.
Temporary problems (flood wait, network) leave the row ``pending`` for the next cycle.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import errors
from telethon.tl import types
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

from ayvona.config import Settings
from ayvona.db.models import Source, SourceAddedVia, SourceStatus, SourceType
from ayvona.db.repositories import sources_repo
from ayvona.services.notifier import Notifier
from ayvona.sources.base import SourceError
from ayvona.sources.telegram_source import normalize_identifier
from ayvona.sources.web import base as web_base
from ayvona.sources.web.rss import parse_feed


class SourceKind(StrEnum):
    TELEGRAM = "telegram"  # public channel: @name
    INVITE = "invite"  # private channel: t.me/+hash
    WEB = "web"  # a website with its own code: web:hh_uz
    RSS = "rss"  # any RSS/Atom feed (Bosqich 16.0)


@dataclass(frozen=True, slots=True)
class ParsedSource:
    kind: SourceKind
    identifier: str  # "@name", "+hash", "web:hh_uz", "rss:https://..."


_USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")
_TME_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z][A-Za-z0-9_]{3,31})/?$", re.I
)
_INVITE_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)([A-Za-z0-9_-]{8,64})/?$",
    re.I,
)
_WEB_RE = re.compile(r"^web:([a-z0-9_]{2,40})$", re.I)
_RSS_RE = re.compile(r"^rss:(https?://\S{4,500})$", re.I)


def parse_source_input(text: str) -> ParsedSource | None:
    """The argument of /addsource -> what kind of source it is, or ``None`` if not understood."""
    t = text.strip()
    if m := _INVITE_RE.match(t):
        return ParsedSource(SourceKind.INVITE, "+" + m.group(1))
    if m := _TME_RE.match(t):
        return ParsedSource(SourceKind.TELEGRAM, "@" + m.group(1))
    if m := _USERNAME_RE.match(t):
        return ParsedSource(SourceKind.TELEGRAM, "@" + m.group(1))
    if m := _WEB_RE.match(t):
        return ParsedSource(SourceKind.WEB, "web:" + m.group(1).lower())
    if m := _RSS_RE.match(t):
        return ParsedSource(SourceKind.RSS, "rss:" + m.group(1))
    return None


# --------------------------------------------------------------------------- RSS / websites
@dataclass(frozen=True, slots=True)
class FeedProbe:
    ok: bool
    title: str = ""
    items: int = 0
    error: str | None = None


async def probe_rss(url: str, settings: Settings) -> FeedProbe:
    """Read the feed once (the bot shows its title before adding it). Never raises."""
    cfg = settings.app.web_sources
    try:
        async with httpx.AsyncClient(
            timeout=min(cfg.timeout_seconds, 20),
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
            transport=web_base.TRANSPORT,
        ) as http:
            resp = await http.get(url)
        if resp.status_code >= 400:
            return FeedProbe(False, error=f"HTTP {resp.status_code}")
        feed = parse_feed(resp.text)
    except SourceError as e:
        return FeedProbe(False, error=str(e))
    except httpx.HTTPError as e:
        return FeedProbe(False, error=f"tarmoq: {type(e).__name__}")
    return FeedProbe(True, title=feed.title[:120], items=len(feed.jobs))


async def enable_feed(
    session: AsyncSession, url: str, title: str, admin_id: int | None, interval: int
) -> Source:
    """``rss:<url>`` row, active (or a paused / deleted one switched back on). Does not commit."""
    ident = f"rss:{url}"
    src = await sources_repo.get_by_identifier(session, ident)
    if src is None:
        src = Source(identifier=ident, type=SourceType.RSS.value, check_interval_minutes=interval)
        session.add(src)
    src.title = title or src.title
    src.status = SourceStatus.ACTIVE
    src.enabled = True
    src.added_via = SourceAddedVia.BOT
    src.added_by = admin_id
    src.last_error = None
    await session.flush()
    return src


# --------------------------------------------------------------------------- checking
@dataclass(frozen=True, slots=True)
class CheckResult:
    ok: bool
    identifier: str | None = None  # final identifier ("@name" or "-100<id>")
    title: str | None = None
    last_post_id: int | None = None
    error: str | None = None  # Uzbek, for the admin
    retry_later: bool = False  # temporary problem: keep it pending


def _channel_identifier(entity: Any) -> str:
    username = getattr(entity, "username", None)
    return "@" + username if username else f"-100{entity.id}"


async def _join_invite(client: Any, invite_hash: str) -> Any:
    """Our reader account joins the private channel (or is already in it)."""
    check = await client(CheckChatInviteRequest(invite_hash))
    if isinstance(check, types.ChatInviteAlready | types.ChatInvitePeek):
        return check.chat
    try:
        updates = await client(ImportChatInviteRequest(invite_hash))
    except errors.UserAlreadyParticipantError:
        check = await client(CheckChatInviteRequest(invite_hash))
        return check.chat
    chats = getattr(updates, "chats", None) or []
    if not chats:
        raise ValueError("taklif havolasi orqali kanal topilmadi")
    return chats[0]


async def check_telegram_source(client: Any, identifier: str) -> CheckResult:
    """Can our reader account read this channel? Never raises."""
    try:
        if identifier.startswith("+"):
            entity = await _join_invite(client, identifier[1:])
        else:
            entity = await client.get_entity(normalize_identifier(identifier))
        if not hasattr(entity, "title") or getattr(entity, "megagroup", False):
            return CheckResult(False, error="bu kanal emas (foydalanuvchi, bot yoki guruh)")
        latest = list(await client.get_messages(entity, limit=1))
    except errors.FloodWaitError as e:
        return CheckResult(
            False, error=f"Telegram {e.seconds} s kutishni so'radi", retry_later=True
        )
    except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
        return CheckResult(False, error="bunday kanal yo'q (username noto'g'ri)")
    except (errors.InviteHashExpiredError, errors.InviteHashInvalidError):
        return CheckResult(False, error="taklif havolasi eskirgan yoki noto'g'ri")
    except (errors.ChannelPrivateError, errors.ChannelInvalidError):
        return CheckResult(False, error="kanal yopiq — taklif havolasi (t.me/+...) kerak")
    except errors.InviteRequestSentError:
        return CheckResult(
            False, error="kanalga qo'shilish so'rovi yuborildi — kanal admini tasdiqlashi kerak"
        )
    except ValueError as e:  # Telethon: "No user has "x" as username", "Cannot find any entity"
        return CheckResult(False, error=f"kanal topilmadi ({e})")
    except (ConnectionError, OSError, TimeoutError) as e:
        return CheckResult(False, error=f"tarmoq xatosi: {e}", retry_later=True)
    except Exception as e:
        logger.exception("{}: tekshirishda kutilmagan xato", identifier)
        return CheckResult(False, error=f"{type(e).__name__}: {e}")
    return CheckResult(
        True,
        identifier=_channel_identifier(entity),
        title=getattr(entity, "title", None),
        last_post_id=latest[0].id if latest else 0,
    )


async def process_pending(
    sf: async_sessionmaker[AsyncSession], client: Any, notifier: Notifier | None = None
) -> int:
    """Check every ``pending`` Telegram source once. Returns how many were decided."""
    async with sf() as s:
        pending = await sources_repo.list_pending(s)
    decided = 0
    for row in pending:
        if row.type != "telegram":
            continue
        if client is None:
            logger.warning("{}: Telegram ulanmagan — tekshirish keyinga qoldi", row.identifier)
            continue
        result = await check_telegram_source(client, row.identifier)
        if result.retry_later:
            logger.warning("{}: tekshirish keyinga qoldi: {}", row.identifier, result.error)
            continue
        text = await _apply(sf, row, result)
        decided += 1
        if notifier is not None:
            await notifier.send(text, chat_id=row.added_by, key=f"source_check:{row.id}")
    return decided


async def _apply(sf: async_sessionmaker[AsyncSession], row: Source, result: CheckResult) -> str:
    """Save the result; returns the message for the admin (HTML)."""
    asked = html.escape(row.identifier)
    async with sf() as s, s.begin():
        src = await s.get(Source, row.id)
        assert src is not None
        if result.ok and result.identifier:
            other = await sources_repo.get_by_identifier(s, result.identifier)
            if other is not None and other.id != src.id:
                # Already known (maybe paused / deleted): switch that one back on instead.
                other.enabled = True
                other.status = SourceStatus.ACTIVE
                src.status = SourceStatus.REJECTED
                src.enabled = False
                src.last_error = f"allaqachon bor: {other.identifier} (#{other.id}) — u yoqildi"
                logger.info("Manba {} allaqachon bor ({}), qayta yoqildi", asked, other.identifier)
                return (
                    f"ℹ️ {asked} allaqachon ro'yxatda edi: {html.escape(other.identifier)} — "
                    "u yoqildi (▶️)."
                )
            src.identifier = result.identifier
            src.title = result.title or src.title
            src.status = SourceStatus.ACTIVE
            src.enabled = True
            src.last_error = None
            src.own_usernames = [result.identifier] if result.identifier.startswith("@") else []
            logger.info("Manba qo'shildi: {} ({})", result.identifier, result.title)
            n = src.backfill_request or 0
            old = f"eski postlardan {n} tasi olinadi" if n else "faqat yangi postlar olinadi"
            return (
                f"✅ <b>Qo'shildi:</b> {html.escape(result.title or result.identifier)} "
                f"({html.escape(result.identifier)})\nOxirgi post ID: {result.last_post_id}. "
                f"Keyingi aylanishdan o'qiladi, {old}."
            )
        src.status = SourceStatus.REJECTED
        src.enabled = False
        src.last_error = result.error
        logger.info("Manba qo'shilmadi: {} — {}", asked, result.error)
        return f"❌ <b>Qo'shilmadi:</b> {asked}\nSabab: {html.escape(result.error or '?')}"
