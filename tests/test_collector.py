"""Bosqich 3: collector reliability with a fake source and a temporary DB."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon.tl import types

from ayvona.apps import collector
from ayvona.apps.collector import (
    ActiveSource,
    advance_cursor,
    build_active_sources,
    poll_source,
    run_collector,
    run_cycle,
)
from ayvona.config import CollectorConfig, SourceConfig, load_settings
from ayvona.db.models import RawPost, RawPostStatus, Source
from ayvona.db.repositories import kv_repo, raw_posts_repo, sources_repo
from ayvona.db.session import create_engine, create_session_factory, sqlite_url
from ayvona.sources.base import FetchResult, SourceRateLimited
from ayvona.sources.registry import SourceDeps
from tests.fakes import FakeChannel, FakeSource, FakeTelethonClient

SF = async_sessionmaker[AsyncSession]

FAST = CollectorConfig(
    poll_interval_seconds=0,
    delay_between_sources_seconds=0,
    fetch_timeout_seconds=5,
    heartbeat_interval_seconds=60,
)


async def _source_row(sf: SF, identifier: str = "@kanal") -> int:
    async with sf() as s, s.begin():
        await sources_repo.sync_from_config(s, [SourceConfig(identifier=identifier)])
    async with sf() as s:
        return (await s.scalars(select(Source.id).where(Source.identifier == identifier))).one()


async def _state(sf: SF, source_id: int) -> tuple[list[str], Source]:
    async with sf() as s:
        ids = (
            await s.scalars(
                select(RawPost.external_id)
                .where(RawPost.source_id == source_id)
                .order_by(RawPost.id)
            )
        ).all()
        src = await s.get(Source, source_id)
        assert src is not None
        return list(ids), src


async def _no_sleep(_seconds: float) -> bool:
    return False


# ------------------------------------------------------------------ catch-up / dedup
async def test_catch_up_after_restart(session_factory: SF) -> None:
    """Collector off for a while -> on restart, every missed post is fetched, none twice."""
    channel = FakeChannel()
    sid = await _source_row(session_factory)
    channel.publish(3)

    # first "process run"
    await run_collector(
        session_factory,
        [ActiveSource(sid, FakeSource("@kanal", channel))],
        FAST,
        asyncio.Event(),
        max_cycles=1,
    )
    ids, src = await _state(session_factory, sid)
    assert ids == ["1", "2", "3"]
    assert src.last_seen_id == "3"

    # collector is OFF, channel keeps posting
    channel.publish(4)

    # second "process run" (brand-new source object, cursor comes only from the DB)
    fresh = FakeSource("@kanal", channel)
    await run_collector(
        session_factory, [ActiveSource(sid, fresh)], FAST, asyncio.Event(), max_cycles=2
    )
    ids, src = await _state(session_factory, sid)
    assert ids == ["1", "2", "3", "4", "5", "6", "7"]
    assert src.last_seen_id == "7"
    assert fresh.calls == ["3", "7"]
    assert fresh.closed


async def test_backlog_is_fetched_in_batches(session_factory: SF) -> None:
    channel = FakeChannel()
    channel.publish(25)
    sid = await _source_row(session_factory)
    src = FakeSource("@kanal", channel, limit=10)

    for _ in range(3):
        await poll_source(session_factory, sid, src, fetch_timeout=5)

    ids, row = await _state(session_factory, sid)
    assert ids == [str(i) for i in range(1, 26)]
    assert row.last_seen_id == "25"
    assert src.calls == [None, "10", "20"]


async def test_duplicates_are_not_written(session_factory: SF) -> None:
    """Even if a source returns the same posts again, each is stored once."""
    channel = FakeChannel()
    channel.publish(3)
    sid = await _source_row(session_factory)
    src = FakeSource("@kanal", channel, ignore_since=True)

    first = await poll_source(session_factory, sid, src, fetch_timeout=5)
    second = await poll_source(session_factory, sid, src, fetch_timeout=5)

    assert (first.inserted, second.inserted) == (3, 0)
    assert second.ok
    ids, _ = await _state(session_factory, sid)
    assert ids == ["1", "2", "3"]


async def test_new_posts_have_status_new(session_factory: SF) -> None:
    channel = FakeChannel()
    channel.publish(2)
    sid = await _source_row(session_factory)
    await poll_source(session_factory, sid, FakeSource("@kanal", channel), fetch_timeout=5)
    async with session_factory() as s:
        posts = await raw_posts_repo.list_by_status(s, RawPostStatus.NEW)
    assert [p.external_id for p in posts] == ["1", "2"]
    assert all(p.fetched_at.tzinfo is not None for p in posts)


# ------------------------------------------------------------------ atomicity
async def test_cursor_unchanged_when_insert_fails(
    session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = FakeChannel()
    channel.publish(3)
    sid = await _source_row(session_factory)
    src = FakeSource("@kanal", channel)

    real_insert = raw_posts_repo.insert_ignore_duplicates

    async def broken_insert(*args: object, **kwargs: object) -> int:
        raise RuntimeError("disk full")

    monkeypatch.setattr(raw_posts_repo, "insert_ignore_duplicates", broken_insert)
    out = await poll_source(session_factory, sid, src, fetch_timeout=5)

    assert not out.ok and "disk full" in (out.error or "")
    ids, row = await _state(session_factory, sid)
    assert ids == []
    assert row.last_seen_id is None  # cursor did NOT move
    assert row.error_count == 1

    # DB is fine again -> the same posts are fetched and stored
    monkeypatch.setattr(raw_posts_repo, "insert_ignore_duplicates", real_insert)
    out = await poll_source(session_factory, sid, src, fetch_timeout=5)
    ids, row = await _state(session_factory, sid)
    assert out.ok
    assert ids == ["1", "2", "3"]
    assert row.last_seen_id == "3"
    assert row.error_count == 0


async def test_posts_rolled_back_when_cursor_update_fails(
    session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Posts and cursor are one transaction: if the cursor update fails, the posts are not kept."""
    channel = FakeChannel()
    channel.publish(2)
    sid = await _source_row(session_factory)

    async def broken_mark_success(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(sources_repo, "mark_success", broken_mark_success)
    out = await poll_source(session_factory, sid, FakeSource("@kanal", channel), fetch_timeout=5)

    assert not out.ok
    ids, row = await _state(session_factory, sid)
    assert ids == []
    assert row.last_seen_id is None


async def test_cursor_moves_without_items(session_factory: SF) -> None:
    """First run without backfill (or only service messages): cursor advances, nothing stored."""
    sid = await _source_row(session_factory)

    class OnlyCursor(FakeSource):
        async def fetch_new(self, since: str | None) -> FetchResult:
            return FetchResult(items=[], cursor="500")

    out = await poll_source(
        session_factory, sid, OnlyCursor("@kanal", FakeChannel()), fetch_timeout=5
    )
    ids, row = await _state(session_factory, sid)
    assert out.ok and ids == [] and row.last_seen_id == "500"


def test_advance_cursor_never_goes_backwards() -> None:
    assert advance_cursor(None, "5") == "5"
    assert advance_cursor("5", "9") == "9"
    assert advance_cursor("5", "5") is None
    assert advance_cursor("9", "5") is None
    assert advance_cursor("9", None) is None
    assert (
        advance_cursor("https://a/1", "https://a/2") == "https://a/2"
    )  # non-numeric: trust source


async def test_db_read_failure_is_contained(
    session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = FakeChannel()
    channel.publish(1)
    sid = await _source_row(session_factory)
    src = FakeSource("@kanal", channel)

    async def locked(*args: object, **kwargs: object) -> None:
        raise RuntimeError("database is locked")

    monkeypatch.setattr(sources_repo, "get", locked)
    out = await poll_source(session_factory, sid, src, fetch_timeout=5)

    assert out.error is not None and "locked" in out.error
    assert src.calls == []  # never fetched with an unknown cursor


# ------------------------------------------------------------------ errors don't spread
async def test_one_failing_source_does_not_stop_others(session_factory: SF) -> None:
    ch_bad, ch_good = FakeChannel(), FakeChannel()
    ch_bad.publish(2)
    ch_good.publish(2)
    bad_id = await _source_row(session_factory, "@bad")
    good_id = await _source_row(session_factory, "@good")
    bad = FakeSource("@bad", ch_bad)
    bad.fail_with.append(ConnectionError("network down"))

    outcomes = await run_cycle(
        session_factory,
        [ActiveSource(bad_id, bad), ActiveSource(good_id, FakeSource("@good", ch_good))],
        FAST,
        _no_sleep,
    )

    assert [o.ok for o in outcomes] == [False, True]
    bad_ids, bad_row = await _state(session_factory, bad_id)
    good_ids, _ = await _state(session_factory, good_id)
    assert bad_ids == [] and good_ids == ["1", "2"]
    assert bad_row.error_count == 1
    assert "network down" in (bad_row.last_error or "")


async def test_rate_limit_waits_as_asked(session_factory: SF) -> None:
    ch1, ch2 = FakeChannel(), FakeChannel()
    ch2.publish(1)
    id1 = await _source_row(session_factory, "@a")
    id2 = await _source_row(session_factory, "@b")
    limited = FakeSource("@a", ch1)
    limited.fail_with.append(SourceRateLimited(30))
    slept: list[float] = []

    async def record_sleep(seconds: float) -> bool:
        slept.append(seconds)
        return False

    outcomes = await run_cycle(
        session_factory,
        [ActiveSource(id1, limited), ActiveSource(id2, FakeSource("@b", ch2))],
        FAST,
        record_sleep,
    )

    assert outcomes[0].rate_limited_for == 30
    assert slept == [31]  # 30 s asked + 1 s margin (no delay after the last source)
    assert outcomes[1].inserted == 1


async def test_hanging_source_times_out(session_factory: SF) -> None:
    sid = await _source_row(session_factory)
    src = FakeSource("@kanal", FakeChannel())
    src.hang = True

    out = await poll_source(session_factory, sid, src, fetch_timeout=0.05)

    assert out.error is not None and "timeout" in out.error
    _, row = await _state(session_factory, sid)
    assert row.error_count == 1


# ------------------------------------------------------------------ loop / heartbeat / stop
async def test_heartbeat_and_last_cycle_written(session_factory: SF) -> None:
    await run_collector(session_factory, [], FAST, asyncio.Event(), max_cycles=1)
    async with session_factory() as s:
        assert await kv_repo.read_heartbeat(s, "collector") is not None
        assert await kv_repo.get(s, collector.LAST_CYCLE_KEY) is not None


async def test_stop_event_interrupts_long_sleep(session_factory: SF) -> None:
    cfg = FAST.model_copy(update={"poll_interval_seconds": 3600})
    stop = asyncio.Event()
    task = asyncio.create_task(run_collector(session_factory, [], cfg, stop))
    await asyncio.sleep(0.2)
    started = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert time.monotonic() - started < 2


async def test_build_active_sources_from_settings(session_factory: SF, tmp_path: Path) -> None:
    (tmp_path / "settings.yaml").write_text(
        "sources:\n  - identifier: '@ish'\n  - identifier: '@off'\n    enabled: false\n",
        encoding="utf-8",
    )
    settings = load_settings(tmp_path, env_file=None)
    deps = SourceDeps(collector=settings.app.collector, telegram_client=object())

    active = await build_active_sources(session_factory, settings, deps)

    assert [a.source.identifier for a in active] == ["@ish"]
    assert type(active[0].source).__name__ == "TelegramSource"


async def test_source_that_cannot_be_built_is_recorded(session_factory: SF, tmp_path: Path) -> None:
    (tmp_path / "settings.yaml").write_text("sources:\n  - identifier: '@ish'\n", encoding="utf-8")
    settings = load_settings(tmp_path, env_file=None)
    deps = SourceDeps(collector=settings.app.collector, telegram_client=None)  # not connected

    active = await build_active_sources(session_factory, settings, deps)

    assert active == []
    async with session_factory() as s:
        row = (await s.scalars(select(Source))).one()
    assert row.error_count == 1 and "not connected" in (row.last_error or "")


# ------------------------------------------------------------------ whole process, fake Telegram
async def test_main_end_to_end_with_fake_telegram(
    db_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """settings.yaml -> sources table -> TelegramSource (fake client) -> raw_posts, via main()."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text(
        "sources:\n  - identifier: 't.me/ish_kanal'\ncollector:\n  initial_backfill: 2\n",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text(f"DB_PATH={db_file.as_posix()}\n", encoding="utf-8")
    settings = load_settings(cfg_dir, env_file=env)

    date = datetime(2026, 9, 29, tzinfo=UTC)
    client = FakeTelethonClient(
        [
            types.Message(id=i, peer_id=types.PeerChannel(1), date=date, message=f"post {i}")
            for i in range(1, 6)
        ]
    )

    async def fake_connect(_settings: object) -> FakeTelethonClient:
        return client

    monkeypatch.setattr(collector, "get_settings", lambda: settings)
    monkeypatch.setattr(collector, "connect_client", fake_connect)
    try:
        rc = await collector.main(once=True)
    finally:
        logger.remove()  # release the log file in tmp_path

    assert rc == 0
    assert client.resolved == ["@ish_kanal"]
    assert getattr(client, "disconnected", False)
    engine = create_engine(sqlite_url(db_file))
    try:
        sf = create_session_factory(engine)
        async with sf() as s:
            src = (await s.scalars(select(Source))).one()
            ids, _ = await _state(sf, src.id)
        assert ids == ["4", "5"]  # initial_backfill: 2
        assert src.last_seen_id == "5"
    finally:
        await engine.dispose()
