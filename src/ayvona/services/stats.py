"""Numbers for the admin commands (/stats, /queue, /sources -> 📊). Read-only queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Job, JobStatus, RawPost, RawPostStatus, Source
from ayvona.db.repositories import jobs_repo, kv_repo, sources_repo
from ayvona.timeutil import to_local

NOT_ADS = (
    RawPostStatus.NOT_JOB,
    RawPostStatus.RESUME,
    RawPostStatus.CLOSED,
    RawPostStatus.OPPORTUNITY,
    RawPostStatus.NO_TEXT,
)


def day_start(now: datetime, tz: ZoneInfo) -> datetime:
    """Local midnight (Asia/Tashkent) of ``now``, as an aware datetime."""
    local = to_local(now, tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(slots=True)
class PeriodStats:
    fetched: int = 0  # raw posts collected
    published: int = 0  # jobs that reached the channel
    duplicates: int = 0
    not_ads: int = 0  # not_job, resume, closed, opportunity, no_text
    suspicious: int = 0
    no_contact: int = 0
    low_quality: int = 0
    errors: int = 0  # raw posts with a processing error
    failed: int = 0  # jobs whose publishing failed (updated in the period)
    skipped_old: int = 0  # jobs too old for the channel (publisher.max_age_hours), in the period
    categories: list[tuple[str, int]] = field(default_factory=list)  # published, most first


async def period_stats(session: AsyncSession, since: datetime) -> PeriodStats:
    st = PeriodStats()
    rows = (
        await session.execute(
            select(RawPost.status, func.count())
            .where(RawPost.fetched_at >= since)
            .group_by(RawPost.status)
        )
    ).all()
    by_status = {str(k): int(v) for k, v in rows}
    st.fetched = sum(by_status.values())
    st.duplicates = by_status.get(RawPostStatus.DUPLICATE, 0)
    st.not_ads = sum(by_status.get(s, 0) for s in NOT_ADS)
    st.suspicious = by_status.get(RawPostStatus.SUSPICIOUS, 0)
    st.no_contact = by_status.get(RawPostStatus.NO_CONTACT, 0)
    st.low_quality = by_status.get(RawPostStatus.LOW_QUALITY, 0)
    st.errors = by_status.get(RawPostStatus.ERROR, 0)
    st.published = int(
        await session.scalar(select(func.count()).select_from(Job).where(Job.published_at >= since))
        or 0
    )
    st.failed = int(
        await session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status == JobStatus.FAILED, Job.updated_at >= since)
        )
        or 0
    )
    st.skipped_old = int(
        await session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status == JobStatus.SKIPPED_OLD, Job.updated_at >= since)
        )
        or 0
    )
    cats = (
        await session.execute(
            select(Job.category, func.count())
            .where(Job.published_at >= since)
            .group_by(Job.category)
            .order_by(func.count().desc(), Job.category)
        )
    ).all()
    st.categories = [(str(c), int(n)) for c, n in cats]
    return st


@dataclass(slots=True)
class QueueOverview:
    paused: bool
    counts: dict[str, int]
    due_now: int
    upcoming: list[Job]


async def queue_overview(session: AsyncSession, now: datetime, limit: int = 10) -> QueueOverview:
    counts = await jobs_repo.count_by_status(
        session, [JobStatus.QUEUED, JobStatus.RETRY, JobStatus.SENDING, JobStatus.FAILED]
    )
    due = int(
        await session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(jobs_repo.SENDABLE))
            .where((Job.next_retry_at.is_(None)) | (Job.next_retry_at <= now))
        )
        or 0
    )
    upcoming = list(
        (
            await session.scalars(
                select(Job)
                .where(Job.status.in_([*jobs_repo.SENDABLE, JobStatus.SENDING]))
                .order_by(func.coalesce(Job.next_retry_at, Job.created_at), Job.id)
                .limit(limit)
            )
        ).all()
    )
    paused = await kv_repo.get_bool(session, kv_repo.PUBLISHER_PAUSED)
    return QueueOverview(paused, counts, due, upcoming)


async def failed_jobs(session: AsyncSession, limit: int = 20) -> list[Job]:
    return list(
        (
            await session.scalars(
                select(Job)
                .where(Job.status == JobStatus.FAILED)
                .order_by(Job.updated_at.desc(), Job.id.desc())
                .limit(limit)
            )
        ).all()
    )


@dataclass(slots=True)
class SourceStats:
    source: Source
    total: int
    week: int
    jobs: int  # became a job (done)
    duplicates: int
    not_ads: int
    last_post_at: datetime | None


async def source_stats(session: AsyncSession, source: Source, now: datetime) -> SourceStats:
    week_ago = now - timedelta(days=7)
    rows = (
        await session.execute(
            select(RawPost.status, func.count())
            .where(RawPost.source_id == source.id)
            .group_by(RawPost.status)
        )
    ).all()
    by_status = {str(k): int(v) for k, v in rows}
    week = int(
        await session.scalar(
            select(func.count())
            .select_from(RawPost)
            .where(RawPost.source_id == source.id, RawPost.fetched_at >= week_ago)
        )
        or 0
    )
    last = (await sources_repo.last_post_times(session)).get(source.id)
    return SourceStats(
        source=source,
        total=sum(by_status.values()),
        week=week,
        jobs=by_status.get(RawPostStatus.DONE, 0),
        duplicates=by_status.get(RawPostStatus.DUPLICATE, 0),
        not_ads=sum(by_status.get(s, 0) for s in NOT_ADS),
        last_post_at=last,
    )
