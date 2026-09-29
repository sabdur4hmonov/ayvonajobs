"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

_ENV_KEYS = (
    "API_ID",
    "API_HASH",
    "TELETHON_SESSION",
    "BOT_TOKEN",
    "CHANNEL_ID",
    "ADMIN_IDS",
    "ADMIN_CHAT_ID",
    "DB_PATH",
    "LOG_LEVEL",
    "TZ",
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never pick up the developer's real environment variables."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
