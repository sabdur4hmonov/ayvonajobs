"""How a job looks inside the bot: the full card (the channel caption) and a one-line summary
for lists (favorites, search results)."""

from __future__ import annotations

import html
from datetime import datetime

from ayvona.bot import texts as T
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.processing.formatter import CURRENCY_NAMES, PERIOD_NAMES, format_amount
from ayvona.processing.salary import UZS
from ayvona.services.jobs_public import is_open

MAX_TITLE = 60


def salary_short(job: Job) -> str:
    """``4 000 000 – 6 000 000 so'm`` / ``500 $ dan`` / ``Kelishiladi``."""
    lo, hi = job.salary_min, job.salary_max
    if lo is None and hi is None:
        text = (job.salary_text or "").strip()
        return text[:40] if text else T.SALARY_NEGOTIABLE
    cur = CURRENCY_NAMES.get(job.currency or UZS, job.currency or "")
    glue = "" if cur == "so'm" else " "
    if lo is not None and hi is not None and lo != hi:
        out = f"{format_amount(lo)} – {format_amount(hi)} {cur}"
    elif lo is not None and hi is not None:
        out = f"{format_amount(lo)} {cur}"
    elif lo is not None:
        out = f"{format_amount(lo)} {cur}{glue}dan"
    else:
        assert hi is not None
        out = f"{format_amount(hi)} {cur}{glue}gacha"
    if period := PERIOD_NAMES.get(job.salary_period or ""):
        out += f" ({period})"
    return out


def place_short(job: Job, settings: Settings) -> str | None:
    regions = settings.regions
    parts: list[str] = []
    if job.is_remote:
        parts.append(T.REMOTE)
    if job.region == regions.multi_region:
        parts.append(regions.multi_region_title)
    elif job.region and (reg := regions.regions.get(job.region)):
        parts.append(reg.title)
    return ", ".join(parts) or None


def short_line(job: Job, settings: Settings, n: int, now: datetime) -> str:
    """``3. <b>Sotuvchi</b> — Ishonch savdo\n    💰 4 000 000 so'm · 📍 Toshkent sh.``"""
    title = html.escape((job.title or "—")[:MAX_TITLE])
    company = f" — {html.escape(job.company[:40])}" if job.company else ""
    closed = "" if is_open(job, now) else T.CARD_CLOSED
    details = [f"💰 {html.escape(salary_short(job))}"]
    if place := place_short(job, settings):
        details.append(f"📍 {html.escape(place)}")
    return f"{n}. <b>{title}</b>{company}{closed}\n    " + " · ".join(details)


def full_card(job: Job, now: datetime) -> str:
    """The channel caption (already HTML), marked when the job is closed."""
    text = job.formatted_text or html.escape(job.title or "—")
    return (T.JOB_CLOSED_MARK + text) if not is_open(job, now) else text
