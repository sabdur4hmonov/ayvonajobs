"""🔓 Admin: the unfiltered alerts — ``/alerts`` (the subscription list: ⏸ / ▶️ / 🗑 / ➕, the
same screen as "🔔 Obunalar") and the 🔄 button under an alert (the post's current state: a post
that was waiting in the queue may be in the channel by now). Delivery: services/admin_alerts.py.
"""

from __future__ import annotations

import contextlib

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.alerts_render import render_admin_alert
from ayvona.bot.callbacks import AdmAlertCb
from ayvona.bot.handlers.alerts import show_list
from ayvona.config import Settings
from ayvona.services import admin_alerts

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="admin_alerts")


@router.message(Command("alerts"))
async def alerts_command(
    message: Message, state: FSMContext, sf: SessionFactory, settings: Settings
) -> None:
    await state.set_state(None)
    await show_list(message, sf, settings)


@router.callback_query(AdmAlertCb.filter())
async def refresh_alert(
    query: CallbackQuery, callback_data: AdmAlertCb, sf: SessionFactory, settings: Settings
) -> None:
    async with sf() as s:
        view = await admin_alerts.view_for(s, callback_data.raw, callback_data.sub, settings)
    if view is None:
        await query.answer(T.ADM_ALERT_GONE, show_alert=True)
        return
    await query.answer(T.ADM_ALERT_REFRESHED)
    if not isinstance(query.message, Message):
        return
    text, kb = render_admin_alert(settings, view)
    with contextlib.suppress(TelegramBadRequest):  # "message is not modified": nothing changed
        await query.message.edit_text(text, reply_markup=kb)
