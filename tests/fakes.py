"""Test doubles: a fake source ("channel" in memory) and a fake Telethon client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, ClassVar

from ayvona.sources.base import BaseSource, FetchResult, RawItem
from ayvona.timeutil import utcnow


def make_item(n: int, text: str | None = None) -> RawItem:
    return RawItem(
        external_id=str(n),
        text=text if text is not None else f"Vakansiya #{n}: sotuvchi kerak. Tel: +998901234567",
        has_media=False,
        posted_at=utcnow() - timedelta(minutes=100 - n),
    )


class FakeChannel:
    """An in-memory channel whose posts get ids 1, 2, 3..."""

    def __init__(self) -> None:
        self.posts: list[RawItem] = []

    def publish(self, count: int = 1) -> None:
        start = len(self.posts) + 1
        self.posts.extend(make_item(n) for n in range(start, start + count))


class FakeSource(BaseSource):
    """Behaves like TelegramSource: returns posts with id > since, oldest first, max ``limit``."""

    type: ClassVar[str] = "fake"

    def __init__(
        self,
        identifier: str,
        channel: FakeChannel,
        *,
        limit: int = 100,
        ignore_since: bool = False,
    ) -> None:
        super().__init__(identifier)
        self.channel = channel
        self.limit = limit
        self.ignore_since = ignore_since
        self.calls: list[str | None] = []
        self.fail_with: list[BaseException] = []  # raised (and consumed) one per call
        self.hang = False
        self.closed = False

    async def fetch_new(self, since: str | None) -> FetchResult:
        self.calls.append(since)
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail_with:
            raise self.fail_with.pop(0)
        after = 0 if (since is None or self.ignore_since) else int(since)
        new = [p for p in self.channel.posts if int(p.external_id) > after][: self.limit]
        return FetchResult(items=new, cursor=new[-1].external_id if new else None)

    async def close(self) -> None:
        self.closed = True


class FakeTelethonClient:
    """Implements the tiny part of ``TelegramClient`` that ``TelegramSource`` uses."""

    def __init__(self, messages: list[Any] | None = None) -> None:
        self.messages: list[Any] = sorted(messages or [], key=lambda m: m.id)
        self.resolved: list[Any] = []
        self.raise_on_fetch: BaseException | None = None
        self.iter_calls: list[dict[str, Any]] = []

    async def get_me(self) -> Any:
        return type("Me", (), {"id": 1, "username": "test_reader"})()

    async def disconnect(self) -> None:
        self.disconnected = True

    async def get_entity(self, identifier: Any) -> str:
        self.resolved.append(identifier)
        return f"entity:{identifier}"

    async def get_messages(self, entity: Any, limit: int = 1) -> list[Any]:
        if self.raise_on_fetch:
            raise self.raise_on_fetch
        return list(reversed(self.messages))[:limit]  # newest first, like Telethon

    async def iter_messages(
        self, entity: Any, limit: int | None = None, *, min_id: int = 0, reverse: bool = False
    ) -> AsyncIterator[Any]:
        self.iter_calls.append({"min_id": min_id, "reverse": reverse, "limit": limit})
        if self.raise_on_fetch:
            raise self.raise_on_fetch
        selected = [m for m in self.messages if m.id > min_id]
        if not reverse:
            selected.reverse()
        for m in selected[:limit] if limit else selected:
            yield m
