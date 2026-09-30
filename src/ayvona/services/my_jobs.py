"""📋 Mening e'lonlarim: a user's own jobs — list, close ("✅ Ish topildi"), extend.
Shared by the bot and the future website.

Closing: ``published`` → ``closed`` (out of search; the channel post gets "❌ YOPILDI" and loses
its buttons — services/channel.py), or a job still waiting (``pending_review`` / ``queued`` /
``retry``) → ``closed`` before it reaches the channel. A job being sent right now cannot be
closed (the conditional UPDATE refuses it; the user tries again a minute later).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin, JobStatus

CLOSABLE = (JobStatus.PENDING_REVIEW, JobStatus.QUEUED, JobStatus.RETRY, JobStatus.PUBLISHED)
SHOWN = (*CLOSABLE, JobStatus.SENDING, JobStatus.CLOSED, JobStatus.EXPIRED)


async def list_jobs(session: AsyncSession, user_id: int, limit: int = 10) -> list[Job]:
    """The user's jobs (not rejected), newest first."""
    rows = await session.scalars(
        select(Job)
        .where(Job.origin == JobOrigin.USER, Job.author_id == user_id, Job.status.in_(SHOWN))
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(limit)
    )
    return list(rows.all())


async def close_job(
    session: AsyncSession, user_id: int, job_id: int, now: datetime
) -> tuple[Job | None, bool]:
    """Close one of the user's jobs. Returns (job, was_published) or (None, False) if it is not
    theirs / already closed / being sent. Does not commit."""
    job = await session.get(Job, job_id)
    if job is None or job.author_id != user_id or job.origin != JobOrigin.USER:
        return None, False
    was_published = job.status == JobStatus.PUBLISHED
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(CLOSABLE))
        .values(status=JobStatus.CLOSED, closed_at=now, next_retry_at=None)
        .execution_options(synchronize_session=False)
    )
    if (result.rowcount or 0) != 1:
        return None, False
    await session.refresh(job)
    return job, was_published


async def extend_job(
    session: AsyncSession, user_id: int, job_id: int, now: datetime, settings: Settings
) -> Job | None:
    """ "🔄 Uzaytirish": a published (or just expired) user job gets ``user_days`` more from now
    and is back in search. Does not commit."""
    job = await session.get(Job, job_id)
    if job is None or job.author_id != user_id or job.origin != JobOrigin.USER:
        return None
    if job.status not in (JobStatus.PUBLISHED, JobStatus.EXPIRED):
        return None
    job.status = JobStatus.PUBLISHED
    job.expires_at = now + timedelta(days=settings.app.expiry.user_days)
    job.reminded_at = None
    await session.flush()
    return job
