"""🔍 Job search — shared by the bot and the future website.

* filters: category → profession → region (or "Masofaviy") → minimum monthly salary, or a keyword;
* only open jobs (``published`` and not past ``expires_at``), best priority tier first, then
  newest first;
* keyword: SQLite FTS5 over ``jobs.search_text`` — both sides folded (Cyrillic → Latin,
  lowercase, no apostrophes), each word as a prefix ("sotuv" finds "sotuvchi");
* salary: monthly salaries only, USD compared in so'm with ``kv_store.usd_rate``; jobs without a
  salary number are shown only when there is no salary filter;
* ``search_logs``: every search is written; "🔁 Oxirgi qidiruv" reads the last one.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, column, func, or_, select, table, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Job, JobKind, JobStatus, SearchLog
from ayvona.db.repositories import kv_repo
from ayvona.db.repositories.jobs_repo import tier_of_job
from ayvona.processing.normalize import search_text
from ayvona.processing.salary import USD, UZS

REMOTE = "remote"
USD_RATE_KEY = "usd_rate"
MAX_QUERY_WORDS = 6
_WORD_RE = re.compile(r"\w+")


@dataclass(slots=True)
class SearchFilters:
    category: str | None = None
    profession: str | None = None
    region: str | None = None  # regions.yaml key or REMOTE
    min_salary: int | None = None  # so'm per month
    keyword: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SearchFilters:
        names = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (data or {}).items() if k in names})

    @property
    def empty(self) -> bool:
        return not self.to_dict()


def fts_query(keyword: str | None) -> str | None:
    """User text -> a safe FTS5 query: every word (2+ letters) as a quoted prefix, AND-ed."""
    words = [w for w in _WORD_RE.findall(search_text(keyword or "")) if len(w) >= 2]
    if not words:
        return None
    return " AND ".join(f'"{w}"*' for w in words[:MAX_QUERY_WORDS])


def _open_jobs(now: datetime) -> list[Any]:
    return [
        Job.kind == JobKind.JOB.value,  # one-time projects have their own list (Loyihalar)
        Job.status == JobStatus.PUBLISHED,
        or_(Job.expires_at.is_(None), Job.expires_at > now),
    ]


def conditions(f: SearchFilters, now: datetime, usd_rate: float) -> list[Any] | None:
    """SQL conditions of ``f``; ``None`` if the keyword has no searchable word."""
    conds = _open_jobs(now)
    if f.category:
        conds.append(Job.category == f.category)
    if f.profession:
        conds.append(Job.profession == f.profession)
    if f.region == REMOTE:
        conds.append(Job.is_remote.is_(True))
    elif f.region:
        conds.append(Job.region == f.region)
    if f.min_salary:
        rate = case((Job.currency == USD, usd_rate), else_=1)
        conds.append(
            and_(
                Job.currency.in_((UZS, USD)),
                or_(Job.salary_period.is_(None), Job.salary_period == "month"),
                or_(Job.salary_max * rate >= f.min_salary, Job.salary_min * rate >= f.min_salary),
            )
        )
    if f.keyword:
        query = fts_query(f.keyword)
        if query is None:
            return None
        matched = (
            select(column("rowid"))
            .select_from(table("jobs_fts"))
            .where(text("jobs_fts MATCH :fts_q").bindparams(fts_q=query))
        )
        conds.append(Job.id.in_(matched))
    return conds


def job_matches(f: SearchFilters, job: Job, now: datetime, usd_rate: float) -> bool:
    """:func:`conditions` for one job in Python (alerts check each newly published job)."""
    if job.kind != JobKind.JOB.value:
        return False
    if job.status != JobStatus.PUBLISHED or (job.expires_at is not None and job.expires_at <= now):
        return False
    if f.category and job.category != f.category:
        return False
    if f.profession and job.profession != f.profession:
        return False
    if f.region == REMOTE and not job.is_remote:
        return False
    if f.region and f.region != REMOTE and job.region != f.region:
        return False
    if f.min_salary:
        if job.currency not in (UZS, USD) or job.salary_period not in (None, "month"):
            return False
        rate = usd_rate if job.currency == USD else 1
        amounts = [a * rate for a in (job.salary_min, job.salary_max) if a is not None]
        if not any(a >= f.min_salary for a in amounts):
            return False
    if f.keyword:
        words = [w for w in _WORD_RE.findall(search_text(f.keyword)) if len(w) >= 2]
        tokens = _WORD_RE.findall(job.search_text or "")
        if not words or not all(any(t.startswith(w) for t in tokens) for w in words):
            return False
    return True


async def search(
    session: AsyncSession,
    f: SearchFilters,
    now: datetime,
    *,
    usd_rate: float,
    offset: int = 0,
    limit: int = 5,
) -> tuple[list[Job], int]:
    """Matching open jobs and how many there are in total: best priority tier first (see
    processing/priority.py), newest first within a tier."""
    conds = conditions(f, now, usd_rate)
    if conds is None:
        return [], 0
    total = int(await session.scalar(select(func.count()).select_from(Job).where(*conds)) or 0)
    if not total or limit <= 0:
        return [], total
    rows = await session.scalars(
        select(Job)
        .where(*conds)
        .order_by(tier_of_job(), Job.published_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.all()), total


async def log_search(
    session: AsyncSession, user_id: int | None, f: SearchFilters, total: int, now: datetime
) -> None:
    """Does not commit."""
    session.add(
        SearchLog(user_id=user_id, filters=f.to_dict(), results_count=total, created_at=now)
    )


async def last_filters(session: AsyncSession, user_id: int) -> SearchFilters | None:
    """The user's last search ("🔁 Oxirgi qidiruv"), survives restarts."""
    row = await session.scalar(
        select(SearchLog)
        .where(SearchLog.user_id == user_id)
        .order_by(SearchLog.created_at.desc(), SearchLog.id.desc())
        .limit(1)
    )
    return SearchFilters.from_dict(row.filters) if row is not None else None


# --------------------------------------------------------------------------- search_text backfill
async def fill_search_text(session: AsyncSession, limit: int = 500) -> int:
    """Jobs written before ``search_text`` existed get it (worker / bot start). Does not commit."""
    rows = (
        await session.execute(
            select(Job.id, Job.title, Job.company, Job.city, Job.description)
            .where(Job.search_text.is_(None))
            .limit(limit)
        )
    ).all()
    for job_id, title, company, city, description in rows:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(search_text=search_text(title, company, city, description))
            .execution_options(synchronize_session=False)
        )
    return len(rows)


# --------------------------------------------------------------------------- USD rate
async def usd_rate(session: AsyncSession, fallback: float) -> float:
    raw = await kv_repo.get(session, USD_RATE_KEY)
    if raw:
        try:
            rate = float(json.loads(raw)["rate"])
            if rate > 0:
                return rate
        except (ValueError, KeyError, TypeError):
            pass
    return fallback


async def set_usd_rate(session: AsyncSession, rate: float, now: datetime) -> None:
    """Does not commit."""
    await kv_repo.set_value(
        session, USD_RATE_KEY, json.dumps({"rate": rate, "at": now.isoformat()})
    )
