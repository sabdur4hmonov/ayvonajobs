"""Public bot: /start (+ deep links), main menu, help, job card with ⭐ / 📤.

Deep links (channel post buttons and shares — keep the format):
* ``?start=save_<id>``  — save the job, show it;
* ``?start=job_<id>``   — show the job;
* ``?start=search``     — open the search.
Everything else about jobs / favorites lives in ``services/`` (the website reuses it).
"""

from __future__ import annotations

import html
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import JobCb
from ayvona.bot.cards import full_card
from ayvona.bot.keyboards import job_keyboard, main_menu
from ayvona.config import Settings
from ayvona.db.models import User
from ayvona.services import favorites
from ayvona.services.favorites import SaveResult
from ayvona.services.jobs_public import channel_post_url, get_visible_job, is_open
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_start")

_DEEP_LINK_RE = re.compile(r"^(save|job)_(\d{1,12})$")


async def send_job(
    message: Message, sf: SessionFactory, settings: Settings, user_id: int, job_id: int
) -> bool:
    """The job card + [📩 Murojaat] [⭐ Saqlash] [📤 Ulashish]. False if it is not visible."""
    now = utcnow()
    async with sf() as s:
        job = await get_visible_job(s, job_id)
        saved = job is not None and await favorites.is_saved(s, user_id, job_id)
    if job is None:
        await message.answer(T.JOB_NOT_FOUND)
        return False
    open_ = is_open(job, now)
    await message.answer(
        full_card(job, now),
        reply_markup=job_keyboard(
            job, saved=saved, open_=open_, post_url=channel_post_url(settings, job)
        ),
    )
    return True


async def open_search(message: Message, state: FSMContext, **data: object) -> None:
    """Entry of the search (``?start=search`` and the menu). Bosqich 12 replaces it."""
    await message.answer(T.SOON)


@router.message(CommandStart())
async def start_cmd(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    sf: SessionFactory,
    settings: Settings,
    db_user: User,
) -> None:
    await state.clear()  # /start always leaves a half-filled form
    arg = (command.args or "").strip()
    if m := _DEEP_LINK_RE.match(arg):
        kind, job_id = m.group(1), int(m.group(2))
        if kind == "save":
            async with sf() as s, s.begin():
                result = await favorites.save(s, db_user.tg_id, job_id, utcnow())
            if result is SaveResult.NOT_FOUND:
                await message.answer(T.JOB_NOT_FOUND, reply_markup=main_menu())
                return
            note = {
                SaveResult.SAVED: T.SAVED,
                SaveResult.ALREADY: T.ALREADY_SAVED,
                SaveResult.CLOSED: T.SAVE_CLOSED,
            }[result]
            await message.answer(note, reply_markup=main_menu())
        await send_job(message, sf, settings, db_user.tg_id, job_id)
        return
    if arg == "search":
        await open_search(message, state, sf=sf, settings=settings, db_user=db_user)
        return
    name = html.escape(message.from_user.first_name if message.from_user else "")
    await message.answer(
        T.WELCOME.format(name=name, channel=settings.app.branding.channel_username),
        reply_markup=main_menu(),
    )


@router.message(F.text == T.MENU_SEARCH)
async def search_menu(
    message: Message, state: FSMContext, sf: SessionFactory, settings: Settings, db_user: User
) -> None:
    await state.clear()
    await open_search(message, state, sf=sf, settings=settings, db_user=db_user)


@router.message(F.text.in_({T.MENU_POST, T.MENU_ALERTS}))
async def not_yet(message: Message) -> None:
    await message.answer(T.SOON, reply_markup=main_menu())


@router.message(Command("help"))
@router.message(F.text == T.MENU_HELP)
async def help_cmd(message: Message, settings: Settings) -> None:
    await message.answer(
        T.HELP_PUBLIC.format(channel=settings.app.branding.channel_username),
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(T.NOTHING_TO_CANCEL, reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(T.CANCELLED, reply_markup=main_menu())


# ------------------------------------------------------------------ job card buttons
@router.callback_query(JobCb.filter(F.action == "show"))
async def show_job_cb(
    query: CallbackQuery, callback_data: JobCb, sf: SessionFactory, settings: Settings
) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await send_job(query.message, sf, settings, query.from_user.id, callback_data.id)


@router.callback_query(JobCb.filter(F.action.in_({"save", "unsave"})))
async def toggle_save_cb(
    query: CallbackQuery, callback_data: JobCb, sf: SessionFactory, settings: Settings
) -> None:
    now = utcnow()
    user_id = query.from_user.id
    async with sf() as s, s.begin():
        if callback_data.action == "save":
            result = await favorites.save(s, user_id, callback_data.id, now)
            note = {
                SaveResult.SAVED: T.SAVED,
                SaveResult.ALREADY: T.ALREADY_SAVED,
                SaveResult.CLOSED: T.SAVE_CLOSED,
                SaveResult.NOT_FOUND: T.JOB_NOT_FOUND,
            }[result]
        else:
            await favorites.remove(s, user_id, callback_data.id)
            note = T.UNSAVED
        job = await get_visible_job(s, callback_data.id)
        saved = await favorites.is_saved(s, user_id, callback_data.id)
    await query.answer(note)
    if job is not None and isinstance(query.message, Message):
        await query.message.edit_reply_markup(
            reply_markup=job_keyboard(
                job, saved=saved, open_=is_open(job, now), post_url=channel_post_url(settings, job)
            )
        )
