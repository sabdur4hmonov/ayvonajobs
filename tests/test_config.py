from pathlib import Path

import pytest
from pydantic import ValidationError

from ayvona.config import (
    DEFAULT_CONFIG_DIR,
    FALLBACK_CATEGORY,
    PROJECT_ROOT,
    load_settings,
)


def test_repository_config_loads() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)

    assert all(src.identifier.startswith("@") for src in s.app.sources)
    assert s.app.collector.poll_interval_seconds == 90
    assert s.app.collector.initial_backfill == 0
    assert s.app.publisher.publish_interval_seconds == 60
    assert s.app.publisher.max_publish_attempts == 8
    assert FALLBACK_CATEGORY in s.categories
    assert s.regions.regions and s.regions.remote_keywords
    assert s.filters.scam
    assert s.filters.job_markers and s.filters.closed_markers and s.filters.opportunity_markers
    assert s.source_rules.defaults.drop_link_patterns
    assert s.source_rules.for_source("@NEXTHIREX").header_junk_words == ["new", "without"]
    assert s.source_rules.for_source("@unknown_channel").cut_from == []


def test_env_defaults_without_env_file() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)

    assert s.env.api_id is None
    assert s.env.admin_ids == []
    assert s.env.tz == "Asia/Tashkent"
    assert s.db_file == PROJECT_ROOT / "data" / "ayvona.db"
    assert s.db_url.startswith("sqlite+aiosqlite:///")


def test_env_file_is_parsed(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "API_ID=12345\n"
        "API_HASH=abc\n"
        "BOT_TOKEN=\n"  # left blank -> None, not an error
        "ADMIN_IDS=111, 222,333\n"
        "ADMIN_CHAT_ID=-1001\n"
        "LOG_LEVEL=debug\n"
        f"DB_PATH={(tmp_path / 'x.db').as_posix()}\n",
        encoding="utf-8",
    )
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=env)

    assert s.env.api_id == 12345
    assert s.env.api_hash is not None and s.env.api_hash.get_secret_value() == "abc"
    assert s.env.bot_token is None
    assert s.env.admin_ids == [111, 222, 333]
    assert s.env.admin_chat_id == -1001
    assert s.env.log_level == "DEBUG"
    assert s.db_file == tmp_path / "x.db"


def test_sources_from_yaml(tmp_path: Path) -> None:
    (tmp_path / "settings.yaml").write_text(
        "sources:\n"
        "  - identifier: ' @ish_kanal '\n"
        "    own_usernames: ['@ish_kanal']\n"
        "  - type: telegram\n"
        "    identifier: '@boshqa'\n"
        "    enabled: false\n"
        "collector:\n"
        "  initial_backfill: 5\n",
        encoding="utf-8",
    )
    s = load_settings(tmp_path, env_file=None)

    assert [src.identifier for src in s.app.sources] == ["@ish_kanal", "@boshqa"]
    assert s.app.sources[0].type == "telegram"
    assert s.app.sources[1].enabled is False
    assert s.app.collector.initial_backfill == 5
    assert s.app.collector.poll_interval_seconds == 90  # default kept


def test_invalid_timezone_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "Mars/Olympus")
    with pytest.raises(ValidationError):
        load_settings(DEFAULT_CONFIG_DIR, env_file=None)
