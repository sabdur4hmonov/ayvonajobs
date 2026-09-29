"""Queries for the ``jobs`` table as the publishing outbox.

Status flow: ``queued`` -> ``sending`` -> ``published``; on a send error ``retry`` (with
``next_retry_at``) and after ``max_publish_attempts`` errors ``failed``. A job is moved to
``sending`` with a conditional UPDATE, so two publishers (or a publisher and the pipeline
replacing a queued job) can never both take it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Job, JobStatus

MAX_ERROR_LEN = 2000
SENDABLE = (JobStatus.QUEUED, JobStatus.RETRY)


def _due(now: datetime) -> ColumnElement[bool]:
    return Job.status.in_(SENDABLE) & or_(Job.next_retry_at.is_(None), Job.next_retry_at <= now)


async def next_due(session: AsyncSession, now: datetime) -> Job | None:
    """The job to publish next: due (hold window / backoff over), earliest first."""
    stmt = (
        select(Job)
        .where(_due(now))
        .order_by(func.coalesce(Job.next_retry_at, Job.created_at), Job.id)
        .limit(1)
    )
    return (await session.scalars(stmt)).first()


async def claim(session: AsyncSession, job: Job) -> bool:
    """``queued``/``retry`` -> ``sending`` if nobody changed the job meanwhile. Does not commit."""
    result = await session.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == job.status, Job.attempts == job.attempts)
        .values(status=JobStatus.SENDING)
        .execution_options(synchronize_session=False)
    )
    return (result.rowcount or 0) == 1


async def mark_published(
    session: AsyncSession, job_id: int, message_id: int, now: datetime
) -> None:
    """Does not commit."""
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=JobStatus.PUBLISHED,
            channel_message_id=message_id,
            published_at=now,
            last_error=None,
            next_retry_at=None,
        )
    )


async def mark_attempt_failed(
    session: AsyncSession,
    job_id: int,
    error: str,
    *,
    attempts: int,
    next_retry_at: datetime | None,
) -> None:
    """A send attempt failed: ``retry`` at ``next_retry_at``, or ``failed`` if it is ``None``.
    Does not commit."""
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=JobStatus.FAILED if next_retry_at is None else JobStatus.RETRY,
            attempts=attempts,
            next_retry_at=next_retry_at,
            last_error=error[:MAX_ERROR_LEN],
        )
    )


async def release(
    session: AsyncSession,
    job_id: int,
    status: JobStatus,
    *,
    not_before: datetime | None,
    error: str | None = None,
) -> None:
    """Give a ``sending`` job back without using an attempt (flood wait, bad bot setup).
    Does not commit."""
    values: dict[str, object] = {"status": status, "next_retry_at": not_before}
    if error is not None:
        values["last_error"] = error[:MAX_ERROR_LEN]
    await session.execute(update(Job).where(Job.id == job_id).values(**values))


async def reset_stuck_sending(session: AsyncSession, now: datetime) -> list[int]:
    """On start: jobs left in ``sending`` by a crash go back to the queue (``retry``, due now).

    At-least-once: if Telegram accepted the post just before the crash, it is posted twice —
    a rare duplicate is better than a lost job (CLAUDE.md, hard rule 2). Does not commit.
    """
    ids = list((await session.scalars(select(Job.id).where(Job.status == JobStatus.SENDING))).all())
    if ids:
        await session.execute(
            update(Job).where(Job.id.in_(ids)).values(status=JobStatus.RETRY, next_retry_at=now)
        )
    return ids


async def count_by_status(
    session: AsyncSession, statuses: Sequence[JobStatus] | None = None
) -> dict[str, int]:
    stmt = select(Job.status, func.count()).group_by(Job.status)
    if statuses:
        stmt = stmt.where(Job.status.in_(statuses))
    return {str(status): int(n) for status, n in (await session.execute(stmt)).all()}
