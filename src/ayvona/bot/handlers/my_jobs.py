"""📋 Mening e'lonlarim: the user's own jobs with [✅ Ish topildi N] (confirm → closed, the
channel post gets "❌ YOPILDI") and [🔄 Uzaytirish N] (also from the "Uzaytirasizmi?" reminder).
Logic: services/my_jobs.py, channel edit: services/channel.py.
"""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import MyJobCb
from ayvona.config import Settings
from ayvona.db.models import Job, JobStatus
from ayvona.services import my_jobs
from ayvona.services.channel import mark_closed
from ayvona.services.lifetime import active_days
from ayvona.timeutil import to_local, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_my_jobs")


def _until(job: Job, settings: Settings) -> str:
    return to_local(job.expires_at, settings.timezone).strftime("%d.%m") if job.expires_at else "—"


def list_view(jobs: list[Job], settings: Settings) -> tuple[str, InlineKeyboardMarkup | None]:
    if not jobs:
        return T.MY_EMPTY, None
    lines = [T.MY_HEAD.format(n=len(jobs)), ""]
    rows: list[list[InlineKeyboardButton]] = []
    for n, job in enumerate(jobs, start=1):
        state = T.MY_STATES.get(str(job.status), str(job.status)).format(
            until=_until(job, settings)
        )
        lines.append(T.MY_ITEM.format(n=n, title=html.escape(job.title or "—"), state=state))
        row: list[InlineKeyboardButton] = []
        if job.status in my_jobs.CLOSABLE:
            row.append(
                InlineKeyboardButton(
                    text=T.BTN_MY_CLOSE.format(n=n),
                    callback_data=MyJobCb(action="close", id=job.id).pack(),
                )
            )
        if job.status in (JobStatus.PUBLISHED, JobStatus.EXPIRED):
            row.append(
                InlineKeyboardButton(
                    text=T.BTN_MY_EXTEND.format(n=n),
                    callback_data=MyJobCb(action="extend", id=job.id).pack(),
                )
            )
        if row:
            rows.append(row)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def reminder_view(settings: Settings, job: Job) -> tuple[str, InlineKeyboardMarkup]:
    """The worker's "⏳ Uzaytirasizmi?" message (services/expiry.py)."""
    text = T.REMIND_TEXT.format(title=html.escape(job.title or "—"), until=_until(job, settings))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.BTN_REMIND_EXTEND.format(days=active_days(job, settings)),
                    callback_data=MyJobCb(action="extend", id=job.id).pack(),
                ),
                InlineKeyboardButton(
                    text=T.BTN_REMIND_CLOSE, callback_data=MyJobCb(action="close", id=job.id).pack()
                ),
            ]
        ]
    )
    return text, kb


@router.message(F.text == T.MENU_MY_JOBS)
async def my_jobs_menu(message: Message, sf: SessionFactory, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with sf() as s:
        jobs = await my_jobs.list_jobs(s, message.from_user.id)
    text, kb = list_view(jobs, settings)
    await message.answer(text, reply_markup=kb)


@router.callback_query(MyJobCb.filter(F.action == "close"))
async def ask_close(query: CallbackQuery, callback_data: MyJobCb, sf: SessionFactory) -> None:
    await query.answer()
    async with sf() as s:
        job = await s.get(Job, callback_data.id)
    if job is None or job.author_id != query.from_user.id or not isinstance(query.message, Message):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.BTN_YES_CLOSE, callback_data=MyJobCb(action="closeok", id=job.id).pack()
                ),
                InlineKeyboardButton(text=T.BTN_NO, callback_data=MyJobCb(action="list").pack()),
            ]
        ]
    )
    await query.message.answer(
        T.MY_CLOSE_CONFIRM.format(title=html.escape(job.title or "—")), reply_markup=kb
    )


@router.callback_query(MyJobCb.filter(F.action == "closeok"))
async def close(
    query: CallbackQuery, callback_data: MyJobCb, sf: SessionFactory, settings: Settings, bot: Bot
) -> None:
    async with sf() as s, s.begin():
        job, was_published = await my_jobs.close_job(
            s, query.from_user.id, callback_data.id, utcnow()
        )
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if job is None:
        await query.message.edit_text(T.MY_CLOSE_FAIL)
        return
    if was_published:
        await mark_closed(bot, settings, job)
    await query.message.edit_text(T.MY_CLOSED)


@router.callback_query(MyJobCb.filter(F.action == "extend"))
async def extend(
    query: CallbackQuery, callback_data: MyJobCb, sf: SessionFactory, settings: Settings
) -> None:
    async with sf() as s, s.begin():
        job = await my_jobs.extend_job(s, query.from_user.id, callback_data.id, utcnow(), settings)
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if job is None:
        await query.message.answer(T.MY_EXTEND_FAIL)
        return
    await query.message.answer(T.MY_EXTENDED.format(until=_until(job, settings)))


@router.callback_query(MyJobCb.filter(F.action == "list"))
async def back_to_list(query: CallbackQuery, sf: SessionFactory, settings: Settings) -> None:
    await query.answer()
    async with sf() as s:
        jobs = await my_jobs.list_jobs(s, query.from_user.id)
    text, kb = list_view(jobs, settings)
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=kb)
