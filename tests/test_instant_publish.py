"""The admin's approval of a user ad publishes it to the channel RIGHT THEN (not through the
queue), exactly once, and never loses it when Telegram refuses. Mocked Bot API only."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import EditMessageText, SendMessage, SendPhoto
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.db.models import Job, JobStatus
from ayvona.db.repositories import jobs_repo, kv_repo
from ayvona.publisher.outbox import ChannelSender, Outcome, Publisher
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, make_bot
from tests.test_admin_bot import ADMIN, BotHarness, callback_update
from tests.test_post_job import USER, all_jobs, fill, sent_to
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, make_image


def channel_settings(tmp_path: Path, *, with_channel: bool = True, **publisher):  # noqa: ANN201
    s = bot_settings(tmp_path)
    env = s.env.model_copy(update={"channel_id": str(CHANNEL) if with_channel else None})
    pub = s.app.publisher.model_copy(update=publisher)
    return s.model_copy(update={"env": env, "app": s.app.model_copy(update={"publisher": pub})})


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    make_image(tmp_path / "images", "boshqa/1.jpg")
    return BotHarness(channel_settings(tmp_path), session_factory)


def channel_posts(h: BotHarness) -> list[object]:
    """Everything sent to the channel (photo or text)."""
    return [
        r
        for r in h.session.requests
        if isinstance(r, SendPhoto | SendMessage) and r.chat_id == CHANNEL
    ]


async def pending_job(h: BotHarness, sf: SF) -> Job:
    await fill(h)
    await h.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(sf)
    assert job.status is JobStatus.PENDING_REVIEW
    return job


# ------------------------------------------------------------------ approval = publish now
async def test_approval_publishes_at_once_and_skips_the_queue(
    harness: BotHarness, session_factory: SF
) -> None:
    job = await pending_job(harness, session_factory)
    assert channel_posts(harness) == []  # nothing before the decision

    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))

    [post] = channel_posts(harness)
    assert isinstance(post, SendPhoto) and post.caption and post.caption.startswith("💼")
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.PUBLISHED  # sending -> published, never `queued`
    assert job.channel_message_id and job.published_at and job.expires_at
    # the author gets the link to the post (not the "will appear soon" text)
    texts = sent_to(harness, USER)
    assert any("t.me/" in t and str(job.channel_message_id) in t for t in texts)
    assert T.POST_APPROVED_USER not in texts
    # the admin's message shows the result
    edits = [r for r in harness.session.sent(EditMessageText) if r.text]
    assert "kanalga chiqdi" in edits[-1].text

    # the queue never held it: the worker's publisher finds nothing to send
    pub = Publisher(harness.settings, session_factory, ChannelSender(harness.bot, CHANNEL), None)
    assert (await pub.publish_next()).outcome is Outcome.IDLE
    assert len(channel_posts(harness)) == 1


async def test_double_click_and_second_admin_publish_once(
    harness: BotHarness, session_factory: SF
) -> None:
    job = await pending_job(harness, session_factory)
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))  # double click
    await harness.send(callback_update(f"mod:no:{job.id}", uid=ADMIN))  # a change of mind
    assert len(channel_posts(harness)) == 1
    assert (await all_jobs(session_factory))[0].status is JobStatus.PUBLISHED


async def test_simultaneous_clicks_publish_once(harness: BotHarness, session_factory: SF) -> None:
    job = await pending_job(harness, session_factory)
    await asyncio.gather(
        *(harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN)) for _ in range(4))
    )
    assert len(channel_posts(harness)) == 1
    assert (await all_jobs(session_factory))[0].status is JobStatus.PUBLISHED


async def test_rejected_ad_is_never_published(harness: BotHarness, session_factory: SF) -> None:
    job = await pending_job(harness, session_factory)
    await harness.send(callback_update(f"mod:no:{job.id}", uid=ADMIN))
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))  # too late
    assert channel_posts(harness) == []
    assert (await all_jobs(session_factory))[0].status is JobStatus.REJECTED
    assert T.POST_REJECTED_USER in sent_to(harness, USER)


async def test_night_pause_does_not_hold_back_an_approved_ad(
    tmp_path: Path, session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision: the admin's click is a manual action — quiet hours / spacing do not apply."""
    make_image(tmp_path / "images", "boshqa/1.jpg")
    h = BotHarness(channel_settings(tmp_path, quiet_hours="00:00-23:59"), session_factory)

    def boom(self: Publisher, now: object) -> None:  # the night check must not even run
        raise AssertionError("quiet hours consulted for an approved ad")

    monkeypatch.setattr(Publisher, "_quiet_hours", boom)
    job = await pending_job(h, session_factory)
    await h.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    assert len(channel_posts(h)) == 1


