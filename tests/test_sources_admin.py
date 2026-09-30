"""Sources managed from the bot: parsing /addsource, the collector checking pending channels
(fake Telethon), and the collector re-reading the sources table every cycle."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from telethon import errors

from ayvona.apps.collector import SourcePool, run_collector
from ayvona.config import CollectorConfig
from ayvona.db.models import Source, SourceAddedVia, SourceStatus
from ayvona.services.sources_admin import (
    SourceKind,
    check_telegram_source,
    parse_source_input,
    process_pending,
)
from ayvona.sources.registry import SourceDeps
from tests.fakes import FakeChannel, FakeSource
from tests.worker_helpers import SF, RecordingNotifier, add_source


@pytest.mark.parametrize(
    ("text", "kind", "ident"),
    [
        ("@Ish_Kanal", SourceKind.TELEGRAM, "@Ish_Kanal"),
        ("ish_kanal", SourceKind.TELEGRAM, "@ish_kanal"),
        ("https://t.me/ish_kanal", SourceKind.TELEGRAM, "@ish_kanal"),
        ("t.me/s/ish_kanal/", SourceKind.TELEGRAM, "@ish_kanal"),
        ("https://t.me/+AbCdEf123456", SourceKind.INVITE, "+AbCdEf123456"),
        ("t.me/joinchat/AbCdEf123456", SourceKind.INVITE, "+AbCdEf123456"),
        ("web:HH_UZ", SourceKind.WEB, "web:hh_uz"),
        ("rss:https://sayt.uz/feed", SourceKind.RSS, "rss:https://sayt.uz/feed"),
    ],
)
def test_parse_source_input(text: str, kind: SourceKind, ident: str) -> None:
    parsed = parse_source_input(text)
    assert parsed is not None and (parsed.kind, parsed.identifier) == (kind, ident)


@pytest.mark.parametrize("text", ["", "salom dunyo", "@ab", "https://google.com", "web:"])
def test_parse_source_input_rejects(text: str) -> None:
    assert parse_source_input(text) is None


# ------------------------------------------------------------------ fake Telethon
class FakeClient:
    def __init__(self, entities: dict[str, Any], error: Exception | None = None) -> None:
        self.entities = entities
        self.error = error
        self.calls: list[Any] = []

    async def get_entity(self, ident: Any) -> Any:
        self.calls.append(ident)
        if self.error:
            raise self.error
        if ident not in self.entities:
            raise ValueError(f'No user has "{ident}" as username')
        return self.entities[ident]

    async def get_messages(self, entity: Any, limit: int = 1) -> list[Any]:
        return [SimpleNamespace(id=777)]

    async def __call__(self, request: Any) -> Any:  # invite requests
        self.calls.append(type(request).__name__)
        if self.error:
            raise self.error
        chat = self.entities["+invite"]
        if type(request).__name__ == "CheckChatInviteRequest":
            return SimpleNamespace()  # not a member yet
        return SimpleNamespace(chats=[chat])


def channel(username: str | None, cid: int = 555, title: str = "Ish kanali") -> Any:
    return SimpleNamespace(id=cid, username=username, title=title, megagroup=False)


async def test_check_public_channel() -> None:
    client = FakeClient({"@ish_kanal": channel("Ish_Kanal")})
    res = await check_telegram_source(client, "@ish_kanal")
    assert res.ok and res.identifier == "@Ish_Kanal" and res.last_post_id == 777


async def test_check_private_channel_joins_by_invite() -> None:
    client = FakeClient({"+invite": channel(None, cid=987)})
    res = await check_telegram_source(client, "+invite")
    assert res.ok and res.identifier == "-100987"
    assert client.calls == ["CheckChatInviteRequest", "ImportChatInviteRequest"]


@pytest.mark.parametrize(
    ("entities", "error", "text", "retry"),
    [
        ({}, None, "topilmadi", False),
        ({"@x_user": SimpleNamespace(id=1, username="x_user")}, None, "kanal emas", False),
        ({}, errors.FloodWaitError(request=None, capture=30), "kutishni", True),
        ({}, ConnectionError("down"), "tarmoq", True),
    ],
)
async def test_check_failures(entities, error, text: str, retry: bool) -> None:
    ident = "@x_user" if entities else "@yoq_kanal"
    res = await check_telegram_source(FakeClient(entities, error), ident)
    assert not res.ok and text in (res.error or "") and res.retry_later is retry


async def _pending(sf: SF, ident: str, by: int = 111) -> int:
    async with sf() as s, s.begin():
        src = Source(
            identifier=ident,
            status=SourceStatus.PENDING,
            enabled=False,
            added_via=SourceAddedVia.BOT,
            added_by=by,
            backfill_request=5,
        )
        s.add(src)
        await s.flush()
        return src.id


async def test_process_pending_activates_and_tells_the_admin(session_factory: SF) -> None:
    ok = await _pending(session_factory, "@ish_kanal")
    bad = await _pending(session_factory, "@yoq_kanal")
    notifier = RecordingNotifier()
    client = FakeClient({"@ish_kanal": channel("ish_kanal")})
    assert await process_pending(session_factory, client, notifier) == 2  # type: ignore[arg-type]
    async with session_factory() as s:
        a, b = await s.get(Source, ok), await s.get(Source, bad)
    assert a.status is SourceStatus.ACTIVE and a.enabled and a.title == "Ish kanali"  # type: ignore[union-attr]
    assert b.status is SourceStatus.REJECTED and "topilmadi" in (b.last_error or "")  # type: ignore[union-attr]
    assert notifier.targets == [111, 111]
    assert "Qo'shildi" in notifier.messages[0] and "5 tasi" in notifier.messages[0]
    assert "Qo'shilmadi" in notifier.messages[1]


async def test_pending_duplicate_of_a_known_channel_reenables_it(session_factory: SF) -> None:
    known = await add_source(session_factory, "@ish_kanal")
    async with session_factory() as s, s.begin():
        (await s.get(Source, known)).enabled = False  # type: ignore[union-attr]
    pending = await _pending(session_factory, "+invite")
    client = FakeClient({"+invite": channel("ish_kanal")})
    await process_pending(session_factory, client, RecordingNotifier())  # type: ignore[arg-type]
    async with session_factory() as s:
        assert (await s.get(Source, known)).enabled is True  # type: ignore[union-attr]
        assert (await s.get(Source, pending)).status is SourceStatus.REJECTED  # type: ignore[union-attr]


async def test_temporary_problem_keeps_it_pending(session_factory: SF) -> None:
    pid = await _pending(session_factory, "@ish_kanal")
    client = FakeClient({}, ConnectionError("down"))
    assert await process_pending(session_factory, client, None) == 0
    async with session_factory() as s:
        assert (await s.get(Source, pid)).status is SourceStatus.PENDING  # type: ignore[union-attr]


# ------------------------------------------------------------------ collector re-reads the DB
async def test_source_pool_follows_the_db(
    session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    channels: dict[str, FakeChannel] = {}

    def fake_create(row: Source, deps: SourceDeps) -> FakeSource:
        return FakeSource(row.identifier, channels.setdefault(row.identifier, FakeChannel()))

    monkeypatch.setattr("ayvona.apps.collector.create_source", fake_create)
    pool = SourcePool(session_factory, SourceDeps(collector=CollectorConfig()))
    a = await add_source(session_factory, "@a")
    assert [x.source.identifier for x in await pool.refresh()] == ["@a"]

    b = await add_source(session_factory, "@b")  # added from the bot, no restart
    first = await pool.refresh()
    assert [x.source.identifier for x in first] == ["@a", "@b"]

    async with session_factory() as s, s.begin():
        (await s.get(Source, a)).enabled = False  # type: ignore[union-attr]  # paused
    second = await pool.refresh()
    assert [x.source.identifier for x in second] == ["@b"]
    assert first[0].source.closed  # type: ignore[attr-defined]
    assert second[0] is first[1]  # the running one is kept, not rebuilt
    assert b


async def test_collector_checks_pending_before_each_cycle(session_factory: SF) -> None:
    calls: list[int] = []

    async def before() -> None:
        calls.append(1)

    pool = SourcePool(session_factory, SourceDeps(collector=CollectorConfig()))
    cfg = CollectorConfig(poll_interval_seconds=0, heartbeat_interval_seconds=60)
    await run_collector(
        session_factory, pool, cfg, asyncio.Event(), max_cycles=2, before_cycle=before
    )
    assert calls == [1, 1]
