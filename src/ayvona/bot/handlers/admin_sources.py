"""Managing sources from the bot (only ``ADMIN_IDS``): /addsource, /sources + inline buttons.

The DB is the source of truth; the collector re-reads it every cycle, so every change here works
without a restart. A new Telegram channel is written as ``pending`` — the collector checks it
(it owns the Telethon connection) and reports the result to the admin who asked.
Deleting never removes the row (its posts stay): ``status='deleted'``.
"""

from __future__ import annotations

import html
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import RssCb
from ayvona.bot.handlers.admin import ago, local_time
from ayvona.config import Settings
from ayvona.db.models import Source, SourceAddedVia, SourceStatus, SourceType
from ayvona.db.repositories import sources_repo
from ayvona.services.sources_admin import (
    SourceKind,
    enable_feed,
    parse_source_input,
    probe_rss,
)
from ayvona.services.stats import source_stats
from ayvona.sources.web import SITES
from ayvona.timeutil import ensure_utc, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="admin_sources")

BACKFILL_CHOICES = (0, 5, 20)
DEFAULT_WEB_INTERVAL = 30
MAX_LIST_BUTTONS = 90


class AddSourceCb(CallbackData, prefix="as"):
    n: int
    ident: str


class SourceCb(CallbackData, prefix="src"):
    action: str  # list | show | pause | resume | del | delok | stats | recheck | int
    id: int = 0
    value: int = 0


def _who(user_id: int | None) -> str:
    return f"admin {user_id}"


def _name(src: Source) -> str:
    title = f" — {src.title}" if src.title and src.title != src.identifier else ""
    return html.escape(f"{src.identifier}{title}")


def _state(src: Source) -> str:
    if src.status == SourceStatus.ACTIVE:
        return "active" if src.enabled else "paused"
    return str(src.status)


ICONS = {
    "active": T.SOURCE_ICON_ACTIVE,
    "paused": T.SOURCE_ICON_PAUSED,
    "pending": T.SOURCE_ICON_PENDING,
    "rejected": T.SOURCE_ICON_REJECTED,
}


# ------------------------------------------------------------------ /addsource
@router.callback_query(RssCb.filter())
async def rss_decide(
    query: CallbackQuery,
    callback_data: RssCb,
    state: FSMContext,
    sf: SessionFactory,
    settings: Settings,
) -> None:
    await query.answer()
    pending = (await state.get_data()).get("pending_rss")
    await state.update_data(pending_rss=None)
    if not isinstance(query.message, Message):
        return
    if callback_data.action != "add":
        await query.message.edit_text(T.CANCELLED)
        return
    if not pending:
        await query.message.edit_text(T.ADDSOURCE_RSS_EXPIRED)
        return
    interval = settings.app.web_sources.default_interval_minutes
    async with sf() as s, s.begin():
        src = await enable_feed(s, pending["url"], pending["title"], query.from_user.id, interval)
        interval = src.check_interval_minutes or interval
    logger.info("{}: RSS qo'shildi: {}", _who(query.from_user.id), pending["url"])
    await query.message.edit_text(
        T.ADDSOURCE_RSS_ADDED.format(title=html.escape(pending["title"]), interval=interval)
    )