# ------------------------------------------------------------------ never lost
async def test_telegram_error_hands_the_ad_to_the_queue(
    harness: BotHarness, session_factory: SF
) -> None:
    job = await pending_job(harness, session_factory)
    harness.session.ok()  # answerCallbackQuery
    harness.session.network_error()  # the channel post fails
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))

    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.RETRY and job.attempts == 1  # waits for the worker
    assert T.POST_APPROVED_USER in sent_to(harness, USER)
    edits = [r for r in harness.session.sent(EditMessageText) if r.text]
    assert "navbatga qo'yildi" in edits[-1].text

    # the worker's publisher finishes it, once
    async with session_factory() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job.id).values(next_retry_at=utcnow()))
    pub = Publisher(harness.settings, session_factory, ChannelSender(harness.bot, CHANNEL), None)
    assert (await pub.publish_next()).outcome is Outcome.PUBLISHED
    assert (await pub.publish_next()).outcome is Outcome.IDLE
    assert (await all_jobs(session_factory))[0].status is JobStatus.PUBLISHED


async def test_flood_wait_goes_back_to_the_queue_without_using_an_attempt(
    harness: BotHarness, session_factory: SF
) -> None:
    job = await pending_job(harness, session_factory)
    harness.session.ok()
    harness.session.fail(429, "Too Many Requests: retry after 30", retry_after=30)
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.QUEUED and job.attempts == 0
    assert job.next_retry_at is not None and job.next_retry_at > utcnow()


async def test_paused_publisher_keeps_the_approved_ad_in_the_queue(
    harness: BotHarness, session_factory: SF
) -> None:
    async with session_factory() as s, s.begin():
        await kv_repo.set_bool(s, kv_repo.PUBLISHER_PAUSED, True)
    job = await pending_job(harness, session_factory)
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    assert channel_posts(harness) == []
    assert (await all_jobs(session_factory))[0].status is JobStatus.QUEUED
    assert T.POST_APPROVED_USER in sent_to(harness, USER)


async def test_no_channel_configured_queues_the_approved_ad(
    tmp_path: Path, session_factory: SF
) -> None:
    h = BotHarness(channel_settings(tmp_path, with_channel=False), session_factory)
    job = await pending_job(h, session_factory)
    await h.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    assert channel_posts(h) == []
    assert (await all_jobs(session_factory))[0].status is JobStatus.QUEUED


# ------------------------------------------------------------------ crash recovery
async def test_a_job_stuck_in_sending_is_rescued_only_when_stale(
    tmp_path: Path, session_factory: SF
) -> None:
    """The bot died between the approval and the send: the worker's publisher takes the job back
    after 10 minutes (a fresh `sending` is somebody's running send and is left alone)."""
    make_image(tmp_path / "images", "boshqa/1.jpg")
    bot, session = make_bot()
    pub = Publisher(channel_settings(tmp_path), session_factory, ChannelSender(bot, CHANNEL), None)
    from tests.worker_helpers import add_job

    job_id = await add_job(session_factory, status=JobStatus.SENDING)
    assert (await pub.publish_next()).outcome is Outcome.IDLE  # fresh: untouched
    async with session_factory() as s:
        assert (await s.get(Job, job_id)).status is JobStatus.SENDING  # type: ignore[union-attr]

    old = utcnow() - timedelta(minutes=11)
    async with session_factory() as s, s.begin():
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(updated_at=old)
            .execution_options(synchronize_session=False)
        )
    assert (await pub.publish_next()).outcome is Outcome.PUBLISHED
    assert len(session.sent(SendPhoto) + session.sent(SendMessage)) == 1
    assert [j for j in (await _jobs(session_factory)) if j.status is JobStatus.PUBLISHED]


async def _jobs(sf: SF) -> list[Job]:
    async with sf() as s:
        return list((await s.scalars(select(Job))).all())


async def test_reset_stuck_sending_without_age_still_resets_everything(
    session_factory: SF,
) -> None:
    from tests.worker_helpers import add_job

    job_id = await add_job(session_factory, status=JobStatus.SENDING)
    async with session_factory() as s, s.begin():
        assert await jobs_repo.reset_stuck_sending(s, utcnow()) == [job_id]
