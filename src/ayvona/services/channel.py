"""Changes to posts already in our channel (Bot API).

Only a closed job's post is edited: "❌ YOPILDI" on top, the buttons removed. Expired jobs are
never touched in the channel (ROADMAP Bosqich 14).
"""

from __future__ import annotations

import html

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from loguru import logger

from ayvona.botapi import parse_chat_id
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.processing.formatter import visible_len

CLOSED_MARK = "❌ <b>YOPILDI</b>\n\n"
_NO_BUTTONS = InlineKeyboardMarkup(inline_keyboard=[])


def closed_caption(job: Job, limit: int) -> str:
    """The post with the mark on top; if it no longer fits, the mark + the title only."""
    text = CLOSED_MARK + (job.formatted_text or "")
    if visible_len(text) <= limit:
        return text
    return CLOSED_MARK + f"💼 <b>{html.escape(job.title or '—')}</b>"


async def mark_closed(bot: Bot, settings: Settings, job: Job) -> bool:
    """Edit the channel post of ``job``. A post with a picture has a caption, a text post has a
    text — the caption is tried first. Never raises; False if nothing could be changed."""
    channel = parse_chat_id(settings.env.channel_id)
    if channel is None or not job.channel_message_id:
        return False
    caption = closed_caption(job, settings.app.formatter.max_caption_length)
    try:
        await bot.edit_message_caption(
            chat_id=channel,
            message_id=job.channel_message_id,
            caption=caption,
            reply_markup=_NO_BUTTONS,
        )
        return True
    except TelegramBadRequest as e:
        if "no caption" not in e.message.lower() and "there is no" not in e.message.lower():
            logger.warning("job #{}: kanal posti tahrirlanmadi: {}", job.id, e.message)
            return False
    except Exception as e:
        logger.warning("job #{}: kanal posti tahrirlanmadi: {}", job.id, e)
        return False
    try:  # a text post (no picture)
        await bot.edit_message_text(
            chat_id=channel,
            message_id=job.channel_message_id,
            text=CLOSED_MARK + (job.formatted_text or ""),
            reply_markup=_NO_BUTTONS,
        )
        return True
    except Exception as e:
        logger.warning("job #{}: kanal posti tahrirlanmadi: {}", job.id, e)
        return False
