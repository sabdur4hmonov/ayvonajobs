"""What the public (bot, later the website) may see of ``jobs``.

Only jobs that reached the channel are shown: ``published`` (open) and ``closed`` / ``expired``
(still visible in someone's favorites, marked as closed; never in search results).
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import Settings
from ayvona.db.models import Job, JobKind, JobOrigin, JobStatus, RawPost, Source
from ayvona.processing.normalize import to_latin

VISIBLE = (JobStatus.PUBLISHED, JobStatus.CLOSED, JobStatus.EXPIRED)


async def get_visible_job(session: AsyncSession, job_id: int) -> Job | None:
    """A job anyone may look at, or ``None`` (unknown, still in the queue, skipped...)."""
    job = await session.get(Job, job_id)
    return job if job is not None and job.status in VISIBLE else None


def is_open(job: Job, now: datetime) -> bool:
    """Published and not past ``expires_at``."""
    if job.status != JobStatus.PUBLISHED:
        return False
    return job.expires_at is None or job.expires_at > now


def channel_post_url(settings: Settings, job: Job) -> str | None:
    """Link to the job's post in our channel (for "📤 Ulashish")."""
    if not job.channel_message_id:
        return None
    return f"https://t.me/{settings.app.branding.channel_username}/{job.channel_message_id}"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(title: str | None) -> str:
    """URL part of a job page: ``Sotuv menejeri`` -> ``sotuv-menejeri`` (Latin, ≤ 60 chars)."""
    text = to_latin(title or "").lower().replace("'", "").replace("ʻ", "").replace("’", "")
    return _SLUG_RE.sub("-", text).strip("-")[:60].strip("-") or "ish"


async def latest_open(session: AsyncSession, now: datetime, limit: int = 20) -> list[Job]:
    """Newest open jobs (home page)."""
    rows = await session.scalars(
        select(Job)
        .where(
            Job.kind == JobKind.JOB.value,  # the website lists jobs only (projects: bot only)
            Job.status == JobStatus.PUBLISHED,
            or_(Job.expires_at.is_(None), Job.expires_at > now),
        )
        .order_by(Job.published_at.desc(), Job.id.desc())
        .limit(limit)
    )
    return list(rows.all())


async def sitemap_jobs(session: AsyncSession, now: datetime, limit: int) -> list[Job]:
    return await latest_open(session, now, limit)


async def source_kind(session: AsyncSession, job: Job) -> str:
    """``user`` / ``telegram`` / ``web`` / ``rss`` — where the job came from."""
    if job.origin == JobOrigin.USER or job.raw_post_id is None:
        return "user"
    kind = await session.scalar(
        select(Source.type)
        .join(RawPost, RawPost.source_id == Source.id)
        .where(RawPost.id == job.raw_post_id)
    )
    return (kind or "telegram").split(":", 1)[0]


async def allows_job_posting_markup(session: AsyncSession, job: Job) -> bool:
    """schema.org JobPosting (Google Jobs) only for Telegram and our users' jobs: Himalayas /
    Remotive forbid sending their jobs to Google Jobs, so no website / RSS job gets it."""
    return await source_kind(session, job) in ("user", "telegram")
