"""LiteBot (the collector's httpx-only admin notifier) and the import-weight guard that keeps the
collector free of aiogram and the bot free of Telethon (RAM on a 1 GB server)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from ayvona.litebot import LiteBot, LiteBotError
from ayvona.services.notifier import Notifier

TOKEN = "123456789:AAE-secret_token_value_0123456789"
ROOT = Path(__file__).resolve().parents[1]


async def test_send_message_shape_and_notifier_integration() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {}})

    bot = LiteBot(TOKEN, transport=httpx.MockTransport(handler))
    notifier = Notifier(bot, -100123, None)  # type: ignore[arg-type]
    assert await notifier.send("<b>salom</b>") is True
    assert seen["url"] == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert seen["body"] == {
        "chat_id": -100123,
        "text": "<b>salom</b>",
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    await bot.session.close()


async def test_errors_never_contain_the_token() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"ok": False, "description": "Forbidden: bot was blocked"})

    bot = LiteBot(TOKEN, transport=httpx.MockTransport(refuse))
    with pytest.raises(LiteBotError, match="403") as info:
        await bot.send_message(1, "x")
    assert TOKEN not in str(info.value)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    bot2 = LiteBot(TOKEN, transport=httpx.MockTransport(down))
    with pytest.raises(LiteBotError) as info2:
        await bot2.send_message(1, "x")
    assert TOKEN not in str(info2.value) and info2.value.__cause__ is None
    # the Notifier swallows it (never raises) and reports "not sent"
    assert await Notifier(bot2, 1, None).send("x") is False  # type: ignore[arg-type]


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        LiteBot("not-a-token")


def _loaded(module: str) -> set[str]:
    code = (
        "import sys, importlib; importlib.import_module(sys.argv[1]); "
        "print(','.join(m for m in ('aiogram', 'telethon', 'fastapi') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, module],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout.strip()
    return set(filter(None, out.split(",")))


@pytest.mark.parametrize(
    ("module", "must_not_load"),
    [
        ("ayvona.apps.collector", {"aiogram", "fastapi"}),  # telethon IS the collector's job
        ("ayvona.apps.bot", {"telethon", "fastapi"}),
        ("ayvona.apps.worker", {"telethon", "fastapi"}),
        ("ayvona.apps.web", {"aiogram", "telethon"}),
    ],
)
def test_processes_do_not_import_what_they_do_not_use(module: str, must_not_load: set[str]) -> None:
    assert _loaded(module) & must_not_load == set()