@router.message(Command("addsource"))
async def addsource_cmd(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    sf: SessionFactory,
    settings: Settings,
) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer(T.ADDSOURCE_USAGE)
        return
    parsed = parse_source_input(arg)
    if parsed is None:
        await message.answer(T.ADDSOURCE_BAD.format(text=html.escape(arg[:100])))
        return
    user_id = message.from_user.id if message.from_user else None

    if parsed.kind is SourceKind.RSS:
        url = parsed.identifier.removeprefix("rss:")
        probe = await probe_rss(url, settings)
        if not probe.ok:
            await message.answer(T.ADDSOURCE_RSS_BAD.format(error=html.escape(probe.error or "?")))
            return
        await state.update_data(pending_rss={"url": url, "title": probe.title})
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=T.B_ADD, callback_data=RssCb(action="add").pack()),
                    InlineKeyboardButton(
                        text=T.B_CANCEL, callback_data=RssCb(action="cancel").pack()
                    ),
                ]
            ]
        )
        await message.answer(
            T.ADDSOURCE_RSS_FOUND.format(
                title=html.escape(probe.title), url=html.escape(url), n=probe.items
            ),
            reply_markup=keyboard,
        )
        return

    if parsed.kind is SourceKind.WEB:
        info = SITES.get(parsed.identifier)
        if info is None:
            await message.answer(
                T.ADDSOURCE_WEB_UNKNOWN.format(
                    key=html.escape(parsed.identifier), known=", ".join(SITES) or "yo'q"
                )
            )
            return
        if reason := info.unavailable(settings):
            await message.answer(
                T.ADDSOURCE_WEB_NEEDS.format(key=html.escape(info.key), reason=html.escape(reason))
            )
            return
        default = settings.app.web_sources.default_interval_minutes
        async with sf() as s, s.begin():
            src = await sources_repo.get_by_identifier(s, parsed.identifier)
            if src is None:
                src = Source(
                    identifier=parsed.identifier,
                    type=parsed.identifier,
                    title=info.cls.site_name,
                    added_via=SourceAddedVia.BOT,
                    added_by=user_id,
                    check_interval_minutes=default,
                )
                s.add(src)
            src.status = SourceStatus.ACTIVE
            src.enabled = True
            src.last_error = None
            interval = max(src.check_interval_minutes or default, info.cls.min_interval_minutes)
        logger.info("{}: /addsource {} (sayt yoqildi)", _who(user_id), parsed.identifier)
        await message.answer(
            T.ADDSOURCE_WEB_ENABLED.format(
                title=html.escape(info.title),
                key=html.escape(info.key),
                interval=interval,
                note=f"\n⚠️ {html.escape(info.note)}" if info.note else "",
            )
        )
        return

    ident = parsed.identifier
    async with sf() as s, s.begin():
        src = await sources_repo.get_by_identifier(s, ident)
        if src is not None and src.status != SourceStatus.REJECTED:
            if src.status == SourceStatus.PENDING:
                await message.answer(T.ADDSOURCE_PENDING_ALREADY.format(ident=html.escape(ident)))
                return
            if src.status == SourceStatus.ACTIVE and src.enabled:
                await message.answer(T.ADDSOURCE_EXISTS.format(ident=html.escape(ident)))
                return
            src.status = SourceStatus.ACTIVE  # paused or deleted before: switch back on
            src.enabled = True
            logger.info("{}: /addsource {} (qayta yoqildi)", _who(user_id), ident)
            await message.answer(T.ADDSOURCE_REENABLED.format(ident=html.escape(ident)))
            return

    if len(AddSourceCb(n=20, ident=ident).pack()) > 64:  # Telegram's callback_data limit
        await _queue_source(sf, ident, 0, user_id)
        await message.answer(T.ADDSOURCE_QUEUED.format(ident=html.escape(ident), n=0))
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(n), callback_data=AddSourceCb(n=n, ident=ident).pack()
                )
                for n in BACKFILL_CHOICES
            ]
        ]
    )
    publish = T.YES if settings.app.publisher.publish_backfill else T.NO
    await message.answer(
        T.ADDSOURCE_ASK_BACKFILL.format(ident=html.escape(ident), publish=publish),
        reply_markup=keyboard,
    )


async def _queue_source(sf: SessionFactory, ident: str, n: int, user_id: int | None) -> None:
    """Write (or re-queue a rejected) ``pending`` row for the collector to check."""
    async with sf() as s, s.begin():
        src = await sources_repo.get_by_identifier(s, ident)
        if src is None:
            src = Source(identifier=ident, type=SourceType.TELEGRAM.value)
            s.add(src)
        src.status = SourceStatus.PENDING
        src.enabled = False
        src.added_via = SourceAddedVia.BOT
        src.added_by = user_id
        src.backfill_request = n
        src.last_error = None
    logger.info("{}: /addsource {} (eski postlar: {}) -> pending", _who(user_id), ident, n)


@router.callback_query(AddSourceCb.filter())
async def addsource_backfill(
    query: CallbackQuery, callback_data: AddSourceCb, sf: SessionFactory
) -> None:
    n = callback_data.n if callback_data.n in BACKFILL_CHOICES else 0
    await _queue_source(sf, callback_data.ident, n, query.from_user.id)
    text = T.ADDSOURCE_QUEUED.format(ident=html.escape(callback_data.ident), n=n)
    if isinstance(query.message, Message):
        await query.message.edit_text(text)
    await query.answer()


