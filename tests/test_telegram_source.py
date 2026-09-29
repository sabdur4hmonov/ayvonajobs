"""Bosqich 3: TelegramSource with a fake client and real Telethon message objects."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from telethon.errors import FloodWaitError
from telethon.tl import types

from ayvona.config import load_settings
from ayvona.db.models import Source
from ayvona.sources.base import SourceError, SourceRateLimited
from ayvona.sources.registry import (
    SourceDeps,
    UnknownSourceTypeError,
    create_source,
    registered_types,
)
from ayvona.sources.telegram_source import (
    TelegramConfigError,
    TelegramSource,
    connect_client,
    message_to_item,
    normalize_identifier,
)
from tests.fakes import FakeTelethonClient

DATE = datetime(2026, 9, 29, 6, 0, tzinfo=UTC)
PEER = types.PeerChannel(channel_id=1)


def text_msg(mid: int, text: str = "Sotuvchi kerak", **kw: object) -> types.Message:
    return types.Message(id=mid, peer_id=PEER, date=DATE, message=text, **kw)


def photo_media() -> types.MessageMediaPhoto:
    photo = types.Photo(id=1, access_hash=1, file_reference=b"", date=DATE, sizes=[], dc_id=2)
    return types.MessageMediaPhoto(photo=photo)


def service_msg(mid: int) -> types.MessageService:
    return types.MessageService(
        id=mid, peer_id=PEER, date=DATE, action=types.MessageActionChatEditTitle(title="Yangi nom")
    )


def source(client: FakeTelethonClient, **kw: int) -> TelegramSource:
    return TelegramSource("@ish_kanal", client, **kw)


# ------------------------------------------------------------------ message conversion
def test_text_message() -> None:
    item = message_to_item(text_msg(10, "Vakansiya: oshpaz"))
    assert item is not None
    assert (item.external_id, item.text, item.has_media, item.media_type) == (
        "10",
        "Vakansiya: oshpaz",
        False,
        None,
    )
    assert item.posted_at == DATE
    assert item.extra is None


def test_service_and_empty_messages_are_skipped() -> None:
    assert message_to_item(service_msg(1)) is None
    assert message_to_item(text_msg(2, "   ")) is None


def test_photo_only_post_is_kept() -> None:
    item = message_to_item(text_msg(3, "", media=photo_media(), grouped_id=555))
    assert item is not None
    assert item.text == ""
    assert item.has_media and item.media_type == "photo"
    assert item.grouped_id == 555


def test_link_preview_is_not_media() -> None:
    msg = text_msg(4, "https://example.uz", media=types.MessageMediaWebPage(types.WebPageEmpty(1)))
    item = message_to_item(msg)
    assert item is not None and not item.has_media


def test_hidden_links_and_buttons_are_saved() -> None:
    text = "Ishga taklif 👋 HR bilan bog'lanish"
    start = len("Ishga taklif 👋 ".encode("utf-16-le")) // 2  # Telegram offsets are UTF-16
    msg = text_msg(
        5,
        text,
        entities=[
            types.MessageEntityTextUrl(offset=start, length=19, url="https://t.me/hr_ayvona"),
            types.MessageEntityMentionName(offset=0, length=5, user_id=777),
        ],
        reply_markup=types.ReplyInlineMarkup(
            rows=[
                types.KeyboardButtonRow(
                    buttons=[
                        types.KeyboardButton(
                            text="Murojaat", type=types.InlineButtonTypeUrl(url="https://t.me/boss")
                        )
                    ]
                )
            ]
        ),
    )
    item = message_to_item(msg)
    assert item is not None and item.extra is not None
    assert {"text": "HR bilan bog'lanish", "url": "https://t.me/hr_ayvona"} in item.extra["links"]
    assert {"text": "Ishga", "user_id": 777} in item.extra["links"]
    assert item.extra["buttons"] == [{"text": "Murojaat", "url": "https://t.me/boss"}]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@kanal", "@kanal"),
        ("kanal", "@kanal"),
        ("t.me/kanal", "@kanal"),
        ("https://t.me/kanal/", "@kanal"),
        ("https://t.me/s/kanal", "@kanal"),
        ("-1001234567890", -1001234567890),
    ],
)
def test_normalize_identifier(raw: str, expected: str | int) -> None:
    assert normalize_identifier(raw) == expected


# ------------------------------------------------------------------ fetch_new
async def test_first_run_without_backfill_only_remembers_latest_id() -> None:
    client = FakeTelethonClient([text_msg(i) for i in range(1, 6)])
    result = await source(client, initial_backfill=0).fetch_new(None)
    assert result.items == []
    assert result.cursor == "5"


async def test_first_run_on_empty_channel() -> None:
    result = await source(FakeTelethonClient([]), initial_backfill=0).fetch_new(None)
    assert result.items == [] and result.cursor == "0"


async def test_first_run_with_backfill_takes_latest_n_oldest_first() -> None:
    client = FakeTelethonClient([text_msg(i) for i in range(1, 11)])
    result = await source(client, initial_backfill=3).fetch_new(None)
    assert [it.external_id for it in result.items] == ["8", "9", "10"]
    assert result.cursor == "10"


async def test_poll_returns_only_newer_posts_and_skips_service_messages() -> None:
    msgs = [text_msg(1), text_msg(2), service_msg(3), text_msg(4, "", media=photo_media())]
    client = FakeTelethonClient(msgs)
    result = await source(client, fetch_limit=50).fetch_new("1")

    assert [it.external_id for it in result.items] == ["2", "4"]
    assert result.cursor == "4"
    assert client.iter_calls == [{"min_id": 1, "reverse": True, "limit": 50}]
    assert client.resolved == ["@ish_kanal"]


async def test_cursor_moves_past_trailing_service_message() -> None:
    client = FakeTelethonClient([text_msg(1), service_msg(2)])
    result = await source(client).fetch_new("1")
    assert result.items == [] and result.cursor == "2"


async def test_nothing_new_keeps_cursor() -> None:
    client = FakeTelethonClient([text_msg(1), text_msg(2)])
    result = await source(client).fetch_new("2")
    assert result.items == [] and result.cursor is None


async def test_entity_resolved_once() -> None:
    client = FakeTelethonClient([text_msg(1)])
    src = source(client)
    await src.fetch_new("0")
    await src.fetch_new("1")
    assert client.resolved == ["@ish_kanal"]


async def test_flood_wait_becomes_rate_limited() -> None:
    client = FakeTelethonClient([text_msg(1)])
    client.raise_on_fetch = FloodWaitError(request=None, capture=42)
    with pytest.raises(SourceRateLimited) as info:
        await source(client).fetch_new("0")
    assert info.value.seconds == 42


async def test_unknown_channel_becomes_source_error() -> None:
    class NoSuchChannel(FakeTelethonClient):
        async def get_entity(self, identifier: object) -> str:
            raise ValueError('No user has "yoq_kanal" as username')

    with pytest.raises(SourceError, match="yoq_kanal"):
        await source(NoSuchChannel()).fetch_new(None)


# ------------------------------------------------------------------ registry / client
def test_registry_creates_telegram_source() -> None:
    settings = load_settings(env_file=None)
    deps = SourceDeps(collector=settings.app.collector, telegram_client=FakeTelethonClient())
    src = create_source(Source(identifier="@a", type="telegram"), deps)
    assert isinstance(src, TelegramSource)
    assert "telegram" in registered_types()


def test_registry_rejects_unknown_type() -> None:
    settings = load_settings(env_file=None)
    deps = SourceDeps(collector=settings.app.collector)
    with pytest.raises(UnknownSourceTypeError):
        create_source(Source(identifier="https://x.uz", type="web:x"), deps)


async def test_connect_client_requires_api_keys(tmp_path: Path) -> None:
    settings = load_settings(env_file=None)
    with pytest.raises(TelegramConfigError, match="API_ID"):
        await connect_client(settings)


async def test_connect_client_requires_session_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        f"API_ID=1\nAPI_HASH=x\nTELETHON_SESSION={(tmp_path / 'none').as_posix()}\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file=env)
    with pytest.raises(TelegramConfigError, match="login_telethon"):
        await connect_client(settings)
