"""Custom column types."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Dialect, Enum
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC in the DB, always returns timezone-aware UTC ``datetime``.

    SQLite has no timezone support; without this, values would come back naive and comparisons
    with ``utcnow()`` would fail.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to UTCDateTime; use timeutil.utcnow()")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def str_enum(enum_cls: type[StrEnum], length: int = 32) -> Enum:
    """Store a ``StrEnum`` by its *value* (e.g. ``"new"``) as plain VARCHAR.

    No DB-level CHECK constraint on purpose: adding a status later would otherwise need a
    table-rebuilding migration in SQLite. Python still rejects unknown values.
    """
    return Enum(
        enum_cls,
        values_callable=lambda cls: [m.value for m in cls],
        native_enum=False,
        create_constraint=False,
        length=length,
        validate_strings=True,
    )
