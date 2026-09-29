"""Tiny key/value store (``kv_store`` table): flags, cached values, heartbeats."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import KVStore
from ayvona.timeutil import ensure_utc, utcnow

HEARTBEAT_PREFIX = "heartbeat:"


async def get(session: AsyncSession, key: str) -> str | None:
    row = await session.get(KVStore, key)
    return row.value if row else None


async def set_value(session: AsyncSession, key: str, value: str | None) -> None:
    """Upsert. Does not commit."""
    now = utcnow()
    stmt = sqlite_insert(KVStore).values(key=key, value=value, updated_at=now)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value, "updated_at": now}
    )
    await session.execute(stmt)


async def write_heartbeat(session: AsyncSession, process: str, now: datetime | None = None) -> None:
    """``heartbeat:<process>`` = ISO-8601 UTC time. Does not commit."""
    await set_value(session, HEARTBEAT_PREFIX + process, ensure_utc(now or utcnow()).isoformat())


async def read_heartbeat(session: AsyncSession, process: str) -> datetime | None:
    raw = await get(session, HEARTBEAT_PREFIX + process)
    return datetime.fromisoformat(raw) if raw else None