# ------------------------------------------------------------------ /sources
async def _list_view(
    sf: SessionFactory, settings: Settings
) -> tuple[str, InlineKeyboardMarkup | None]:
    now = utcnow()
    async with sf() as s:
        rows = await sources_repo.list_visible(s)
        last = await sources_repo.last_post_times(s)
    if not rows:
        return T.SOURCES_EMPTY, None
    lines = [T.SOURCES_HEAD.format(n=len(rows))]
    buttons: list[InlineKeyboardButton] = []
    for i, src in enumerate(rows, 1):
        when = last.get(src.id)
        lines.append(
            T.SOURCE_LINE.format(
                n=i,
                icon=ICONS.get(_state(src), "•"),
                name=html.escape(src.identifier),
                last=f"{ago(now - when)} oldin" if when else T.SOURCE_NEVER,
            )
        )
        if len(buttons) < MAX_LIST_BUTTONS:
            buttons.append(
                InlineKeyboardButton(
                    text=f"{i}. {src.identifier}"[:40],
                    callback_data=SourceCb(action="show", id=src.id).pack(),
                )
            )
    rows_kb = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows_kb)


def _card_keyboard(src: Source) -> InlineKeyboardMarkup:
    cb = SourceCb
    state = _state(src)
    first: list[InlineKeyboardButton] = []
    if state == "active":
        first.append(
            InlineKeyboardButton(text=T.B_PAUSE, callback_data=cb(action="pause", id=src.id).pack())
        )
    elif state == "paused":
        first.append(
            InlineKeyboardButton(
                text=T.B_RESUME, callback_data=cb(action="resume", id=src.id).pack()
            )
        )
    elif state == "rejected":
        first.append(
            InlineKeyboardButton(
                text=T.B_RECHECK, callback_data=cb(action="recheck", id=src.id).pack()
            )
        )
    first.append(
        InlineKeyboardButton(text=T.B_DELETE, callback_data=cb(action="del", id=src.id).pack())
    )
    rows = [
        first,
        [InlineKeyboardButton(text=T.B_STATS, callback_data=cb(action="stats", id=src.id).pack())],
    ]
    if SourceType.of(src.type) in (SourceType.WEB, SourceType.RSS):
        rows.append(
            [
                InlineKeyboardButton(
                    text=label, callback_data=cb(action="int", id=src.id, value=m).pack()
                )
                for m, label in T.B_INTERVALS
            ]
        )
    rows.append([InlineKeyboardButton(text=T.B_BACK, callback_data=cb(action="list").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _card_view(
    sf: SessionFactory, settings: Settings, source_id: int
) -> tuple[str, InlineKeyboardMarkup | None]:
    async with sf() as s:
        src = await sources_repo.get(s, source_id)
        last = (await sources_repo.last_post_times(s)).get(source_id)
    if src is None or src.status == SourceStatus.DELETED:
        return T.SOURCE_NOT_FOUND, None
    state = _state(src)
    error = f"\n<code>{html.escape(src.last_error[:300])}</code>" if src.last_error else ""
    interval = ""
    if src.check_interval_minutes:
        site = SITES.get(src.type)
        minimum = site.cls.min_interval_minutes if site else 0
        interval = T.SOURCE_INTERVAL.format(m=src.check_interval_minutes)
        if minimum > src.check_interval_minutes:  # the site's terms win
            interval += T.SOURCE_SITE_MINIMUM.format(m=minimum)
    text = T.SOURCE_CARD.format(
        icon=ICONS.get(state, "•"),
        name=_name(src),
        type=html.escape(src.type),
        via=f"{src.added_via}" + (f" ({src.added_by})" if src.added_by else ""),
        state=T.SOURCE_STATE.get(state, state),
        last_post=_when(last, settings),
        last_check=_when(src.last_checked_at, settings),
        errors=src.error_count,
        error=error,
        interval=interval,
    )
    return text, _card_keyboard(src)


def _when(dt: datetime | None, settings: Settings) -> str:
    if dt is None:
        return "—"
    return f"{local_time(dt, settings)} ({ago(utcnow() - ensure_utc(dt))} oldin)"


@router.message(Command("sources"))
async def sources_cmd(message: Message, sf: SessionFactory, settings: Settings) -> None:
    text, keyboard = await _list_view(sf, settings)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(SourceCb.filter(F.action == "list"))
async def sources_list_cb(query: CallbackQuery, sf: SessionFactory, settings: Settings) -> None:
    text, keyboard = await _list_view(sf, settings)
    await _edit(query, text, keyboard)
    await query.answer()


@router.callback_query(SourceCb.filter(F.action == "show"))
async def source_show_cb(
    query: CallbackQuery, callback_data: SourceCb, sf: SessionFactory, settings: Settings
) -> None:
    text, keyboard = await _card_view(sf, settings, callback_data.id)
    await _edit(query, text, keyboard)
    await query.answer()


@router.callback_query(
    SourceCb.filter(F.action.in_({"pause", "resume", "delok", "recheck", "int"}))
)
async def source_change_cb(
    query: CallbackQuery, callback_data: SourceCb, sf: SessionFactory, settings: Settings
) -> None:
    action = callback_data.action
    async with sf() as s, s.begin():
        src = await sources_repo.get(s, callback_data.id)
        if src is None or src.status == SourceStatus.DELETED:
            await query.answer(T.SOURCE_NOT_FOUND, show_alert=True)
            return
        name = _name(src)
        if action == "pause":
            src.enabled = False
            note = T.SOURCE_PAUSED.format(name=name)
        elif action == "resume":
            src.enabled = True
            src.status = SourceStatus.ACTIVE
            note = T.SOURCE_RESUMED.format(name=name)
        elif action == "recheck":
            src.status = SourceStatus.PENDING
            src.enabled = False
            src.added_by = query.from_user.id
            src.last_error = None
            note = T.SOURCE_RECHECK.format(name=name)
        elif action == "int":
            src.check_interval_minutes = callback_data.value or DEFAULT_WEB_INTERVAL
            note = T.SOURCE_INTERVAL.format(m=src.check_interval_minutes).strip()
        else:  # delok
            src.status = SourceStatus.DELETED
            src.enabled = False
            note = T.SOURCE_DELETED.format(name=name)
        identifier = src.identifier
    logger.info("{}: manba {} -> {}", _who(query.from_user.id), identifier, action)
    if action == "delok":
        text, keyboard = await _list_view(sf, settings)
        await _edit(query, f"{note}\n\n{text}", keyboard)
    else:
        text, keyboard = await _card_view(sf, settings, callback_data.id)
        await _edit(query, f"{note}\n\n{text}", keyboard)
    await query.answer()


@router.callback_query(SourceCb.filter(F.action == "del"))
async def source_delete_ask_cb(
    query: CallbackQuery, callback_data: SourceCb, sf: SessionFactory
) -> None:
    async with sf() as s:
        src = await sources_repo.get(s, callback_data.id)
    if src is None:
        await query.answer(T.SOURCE_NOT_FOUND, show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.B_CONFIRM_DELETE,
                    callback_data=SourceCb(action="delok", id=src.id).pack(),
                ),
                InlineKeyboardButton(
                    text=T.B_CANCEL, callback_data=SourceCb(action="show", id=src.id).pack()
                ),
            ]
        ]
    )
    await _edit(query, T.SOURCE_DELETE_CONFIRM.format(name=_name(src)), keyboard)
    await query.answer()


@router.callback_query(SourceCb.filter(F.action == "stats"))
async def source_stats_cb(
    query: CallbackQuery, callback_data: SourceCb, sf: SessionFactory, settings: Settings
) -> None:
    async with sf() as s:
        src = await sources_repo.get(s, callback_data.id)
        if src is None:
            await query.answer(T.SOURCE_NOT_FOUND, show_alert=True)
            return
        st = await source_stats(s, src, utcnow())
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.B_BACK, callback_data=SourceCb(action="show", id=src.id).pack()
                )
            ]
        ]
    )
    text = T.SOURCE_STATS.format(name=_name(src), s=st, last=_when(st.last_post_at, settings))
    await _edit(query, text, keyboard)
    await query.answer()


async def _edit(query: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup | None) -> None:
    """Replace the message the button belongs to (the caller answers the callback)."""
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=keyboard)
