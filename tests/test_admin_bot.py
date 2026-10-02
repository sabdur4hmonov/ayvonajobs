"""Admin bot (Bosqich 8) through aiogram's Dispatcher with the mocked Bot API: commands, sources
and pictures managed from the bot, admin-only access. Nothing leaves the machine."""

from __future__ import annotations

import itertools
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import Update
from sqlalchemy import select

from ayvona.bot.handlers.admin import eta_text
from ayvona.bot.handlers.admin_images import ImageDelCb, resolve_target
from ayvona.bot.handlers.admin_sources import AddSourceCb, SourceCb
from ayvona.bot.setup import build_dispatcher
from ayvona.config import Settings
from ayvona.db.models import JobStatus, Source, SourceAddedVia, SourceStatus
from ayvona.db.repositories import kv_repo
from tests.fake_bot import FakeBotSession, make_bot
from tests.worker_helpers import (
    SF,
    add_job,
    add_job_from_post,
    add_raw,
    add_source,
    get_job,
    make_image,
    make_settings,
)

ADMIN = 111
STRANGER = 222
_ids = itertools.count(1)


def _user(uid: int) -> dict[str, Any]:
    return {"id": uid, "is_bot": False, "first_name": "Sardor", "username": f"u{uid}"}


def _message(text: str | None, uid: int, **extra: Any) -> dict[str, Any]:
    n = next(_ids)
    msg: dict[str, Any] = {
        "message_id": n,
        "date": 1_790_000_000,
        "chat": {"id": uid, "type": "private"},
        "from": _user(uid),
        **extra,
    }
    if text is not None:
        msg["text"] = text
    return msg


def message_update(text: str | None, uid: int = ADMIN, **extra: Any) -> Update:
    return Update.model_validate({"update_id": next(_ids), "message": _message(text, uid, **extra)})


def callback_update(data: str, uid: int = ADMIN) -> Update:
    return Update.model_validate(
        {
            "update_id": next(_ids),
            "callback_query": {
                "id": str(next(_ids)),
                "from": _user(uid),
                "chat_instance": "ci",
                "data": data,
                "message": _message("old", uid),
            },
        }
    )


class BotHarness:
    def __init__(self, settings: Settings, sf: SF) -> None:
        self.settings = settings
        self.sf = sf
        self.bot: Bot
        self.bot, self.session = make_bot()
        self.dp: Dispatcher = build_dispatcher(settings, sf)

    async def send(self, update: Update) -> None:
        await self.dp.feed_update(self.bot, update)

    def texts(self) -> list[str]:
        return [
            r.text for r in self.session.requests if isinstance(r, SendMessage | EditMessageText)
        ]

    @property
    def last(self) -> Any:
        return [r for r in self.session.requests if isinstance(r, SendMessage | EditMessageText)][
            -1
        ]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = make_settings(tmp_path / "images", db_file=tmp_path / "data" / "ayvona.db")
    app = s.app.model_copy(update={"bot": s.app.bot.model_copy(update={"throttle_seconds": 0})})
    return s.model_copy(update={"env": s.env.model_copy(update={"admin_ids": [ADMIN]}), "app": app})


@pytest.fixture
def harness(settings: Settings, session_factory: SF) -> BotHarness:
    return BotHarness(settings, session_factory)


FakeBotSession  # re-exported for type checkers  # noqa: B018


# ------------------------------------------------------------------ access
async def test_only_admins_get_admin_commands(harness: BotHarness) -> None:
    await harness.send(message_update("/stats", uid=STRANGER))
    await harness.send(message_update("/start", uid=STRANGER))
    texts = harness.texts()
    assert len(texts) == 1 and "Assalomu alaykum" in texts[0]  # public /start only, no /stats

    await harness.send(message_update("/help"))
    assert "Admin buyruqlari" in harness.texts()[-1]


# ------------------------------------------------------------------ stats / queue / retry / pause
async def test_stats_and_queue(harness: BotHarness, session_factory: SF) -> None:
    src = await add_source(session_factory)
    await add_raw(session_factory, src, "x")
    await add_job(session_factory)
    await harness.send(message_update("/stats"))
    stats = harness.texts()[-1]
    assert "Keldi (post): 1 / 1" in stats
    assert "Navbat: 1 ta, taxminan 1 daqiqada chiqadi" in stats
    assert "Collector ⚪️" in stats

    await harness.send(message_update("/queue"))
    assert "Kutmoqda: 1" in harness.texts()[-1] and "Sotuvchi" in harness.texts()[-1]


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "1 daqiqa"),
        (40 * 60, "40 daqiqa"),
        (60 * 60, "1 soat"),
        (90 * 60, "1,5 soat"),
        (9 * 3600, "9 soat"),
        (26.4 * 3600, "26 soat"),
    ],
)
def test_queue_eta_text(seconds: float, text: str) -> None:
    assert eta_text(timedelta(seconds=seconds)) == text


