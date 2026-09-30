"""How alert messages look (used by the worker's services.alerts.AlertService)."""

from __future__ import annotations

from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ayvona.bot import texts as T
from ayvona.bot.callbacks import JobCb, SubCb
from ayvona.bot.cards import filters_summary, full_card, short_line
from ayvona.bot.keyboards import job_keyboard
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.services.jobs_public import channel_post_url
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow


def render_alert(
    settings: Settings, job: Job, filters: SearchFilters, subscription_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    now = utcnow()
    text = T.ALERT_HEAD.format(summary=filters_summary(filters, settings)) + full_card(job, now)
    kb = job_keyboard(job, saved=False, open_=True, post_url=channel_post_url(settings, job))
    kb.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=T.ALERT_STOP, callback_data=SubCb(action="pause", id=subscription_id).pack()
            )
        ]
    )
    return text, kb


def render_digest(
    settings: Settings, jobs: list[Job], now: datetime
) -> tuple[str, InlineKeyboardMarkup]:
    lines = [T.DIGEST_HEAD.format(n=len(jobs)), ""]
    lines += [short_line(j, settings, i, now) for i, j in enumerate(jobs, start=1)]
    buttons = [
        InlineKeyboardButton(
            text=f"{i}. {T.BTN_DETAILS}", callback_data=JobCb(action="show", id=j.id).pack()
        )
        for i, j in enumerate(jobs, start=1)
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)
