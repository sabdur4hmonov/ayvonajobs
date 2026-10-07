"""📢 E'lon joylash form (Bosqich 11) through the Dispatcher with the mocked Bot API: steps,
back / cancel / edit, required contact, limits, filters, admin review, author notices."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.db.models import Job, JobOrigin, JobStatus, User
from ayvona.publisher.outbox import ChannelSender, Outcome, Publisher
from ayvona.services import users as users_svc
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, make_bot
from tests.test_admin_bot import ADMIN, BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, RecordingNotifier

USER = 777


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


def contact_update(uid: int, phone: str = "998901234567"):  # noqa: ANN201
    return message_update(
        None, uid=uid, contact={"phone_number": phone, "first_name": "A", "user_id": uid}
    )


async def fill(
    h: BotHarness,
    uid: int = USER,
    title: str = "Sotuvchi",
    contact: bool = True,
    days: int | None = 7,
) -> None:
    """Answer every step up to the preview."""
    await h.send(message_update(T.MENU_POST, uid=uid))
    await h.send(callback_update("pj:cat:sotuv", uid=uid))
    await h.send(message_update(title, uid=uid))
    await h.send(message_update(T.BTN_SKIP, uid=uid))  # company
    await h.send(message_update("4-6 mln so'm", uid=uid))
    await h.send(callback_update("pj:reg:toshkent_sh", uid=uid))
    await h.send(message_update("Chilonzor tumani", uid=uid))
    await h.send(message_update(T.BTN_SKIP, uid=uid))  # schedule
    await h.send(message_update("Mas'uliyatli, xushmuomala", uid=uid))
    if contact:
        await h.send(contact_update(uid))
        if days:  # "how long should the ad stay active?"
            await h.send(callback_update(f"pj:days:{days}", uid=uid))


async def all_jobs(sf: SF) -> list[Job]:
    async with sf() as s:
        return list((await s.scalars(select(Job).order_by(Job.id))).all())


def sent_to(h: BotHarness, chat_id: int) -> list[str]:
    return [r.text for r in h.session.sent(SendMessage) if r.chat_id == chat_id]


# ------------------------------------------------------------------ happy path + review
async def test_full_form_review_and_approval(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness)
    texts = harness.texts()
    assert T.POST_PREVIEW_HEAD in texts
    preview = texts[texts.index(T.POST_PREVIEW_HEAD) + 1]
    assert preview.startswith("💼 <b>Sotuvchi</b>")
    assert "💰 Maosh: 4 000 000 – 6 000 000 so'm" in preview
    assert "📞 Aloqa: +998 90 123 45 67" in preview
    assert await all_jobs(session_factory) == []  # nothing written before "Yuborish"

    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.PENDING_REVIEW and job.origin is JobOrigin.USER
    assert job.author_id == USER and job.formatted_text == preview
    assert harness.texts()[-2] == T.POST_REVIEW or T.POST_REVIEW in harness.texts()

    # the admin got the job with the decision buttons (no ADMIN_CHAT_ID -> the admin in private)
    [notice] = [r for r in harness.session.sent(SendMessage) if r.chat_id == ADMIN]
    assert "Yangi e'lon" in notice.text and "yangi foydalanuvchi" in notice.text
    assert [b.text for b in notice.reply_markup.inline_keyboard[0]] == [
        T.MOD_OK,
        T.MOD_NO,
        T.MOD_BAN,
    ]

    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.QUEUED
    assert T.POST_APPROVED_USER in sent_to(harness, USER)
    async with session_factory() as s:
        assert (await s.get(User, USER)).trust_level == 1  # type: ignore[union-attr]

    # pressing again: already decided
    await harness.send(callback_update(f"mod:no:{job.id}", uid=ADMIN))
    assert (await all_jobs(session_factory))[0].status is JobStatus.QUEUED


async def test_trusted_user_is_queued_without_review(
    harness: BotHarness, session_factory: SF
) -> None:
    async with session_factory() as s, s.begin():
        u = await users_svc.touch_user(s, USER, "u", "U", utcnow())
        u.trust_level = 1
    await fill(harness)
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.QUEUED
    assert T.POST_QUEUED in harness.texts()
    assert sent_to(harness, ADMIN) == []


async def test_ban_button_rejects_and_blocks(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness)
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    await harness.send(callback_update(f"mod:ban:{job.id}", uid=ADMIN))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.REJECTED
    async with session_factory() as s:
        assert (await s.get(User, USER)).is_banned  # type: ignore[union-attr]


async def test_non_admin_cannot_decide(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness)
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    await harness.send(callback_update(f"mod:ok:{job.id}", uid=USER))
    assert (await all_jobs(session_factory))[0].status is JobStatus.PENDING_REVIEW


# ------------------------------------------------------------------ contact is required
async def test_contact_is_required(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness, contact=False)
    await harness.send(message_update("qo'ng'iroq qiling", uid=USER))
    assert harness.texts()[-1] == T.POST_NO_CONTACT
    await harness.send(contact_update(USER, phone="+79991234567"))  # not an Uzbek number
    assert harness.texts()[-1] == T.POST_NO_CONTACT
    await harness.send(callback_update("pj:send:", uid=USER))  # no preview yet -> nothing
    assert await all_jobs(session_factory) == []

    await harness.send(message_update("@hr_manager", uid=USER))
    assert T.POST_ASK_DURATION in harness.texts()[-2]  # the contact is accepted: next question
    await harness.send(callback_update("pj:days:14", uid=USER))
    assert T.POST_PREVIEW_HEAD in harness.texts()
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.contact_username == "@hr_manager" and job.contact_phone is None


async def test_own_username_button(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness, contact=False)
    await harness.send(message_update(T.BTN_MY_USERNAME.format(username=f"@u{USER}"), uid=USER))
    await harness.send(callback_update("pj:days:7", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.contact_username == f"@u{USER}"


# ------------------------------------------------------------------ navigation
async def test_back_cancel_and_text_on_button_steps(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    await harness.send(message_update("Savdo", uid=USER))  # typed instead of a button
    assert harness.texts()[-1] == T.POST_NEED_BUTTON
    await harness.send(callback_update("pj:cat:sotuv", uid=USER))
    assert harness.texts()[-1] == f"2/9. {T.POST_ASK_TITLE}"
    await harness.send(message_update(T.BTN_BACK, uid=USER))
    assert f"1/9. {T.POST_ASK_CATEGORY}" in harness.texts()[-2:]
    await harness.send(message_update(T.BTN_CANCEL, uid=USER))
    assert harness.texts()[-1] == T.CANCELLED
    await harness.send(message_update("Sotuvchi", uid=USER))  # not in the form any more
    assert harness.texts()[-1] == T.CANCELLED


async def test_edit_from_the_preview(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness)
    await harness.send(callback_update("pj:edit:", uid=USER))
    assert harness.texts()[-1] == T.POST_EDIT_WHICH
    await harness.send(callback_update("pj:field:title", uid=USER))
    assert harness.texts()[-1] == f"2/9. {T.POST_ASK_TITLE}"
    await harness.send(message_update("Katta sotuvchi", uid=USER))
    assert any(t.startswith("💼 <b>Katta sotuvchi</b>") for t in harness.texts()[-3:])
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.title == "Katta sotuvchi"


# ------------------------------------------------------------------ limits and filters
async def test_limit_is_checked_before_the_form(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness)
    await harness.send(callback_update("pj:send:", uid=USER))  # waits for review
    await harness.send(message_update(T.MENU_POST, uid=USER))
    assert harness.texts()[-1] == T.POST_LIMIT_WAITING


async def test_ban_word_is_rejected(harness: BotHarness, session_factory: SF) -> None:
    await fill(harness, title="Kazino dilleri")
    await harness.send(callback_update("pj:send:", uid=USER))
    assert T.POST_REJECTED in harness.texts()
    assert await all_jobs(session_factory) == []


# ------------------------------------------------------------------ publishing
async def test_author_gets_the_channel_link(harness: BotHarness, session_factory: SF) -> None:
    async with session_factory() as s, s.begin():
        u = await users_svc.touch_user(s, USER, "u", "U", utcnow())
        u.trust_level = 1
    await fill(harness)
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    async with session_factory() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job.id).values(next_retry_at=utcnow()))

    bot, session = make_bot()
    pub = Publisher(
        harness.settings, session_factory, ChannelSender(bot, CHANNEL), RecordingNotifier()
    )  # type: ignore[arg-type]
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED and res.job_id == job.id
    channel_post, note = session.sent(SendMessage)
    assert channel_post.chat_id == CHANNEL
    assert note.chat_id == USER and "t.me/ayvonajobs/" in note.text
