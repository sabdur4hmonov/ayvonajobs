"""The poster always chooses how long the ad stays active (3 / 7 / 14 / 30 days); the choice is
the ad's expiry, shown to the admin, used by the existing reminder / extend / expiry mechanism."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select

from ayvona.bot import texts as T
from ayvona.bot.handlers.my_jobs import reminder_view
from ayvona.db.models import Job, JobStatus
from ayvona.services import expiry as expiry_svc
from ayvona.services import my_jobs
from ayvona.services import search as search_svc
from ayvona.services.expiry import ExpiryService
from ayvona.services.lifetime import active_days, remind_lead
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, make_bot
from tests.test_admin_bot import ADMIN, BotHarness, callback_update, message_update
from tests.test_instant_publish import channel_posts, channel_settings
from tests.test_lifecycle import USER as AUTHOR
from tests.test_lifecycle import get, user_job
from tests.test_post_job import USER, all_jobs, contact_update
from tests.worker_helpers import SF, make_image, make_settings


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    make_image(tmp_path / "images", "boshqa/1.jpg")
    return BotHarness(channel_settings(tmp_path), session_factory)


async def walk_to_duration(h: BotHarness) -> None:
    await h.send(message_update(T.MENU_POST, uid=USER))
    await h.send(callback_update("pj:cat:sotuv", uid=USER))
    await h.send(message_update("Sotuvchi", uid=USER))
    await h.send(message_update(T.BTN_SKIP, uid=USER))
    await h.send(message_update("4-6 mln so'm", uid=USER))
    await h.send(callback_update("pj:reg:toshkent_sh", uid=USER))
    await h.send(message_update("Chilonzor tumani", uid=USER))
    await h.send(message_update(T.BTN_SKIP, uid=USER))
    await h.send(message_update("Mas'uliyatli", uid=USER))
    await h.send(contact_update(USER))


# ------------------------------------------------------------------ the question
async def test_the_form_always_asks_the_duration_with_buttons(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_to_duration(harness)
    asked = harness.session.sent(SendMessage)
    question = next(m for m in asked if m.text and m.text.startswith("9/9."))
    assert T.POST_ASK_DURATION in question.text
    buttons = [
        b
        for m in asked
        if m.reply_markup and hasattr(m.reply_markup, "inline_keyboard")
        for row in m.reply_markup.inline_keyboard
        for b in row
        if b.callback_data.startswith("pj:days:")
    ]
    assert [b.text for b in buttons] == ["3 kun", "7 kun", "14 kun", "30 kun"]

    # no preview until the poster answers; a typed answer is not accepted
    assert T.POST_PREVIEW_HEAD not in harness.texts()
    await harness.send(message_update("10 kun", uid=USER))
    assert harness.texts()[-1] == T.POST_NEED_BUTTON
    await harness.send(callback_update("pj:days:5", uid=USER))  # not an offered option: ignored
    assert T.POST_PREVIEW_HEAD not in harness.texts()

    await harness.send(callback_update("pj:days:14", uid=USER))
    texts = harness.texts()
    assert T.POST_PREVIEW_HEAD in texts
    assert T.POST_PREVIEW_DAYS.format(n=14) in texts


async def test_the_choice_is_stored_and_shown_to_the_admin(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_to_duration(harness)
    await harness.send(callback_update("pj:days:7", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.active_days == 7 and job.status is JobStatus.PENDING_REVIEW
    [notice] = [r for r in harness.session.sent(SendMessage) if r.chat_id == ADMIN]
    assert "Faol muddat: <b>7 kun</b>" in notice.text


async def test_duration_can_be_changed_from_the_preview(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_to_duration(harness)
    await harness.send(callback_update("pj:days:3", uid=USER))
    await harness.send(callback_update("pj:edit:", uid=USER))
    await harness.send(callback_update("pj:field:duration", uid=USER))
    await harness.send(callback_update("pj:days:30", uid=USER))
    assert harness.texts()[-1] == T.POST_PREVIEW_ASK  # straight back to the preview
    await harness.send(callback_update("pj:send:", uid=USER))
    assert (await all_jobs(session_factory))[0].active_days == 30


# ------------------------------------------------------------------ the clock starts at publication
async def test_expiry_is_publication_plus_the_chosen_days(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_to_duration(harness)
    await harness.send(callback_update("pj:days:7", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    assert len(channel_posts(harness)) == 1
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.PUBLISHED and job.expires_at and job.published_at
    assert job.expires_at - job.published_at == timedelta(days=7)


async def test_ads_without_a_choice_keep_the_old_default(session_factory: SF) -> None:
    ad = await user_job(session_factory)
    job = await get(session_factory, ad)
    assert active_days(job, make_settings()) == 30  # expiry.user_days
    job.origin = job.origin.__class__.AGGREGATOR
    assert active_days(job, make_settings()) == 21  # expiry.aggregator_days


# ------------------------------------------------------------------ reminder, extend, expiry
def test_reminder_lead_is_at_most_a_third_of_a_short_ads_life() -> None:
    s = make_settings()
    job = Job(active_days=3)
    assert remind_lead(job, s) == timedelta(days=1)
    assert remind_lead(Job(active_days=7), s) == timedelta(days=2)
    assert remind_lead(Job(active_days=30), s) == timedelta(days=2)


async def test_short_ad_is_reminded_one_day_before_the_end(session_factory: SF) -> None:
    sf = session_factory
    now = utcnow()
    ad = await user_job(sf, active_days=3, published_at=now, expires_at=now + timedelta(days=3))
    async with sf() as s:
        assert await expiry_svc.due_reminders(s, now + timedelta(hours=1), make_settings()) == []
        assert (
            await expiry_svc.due_reminders(s, now + timedelta(days=1, hours=12), make_settings())
            == []
        )
        due = await expiry_svc.due_reminders(s, now + timedelta(days=2, hours=1), make_settings())
    assert [j.id for j in due] == [ad]


async def test_reminder_offers_the_ads_own_duration_and_extend_adds_it(
    session_factory: SF,
) -> None:
    sf = session_factory
    now = utcnow()
    ad = await user_job(sf, active_days=7, expires_at=now + timedelta(days=1))
    bot, session = make_bot()
    report = await ExpiryService(make_settings(), sf, bot, reminder_view).check(now)
    assert report.reminded == 1
    [msg] = session.sent(SendMessage)
    assert "+7 kun" in msg.reply_markup.inline_keyboard[0][0].text

    async with sf() as s, s.begin():
        extended = await my_jobs.extend_job(s, AUTHOR, ad, now, make_settings())
    assert extended is not None and extended.expires_at == now + timedelta(days=7)
    assert extended.reminded_at is None  # it can be reminded again


async def test_expired_ad_leaves_search_and_is_never_sent_again(session_factory: SF) -> None:
    sf = session_factory
    now = utcnow()
    ad = await user_job(sf, "Kassir", active_days=3, expires_at=now - timedelta(minutes=1))
    report = await ExpiryService(make_settings(), sf, None, reminder_view).check(now)  # type: ignore[arg-type]
    assert report.expired == 1 and (await get(sf, ad)).status is JobStatus.EXPIRED
    async with sf() as s:
        found, _ = await search_svc.search(
            s, SearchFilters(keyword="kassir"), now, usd_rate=1, limit=10
        )
        assert found == []
        # nothing in the publishing queue picks an expired job
        from ayvona.db.repositories import jobs_repo

        assert await jobs_repo.next_due(s, now + timedelta(days=1)) is None
        assert (await s.scalars(select(Job.id).where(Job.status == JobStatus.QUEUED))).all() == []
    # it still shows in the author's own list (history), marked as expired
    async with sf() as s:
        assert [j.id for j in await my_jobs.list_jobs(s, AUTHOR)] == [ad]
    _ = CHANNEL
