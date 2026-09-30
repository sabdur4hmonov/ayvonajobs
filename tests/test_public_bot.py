"""Public bot foundation (Bosqich 10): /start + users, main menu, deep links (save_<id>,
job_<id>, search), ⭐ favorites, middlewares (ban, throttling).
Mocked Bot API — nothing leaves the machine."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.config import Settings
from ayvona.db.models import Favorite, Job, JobStatus, User
from ayvona.services import users as users_svc
from ayvona.timeutil import utcnow
from tests.test_admin_bot import ADMIN, STRANGER, BotHarness, callback_update, message_update
from tests.worker_helpers import SF, add_job, make_settings

USER = 333


def bot_settings(tmp_path: Path, throttle: float = 0) -> Settings:
    s = make_settings(tmp_path / "images", db_file=tmp_path / "data" / "ayvona.db")
    app = s.app.model_copy(
        update={"bot": s.app.bot.model_copy(update={"throttle_seconds": throttle})}
    )
    return s.model_copy(update={"env": s.env.model_copy(update={"admin_ids": [ADMIN]}), "app": app})


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def published_job(
    sf: SF, *, status: JobStatus = JobStatus.PUBLISHED, msg_id: int = 77
) -> int:
    job_id = await add_job(sf, status=status)
    async with sf() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job_id).values(channel_message_id=msg_id))
    return job_id


def messages(h: BotHarness) -> list[SendMessage]:
    return h.session.sent(SendMessage)


# ------------------------------------------------------------------ /start, menu, users
async def test_start_registers_user_and_shows_the_menu(
    harness: BotHarness, session_factory: SF
) -> None:
    await harness.send(message_update("/start", uid=USER))
    [msg] = messages(harness)
    assert "Assalomu alaykum" in msg.text and "@ayvonajobs" in msg.text
    assert isinstance(msg.reply_markup, ReplyKeyboardMarkup)
    buttons = [b.text for row in msg.reply_markup.keyboard for b in row]
    assert buttons == [
        T.MENU_POST,
        T.MENU_SEARCH,
        T.MENU_FAVORITES,
        T.MENU_ALERTS,
        T.MENU_MY_JOBS,
        T.MENU_HELP,
    ]
    async with session_factory() as s:
        user = await s.get(User, USER)
    assert user is not None and user.username == f"u{USER}" and user.last_active_at is not None
    assert user.trust_level == 0


async def test_admin_gets_the_menu_too_and_admin_help(
    harness: BotHarness, session_factory: SF
) -> None:
    await harness.send(message_update("/start"))
    assert "Assalomu alaykum" in harness.texts()[-1]
    await harness.send(message_update("/help"))
    assert "Admin buyruqlari" in harness.texts()[-1]
    await harness.send(message_update("/help", uid=USER))
    assert "Yordam" in harness.texts()[-1] and "Admin" not in harness.texts()[-1]
    async with session_factory() as s:
        admin = await s.get(User, ADMIN)
    assert admin is not None and admin.trust_level == users_svc.TRUST_ADMIN


async def test_menu_buttons(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_HELP, uid=USER))
    assert "Yordam" in harness.texts()[-1]
    await harness.send(message_update(T.MENU_FAVORITES, uid=USER))
    assert harness.texts()[-1] == T.FAV_EMPTY


# ------------------------------------------------------------------ deep links
async def test_save_deep_link_saves_and_shows_the_job(
    harness: BotHarness, session_factory: SF
) -> None:
    job_id = await published_job(session_factory)
    await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    note, card = messages(harness)
    assert note.text == T.SAVED
    assert card.text.startswith("💼 <b>Sotuvchi</b>")
    kb = card.reply_markup.inline_keyboard
    flat = [b for row in kb for b in row]
    assert any(b.text == T.BTN_UNSAVE for b in flat)
    share = next(b for b in flat if b.text == T.BTN_SHARE)
    assert share.url == "https://t.me/share/url?url=https%3A%2F%2Ft.me%2Fayvonajobs%2F77"
    async with session_factory() as s:
        assert (await s.scalars(select(Favorite))).one().job_id == job_id

    await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    assert messages(harness)[-2].text == T.ALREADY_SAVED


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.SKIPPED_OLD, JobStatus.FAILED])
async def test_job_not_in_the_channel_is_not_found(
    harness: BotHarness, session_factory: SF, status: JobStatus
) -> None:
    job_id = await published_job(session_factory, status=status)
    await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    await harness.send(message_update(f"/start job_{job_id}", uid=USER))
    await harness.send(message_update("/start save_999999", uid=USER))
    assert [m.text for m in messages(harness)] == [T.JOB_NOT_FOUND] * 3
    async with session_factory() as s:
        assert (await s.scalars(select(Favorite))).all() == []


async def test_closed_job_is_shown_marked_but_not_saved(
    harness: BotHarness, session_factory: SF
) -> None:
    job_id = await published_job(session_factory, status=JobStatus.CLOSED)
    await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    note, card = messages(harness)
    assert note.text == T.SAVE_CLOSED
    assert card.text.startswith(T.JOB_CLOSED_MARK)
    assert card.reply_markup.inline_keyboard == []  # no contact, save or share for a closed job


async def test_job_deep_link_and_search_link(harness: BotHarness, session_factory: SF) -> None:
    job_id = await published_job(session_factory)
    await harness.send(message_update(f"/start job_{job_id}", uid=USER))
    [card] = messages(harness)
    flat = [b for row in card.reply_markup.inline_keyboard for b in row]
    assert any(b.text == T.BTN_SAVE for b in flat)
    await harness.send(message_update("/start search", uid=USER))
    assert harness.texts()[-1] != ""  # the search entry answers (Bosqich 12)


# ------------------------------------------------------------------ ⭐ buttons and list
async def test_save_and_unsave_buttons(harness: BotHarness, session_factory: SF) -> None:
    job_id = await published_job(session_factory)
    await harness.send(message_update("/start", uid=USER))  # the users row
    await harness.send(callback_update(f"job:save:{job_id}", uid=USER))
    async with session_factory() as s:
        assert len((await s.scalars(select(Favorite))).all()) == 1
    [edit] = harness.session.sent(EditMessageReplyMarkup)
    assert any(b.text == T.BTN_UNSAVE for row in edit.reply_markup.inline_keyboard for b in row)

    await harness.send(callback_update(f"job:unsave:{job_id}", uid=USER))
    async with session_factory() as s:
        assert (await s.scalars(select(Favorite))).all() == []


async def test_favorites_list_pages_and_closed_mark(
    harness: BotHarness, session_factory: SF
) -> None:
    ids = [await published_job(session_factory, msg_id=100 + i) for i in range(7)]
    for job_id in ids:
        await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    async with session_factory() as s, s.begin():
        await s.execute(update(Job).where(Job.id == ids[-1]).values(status=JobStatus.CLOSED))

    await harness.send(message_update(T.MENU_FAVORITES, uid=USER))
    first = messages(harness)[-1]
    assert "7 ta (sahifa 1/2)" in first.text
    assert "1. <b>Sotuvchi</b>" in first.text and "Yopilgan" in first.text  # newest saved first
    nav = first.reply_markup.inline_keyboard[-1]
    assert [b.text for b in nav] == [T.BTN_NEXT]

    await harness.send(callback_update(nav[0].callback_data, uid=USER))
    [page2] = harness.session.sent(EditMessageText)
    assert "sahifa 2/2" in page2.text and "6. " in page2.text and "7. " in page2.text

    show = first.reply_markup.inline_keyboard[0][0].callback_data
    await harness.send(callback_update(show, uid=USER))
    assert messages(harness)[-1].text.startswith(T.JOB_CLOSED_MARK)


# ------------------------------------------------------------------ middlewares
async def test_banned_user_gets_only_the_ban_notice(
    harness: BotHarness, session_factory: SF
) -> None:
    job_id = await published_job(session_factory)
    async with session_factory() as s, s.begin():
        await users_svc.set_banned(s, USER, True, utcnow())
        await users_svc.set_banned(s, ADMIN, True, utcnow())  # an admin is never blocked
    await harness.send(message_update(f"/start save_{job_id}", uid=USER))
    await harness.send(message_update("/start", uid=USER))  # the notice is not repeated
    assert [m.text for m in messages(harness)] == [T.BANNED]
    async with session_factory() as s:
        assert (await s.scalars(select(Favorite))).all() == []
    await harness.send(message_update("/start"))
    assert "Assalomu alaykum" in harness.texts()[-1]


async def test_throttling_drops_fast_repeats_but_not_for_admins(
    tmp_path: Path, session_factory: SF
) -> None:
    h = BotHarness(bot_settings(tmp_path, throttle=60), session_factory)
    await h.send(message_update("/start", uid=USER))
    await h.send(message_update("/start", uid=USER))
    await h.send(message_update(T.MENU_HELP, uid=USER))
    assert len(h.texts()) == 1
    for _ in range(3):
        await h.send(message_update("/help"))
    assert len(h.texts()) == 4


async def test_last_active_is_not_written_on_every_message(
    harness: BotHarness, session_factory: SF
) -> None:
    await harness.send(message_update("/start", uid=USER))
    async with session_factory() as s:
        first = (await s.get(User, USER)).last_active_at  # type: ignore[union-attr]
    await harness.send(message_update(T.MENU_HELP, uid=USER))
    async with session_factory() as s:
        assert (await s.get(User, USER)).last_active_at == first  # type: ignore[union-attr]


async def test_group_messages_are_ignored(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(
        message_update("/start", uid=STRANGER, chat={"id": -100555, "type": "supergroup"})
    )
    assert harness.texts() == []
    async with session_factory() as s:
        assert await s.get(User, STRANGER) is None
