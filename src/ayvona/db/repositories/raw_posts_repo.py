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


def _row(
    source_id: int, item: RawItem, fetched_at: datetime, is_backfill: bool = False
) -> dict[str, Any]:
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
        "is_backfill": is_backfill,
    }


async def insert_ignore_duplicates(
    session: AsyncSession,
    source_id: int,
    items: Sequence[RawItem],
    fetched_at: datetime,
    *,
    is_backfill: bool = False,
) -> int:
    """``INSERT ... ON CONFLICT(source_id, external_id) DO NOTHING``; returns rows inserted.

    ``is_backfill``: the posts come from the channel's history (first poll of a new source).
    Does not commit — the caller commits together with the source cursor (one transaction).
    """
    inserted = 0
    # Chunked: one multi-row INSERT per chunk keeps us far below SQLite's bound-parameter limit.
    for start in range(0, len(items), INSERT_CHUNK):
        chunk = items[start : start + INSERT_CHUNK]
        stmt = (
            sqlite_insert(RawPost)
            .values([_row(source_id, it, fetched_at, is_backfill) for it in chunk])
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


async def album_parts(session: AsyncSession, source_id: int, grouped_id: int) -> list[RawPost]:
    """Every stored part of one album (any status), in id order."""
    stmt = (
        select(RawPost)
        .where(RawPost.source_id == source_id, RawPost.grouped_id == grouped_id)
        .order_by(RawPost.id)
    )
    return list((await session.scalars(stmt)).all())


async def skip_existing_new(session: AsyncSession, fetched_up_to: datetime) -> int:
    """One-time (worker's first start): every ``new`` post fetched so far -> ``skipped_backfill``.
    Does not commit."""
    result = await session.execute(
        update(RawPost)
        .where(RawPost.status == RawPostStatus.NEW, RawPost.fetched_at <= fetched_up_to)
        .values(status=RawPostStatus.SKIPPED_BACKFILL)
    )
    return result.rowcount or 0


async def dedup_entries_since(session: AsyncSession, since: datetime) -> list[RawPost]:
    """Posts that are in the dedup index (have ``dedup_text``), posted after ``since``,
    oldest first."""
    when = func.coalesce(RawPost.posted_at, RawPost.fetched_at)
    stmt = (
        select(RawPost)
        .where(RawPost.dedup_text.is_not(None), when >= since)
        .order_by(when, RawPost.id)
    )
    return list((await session.scalars(stmt)).all())
