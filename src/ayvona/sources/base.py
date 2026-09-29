"""Source interface. Every source (Telegram channel, website...) implements :class:`BaseSource`.

The collector only knows this interface, so adding a website never changes the pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class RawItem:
    """One post exactly as the source gave it (before any processing)."""

    external_id: str
    text: str
    has_media: bool
    posted_at: datetime | None
    grouped_id: int | None = None
    media_type: str | None = None
    # Data not visible in plain text that later stages need: hidden links, URL buttons, ...
    extra: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class FetchResult:
    """What one poll returned.

    ``cursor`` is the new ``sources.last_seen_id`` to store *after* ``items`` are committed.
    It can move forward even with no items (skipped service messages, first run without backfill).
    ``None`` means "keep the old cursor".
    """

    items: list[RawItem] = field(default_factory=list)
    cursor: str | None = None


class SourceError(Exception):
    """A source failed in an expected way (network, access, parsing). Collector logs, continues."""


class SourceRateLimited(SourceError):
    """The remote side asked us to wait (Telegram FloodWait, HTTP 429)."""

    def __init__(self, seconds: float, message: str = "") -> None:
        super().__init__(message or f"rate limited, wait {seconds:.0f}s")
        self.seconds = seconds


class BaseSource(ABC):
    """A pollable source of raw posts."""

    type: ClassVar[str]

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier

    @abstractmethod
    async def fetch_new(self, since: str | None) -> FetchResult:
        """Return posts newer than cursor ``since`` (oldest first).

        ``since=None`` means the source was never polled; the implementation decides how much
        history to take (see ``collector.initial_backfill``).
        Raise :class:`SourceRateLimited` when asked to slow down, any other exception on failure.
        Must not write to the DB.
        """

    async def close(self) -> None:  # noqa: B027 — optional hook, default no-op
        """Release resources (optional)."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.identifier}>"
