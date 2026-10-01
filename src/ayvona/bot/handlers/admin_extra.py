"""Admin commands of Bosqich 14 (only ``ADMIN_IDS``): /addword /delword /words (filter words),
/ban /unban (users), /broadcast (message to everyone, after a confirmation, sent slowly in the
background). Logic: services/filter_words.py, services/users.py, services/broadcast.py.
"""

from __future__ import annotations

import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.ai.helper import AIHelper, set_admin_disabled
from ayvona.bot import texts as T
from ayvona.bot.callbacks import AICb, BroadcastCb
from ayvona.bot.handlers.admin import log_admin
from ayvona.config import Settings
from ayvona.db.models import FilterKind
from ayvona.services import broadcast, filter_words
from ayvona.services import users as users_svc
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="admin_extra")
_background: set[asyncio.Task[None]] = set()


# ------------------------------------------------------------------ filter words
@router.message(Command("addword"))
async def addword_cmd(message: Message, command: CommandObject, sf: SessionFactory) -> None:
    parts = (command.args or "").strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() not in {k.value for k in FilterKind}:
        await message.answer(T.ADDWORD_USAGE)
        return
    kind = FilterKind(parts[0].lower())
    word = filter_words.clean_word(parts[1])
    async with sf() as s, s.begin():
        added = await filter_words.add_word(s, word, kind, message.from_user.id)  # type: ignore[union-attr]
    log_admin(message, f"/addword {kind} {word!r} -> {added}")
    await message.answer(
        T.ADDWORD_OK.format(kind=kind, word=html.escape(word)) if added else T.ADDWORD_EXISTS
    )


@router.message(Command("delword"))
async def delword_cmd(message: Message, command: CommandObject, sf: SessionFactory) -> None:
    word = (command.args or "").strip()
    if not word:
        await message.answer(T.DELWORD_USAGE)
        return
    async with sf() as s, s.begin():
        n = await filter_words.delete_word(s, word)
    log_admin(message, f"/delword {word!r} -> {n}")
    await message.answer(
        T.DELWORD_OK.format(word=html.escape(filter_words.clean_word(word)))
        if n
        else T.DELWORD_NONE
    )


@router.message(Command("words"))
async def words_cmd(message: Message, sf: SessionFactory) -> None:
    async with sf() as s:
        words = await filter_words.list_words(s)
    if not words:
        await message.answer(T.WORDS_EMPTY)
        return
    lines = [T.WORDS_HEAD] + [f"• {w.kind}: {html.escape(w.word)}" for w in words[:200]]
    await message.answer("\n".join(lines))


# ------------------------------------------------------------------ ban / unban
async def _ban(
    message: Message, command: CommandObject, sf: SessionFactory, settings: Settings, ban: bool
) -> None:
    ref = (command.args or "").strip()
    if not ref:
        await message.answer(T.BAN_USAGE)
        return
    async with sf() as s, s.begin():
        user = await users_svc.find_user(s, ref)
        if user is None and ref.lstrip("-").isdigit():  # never wrote to the bot: ban anyway
            user = await users_svc.set_banned(s, int(ref), ban, utcnow())
        if user is None:
            await message.answer(T.BAN_NOT_FOUND)
            return
        if ban and user.tg_id in settings.env.admin_ids:
            await message.answer(T.BAN_ADMIN)
            return
        await users_svc.set_banned(s, user.tg_id, ban, utcnow())
    who = f"{user.tg_id}" + (f" (@{html.escape(user.username)})" if user.username else "")
    log_admin(message, f"/{'ban' if ban else 'unban'} {user.tg_id}")
    await message.answer((T.BAN_OK if ban else T.UNBAN_OK).format(who=who))


@router.message(Command("ban"))
async def ban_cmd(
    message: Message, command: CommandObject, sf: SessionFactory, settings: Settings
) -> None:
    await _ban(message, command, sf, settings, True)


@router.message(Command("unban"))
async def unban_cmd(
    message: Message, command: CommandObject, sf: SessionFactory, settings: Settings
) -> None:
    await _ban(message, command, sf, settings, False)


