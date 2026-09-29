"""Queries for the ``raw_posts`` table."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import RawPost, RawPostStatus
from ayvona.sources.base import RawItem

INSERT_CHUNK = 200


def _row(source_id: int, item: RawItem, fetched_at: datetime) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "external_id": item.external_id,
        "grouped_id": item.grouped_id,
        "text": item.text,
        "has_media": item.has_media,
        "media_type": item.media_type,
        "extra": item.extra,
        "posted_at": item.posted_at,
        "fetched_at": fetched_at,
        "status": RawPostStatus.NEW,
    }


async def insert_ignore_duplicates(
    session: AsyncSession, source_id: int, items: Sequence[RawItem], fetched_at: datetime
) -> int:
    """``INSERT ... ON CONFLICT(source_id, external_id) DO NOTHING``; returns rows inserted.

    Does not commit — the caller commits together with the source cursor (one transaction).
    """
    inserted = 0
    # Chunked: one multi-row INSERT per chunk keeps us far below SQLite's bound-parameter limit.
    for start in range(0, len(items), INSERT_CHUNK):
        chunk = items[start : start + INSERT_CHUNK]
        stmt = (
            sqlite_insert(RawPost)
            .values([_row(source_id, it, fetched_at) for it in chunk])
            .on_conflict_do_nothing(index_elements=["source_id", "external_id"])
            .returning(RawPost.id)
        )
        result = await session.execute(stmt)
        inserted += len(result.all())
    return inserted


async def count(session: AsyncSession, source_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(RawPost)
    if source_id is not None:
        stmt = stmt.where(RawPost.source_id == source_id)
    return int(await session.scalar(stmt) or 0)


async def list_by_status(
    session: AsyncSession,
    status: RawPostStatus,
    *,
    fetched_before: datetime | None = None,
    limit: int = 100,
) -> list[RawPost]:
    """Oldest first. ``fetched_before`` lets the worker wait until album parts have all arrived."""
    stmt = select(RawPost).where(RawPost.status == status)
    if fetched_before is not None:
        stmt = stmt.where(RawPost.fetched_at < fetched_before)
    stmt = stmt.order_by(RawPost.id).limit(limit)
    return list((await session.scalars(stmt)).all())


async def set_status(
    session: AsyncSession,
    ids: Iterable[int],
    status: RawPostStatus,
    error: str | None = None,
) -> None:
    """Move posts to ``status``. Does not commit."""
    id_list = list(ids)
    if id_list:
        await session.execute(
            update(RawPost).where(RawPost.id.in_(id_list)).values(status=status, error=error)
        )


async def reset_stuck_processing(session: AsyncSession) -> int:
    """On worker start: posts left in ``processing`` by a crash go back to ``new``. No commit."""
    result = await session.execute(
        update(RawPost)
        .where(RawPost.status == RawPostStatus.PROCESSING)
        .values(status=RawPostStatus.NEW)
    )
    return result.rowcount or 0
