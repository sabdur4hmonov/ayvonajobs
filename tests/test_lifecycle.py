"""Bosqich 14: closing own jobs (channel post "❌ YOPILDI"), expiry (+ reminder, extend),
extended /stats, /addword /delword /words, /ban /unban, /broadcast. Mocked Bot API."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import EditMessageCaption, EditMessageText, SendMessage
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.bot.handlers.my_jobs import reminder_view
from ayvona.config import Settings
from ayvona.db.models import FilterWord, Job, JobOrigin, JobStatus, User
from ayvona.publisher.outbox import ChannelSender, Publisher
from ayvona.services import search as search_svc
from ayvona.services import users as users_svc
from ayvona.services.expiry import ExpiryService
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, make_bot
from tests.test_admin_bot import ADMIN, BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.test_search import job
from tests.worker_helpers import SF, RecordingNotifier, add_job, make_settings

USER = 4242


def with_channel(s: Settings) -> Settings:
    return s.model_copy(update={"env": s.env.model_copy(update={"channel_id": str(CHANNEL)})})


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(with_channel(bot_settings(tmp_path)), session_factory)


async def user_job(sf: SF, title: str = "Sotuvchi", **kw: object) -> int:
    async with sf() as s, s.begin():
        await users_svc.touch_user(s, USER, "ali", "Ali", utcnow())
    return await job(
        sf, title, origin=JobOrigin.USER, author_id=USER, contact_phone="+998901234567", **kw
    )


async def get(sf: SF, job_id: int) -> Job:
    async with sf() as s:
        row = await s.get(Job, job_id)
        assert row is not None
        return row


# ------------------------------------------------------------------ expires_at
async def test_publisher_sets_expires_at(session_factory: SF) -> None:
    agg = await add_job(session_factory)
    bot, _ = make_bot()
    pub = Publisher(
        make_settings(), session_factory, ChannelSender(bot, CHANNEL), RecordingNotifier()
    )  # type: ignore[arg-type]
    await pub.publish_next()
    j = await get(session_factory, agg)
    assert j.published_at and j.expires_at
    assert j.expires_at - j.published_at == timedelta(days=21)


async def test_expiry_backfill_remind_expire(session_factory: SF) -> None:
    sf = session_factory
    now = utcnow()
    old = await job(sf, "Eski", published_at=now - timedelta(days=30))  # no expires_at yet
    soon = await user_job(sf, "Kassir", expires_at=now + timedelta(days=1))
    later = await user_job(sf, "Oshpaz", expires_at=now + timedelta(days=10))
    bot, session = make_bot()
    service = ExpiryService(make_settings(), sf, bot, reminder_view)

    report = await service.check(now)
    assert report.backfilled == 1 and report.expired == 1 and report.reminded == 1
    assert (await get(sf, old)).status is JobStatus.EXPIRED  # 30 > 21 days
    [msg] = session.sent(SendMessage)
    assert msg.chat_id == USER and "Kassir" in msg.text and "Uzaytirasizmi" in msg.text
    assert msg.parse_mode == "HTML"  # the worker's Bot has no default parse mode
    assert (await get(sf, soon)).reminded_at is not None
    assert (await get(sf, later)).reminded_at is None

    again = await service.check(now)  # reminded once only
    assert again.reminded == 0 and len(session.sent(SendMessage)) == 1

    await service.check(now + timedelta(days=2))
    assert (await get(sf, soon)).status is JobStatus.EXPIRED
    async with sf() as s:
        found, _ = await search_svc.search(
            s, SearchFilters(keyword="kassir"), now + timedelta(days=2), usd_rate=1, limit=10
        )
    assert found == []  # out of search


# ------------------------------------------------------------------ 📋 Mening e'lonlarim
async def test_close_own_job_edits_the_channel_post(
    harness: BotHarness, session_factory: SF
) -> None:
    job_id = await user_job(session_factory)
    await harness.send(message_update(T.MENU_MY_JOBS, uid=USER))
    listing = harness.texts()[-1]
    assert "1. <b>Sotuvchi</b>" in listing and "kanalda" in listing

    await harness.send(callback_update(f"my:close:{job_id}", uid=USER))
    assert "yopamizmi" in harness.texts()[-1]
    await harness.send(callback_update(f"my:closeok:{job_id}", uid=USER))
    assert harness.texts()[-1] == T.MY_CLOSED
    j = await get(session_factory, job_id)
    assert j.status is JobStatus.CLOSED and j.closed_at is not None

    [edit] = harness.session.sent(EditMessageCaption)
    assert edit.chat_id == CHANNEL and edit.message_id == 500
    assert edit.caption.startswith("❌ <b>YOPILDI</b>")
    assert edit.reply_markup.inline_keyboard == []

    await harness.send(callback_update(f"my:closeok:{job_id}", uid=USER))  # twice: refused
    assert harness.texts()[-1] == T.MY_CLOSE_FAIL


async def test_text_post_is_edited_as_text(harness: BotHarness, session_factory: SF) -> None:
    job_id = await user_job(session_factory)
    await harness.send(message_update("/start", uid=USER))
    harness.session.ok()  # answerCallbackQuery
    harness.session.fail(400, "Bad Request: there is no caption in the message to edit")
    await harness.send(callback_update(f"my:closeok:{job_id}", uid=USER))
    edits = [r for r in harness.session.sent(EditMessageText) if r.chat_id == CHANNEL]
    assert len(edits) == 1 and edits[0].text.startswith("❌ <b>YOPILDI</b>")


async def test_someone_elses_job_cannot_be_closed(harness: BotHarness, session_factory: SF) -> None:
    job_id = await user_job(session_factory)
    await harness.send(callback_update(f"my:closeok:{job_id}", uid=USER + 1))
    assert (await get(session_factory, job_id)).status is JobStatus.PUBLISHED


async def test_extend_expired_job(harness: BotHarness, session_factory: SF) -> None:
    job_id = await user_job(session_factory, status=JobStatus.EXPIRED)
    await harness.send(callback_update(f"my:extend:{job_id}", uid=USER))
    assert harness.texts()[-1].startswith("🔄 Uzaytirildi")
    j = await get(session_factory, job_id)
    assert j.status is JobStatus.PUBLISHED and j.expires_at is not None
    assert j.expires_at > utcnow() + timedelta(days=29)


async def test_waiting_job_can_be_closed_before_publishing(
    harness: BotHarness, session_factory: SF
) -> None:
    job_id = await user_job(session_factory, status=JobStatus.PENDING_REVIEW)
    await harness.send(callback_update(f"my:closeok:{job_id}", uid=USER))
    assert (await get(session_factory, job_id)).status is JobStatus.CLOSED
    assert harness.session.sent(EditMessageCaption) == []  # never was in the channel


# ------------------------------------------------------------------ admin
async def test_extended_stats(harness: BotHarness, session_factory: SF) -> None:
    await user_job(session_factory)
    await harness.send(message_update("/stats"))
    text = harness.texts()[-1]
    # the author and the admin who asked
    assert "Foydalanuvchilar: 2" in text and "Faol obunalar: 0" in text
    assert "Foydalanuvchi e'lonlari (7 kun): 1" in text


async def test_filter_words_commands(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update("/addword"))
    assert harness.texts()[-1] == T.ADDWORD_USAGE
    await harness.send(message_update("/addword ban  Tarmoqli   Marketing "))
    assert "tarmoqli marketing" in harness.texts()[-1]
    await harness.send(message_update("/addword ban tarmoqli marketing"))
    assert harness.texts()[-1] == T.ADDWORD_EXISTS
    await harness.send(message_update("/words"))
    assert "ban: tarmoqli marketing" in harness.texts()[-1]
    async with session_factory() as s:
        assert len((await s.scalars(select(FilterWord))).all()) == 1
    await harness.send(message_update("/delword tarmoqli marketing"))
    await harness.send(message_update("/words"))
    assert harness.texts()[-1] == T.WORDS_EMPTY
    await harness.send(message_update("/addword ban qimor", uid=USER))  # not an admin: ignored
    async with session_factory() as s:
        assert (await s.scalars(select(FilterWord))).all() == []


async def test_ban_and_unban(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update("/start", uid=USER))  # username "u4242"
    await harness.send(message_update("/ban @U4242"))
    assert harness.texts()[-1].startswith("🚫 Bloklandi: 4242")
    async with session_factory() as s:
        assert (await s.get(User, USER)).is_banned  # type: ignore[union-attr]
    await harness.send(message_update(f"/ban {ADMIN}"))
    assert harness.texts()[-1] == T.BAN_ADMIN
    await harness.send(message_update("/ban @nobody_here"))
    assert harness.texts()[-1] == T.BAN_NOT_FOUND
    await harness.send(message_update("/unban 4242"))
    async with session_factory() as s:
        assert not (await s.get(User, USER)).is_banned  # type: ignore[union-attr]


async def test_broadcast_with_confirmation(harness: BotHarness, session_factory: SF) -> None:
    for uid in (USER, USER + 1, USER + 2):
        await harness.send(message_update("/start", uid=uid))
    async with session_factory() as s, s.begin():
        await s.execute(update(User).where(User.tg_id == USER + 2).values(is_banned=True))

    await harness.send(message_update("/broadcast"))
    assert harness.texts()[-1] == T.BROADCAST_USAGE
    await harness.send(message_update("/broadcast Yangi funksiya: obunalar!"))
    # two users + the admin (a user of the bot too); the banned one is not counted
    assert "<b>3</b> ta" in harness.texts()[-1] and "Yangi funksiya" in harness.texts()[-1]
    await harness.send(callback_update("bc:send", uid=ADMIN))
    for _ in range(50):
        if any(t.startswith("📣 Tayyor") for t in harness.texts()):
            break
        await asyncio.sleep(0.05)
    text = "Yangi funksiya: obunalar!"
    got = {r.chat_id for r in harness.session.sent(SendMessage) if r.text == text}
    assert got == {USER, USER + 1, ADMIN}  # the banned user is skipped
    assert any(t.startswith("📣 Tayyor: 3 ta") for t in harness.texts())
    await harness.send(callback_update("bc:send", uid=ADMIN))  # used up
    assert harness.texts()[-1] == T.BROADCAST_EXPIRED
