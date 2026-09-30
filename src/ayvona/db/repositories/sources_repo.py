"""Queries for the ``sources`` table.

Since Bosqich 8 the DB is the source of truth (the admin manages sources from the bot).
settings.yaml only seeds: a new identifier there becomes a row; nothing else is copied back.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import SourceConfig
from ayvona.db.models import RawPost, Source, SourceAddedVia, SourceStatus

MAX_ERROR_LEN = 2000


async def sync_from_config(session: AsyncSession, configs: Sequence[SourceConfig]) -> list[Source]:
    """Seed the ``sources`` table from settings.yaml.

    * new identifier      -> row created (``added_via='yaml'``, ``enabled`` as in the YAML)
    * existing identifier -> only ``type`` / ``own_usernames`` / ``title`` (if given) are refreshed;
      ``enabled`` and ``status`` belong to the admin (paused / deleted in the bot stays so)
    * row not in the YAML -> untouched (added from the bot, or removed from the YAML on purpose)

    Does not commit. Returns the rows to poll now (see :func:`list_enabled`).
    """
    existing = {s.identifier: s for s in (await session.scalars(select(Source))).all()}
    seen: set[str] = set()
    for cfg in configs:
        if cfg.identifier in seen:
            continue
        seen.add(cfg.identifier)
        row = existing.get(cfg.identifier)
        if row is None:
            row = Source(
                identifier=cfg.identifier,
                enabled=cfg.enabled,
                status=SourceStatus.ACTIVE,
                added_via=SourceAddedVia.YAML,
            )
            session.add(row)
        row.type = cfg.type
        if cfg.title:
            row.title = cfg.title
        row.own_usernames = list(cfg.own_usernames)
    await session.flush()
    return await list_enabled(session)


async def list_enabled(session: AsyncSession) -> list[Source]:
    """Sources to poll: active and not paused."""
    result = await session.scalars(
        select(Source)
        .where(Source.enabled.is_(True), Source.status == SourceStatus.ACTIVE)
        .order_by(Source.id)
    )
    return list(result.all())


async def list_pending(session: AsyncSession) -> list[Source]:
    result = await session.scalars(
        select(Source).where(Source.status == SourceStatus.PENDING).order_by(Source.id)
    )
    return list(result.all())


async def list_visible(session: AsyncSession) -> list[Source]:
    """Everything the admin sees in /sources (not deleted), in id order."""
    result = await session.scalars(
        select(Source).where(Source.status != SourceStatus.DELETED).order_by(Source.id)
    )
    return list(result.all())


async def get(session: AsyncSession, source_id: int) -> Source | None:
    return await session.get(Source, source_id)


async def get_by_identifier(session: AsyncSession, identifier: str) -> Source | None:
    """Case-insensitive (``@Kanal`` == ``@kanal``)."""
    result = await session.scalars(
        select(Source).where(func.lower(Source.identifier) == identifier.lower())
    )
    return result.first()


async def last_post_times(session: AsyncSession) -> dict[int, datetime]:
    """Newest post per source (posted time, or fetch time if unknown)."""
    when = func.max(func.coalesce(RawPost.posted_at, RawPost.fetched_at))
    rows = (
        await session.execute(select(RawPost.source_id, when).group_by(RawPost.source_id))
    ).all()
    out: dict[int, datetime] = {}
    for source_id, value in rows:
        if value is not None:
            # func.max() bypasses the UTCDateTime column type: SQLite gives back a string.
            dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
            out[source_id] = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return out


async def mark_success(
    session: AsyncSession, source_id: int, last_seen_id: str | None, now: datetime
) -> None:
    """Record a successful poll. ``last_seen_id=None`` keeps the current cursor. Does not commit."""
    values: dict[str, object] = {
        "last_checked_at": now,
        "last_success_at": now,
        "error_count": 0,
        "last_error": None,
    }
    if last_seen_id is not None:
        values["last_seen_id"] = last_seen_id
    await session.execute(update(Source).where(Source.id == source_id).values(**values))


async def mark_error(session: AsyncSession, source_id: int, error: str, now: datetime) -> None:
    """Record a failed poll (cursor untouched). Does not commit."""
    await session.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(
            last_checked_at=now,
            error_count=Source.error_count + 1,
            last_error=error[:MAX_ERROR_LEN],
        )
    )