async def test_failed_retry_pause_resume(harness: BotHarness, session_factory: SF) -> None:
    job_id = await add_job(session_factory, status=JobStatus.FAILED, attempts=8)
    await harness.send(message_update("/failed"))
    assert f"#{job_id}" in harness.texts()[-1]

    await harness.send(message_update("/retry"))
    assert "Ishlatish" in harness.texts()[-1]
    await harness.send(message_update(f"/retry {job_id}"))
    assert "1 ta" in harness.texts()[-1]
    job = await get_job(session_factory, job_id)
    assert job.status is JobStatus.QUEUED and job.attempts == 0

    await harness.send(message_update("/pause"))
    async with session_factory() as s:
        assert await kv_repo.get_bool(s, kv_repo.PUBLISHER_PAUSED)
    await harness.send(message_update("/resume"))
    async with session_factory() as s:
        assert not await kv_repo.get_bool(s, kv_repo.PUBLISHER_PAUSED)


async def test_retry_of_a_too_old_job_says_why(harness: BotHarness, session_factory: SF) -> None:
    old = await add_job_from_post(
        session_factory, timedelta(hours=30), status=JobStatus.FAILED, attempts=8
    )
    fresh = await add_job_from_post(
        session_factory, timedelta(hours=2), status=JobStatus.FAILED, attempts=8
    )

    await harness.send(message_update("/retry all"))
    reply = harness.texts()[-1]
    assert "1 ta e'lon qayta navbatga" in reply
    assert "eskirgan: 24 soatdan eski" in reply and f"#{old}" in reply
    assert (await get_job(session_factory, old)).status is JobStatus.SKIPPED_OLD
    assert (await get_job(session_factory, fresh)).status is JobStatus.QUEUED

    # only too old ones asked for: no "qayta navbatga" line, just the reason
    other = await add_job_from_post(session_factory, timedelta(days=2), status=JobStatus.FAILED)
    await harness.send(message_update(f"/retry {other}"))
    reply = harness.texts()[-1]
    assert "qayta navbatga" not in reply and "eskirgan" in reply

    await harness.send(message_update("/stats"))
    assert "Eskirgan (chiqmadi): 2 / 2" in harness.texts()[-1]


# ------------------------------------------------------------------ sources
async def test_addsource_asks_backfill_then_queues_pending(
    harness: BotHarness, session_factory: SF
) -> None:
    await harness.send(message_update("/addsource https://t.me/yangi_kanal"))
    ask = harness.last
    assert "@yangi_kanal" in ask.text
    buttons = [b.callback_data for b in ask.reply_markup.inline_keyboard[0]]
    assert buttons == [AddSourceCb(n=n, ident="@yangi_kanal").pack() for n in (0, 5, 20)]

    await harness.send(callback_update(AddSourceCb(n=5, ident="@yangi_kanal").pack()))
    assert "So'rov qabul qilindi" in harness.texts()[-1]
    async with session_factory() as s:
        src = (await s.scalars(select(Source))).one()
    assert src.identifier == "@yangi_kanal" and src.status is SourceStatus.PENDING
    assert src.added_via is SourceAddedVia.BOT and src.added_by == ADMIN
    assert src.backfill_request == 5 and src.enabled is False


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("", "Ishlatish"),
        ("salom dunyo", "Tushunmadim"),
        ("web:hh_uz", "HH_ACCESS_TOKEN"),
        ("web:olx", "kod yo'q"),
    ],
)
async def test_addsource_other_inputs(harness: BotHarness, arg: str, expected: str) -> None:
    await harness.send(message_update(f"/addsource {arg}".strip()))
    assert expected in harness.texts()[-1]


async def test_addsource_existing_channel(harness: BotHarness, session_factory: SF) -> None:
    await add_source(session_factory, "@bor_kanal")
    await harness.send(message_update("/addsource @bor_kanal"))
    assert "allaqachon" in harness.texts()[-1]