# ------------------------------------------------------------------ 🤖 /ai
async def ai_view(sf: SessionFactory, settings: Settings) -> tuple[str, InlineKeyboardMarkup]:
    st = await AIHelper(settings, sf).status()
    if not st.configured:
        state = T.AI_NO_KEY
    elif not st.config_enabled:
        state = T.AI_OFF_CONFIG
    elif st.admin_disabled:
        state = T.AI_OFF_ADMIN
    else:
        state = T.AI_ON
    text = T.AI_STATUS.format(
        state=state,
        model=html.escape(st.model),
        keys=st.keys,
        rotation=T.AI_ROTATION if st.rotation else "",
        calls=st.calls_today,
        limit=st.daily_limit,
        ok=st.ok_today,
        failed=st.failed_today,
        cache_hits=st.cache_hits_today,
        cached_total=st.cached_total,
        paused=T.AI_PAUSED.format(list=", ".join(st.paused)) if st.paused else "",
    )
    button = (
        InlineKeyboardButton(text=T.BTN_AI_ON, callback_data=AICb(action="on").pack())
        if st.admin_disabled
        else InlineKeyboardButton(text=T.BTN_AI_OFF, callback_data=AICb(action="off").pack())
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[button]])


@router.message(Command("ai"))
async def ai_cmd(message: Message, sf: SessionFactory, settings: Settings) -> None:
    text, kb = await ai_view(sf, settings)
    await message.answer(text, reply_markup=kb)


@router.callback_query(AICb.filter())
async def ai_switch(
    query: CallbackQuery, callback_data: AICb, sf: SessionFactory, settings: Settings
) -> None:
    async with sf() as s, s.begin():
        await set_admin_disabled(s, callback_data.action == "off")
    logger.info("admin {}: /ai -> {}", query.from_user.id, callback_data.action)
    await query.answer()
    text, kb = await ai_view(sf, settings)
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=kb)


# ------------------------------------------------------------------ broadcast
@router.message(Command("broadcast"))
async def broadcast_cmd(
    message: Message, command: CommandObject, state: FSMContext, sf: SessionFactory
) -> None:
    text = (message.html_text or "").partition(" ")[2].strip() if message.text else ""
    if not text:
        await message.answer(T.BROADCAST_USAGE)
        return
    async with sf() as s:
        n = await broadcast.count_recipients(s)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.BTN_SUBMIT, callback_data=BroadcastCb(action="send").pack()
                ),
                InlineKeyboardButton(
                    text=T.BTN_CANCEL, callback_data=BroadcastCb(action="cancel").pack()
                ),
            ]
        ]
    )
    try:
        await message.answer(T.BROADCAST_CONFIRM.format(n=n, text=text), reply_markup=kb)
    except TelegramBadRequest as e:  # the admin's HTML does not parse
        await message.answer(T.BROADCAST_BAD_HTML.format(error=html.escape(e.message)))
        return
    await state.update_data(broadcast=text)


@router.callback_query(BroadcastCb.filter(F.action == "cancel"))
async def broadcast_cancel(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(broadcast=None)
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(T.CANCELLED)


@router.callback_query(BroadcastCb.filter(F.action == "send"))
async def broadcast_send(
    query: CallbackQuery, state: FSMContext, sf: SessionFactory, settings: Settings, bot: Bot
) -> None:
    await query.answer()
    text = (await state.get_data()).get("broadcast")
    await state.update_data(broadcast=None)
    if not isinstance(query.message, Message):
        return
    if not text:
        await query.message.edit_text(T.BROADCAST_EXPIRED)
        return
    async with sf() as s:
        n = await broadcast.count_recipients(s)
    rate = settings.app.broadcast.per_second
    await query.message.edit_text(T.BROADCAST_STARTED.format(n=n, rate=rate))
    logger.info("admin {}: /broadcast -> {} ta", query.from_user.id, n)
    chat_id = query.message.chat.id

    async def run() -> None:
        report = await broadcast.send_broadcast(bot, sf, text, rate)
        try:
            await bot.send_message(
                chat_id, T.BROADCAST_DONE.format(ok=report.ok, failed=report.failed)
            )
        except Exception:
            logger.exception("broadcast: hisobot yuborilmadi")

    task = asyncio.create_task(run())  # the bot keeps answering meanwhile
    _background.add(task)
    task.add_done_callback(_background.discard)
