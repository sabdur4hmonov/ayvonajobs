"""Queries for the ``sources`` table."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import SourceConfig
from ayvona.db.models import Source, SourceType

MAX_ERROR_LEN = 2000


def _source_type(value: str) -> SourceType:
    """``"web:hh_uz"`` -> ``SourceType.WEB``; ``"telegram"`` -> ``SourceType.TELEGRAM``."""
    return SourceType(value.split(":", 1)[0])


async def sync_from_config(session: AsyncSession, configs: Sequence[SourceConfig]) -> list[Source]:
    """Make the ``sources`` table match settings.yaml.

    * new identifier       -> row created
    * existing identifier  -> title / enabled / own_usernames / type updated (cursor kept!)
    * row not in config    -> ``enabled=False`` (never deleted: raw_posts reference it)

    Does not commit. Returns all rows that are enabled after the sync.
    """
    existing = {s.identifier: s for s in (await session.scalars(select(Source))).all()}
    seen: set[str] = set()
    for cfg in configs:
        if cfg.identifier in seen:
            continue
        seen.add(cfg.identifier)
        row = existing.get(cfg.identifier)
        if row is None:
            row = Source(identifier=cfg.identifier)
            session.add(row)
        row.type = _source_type(cfg.type)
        row.title = cfg.title
        row.enabled = cfg.enabled
        row.own_usernames = list(cfg.own_usernames)
    for identifier, row in existing.items():
        if identifier not in seen:
            row.enabled = False
    await session.flush()
    return await list_enabled(session)


async def list_enabled(session: AsyncSession) -> list[Source]:
    result = await session.scalars(
        select(Source).where(Source.enabled.is_(True)).order_by(Source.id)
    )
    return list(result.all())


async def get(session: AsyncSession, source_id: int) -> Source | None:
    return await session.get(Source, source_id)


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
