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
from ayvona.services.search import REMOTE, SearchFilters

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


def project_line(job: Job, n: int) -> str:
    """``3. 🧩 <b>Telegram bot yozish</b>
    💰 3 000 000 so'm · ⏳ 2 hafta``"""
    deadline = (
        T.PROJECT_LINE_DEADLINE.format(deadline=html.escape((job.deadline_text or "")[:40]))
        if job.deadline_text
        else ""
    )
    return T.PROJECT_LINE.format(
        n=n,
        title=html.escape((job.title or "—")[:MAX_TITLE]),
        budget=html.escape((job.salary_text or T.SALARY_NEGOTIABLE)[:40]),
        deadline=deadline,
    )


def profession_title(settings: Settings, category: str | None, profession: str | None) -> str:
    if not profession:
        return ""
    for key, cat in settings.categories.items():
        if (category is None or key == category) and profession in cat.professions:
            return cat.professions[profession].title
    return profession


def filters_summary(f: SearchFilters, settings: Settings) -> str:
    """``Sotuv va savdo › Sotuvchi · Toshkent sh. · 4 mln+ · «kassir»`` (HTML-escaped)."""
    parts: list[str] = []
    if f.category and (cat := settings.categories.get(f.category)):
        head = cat.title
        if f.profession:
            head += f" › {profession_title(settings, f.category, f.profession)}"
        parts.append(head)
    if f.region == REMOTE:
        parts.append(T.REMOTE)
    elif f.region and (reg := settings.regions.regions.get(f.region)):
        parts.append(reg.title)
    if f.min_salary:
        parts.append(T.SEARCH_SALARY_STEP.format(mln=f"{f.min_salary / 1_000_000:g}"))
    if f.keyword:
        parts.append(f"«{f.keyword}»")
    return html.escape(" · ".join(parts)) if parts else T.SEARCH_EVERYTHING


def full_card(job: Job, now: datetime) -> str:
    """The job's full card ("📖 To'liq ma'lumot": nothing shortened, the original text of a Russian
    / English post), else the channel caption (already HTML); marked when the job is closed."""
    text = job.full_html or job.formatted_text or html.escape(job.title or "—")
    return (T.JOB_CLOSED_MARK + text) if not is_open(job, now) else text
