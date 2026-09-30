"""⭐ Saved jobs (``favorites``). Shared by the bot and the future website."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Favorite, Job
from ayvona.services.jobs_public import VISIBLE, get_visible_job, is_open


class SaveResult(StrEnum):
    SAVED = "saved"
    ALREADY = "already"
    NOT_FOUND = "not_found"  # no such job, or not in the channel (yet)
    CLOSED = "closed"  # closed / expired: not saved


async def save(session: AsyncSession, user_id: int, job_id: int, now: datetime) -> SaveResult:
    """Save an open job for the user (who must exist in ``users``). Does not commit."""
    job = await get_visible_job(session, job_id)
    if job is None:
        return SaveResult.NOT_FOUND
    if not is_open(job, now):
        return SaveResult.CLOSED
    result = await session.execute(
        sqlite_insert(Favorite)
        .values(user_id=user_id, job_id=job_id, created_at=now)
        .on_conflict_do_nothing()
    )
    return SaveResult.SAVED if (result.rowcount or 0) == 1 else SaveResult.ALREADY


async def remove(session: AsyncSession, user_id: int, job_id: int) -> bool:
    """Does not commit."""
    result = await session.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.job_id == job_id)
    )
    return (result.rowcount or 0) > 0


async def is_saved(session: AsyncSession, user_id: int, job_id: int) -> bool:
    return await session.get(Favorite, (user_id, job_id)) is not None


async def list_saved(
    session: AsyncSession, user_id: int, *, offset: int = 0, limit: int = 5
) -> tuple[list[Job], int]:
    """The user's saved jobs, most recently saved first, and how many there are in total.
    Closed / expired ones stay in the list (the caller marks them)."""
    where = (Favorite.user_id == user_id, Job.status.in_(VISIBLE))
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(Favorite)
            .join(Job, Job.id == Favorite.job_id)
            .where(*where)
        )
        or 0
    )
    rows = await session.scalars(
        select(Job)
        .join(Favorite, Favorite.job_id == Job.id)
        .where(*where)
        .order_by(Favorite.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.all()), total
