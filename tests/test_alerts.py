"""🔔 Alerts (Bosqich 13): subscriptions (limits, duplicates), delivery in the worker (cursor,
one message per user, never twice, daily limit + digest, blocked users), and the bot screens."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.bot.alerts_render import render_alert, render_digest
from ayvona.config import Settings
from ayvona.db.models import AlertDelivery, AlertStatus, Job, Subscription
from ayvona.services import alerts as svc
from ayvona.services import users as users_svc
from ayvona.services.alerts import AlertService, CreateResult
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow
from tests.fake_bot import FakeBotSession, make_bot
from tests.test_admin_bot import BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.test_search import job
from tests.worker_helpers import SF, make_settings

ALI, VALI = 1001, 1002


def settings(**alerts: Any) -> Settings:
    s = make_settings()
    app = s.app.model_copy(
        update={"alerts": s.app.alerts.model_copy(update={"per_second": 30, **alerts})}
    )
    return s.model_copy(update={"app": app})


async def users(sf: SF, *ids: int) -> None:
    async with sf() as s, s.begin():
        for uid in ids:
            await users_svc.touch_user(s, uid, f"u{uid}", "U", utcnow())


async def subscribe(sf: SF, user_id: int, st: Settings | None = None, **f: Any) -> CreateResult:
    async with sf() as s, s.begin():
        result, _ = await svc.create_subscription(
            s, user_id, SearchFilters(**f), utcnow(), st or settings()
        )
    return result


def service(sf: SF, st: Settings | None = None) -> tuple[AlertService, FakeBotSession]:
    bot, session = make_bot()
    return AlertService(st or settings(), sf, bot, render_alert, render_digest), session


def to(session: FakeBotSession, user_id: int) -> list[str]:
    return [r.text for r in session.sent(SendMessage) if r.chat_id == user_id]


# ------------------------------------------------------------------ subscriptions
async def test_create_limits_and_duplicates(session_factory: SF) -> None:
    await users(session_factory, ALI)
    st = settings(max_per_user=2)
    assert await subscribe(session_factory, ALI, st, category="sotuv") is CreateResult.CREATED
    assert await subscribe(session_factory, ALI, st, category="sotuv") is CreateResult.DUPLICATE
    assert await subscribe(session_factory, ALI, st) is CreateResult.EMPTY
    assert await subscribe(session_factory, ALI, st, region="samarqand") is CreateResult.CREATED
    assert await subscribe(session_factory, ALI, st, keyword="kassir") is CreateResult.LIMIT


# ------------------------------------------------------------------ delivery
async def test_alerts_once_per_user_and_never_twice(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI, VALI)
    await subscribe(sf, ALI, category="sotuv")
    await subscribe(sf, ALI, region="toshkent_sh")  # both match: still ONE message
    await subscribe(sf, VALI, category="oshxona")  # does not match
    alerts, session = service(sf)

    old = await job(sf, "Eski sotuvchi", minutes_ago=60, region="toshkent_sh")
    assert await alerts.process_once() == 0  # first start: cursor = now, old jobs are not news
    new = await job(sf, "Sotuvchi", minutes_ago=0, region="toshkent_sh")
    async with sf() as s, s.begin():  # published after the cursor
        await s.execute(
            update(Job).where(Job.id == new).values(published_at=utcnow() + timedelta(seconds=1))
        )

    assert await alerts.process_once(utcnow() + timedelta(seconds=2)) == 1
    [msg] = to(session, ALI)
    assert msg.startswith("🔔 <b>Yangi e'lon</b>") and "💼 <b>Sotuvchi</b>" in msg
    assert to(session, VALI) == []
    async with sf() as s:
        rows = (await s.scalars(select(AlertDelivery))).all()
    assert {r.job_id for r in rows} == {new} and len(rows) == 2  # both subscriptions recorded
    assert old not in {r.job_id for r in rows}

    assert await alerts.process_once(utcnow() + timedelta(seconds=3)) == 0  # never twice


async def test_paused_subscription_and_keyword(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI, VALI)
    await subscribe(sf, ALI, keyword="ОШПАЗ")  # Cyrillic keyword, Latin job
    await subscribe(sf, VALI, category="oshxona")
    async with sf() as s, s.begin():
        vali_sub = (await s.scalars(select(Subscription).where(Subscription.user_id == VALI))).one()
        assert await svc.set_active(s, VALI, vali_sub.id, False)
    alerts, session = service(sf)
    await alerts.process_once(utcnow() - timedelta(minutes=5))
    await job(sf, "Tajribali oshpaz", category="oshxona", minutes_ago=0)
    await alerts.process_once()
    assert len(to(session, ALI)) == 1 and to(session, VALI) == []


async def test_daily_limit_then_evening_digest(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI)
    await subscribe(sf, ALI, category="sotuv")
    alerts, session = service(sf, settings(daily_limit=2))
    await alerts.process_once(utcnow() - timedelta(minutes=10))
    for i in range(4):
        await job(sf, f"Sotuvchi {i}", minutes_ago=5 - i)
    assert await alerts.process_once() == 2
    assert len(to(session, ALI)) == 2
    async with sf() as s:
        statuses = sorted(r.status for r in (await s.scalars(select(AlertDelivery))).all())
    assert statuses == [AlertStatus.DIGEST, AlertStatus.DIGEST, AlertStatus.SENT, AlertStatus.SENT]

    assert await alerts.send_digests(force=True) == 1
    digest = to(session, ALI)[-1]
    assert digest.startswith("📬") and "2 ta" in digest and "Sotuvchi 3" in digest
    async with sf() as s:
        left = (
            await s.scalars(select(AlertDelivery).where(AlertDelivery.status == AlertStatus.DIGEST))
        ).all()
    assert left == []
    assert await alerts.send_digests(force=False) == 0  # once a day


async def test_banned_user_gets_no_alerts(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI)
    await subscribe(sf, ALI, category="sotuv")
    async with sf() as s, s.begin():
        await users_svc.set_banned(s, ALI, True, utcnow())
    alerts, session = service(sf)
    await alerts.process_once(utcnow() - timedelta(minutes=5))
    await job(sf, "Sotuvchi", minutes_ago=0)
    assert await alerts.process_once() == 0 and to(session, ALI) == []


async def test_blocked_user_loses_subscriptions(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI)
    await subscribe(sf, ALI, category="sotuv")
    alerts, session = service(sf)
    await alerts.process_once(utcnow() - timedelta(minutes=5))
    await job(sf, "Sotuvchi", minutes_ago=0)
    session.fail(403, "Forbidden: bot was blocked by the user")
    assert await alerts.process_once() == 0
    async with sf() as s:
        assert not (await s.scalars(select(Subscription))).one().is_active


async def test_flood_wait_is_waited_and_retried(session_factory: SF) -> None:
    sf = session_factory
    await users(sf, ALI)
    await subscribe(sf, ALI, category="sotuv")
    alerts, session = service(sf)
    await alerts.process_once(utcnow() - timedelta(minutes=5))
    await job(sf, "Sotuvchi", minutes_ago=0)
    session.fail(429, "Too Many Requests: retry after 1", retry_after=1)
    assert await alerts.process_once() == 1
    assert len(to(session, ALI)) == 2  # the refused try + the retry


# ------------------------------------------------------------------ bot screens
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def test_subscription_wizard_and_list(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update(T.MENU_ALERTS, uid=ALI))
    assert harness.texts()[-1] == T.SUBS_EMPTY
    for data in ("sub:new:0", "al:cat:sotuv", "al:prof:*", "al:reg:toshkent_sh", "al:sal:4000000"):
        await harness.send(callback_update(data, uid=ALI))
    await harness.send(message_update(T.BTN_SKIP, uid=ALI))
    assert harness.texts()[-1].startswith("✅ Obuna yaratildi")
    assert "Toshkent sh." in harness.texts()[-1] and "4 mln+" in harness.texts()[-1]

    await harness.send(message_update(T.MENU_ALERTS, uid=ALI))
    assert "1. " in harness.texts()[-1] and T.SUBS_ACTIVE in harness.texts()[-1]
    async with session_factory() as s:
        sub = (await s.scalars(select(Subscription))).one()
    assert sub.min_salary == 4_000_000 and sub.region == "toshkent_sh" and sub.keyword is None

    await harness.send(callback_update(f"sub:pause:{sub.id}", uid=ALI))
    assert T.SUBS_PAUSED in harness.texts()[-1]
    await harness.send(callback_update(f"sub:resume:{sub.id}", uid=ALI))
    assert T.SUBS_ACTIVE in harness.texts()[-1]
    await harness.send(callback_update(f"sub:del:{sub.id}", uid=VALI))  # not his: nothing
    await harness.send(callback_update(f"sub:del:{sub.id}", uid=ALI))
    async with session_factory() as s:
        assert (await s.scalars(select(Subscription))).all() == []


async def test_subscribe_from_search_results(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update(T.MENU_SEARCH, uid=ALI))
    await harness.send(callback_update("sq:kw:", uid=ALI))
    await harness.send(message_update("oshpaz", uid=ALI))
    await harness.send(callback_update("sub:fromsearch:0", uid=ALI))
    assert (
        harness.texts()[-1].startswith("✅ Obuna yaratildi") and "«oshpaz»" in harness.texts()[-1]
    )
    async with session_factory() as s:
        assert (await s.scalars(select(Subscription))).one().keyword == "oshpaz"


async def test_keyword_step_rejects_one_letter(harness: BotHarness) -> None:
    for data in ("sub:new:0", "al:cat:*", "al:reg:*", "al:sal:0"):
        await harness.send(callback_update(data, uid=ALI))
    await harness.send(message_update("x", uid=ALI))
    assert harness.texts()[-1] == T.SEARCH_BAD_KEYWORD
    await harness.send(message_update(T.BTN_SKIP, uid=ALI))  # no filter at all -> refused
    assert harness.texts()[-1] == T.SUBS_EMPTY_FILTERS
