"""🧩 Loyihalar: the open one-time paid projects (shared by the bot and, later, the website).

Open = published and not past ``expires_at``. Newest first — the job ranking (priority tiers) does
not apply to projects.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Job, JobKind, JobStatus


def _open(now: datetime) -> list[object]:
    return [
        Job.kind == JobKind.PROJECT.value,
        Job.status == JobStatus.PUBLISHED,
        or_(Job.expires_at.is_(None), Job.expires_at > now),
    ]


async def list_open(
    session: AsyncSession, now: datetime, *, offset: int = 0, limit: int = 5
) -> tuple[list[Job], int]:
    """One page of open projects (newest first) and how many there are in total."""
    total = int(
        await session.scalar(select(func.count()).select_from(Job).where(*_open(now))) or 0  # type: ignore[arg-type]
    )
    if not total or limit <= 0:
        return [], total
    rows = await session.scalars(
        select(Job)
        .where(*_open(now))  # type: ignore[arg-type]
        .order_by(Job.published_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.all()), total
