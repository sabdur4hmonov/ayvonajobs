"""Keyboards of the public bot."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from ayvona.bot import texts as T
from ayvona.bot.callbacks import FavPageCb, JobCb
from ayvona.db.models import Job


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=T.MENU_POST), KeyboardButton(text=T.MENU_SEARCH)],
            [KeyboardButton(text=T.MENU_FAVORITES), KeyboardButton(text=T.MENU_ALERTS)],
            [KeyboardButton(text=T.MENU_MY_JOBS), KeyboardButton(text=T.MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=T.MENU_PLACEHOLDER,
    )


def share_url(post_url: str) -> str:
    """Telegram's own "share" dialog for our channel post."""
    return f"https://t.me/share/url?url={quote(post_url, safe='')}"


def _url_row(buttons: list[Any] | None) -> list[InlineKeyboardButton]:
    """The "📩 Murojaat" / "🔗 Ariza topshirish" buttons of the channel post (first row)."""
    if not buttons:
        return []
    first = buttons[0] or []
    return [
        InlineKeyboardButton(text=b["text"], url=b["url"])
        for b in first
        if b.get("url") and "?start=" not in b["url"]  # not our own bot's deep links
    ]


def job_keyboard(
    job: Job, *, saved: bool, open_: bool, post_url: str | None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if open_ and (contact := _url_row(job.buttons)):
        rows.append(contact)
    second: list[InlineKeyboardButton] = []
    if saved:
        second.append(
            InlineKeyboardButton(
                text=T.BTN_UNSAVE, callback_data=JobCb(action="unsave", id=job.id).pack()
            )
        )
    elif open_:
        second.append(
            InlineKeyboardButton(
                text=T.BTN_SAVE, callback_data=JobCb(action="save", id=job.id).pack()
            )
        )
    if post_url and open_:
        second.append(InlineKeyboardButton(text=T.BTN_SHARE, url=share_url(post_url)))
    if second:
        rows.append(second)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def list_keyboard(
    jobs: list[Job], offset: int, page: int, pages: int, page_cb: Any
) -> InlineKeyboardMarkup:
    """One "N. Batafsil" button per job + ⬅️ ➡️. ``page_cb(page)`` -> packed callback data."""
    rows: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for i, job in enumerate(jobs, start=offset + 1):
        line.append(
            InlineKeyboardButton(
                text=f"{i}. {T.BTN_DETAILS}", callback_data=JobCb(action="show", id=job.id).pack()
            )
        )
        if len(line) == 3:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=T.BTN_PREV, callback_data=page_cb(page - 1)))
    if page < pages:
        nav.append(InlineKeyboardButton(text=T.BTN_NEXT, callback_data=page_cb(page + 1)))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fav_page(page: int) -> str:
    return FavPageCb(page=page).pack()
