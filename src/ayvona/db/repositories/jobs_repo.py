"""Queries for the ``jobs`` table as the publishing outbox.

Status flow: ``queued`` -> ``sending`` -> ``published``; on a send error ``retry`` (with
``next_retry_at``) and after ``max_publish_attempts`` errors ``failed``. A job is moved to
``sending`` with a conditional UPDATE, so two publishers (or a publisher and the pipeline
replacing a queued job) can never both take it. A waiting job whose source post is older than
``publisher.max_age_hours`` becomes ``skipped_old`` instead (:func:`skip_old`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Job, JobStatus, RawPost

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


async def last_published_at(session: AsyncSession) -> datetime | None:
    """When the newest job reached the channel (``None``: nothing published yet)."""
    return await session.scalar(select(func.max(Job.published_at)))


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
    session: AsyncSession,
    job_id: int,
    message_id: int,
    now: datetime,
    expires_at: datetime | None = None,
) -> None:
    """Does not commit."""
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=JobStatus.PUBLISHED,
            channel_message_id=message_id,
            published_at=now,
            expires_at=expires_at,
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


async def skip_old(
    session: AsyncSession,
    posted_before: datetime,
    reason: str,
    *,
    statuses: Sequence[JobStatus] = SENDABLE,
    job_ids: Sequence[int] | None = None,
) -> list[int]:
    """Jobs in ``statuses`` whose source post appeared before ``posted_before``
    (``raw_posts.posted_at``, else ``fetched_at``) -> ``skipped_old``: never published, kept.
    Jobs without a raw post (user submissions) are not touched. ``job_ids=None`` = any job.
    Returns the ids. Does not commit."""
    posted = (
        select(func.coalesce(RawPost.posted_at, RawPost.fetched_at))
        .where(RawPost.id == Job.raw_post_id)
        .scalar_subquery()
    )
    stmt = select(Job.id).where(
        Job.status.in_(statuses), Job.raw_post_id.is_not(None), posted < posted_before
    )
    if job_ids is not None:
        stmt = stmt.where(Job.id.in_(list(job_ids)))
    ids = list((await session.scalars(stmt.order_by(Job.id))).all())
    if ids:
        await session.execute(
            update(Job)
            .where(Job.id.in_(ids), Job.status.in_(statuses))
            .values(
                status=JobStatus.SKIPPED_OLD, next_retry_at=None, last_error=reason[:MAX_ERROR_LEN]
            )
        )
    return ids


async def count_by_status(
    session: AsyncSession, statuses: Sequence[JobStatus] | None = None
) -> dict[str, int]:
    stmt = select(Job.status, func.count()).group_by(Job.status)
    if statuses:
        stmt = stmt.where(Job.status.in_(statuses))
    return {str(status): int(n) for status, n in (await session.execute(stmt)).all()}


async def retry_failed(session: AsyncSession, now: datetime, job_ids: Sequence[int] | None) -> int:
    """Admin /retry: ``failed`` (and ``retry``) jobs back to the queue with fresh attempts.
    ``job_ids=None`` = all of them. Does not commit."""
    stmt = (
        update(Job)
        .where(Job.status.in_((JobStatus.FAILED, JobStatus.RETRY)))
        .values(status=JobStatus.QUEUED, attempts=0, next_retry_at=now)
    )
    if job_ids is not None:
        stmt = stmt.where(Job.id.in_(list(job_ids)))
    result = await session.execute(stmt)
    return result.rowcount or 0


async def list_sendable(session: AsyncSession) -> list[Job]:
    """Every job still waiting to be published (``queued`` / ``retry``), oldest first."""
    stmt = select(Job).where(Job.status.in_(SENDABLE)).order_by(Job.id)
    return list((await session.scalars(stmt)).all())


async def update_if_sendable(
    session: AsyncSession, job_id: int, values: dict[str, Any], *, raw_post_id: int | None
) -> bool:
    """Change a job only while it is still ``queued`` / ``retry`` and still made from
    ``raw_post_id`` (the publisher may take it, or a fuller copy take it over, meanwhile — a job
    being sent or already published is never touched). Does not commit."""
    same_post = Job.raw_post_id.is_(None) if raw_post_id is None else Job.raw_post_id == raw_post_id
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(SENDABLE), same_post)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    return (result.rowcount or 0) == 1
