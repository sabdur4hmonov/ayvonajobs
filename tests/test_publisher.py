"""publisher/outbox.py with a mocked Bot API (tests/fake_bot.py): nothing leaves the machine.

Covers ROADMAP Bosqich 7 step 2: photo + caption + buttons, file_id cache, link preview off,
flood wait, network backoff, HTML fallback, bad setup, attempts limit, pause, crash recovery;
and ``publisher.max_age_hours`` (too old -> ``skipped_old``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import FSInputFile
from sqlalchemy import select

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.db.models import Image, JobStatus
from ayvona.db.repositories import kv_repo
from ayvona.publisher.outbox import (
    ChannelSender,
    Outcome,
    Publisher,
    backoff_seconds,
    keyboard,
    plain_text,
    skip_old_jobs,
    too_old_reason,
)
from ayvona.services.stats import queue_eta
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, FakeBotSession, make_bot
from tests.worker_helpers import (
    SF,
    RecordingNotifier,
    add_job,
    add_job_from_post,
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


# ------------------------------------------------------------------ max_age_hours (skipped_old)
async def test_too_old_job_is_skipped_and_the_next_one_published(session_factory: SF) -> None:
    old = await add_job_from_post(session_factory, timedelta(hours=25))
    fresh = await add_job_from_post(session_factory, timedelta(hours=23))
    pub, session, notifier = publisher(session_factory)

    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED and res.job_id == fresh
    assert len(session.requests) == 1

    job = await get_job(session_factory, old)
    assert job.status is JobStatus.SKIPPED_OLD
    assert job.last_error == "eskirgan: 24 soatdan eski"
    assert job.next_retry_at is None and job.published_at is None
    assert notifier.messages == []  # log and /stats only, no admin notice
    assert (await pub.publish_next()).outcome is Outcome.IDLE


async def test_exactly_max_age_is_still_published(session_factory: SF) -> None:
    now = utcnow()
    job_id = await add_job_from_post(session_factory, timedelta(hours=24), now=now)
    pub, _, _ = publisher(session_factory)
    res = await pub.publish_next(now)
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id
    later = await add_job_from_post(session_factory, timedelta(hours=24, seconds=1), now=now)
    await pub.publish_next(now)
    assert (await get_job(session_factory, later)).status is JobStatus.SKIPPED_OLD


async def test_only_waiting_jobs_become_skipped_old(session_factory: SF) -> None:
    age = timedelta(hours=30)
    ids = {
        st: await add_job_from_post(session_factory, age, status=st)
        for st in (
            JobStatus.QUEUED,
            JobStatus.RETRY,
            JobStatus.SENDING,
            JobStatus.PUBLISHED,
            JobStatus.FAILED,
        )
    }
    skipped = await skip_old_jobs(make_settings(), session_factory)
    assert sorted(skipped) == sorted([ids[JobStatus.QUEUED], ids[JobStatus.RETRY]])
    for st in (JobStatus.SENDING, JobStatus.PUBLISHED, JobStatus.FAILED):
        assert (await get_job(session_factory, ids[st])).status is st


async def test_age_falls_back_to_fetched_at(session_factory: SF) -> None:
    old = await add_job_from_post(session_factory, None, fetched_ago=timedelta(hours=30))
    fresh = await add_job_from_post(session_factory, None, fetched_ago=timedelta(hours=1))
    pub, _, _ = publisher(session_factory)
    assert (await pub.publish_next()).job_id == fresh
    assert (await get_job(session_factory, old)).status is JobStatus.SKIPPED_OLD


async def test_job_without_a_source_post_is_never_too_old(session_factory: SF) -> None:
    job_id = await add_job(session_factory)  # user submission: no raw post
    pub, _, _ = publisher(session_factory)
    res = await pub.publish_next(utcnow() + timedelta(days=3))
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id


async def test_max_age_zero_turns_the_rule_off(session_factory: SF) -> None:
    job_id = await add_job_from_post(session_factory, timedelta(days=5))
    pub, _, _ = publisher(session_factory, max_age_hours=0)
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id


def test_max_age_default_is_24_hours() -> None:
    cfg = load_settings(DEFAULT_CONFIG_DIR, env_file=None).app.publisher
    assert cfg.max_age_hours == 24
    now = utcnow()
    assert cfg.too_old_before(now) == now - timedelta(hours=24)
    assert cfg.model_copy(update={"max_age_hours": 0}).too_old_before(now) is None
    assert too_old_reason(24) == "eskirgan: 24 soatdan eski"
    assert too_old_reason(1.5) == "eskirgan: 1.5 soatdan eski"


# ------------------------------------------------------------------ helpers
# ------------------------------------------------------------------ pacing: interval, quiet hours
TASHKENT = ZoneInfo("Asia/Tashkent")


def tashkent(hour: int, minute: int = 0) -> datetime:
    """2026-10-02 at ``hour:minute`` Asia/Tashkent, as UTC."""
    return datetime(2026, 10, 2, hour, minute, tzinfo=TASHKENT).astimezone(UTC)


NIGHT = "23:00-07:00"


@pytest.mark.parametrize(
    ("local", "until"),
    [
        ((22, 59), None),
        ((23, 0), (3, 7)),  # -> next morning 07:00
        ((2, 30), (2, 7)),
        ((6, 59), (2, 7)),
        ((7, 0), None),
        ((12, 0), None),
    ],
)
def test_quiet_until_over_midnight(local: tuple[int, int], until: tuple[int, int] | None) -> None:
    cfg = make_settings().app.publisher.model_copy(update={"quiet_hours": NIGHT})
    got = cfg.quiet_until(tashkent(*local), TASHKENT)
    if until is None:
        assert got is None
    else:
        day, hour = until
        assert got == datetime(2026, 10, day, hour, tzinfo=TASHKENT)


def test_quiet_hours_within_one_day_and_off() -> None:
    cfg = make_settings().app.publisher.model_copy(update={"quiet_hours": "13:00-14:00"})
    assert cfg.quiet_until(tashkent(13, 30), TASHKENT) == datetime(2026, 10, 2, 14, tzinfo=TASHKENT)
    assert cfg.quiet_until(tashkent(14, 0), TASHKENT) is None
    assert cfg.quiet_until(tashkent(23, 0), TASHKENT) is None
    off = cfg.model_copy(update={"quiet_hours": None})
    assert off.quiet_until(tashkent(13, 30), TASHKENT) is None


async def test_quiet_hours_hold_the_queue_until_morning(session_factory: SF) -> None:
    job_id = await add_job(session_factory)
    pub, session, notifier = publisher(session_factory, quiet_hours=NIGHT)

    res = await pub.publish_next(tashkent(23, 30))
    assert res.outcome is Outcome.QUIET and res.wait_seconds == 7.5 * 3600
    assert session.requests == [] and notifier.messages == []
    assert (await get_job(session_factory, job_id)).status is JobStatus.QUEUED

    res = await pub.publish_next(tashkent(7, 0) + timedelta(days=1))
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job_id


async def test_too_old_rule_still_works_during_quiet_hours(session_factory: SF) -> None:
    night = tashkent(2, 0)
    old = await add_job_from_post(session_factory, timedelta(hours=25), now=night)
    fresh = await add_job_from_post(session_factory, timedelta(hours=20), now=night)
    pub, session, _ = publisher(session_factory, quiet_hours=NIGHT)

    assert (await pub.publish_next(night)).outcome is Outcome.QUIET
    assert (await get_job(session_factory, old)).status is JobStatus.SKIPPED_OLD
    assert (await get_job(session_factory, fresh)).status is JobStatus.QUEUED
    assert session.requests == []


async def test_restart_waits_for_the_interval_since_the_last_post(session_factory: SF) -> None:
    await add_job(session_factory)
    await add_job(session_factory)
    pub, session, _ = publisher(session_factory, publish_interval_seconds=300)
    assert await pub.spacing_wait() == 0  # nothing in the channel yet
    assert (await pub.publish_next()).outcome is Outcome.PUBLISHED

    # a "restarted" publisher: the first post waits for the rest of the 5 minutes
    restarted, _, _ = publisher(session_factory, publish_interval_seconds=300)
    waits: list[float] = []

    async def stop_on_first_sleep(seconds: float) -> bool:
        waits.append(seconds)
        return True

    await restarted.run(stop_on_first_sleep)
    assert len(waits) == 1 and 290 < waits[0] <= 300
    assert len(session.requests) == 1  # the second job was not sent yet
    later = utcnow() + timedelta(seconds=301)
    assert await restarted.spacing_wait(later) == 0


def test_queue_eta_counts_interval_and_quiet_hours() -> None:
    cfg = make_settings().app.publisher.model_copy(
        update={"publish_interval_seconds": 300, "quiet_hours": NIGHT}
    )
    evening = tashkent(22, 0)
    assert queue_eta(0, evening, cfg, TASHKENT) == timedelta(0)
    assert queue_eta(1, evening, cfg, TASHKENT) == timedelta(0)  # goes out right away
    assert queue_eta(12, evening, cfg, TASHKENT) == timedelta(minutes=55)  # 22:00 ... 22:55
    assert queue_eta(13, evening, cfg, TASHKENT) == timedelta(hours=9)  # 13th: 07:00 next day
    assert queue_eta(1, tashkent(3, 0), cfg, TASHKENT) == timedelta(hours=4)
    day = cfg.model_copy(update={"quiet_hours": None})
    assert queue_eta(25, evening, day, TASHKENT) == timedelta(hours=2)


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
