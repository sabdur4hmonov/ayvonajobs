"""How alert messages look (used by the worker's services.alerts.AlertService and
services.admin_alerts.AdminAlertService; the admin's 🔄 button re-renders with the same code)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ayvona.bot import texts as T
from ayvona.bot.callbacks import AdmAlertCb, JobCb, SubCb
from ayvona.bot.cards import filters_summary, full_card, short_line
from ayvona.bot.keyboards import job_keyboard
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.processing.formatter import esc, truncate
from ayvona.services.admin_alerts import AlertView
from ayvona.services.jobs_public import channel_post_url
from ayvona.services.search import SearchFilters
from ayvona.timeutil import to_local, utcnow


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


# ------------------------------------------------------------------ 🔓 admin: unfiltered alerts
DIGEST_PART_CHARS = 3500  # one digest message stays well under Telegram's 4096


def admin_state_line(view: AlertView) -> str:
    st = view.state
    if st.published:
        return T.ADM_ALERT_PUBLISHED_COPY if st.other_copy else T.ADM_ALERT_PUBLISHED
    return T.ADM_ALERT_NOT_PUBLISHED.format(reason=esc(st.reason or "—"))


def _subscription_summary(settings: Settings, view: AlertView) -> str:
    sub = view.subscription
    if sub is None:
        return "—"
    f = SearchFilters(category=sub.category, profession=sub.profession, keyword=sub.keyword)
    return filters_summary(f, settings)


def render_admin_alert(settings: Settings, view: AlertView) -> tuple[str, InlineKeyboardMarkup]:
    """The vacancy text as collected, the source, and whether / why it is (not) in our channel."""
    raw = view.raw
    when = to_local(raw.posted_at or raw.fetched_at, settings.timezone).strftime("%d.%m %H:%M")
    source = view.source.title or view.source.identifier if view.source else "?"
    lines = [
        T.ADM_ALERT_HEAD.format(summary=_subscription_summary(settings, view)),
        admin_state_line(view),
        T.ADM_ALERT_META.format(source=esc(source), when=when),
    ]
    if view.hits:
        lines.append(T.ADM_ALERT_WORDS.format(words=esc(", ".join(view.hits))))
    body = (raw.text or "").strip()
    limit = settings.app.admin_alerts.text_max_chars
    lines += ["", esc(truncate(body, limit)) if body else T.ADM_ALERT_NO_TEXT]
    first: list[InlineKeyboardButton] = []
    if view.url:
        first.append(InlineKeyboardButton(text=T.BTN_ADM_SOURCE, url=view.url))
    if (
        view.job is not None
        and view.state.published
        and (post := channel_post_url(settings, view.job))
    ):
        first.append(InlineKeyboardButton(text=T.BTN_ADM_CHANNEL, url=post))
    refresh = InlineKeyboardButton(
        text=T.BTN_ADM_REFRESH,
        callback_data=AdmAlertCb(
            raw=raw.id, sub=view.subscription.id if view.subscription else 0
        ).pack(),
    )
    rows = [row for row in (first, [refresh]) if row]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _digest_item(n: int, view: AlertView) -> str:
    first_line = next((ln.strip() for ln in (view.raw.text or "").splitlines() if ln.strip()), "")
    title = esc(truncate(first_line, 80)) if first_line else T.ADM_ALERT_NO_TEXT
    st = view.state
    state = "✅" if st.published else f"🚫 {esc(st.reason or '—')}"
    link = T.ADM_DIGEST_LINK.format(url=esc(view.url)) if view.url else "—"
    return T.ADM_DIGEST_ITEM.format(n=n, title=title, state=state, link=link)


def render_admin_digest(
    settings: Settings, views: Sequence[AlertView]
) -> list[tuple[str, list[int]]]:
    """The posts over the hourly cap as short lines, split into messages of ≤ 3500 characters.
    Returns (text, the raw post ids in that message) per message."""
    parts: list[tuple[str, list[int]]] = []
    head = T.ADM_DIGEST_HEAD.format(n=len(views))
    lines: list[str] = [head, ""]
    ids: list[int] = []
    for n, view in enumerate(views, start=1):
        item = _digest_item(n, view)
        if ids and sum(len(x) + 1 for x in lines) + len(item) > DIGEST_PART_CHARS:
            parts.append(("\n".join(lines), ids))
            lines, ids = [], []
        lines.append(item)
        ids.append(view.raw.id)
    if ids:
        parts.append(("\n".join(lines), ids))
    return parts
