"""apps/worker.py end to end (mocked Bot API), missing-token behaviour, botapi, notifier."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import SendMessage, SendPhoto
from loguru import logger

from ayvona.apps.worker import _setup_bot, run_worker
from ayvona.botapi import NO_TOKEN, BotConfigError, create_bot, parse_chat_id
from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.db.models import JobStatus, RawPostStatus
from ayvona.db.repositories import kv_repo
from ayvona.services.notifier import Notifier
from tests.fake_bot import ADMIN_CHAT, CHANNEL, make_bot
from tests.worker_helpers import (
    JOB_TEXT_FULL,
    SF,
    add_raw,
    add_source,
    get_job,
    get_raw,
    make_image,
    make_settings,
)


@pytest.fixture
def logs() -> list[str]:
    messages: list[str] = []
    handler = logger.add(lambda m: messages.append(str(m)), level="INFO")
    yield messages
    logger.remove(handler)


async def test_worker_once_processes_and_publishes(session_factory: SF, tmp_path: Path) -> None:
    make_image(tmp_path / "img", "boshqa/1.jpg")
    settings = make_settings(tmp_path / "img", publisher={"hold_minutes": 0})
    src = await add_source(session_factory)
    old = await add_raw(session_factory, src, JOB_TEXT_FULL)
    bot, session = make_bot()

    stop = asyncio.Event()
    await run_worker(settings, session_factory, stop, bot=bot, channel=CHANNEL, once=True)
    # step 0: the post was in the DB before the first start -> never published
    assert (await get_raw(session_factory, old)).status is RawPostStatus.SKIPPED_BACKFILL
    assert session.requests == []

    fresh = await add_raw(session_factory, src, JOB_TEXT_FULL + "\nIsh vaqti: 9:00-18:00")
    await run_worker(settings, session_factory, stop, bot=bot, channel=CHANNEL, once=True)
    row = await get_raw(session_factory, fresh)
    assert row.status is RawPostStatus.DONE
    job = await get_job(session_factory, row.job_id)  # type: ignore[arg-type]
    assert job.status is JobStatus.PUBLISHED
    [photo] = session.sent(SendPhoto)
    assert photo.chat_id == CHANNEL
    async with session_factory() as s:
        assert await kv_repo.read_heartbeat(s, "worker") is not None


async def test_worker_without_token_queues_and_sends_nothing(
    session_factory: SF, logs: list[str]
) -> None:
    settings = make_settings(publisher={"hold_minutes": 0})
    src = await add_source(session_factory)
    stop = asyncio.Event()
    await run_worker(settings, session_factory, stop, once=True)  # first start (step 0)
    fresh = await add_raw(session_factory, src, JOB_TEXT_FULL)

    await run_worker(settings, session_factory, stop, bot=None, channel=None, once=True)
    row = await get_raw(session_factory, fresh)
    assert row.status is RawPostStatus.DONE
    assert (await get_job(session_factory, row.job_id)).status is JobStatus.QUEUED  # type: ignore[arg-type]
    assert any("Kanalga joylash O'CHIQ" in m and "BOT_TOKEN yo'q" in m for m in logs)


async def test_worker_loop_stops_cleanly(session_factory: SF) -> None:
    settings = make_settings(poll_interval_seconds=0.05, heartbeat_interval_seconds=0.05)
    bot, session = make_bot()
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_worker(settings, session_factory, stop, bot=bot, channel=CHANNEL)
    )
    await asyncio.sleep(0.3)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    async with session_factory() as s:
        assert await kv_repo.read_heartbeat(s, "worker") is not None
    assert session.requests == []


async def test_setup_bot_without_token_is_none(logs: list[str]) -> None:
    settings = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    assert settings.env.bot_token is None
    assert await _setup_bot(settings) is None
    assert any("BOT_TOKEN .env faylida yo'q" in m for m in logs)


# ------------------------------------------------------------------ botapi
def test_create_bot_explains_missing_and_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(BotConfigError, match="BOT_TOKEN .env faylida yo'q"):
        create_bot(load_settings(DEFAULT_CONFIG_DIR, env_file=None))
    assert "@BotFather" in NO_TOKEN
    monkeypatch.setenv("BOT_TOKEN", "not-a-token")
    with pytest.raises(BotConfigError, match="noto'g'ri"):
        create_bot(load_settings(DEFAULT_CONFIG_DIR, env_file=None))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-1001234567890", -1001234567890),
        ("@ayvona_test", "@ayvona_test"),
        ("ayvona_test", "@ayvona_test"),
        ("https://t.me/ayvona_test", "@ayvona_test"),
        ("  ", None),
        (None, None),
    ],
)
def test_parse_chat_id(value, expected) -> None:
    assert parse_chat_id(value) == expected


# ------------------------------------------------------------------ notifier
async def test_notifier_sends_the_same_notice_once_per_10_minutes(session_factory: SF) -> None:
    bot, session = make_bot()
    n = Notifier(bot, ADMIN_CHAT, session_factory)
    assert await n.send("❌ xato A")
    assert not await n.send("❌ xato A")  # throttled (kept in kv_store)
    assert await n.send("❌ xato B")
    assert await Notifier(bot, ADMIN_CHAT, session_factory).send("❌ xato A") is False  # restart
    sent = session.sent(SendMessage)
    assert [m.text for m in sent] == ["❌ xato A", "❌ xato B"]
    assert sent[0].chat_id == ADMIN_CHAT and sent[0].link_preview_options.is_disabled


async def test_notifier_throttle_expires(session_factory: SF) -> None:
    bot, session = make_bot()
    n = Notifier(bot, ADMIN_CHAT, session_factory, throttle_seconds=0)
    assert await n.send("x") and await n.send("x")
    assert len(session.requests) == 2


async def test_notifier_without_bot_only_logs(logs: list[str]) -> None:
    n = Notifier(None, None)
    assert await n.send("⚠️ salom") is False
    assert any("yuborilmadi" in m and "salom" in m for m in logs)


async def test_notifier_never_raises(session_factory: SF) -> None:
    bot, session = make_bot()
    session.network_error()
    n = Notifier(bot, ADMIN_CHAT, session_factory)
    assert await n.send("x") is False
    assert await n.send("x") is True  # a failed send is not remembered


def test_hold_window_default_is_20_minutes() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    assert s.app.publisher.hold_minutes == 20
    assert s.app.publisher.publish_backfill is False
    assert timedelta(minutes=s.app.publisher.hold_minutes) == timedelta(minutes=20)
