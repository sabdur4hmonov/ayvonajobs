"""publisher/outbox.py with a mocked Bot API (tests/fake_bot.py): nothing leaves the machine.

Covers ROADMAP Bosqich 7 step 2: photo + caption + buttons, file_id cache, link preview off,
flood wait, network backoff, HTML fallback, bad setup, attempts limit, pause, crash recovery.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import FSInputFile
from sqlalchemy import select

from ayvona.db.models import Image, JobStatus
from ayvona.db.repositories import kv_repo
from ayvona.publisher.outbox import (
    ChannelSender,
    Outcome,
    Publisher,
    backoff_seconds,
    keyboard,
    plain_text,
)
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, FakeBotSession, make_bot
from tests.worker_helpers import (
    SF,
    RecordingNotifier,
    add_job,
    get_job,
    make_image,
    make_settings,
)


@pytest.fixture
def images(tmp_path: Path) -> Path:
    root = tmp_path / "images"
    make_image(root, "boshqa/1.jpg")
    return root


def publisher(
    sf: SF, images: Path | None = None, **publisher_cfg
) -> tuple[Publisher, FakeBotSession, RecordingNotifier]:
    bot, session = make_bot()
    notifier = RecordingNotifier()
    settings = make_settings(images, publisher=publisher_cfg)
    pub = Publisher(settings, sf, ChannelSender(bot, CHANNEL), notifier)  # type: ignore[arg-type]
    return pub, session, notifier


# ------------------------------------------------------------------ happy path
async def test_publishes_photo_caption_and_buttons(session_factory: SF, images: Path) -> None:
    job_id = await add_job(session_factory)
    pub, session, _ = publisher(session_factory, images)

    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id
    [req] = session.sent(SendPhoto)
    assert req.chat_id == CHANNEL
    assert isinstance(req.photo, FSInputFile)  # first time: the file is uploaded
    assert req.parse_mode == "HTML" and req.caption.startswith("💼 <b>Sotuvchi</b>")
    assert req.reply_markup.inline_keyboard[0][0].url.endswith("start=save_1")

    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.PUBLISHED
    assert job.channel_message_id is not None and job.published_at is not None

    # the uploaded picture's file_id is cached and reused for the next post
    async with session_factory() as s:
        img = (await s.scalars(select(Image))).one()
    assert img.telegram_file_id == "PHOTO_ID_1" and img.times_used == 1
    await add_job(session_factory)
    await pub.publish_next()
    second = session.sent(SendPhoto)[1]
    assert second.photo == "PHOTO_ID_1"


async def test_without_a_picture_sends_text_with_preview_off(session_factory: SF) -> None:
    await add_job(session_factory)
    pub, session, _ = publisher(session_factory, None)
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED
    [req] = session.sent(SendMessage)
    assert req.link_preview_options.is_disabled is True
    assert req.parse_mode == "HTML"


async def test_job_in_collecting_window_waits(session_factory: SF, images: Path) -> None:
    job_id = await add_job(session_factory, next_retry_at=utcnow() + timedelta(minutes=10))
    pub, session, _ = publisher(session_factory, images)
    assert (await pub.publish_next()).outcome is Outcome.IDLE
    assert session.requests == []
    res = await pub.publish_next(utcnow() + timedelta(minutes=11))
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id


async def test_oldest_due_job_goes_first(session_factory: SF) -> None:
    late = await add_job(session_factory, next_retry_at=utcnow() - timedelta(minutes=1))
    early = await add_job(session_factory, next_retry_at=utcnow() - timedelta(minutes=5))
    pub, _, _ = publisher(session_factory)
    assert (await pub.publish_next()).job_id == early
    assert (await pub.publish_next()).job_id == late


async def test_paused_publisher_sends_nothing(session_factory: SF) -> None:
    job_id = await add_job(session_factory)
    async with session_factory() as s, s.begin():
        await kv_repo.set_bool(s, kv_repo.PUBLISHER_PAUSED, True)
    pub, session, _ = publisher(session_factory)
    assert (await pub.publish_next()).outcome is Outcome.PAUSED
    assert session.requests == []
    assert (await get_job(session_factory, job_id)).status is JobStatus.QUEUED

    async with session_factory() as s, s.begin():
        await kv_repo.set_bool(s, kv_repo.PUBLISHER_PAUSED, False)
    assert (await pub.publish_next()).outcome is Outcome.PUBLISHED


# ------------------------------------------------------------------ errors
async def test_flood_wait_uses_no_attempt(session_factory: SF) -> None:
    job_id = await add_job(session_factory)
    pub, session, _ = publisher(session_factory)
    session.fail(429, "Too Many Requests: retry after 17", retry_after=17)
    res = await pub.publish_next()
    assert res.outcome is Outcome.FLOOD and res.wait_seconds == 18
    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.QUEUED and job.attempts == 0
    assert job.next_retry_at is not None and job.next_retry_at > utcnow() + timedelta(seconds=15)


async def test_network_error_backs_off_then_fails(session_factory: SF) -> None:
    job_id = await add_job(session_factory)
    pub, session, notifier = publisher(session_factory, max_publish_attempts=3)

    for attempt, wait in ((1, 30), (2, 60)):
        session.network_error()
        res = await pub.publish_next(utcnow() + timedelta(hours=attempt))
        assert res.outcome is Outcome.RETRY and res.wait_seconds == wait
        job = await get_job(session_factory, job_id)
        assert job.status is JobStatus.RETRY and job.attempts == attempt
        assert "TelegramNetworkError" in (job.last_error or "")

    session.network_error()
    res = await pub.publish_next(utcnow() + timedelta(hours=5))
    assert res.outcome is Outcome.FAILED
    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.FAILED and job.attempts == 3
    assert any("kanalga chiqmadi" in m and f"/retry {job_id}" in m for m in notifier.messages)


async def test_html_error_is_resent_as_plain_text(session_factory: SF) -> None:
    job_id = await add_job(
        session_factory, text='💼 <b>Sotuvchi</b>\n<i><a href="https://t.me/k/1">manba</a></i>'
    )
    pub, session, _ = publisher(session_factory)
    session.fail(400, "Bad Request: can't parse entities: Unsupported start tag")
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED
    first, second = session.sent(SendMessage)
    assert first.parse_mode == "HTML"
    assert second.parse_mode is None
    assert second.text == "💼 Sotuvchi\nmanba (https://t.me/k/1)"
    assert (await get_job(session_factory, job_id)).status is JobStatus.PUBLISHED


async def test_stale_file_id_is_uploaded_again(session_factory: SF, images: Path) -> None:
    await add_job(session_factory)
    pub, session, _ = publisher(session_factory, images)
    await pub.publish_next()  # caches PHOTO_ID_1
    await add_job(session_factory)
    session.fail(400, "Bad Request: wrong file identifier/HTTP URL specified")
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED
    _, cached, upload = session.sent(SendPhoto)
    assert cached.photo == "PHOTO_ID_1"
    assert isinstance(upload.photo, FSInputFile)


@pytest.mark.parametrize(
    ("status", "description"),
    [
        (401, "Unauthorized"),
        (403, "Forbidden: bot is not a member of the channel chat"),
        (400, "Bad Request: chat not found"),
        (400, "Bad Request: not enough rights to send photos to the chat"),
    ],
)
async def test_bad_setup_keeps_the_job_and_tells_the_admin(
    session_factory: SF, status: int, description: str
) -> None:
    job_id = await add_job(session_factory)
    pub, session, notifier = publisher(session_factory)
    session.fail(status, description)
    res = await pub.publish_next()
    assert res.outcome is Outcome.CONFIG and res.wait_seconds == 300
    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.QUEUED and job.attempts == 0
    assert job.next_retry_at is not None
    assert len(notifier.messages) == 1 and "joylab bo'lmayapti" in notifier.messages[0]


async def test_stuck_sending_job_is_queued_again(session_factory: SF) -> None:
    job_id = await add_job(session_factory, status=JobStatus.SENDING, attempts=2)
    pub, session, _ = publisher(session_factory)
    assert await pub.requeue_stuck() == 1
    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.RETRY and job.attempts == 2
    assert (await pub.publish_next()).outcome is Outcome.PUBLISHED


async def test_run_once_respects_the_queue(session_factory: SF) -> None:
    for _ in range(3):
        await add_job(session_factory)
    await add_job(session_factory, next_retry_at=utcnow() + timedelta(hours=1))
    pub, session, _ = publisher(session_factory)

    async def no_sleep(_: float) -> bool:
        return False

    await pub.run(no_sleep, once=True)
    assert len(session.requests) == 3


# ------------------------------------------------------------------ helpers
def test_backoff_doubles_up_to_the_cap() -> None:
    assert [backoff_seconds(n, 30, 3600) for n in (1, 2, 3, 8, 20)] == [30, 60, 120, 3600, 3600]


def test_plain_text_keeps_links_readable() -> None:
    assert plain_text('<b>A &amp; B</b> <a href="https://x.uz/?a=1&amp;b=2">bu yerda</a>') == (
        "A & B bu yerda (https://x.uz/?a=1&b=2)"
    )


def test_keyboard_from_stored_buttons() -> None:
    kb = keyboard([[{"text": "📩 Murojaat", "url": "https://t.me/hr"}], []])
    assert kb is not None and kb.inline_keyboard[0][0].text == "📩 Murojaat"
    assert keyboard(None) is None and keyboard([[]]) is None
