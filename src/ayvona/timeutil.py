"""Time helpers. Rule: store UTC, display in Asia/Tashkent."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Timezone-aware current time in UTC."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC; convert aware ones to UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_local(dt: datetime, tz: ZoneInfo | str = "Asia/Tashkent") -> datetime:
    """Convert a (UTC) datetime to the display timezone."""
    zone = ZoneInfo(tz) if isinstance(tz, str) else tz
    return ensure_utc(dt).astimezone(zone)
