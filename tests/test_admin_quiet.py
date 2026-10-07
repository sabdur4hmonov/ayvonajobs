"""The admin is NOT spammed: the only push is "a new user ad waits for approval". Errors, silent
process alerts, backups, suspicious posts ... go to the log. ``ADMIN_EXTRA_NOTIFICATIONS=true``
brings the old messages back. Mocked Bot API only."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from aiogram.methods import SendDocument, SendMessage
from loguru import logger

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.db.repositories import kv_repo
from ayvona.publisher.outbox import ChannelSender, Outcome, Publisher
from ayvona.services.backup import BackupService
from ayvona.services.heartbeat import Monitor
from ayvona.services.notifier import Notifier, for_settings, plain
from ayvona.timeutil import utcnow
from tests.fake_bot import ADMIN_CHAT, CHANNEL, make_bot
from tests.worker_helpers import SF, add_job, make_settings

DB = "<b>Backup</b> tayyor"


def admin_messages(session) -> list[object]:  # noqa: ANN001
    return [r for r in session.requests if isinstance(r, SendMessage | SendDocument)]


@pytest.fixture
def log_lines():  # noqa: ANN201
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="INFO", format="{message}")
    yield lines
    logger.remove(sink)


# ------------------------------------------------------------------ the gate
async def test_quiet_notifier_sends_nothing_but_logs(log_lines: list[str]) -> None:
    bot, session = make_bot()
    n = Notifier(bot, ADMIN_CHAT, None, extra_enabled=False)
    assert await n.send("🔴 <b>Collector jim</b>: 30 daqiqa") is False
    assert await n.send_document(Path("data/backups/x.db"), DB) is False
    assert admin_messages(session) == []
    joined = "\n".join(log_lines)
    assert "faqat logda" in joined and "Collector jim: 30 daqiqa" in joined  # tags stripped


async def test_reply_to_an_admin_command_is_still_delivered() -> None:
    """``chat_id`` given = the answer to something that admin asked (the /addsource result)."""
    bot, session = make_bot()
    n = Notifier(bot, ADMIN_CHAT, None, extra_enabled=False)
    assert await n.send("✅ kanal qo'shildi", chat_id=777) is True
    [req] = admin_messages(session)
    assert req.chat_id == 777


async def test_flag_brings_the_old_messages_back() -> None:
    bot, session = make_bot()
    n = Notifier(bot, ADMIN_CHAT, None, extra_enabled=True)
    assert await n.send("⚠️ eski xabar") is True
    assert len(admin_messages(session)) == 1


def test_env_flag_defaults_off_and_for_settings_follows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADMIN_EXTRA_NOTIFICATIONS", raising=False)
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    assert s.env.admin_extra_notifications is False
    assert for_settings(None, s).extra_enabled is False
    env = tmp_path / ".env"
    env.write_text("ADMIN_EXTRA_NOTIFICATIONS=true\n", encoding="utf-8")
    on = load_settings(DEFAULT_CONFIG_DIR, env_file=env)
    assert for_settings(None, on).extra_enabled is True
    env.write_text("ADMIN_EXTRA_NOTIFICATIONS=\n", encoding="utf-8")  # blank = default (off)
    assert load_settings(DEFAULT_CONFIG_DIR, env_file=env).env.admin_extra_notifications is False


def test_plain_makes_one_log_line() -> None:
    assert plain("<b>A</b> &amp; b\n\n<code>c</code>") == "A & b | c"


# ------------------------------------------------------------------ the real code paths
async def test_monitoring_alerts_stay_in_the_log(session_factory: SF, log_lines: list[str]) -> None:
    bot, session = make_bot()
    notifier = Notifier(bot, ADMIN_CHAT, session_factory, extra_enabled=False)
    mon = Monitor(make_settings(), session_factory, notifier, ("collector",))
    now = utcnow()
    async with session_factory() as s, s.begin():
        await kv_repo.write_heartbeat(s, "collector", now - timedelta(minutes=30))
    sent = await mon.check(now)  # the check itself still works and still returns its findings
    assert len(sent) == 1 and "Collector jim" in sent[0]
    assert admin_messages(session) == []
    assert any("Collector jim" in line for line in log_lines)


async def test_backup_is_kept_on_the_server_and_not_uploaded(
    session_factory: SF, tmp_path: Path
) -> None:
    import sqlite3

    db = tmp_path / "ayvona.db"
    sqlite3.connect(db).executescript("create table t(x); insert into t values (1);")
    settings = make_settings(db_file=db, backup_dir=tmp_path / "backups")
    bot, session = make_bot()
    svc = BackupService(
        settings, session_factory, Notifier(bot, ADMIN_CHAT, None, extra_enabled=False)
    )
    path = await svc.run_backup()
    assert path.exists()  # the local copy is made
    assert admin_messages(session) == []  # but not pushed to Telegram


async def test_failed_publish_does_not_ping_the_admin(
    session_factory: SF, log_lines: list[str]
) -> None:
    bot, session = make_bot()
    notifier = Notifier(bot, ADMIN_CHAT, session_factory, extra_enabled=False)
    settings = make_settings(publisher={"max_publish_attempts": 1})
    pub = Publisher(settings, session_factory, ChannelSender(bot, CHANNEL), notifier)
    await add_job(session_factory)
    session.fail(400, "Bad Request: chat not found")  # a setup problem
    assert (await pub.publish_next()).outcome is Outcome.CONFIG
    session.network_error()  # the only allowed attempt fails -> the job is given up
    assert (await pub.publish_next(utcnow() + timedelta(hours=2))).outcome is Outcome.FAILED
    to_admin = [r for r in admin_messages(session) if r.chat_id == ADMIN_CHAT]
    assert to_admin == []
    assert any(
        "Kanalga yuborib bo'lmadi" in line or "kanalga chiqmadi" in line for line in log_lines
    )