async def test_sources_list_card_pause_resume_delete(
    harness: BotHarness, session_factory: SF
) -> None:
    src_id = await add_source(session_factory, "@kanal_a")
    await harness.send(message_update("/sources"))
    listing = harness.last
    assert "@kanal_a" in listing.text
    show = SourceCb(action="show", id=src_id).pack()
    assert listing.reply_markup.inline_keyboard[0][0].callback_data == show

    await harness.send(callback_update(show))
    assert "ishlayapti" in harness.texts()[-1]
    await harness.send(callback_update(SourceCb(action="pause", id=src_id).pack()))
    assert "pauzaga" in harness.texts()[-1]
    async with session_factory() as s:
        assert (await s.get(Source, src_id)).enabled is False  # type: ignore[union-attr]
    await harness.send(callback_update(SourceCb(action="resume", id=src_id).pack()))
    async with session_factory() as s:
        assert (await s.get(Source, src_id)).enabled is True  # type: ignore[union-attr]

    await harness.send(callback_update(SourceCb(action="stats", id=src_id).pack()))
    assert "Jami post: 0" in harness.texts()[-1]

    await harness.send(callback_update(SourceCb(action="del", id=src_id).pack()))
    assert "o'chirilsinmi" in harness.texts()[-1]
    await harness.send(callback_update(SourceCb(action="delok", id=src_id).pack()))
    async with session_factory() as s:
        src = await s.get(Source, src_id)
    assert src is not None  # the row (and its posts) stay
    assert src.status is SourceStatus.DELETED and src.enabled is False
    await harness.send(message_update("/sources"))
    assert "@kanal_a" not in harness.texts()[-1]


# ------------------------------------------------------------------ images
async def test_images_overview_and_folder(harness: BotHarness, settings: Settings) -> None:
    root = settings.images_dir
    make_image(root, "oshxona/oshpaz/1.jpg")
    make_image(root, "oshxona/placeholder_1.jpg")
    await harness.send(message_update("/images"))
    report = "\n".join(harness.texts())
    assert "oshxona" in report and "Kategoriya uchun kamida 3" in report

    await harness.send(message_update("/images oshpaz"))
    folder = harness.last
    assert "1.jpg" in folder.text
    assert folder.reply_markup.inline_keyboard[0][0].callback_data == (
        ImageDelCb(key="oshpaz", name="1.jpg").pack()
    )
    await harness.send(message_update("/images yoq_narsa"))
    assert "bunday kasb" in harness.texts()[-1]


async def test_addimage_saves_the_picture(harness: BotHarness, settings: Settings) -> None:
    await harness.send(message_update("/addimage #oshpaz"))
    assert "rasm yuboring" in harness.texts()[-1]
    photo = [
        {"file_id": "small", "file_unique_id": "s", "width": 90, "height": 51},
        {"file_id": "BIG", "file_unique_id": "b", "width": 1280, "height": 720},
    ]
    await harness.send(message_update(None, photo=photo))
    assert "Saqlandi" in harness.texts()[-1]
    saved = settings.images_dir / "oshxona" / "oshpaz" / "1.jpg"
    assert saved.is_file() and saved.read_bytes() == harness.session.download_bytes

    await harness.send(message_update(None, photo=photo))  # second one -> 2.jpg
    assert (saved.parent / "2.jpg").is_file()

    harness.session.download_bytes = b"not an image"
    await harness.send(message_update(None, photo=photo))
    assert "rasm emas" in harness.texts()[-1]
    assert not (saved.parent / "3.jpg").exists()

    await harness.send(message_update("/cancel"))
    assert "Bekor" in harness.texts()[-1]


async def test_deleting_a_picture_moves_it_to_trash(
    harness: BotHarness, settings: Settings
) -> None:
    path = make_image(settings.images_dir, "oshxona/oshpaz/1.jpg")
    await harness.send(callback_update(ImageDelCb(key="oshpaz", name="1.jpg").pack()))
    assert not path.exists()
    trash = list((settings.data_dir / "images_trash" / "oshxona" / "oshpaz").iterdir())
    assert len(trash) == 1 and trash[0].name.endswith("_1.jpg")
    # a crafted name cannot escape the folder
    await harness.send(callback_update(ImageDelCb(key="oshpaz", name="../x.jpg").pack()))
    assert len(list(trash[0].parent.iterdir())) == 1


def test_resolve_target(settings: Settings) -> None:
    t = resolve_target(settings, "#Oshpaz")
    assert t is not None and (t.category, t.profession) == ("oshxona", "oshpaz")
    c = resolve_target(settings, "oshxona")
    assert c is not None and c.profession is None
    assert resolve_target(settings, "yo'q") is None
