"""🔓 The admin's unfiltered alerts (services/admin_alerts.py): every collected post that names the
subscribed profession — before any filter, published or not, with the reason — never twice, with
an hourly cap + digest, flood waits; normal users keep the filtered alerts. Mocked Bot API."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram.methods import EditMessageText, SendMessage
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.bot.alerts_render import (
    render_admin_alert,
    render_admin_digest,
    render_alert,
    render_digest,
)
from ayvona.config import EnvSettings, Settings
from ayvona.db.models import (
    AdminAlertDelivery,
    AdminAlertStatus,
    Job,
    JobStatus,
    RawPost,
    RawPostStatus,
    Subscription,
)
from ayvona.db.repositories import kv_repo
from ayvona.processing.normalize import fold
from ayvona.services import admin_alerts as svc
from ayvona.services import alerts as alerts_svc
from ayvona.services import users as users_svc
from ayvona.services.admin_alerts import CURSOR_KEY, AdminAlertService
from ayvona.services.alerts import AlertService
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow
from tests.fake_bot import FakeBotSession, make_bot
from tests.test_admin_bot import ADMIN, BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, add_job, add_raw, add_source, make_settings

USER = 5005  # a normal user
MANAGER_POST = "Kompaniyaga sotuv menejeri kerak. Maosh 6 mln. Tel: +998 90 123 45 67"


def settings(*, flag: bool = True, **cfg: Any) -> Settings:
    s = make_settings()
    env = s.env.model_copy(update={"admin_ids": [ADMIN], "admin_unfiltered_alerts": flag})
    admin_cfg = s.app.admin_alerts.model_copy(update={"send_delay_seconds": 0, **cfg})
    app = s.app.model_copy(
        update={
            "admin_alerts": admin_cfg,
            "alerts": s.app.alerts.model_copy(update={"per_second": 30}),
        }
    )
    return s.model_copy(update={"env": env, "app": app})


def category_of(st: Settings, profession: str) -> str:
    return next(k for k, c in st.categories.items() if profession in c.professions)


async def subscribe(sf: SF, user_id: int, st: Settings, **f: Any) -> Subscription:
    async with sf() as s, s.begin():
        await users_svc.touch_user(s, user_id, f"u{user_id}", "U", utcnow() - timedelta(days=1))
        result, sub = await alerts_svc.create_subscription(
            s, user_id, SearchFilters(**f), utcnow() - timedelta(hours=1), st
        )
    assert sub is not None, result
    return sub


async def subscribe_manager(sf: SF, st: Settings, user_id: int = ADMIN) -> Subscription:
    return await subscribe(
        sf, user_id, st, category=category_of(st, "menejer"), profession="menejer"
    )


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def service(sf: SF, st: Settings) -> tuple[AdminAlertService, FakeBotSession, Sleeps]:
    bot, session = make_bot()
    sleeps = Sleeps()
    return (
        AdminAlertService(st, sf, bot, render_admin_alert, render_admin_digest, sleep=sleeps),
        session,
        sleeps,
    )


def to(session: FakeBotSession, user_id: int) -> list[str]:
    return [r.text for r in session.sent(SendMessage) if r.chat_id == user_id]


async def start(alerts: AdminAlertService) -> None:
    """First start: the cursor is set to "now" (the newest stored post), nothing is sent."""
    assert await alerts.process_once() == 0


async def link_job(sf: SF, raw_id: int, job_id: int, status: RawPostStatus) -> None:
    async with sf() as s, s.begin():
        await s.execute(
            update(RawPost).where(RawPost.id == raw_id).values(job_id=job_id, status=status)
        )


async def deliveries(sf: SF) -> list[AdminAlertDelivery]:
    async with sf() as s:
        return list((await s.scalars(select(AdminAlertDelivery))).all())


# ------------------------------------------------------------------ words / matching
def test_words_and_matching_cover_scripts_and_languages() -> None:
    st = settings()
    sub = Subscription(
        id=1,
        user_id=ADMIN,
        category=category_of(st, "menejer"),
        profession="menejer",
        is_active=True,
        created_at=utcnow(),
    )
    words = {fold(w) for w in svc.words_of(sub, st)}  # once each, case / script folded
    assert {fold(w) for w in ("menejer", "manager", "менеджер", "rahbar")} <= words
    matcher = svc.Matcher([sub], st)
    for text in (
        "Filialga MENEJER kerak",
        "Требуется менеджер по продажам",
        "Hiring: Office Manager (Tashkent)",
        "Bo'lim rahbari lavozimiga",
        "Менежер керак, иш вақти 9-18",  # Uzbek Cyrillic
    ):
        assert ADMIN in matcher.match(text), text
    assert matcher.match("Oshpaz kerak, tel +998901234567") == {}
    assert matcher.match("") == {}

    normal = Subscription(id=2, user_id=USER, profession="menejer", is_active=True)
    assert not svc.is_unfiltered(normal, st)  # not an admin
    assert not svc.is_unfiltered(sub, settings(flag=False))  # mode switched off
    only_region = Subscription(id=3, user_id=ADMIN, region="samarqand", is_active=True)
    assert not svc.is_unfiltered(only_region, st)  # nothing to look for: stays a normal one


def test_env_flag_default_on_blank_on_false_off() -> None:
    assert EnvSettings(_env_file=None).admin_unfiltered_alerts is True
    assert EnvSettings(_env_file=None, admin_unfiltered_alerts="").admin_unfiltered_alerts is True
    assert (
        EnvSettings(_env_file=None, admin_unfiltered_alerts="false").admin_unfiltered_alerts
        is False
    )


# ------------------------------------------------------------------ delivery before every filter
async def test_posts_the_pipeline_drops_still_reach_the_admin(session_factory: SF) -> None:
    sf = session_factory
    st = settings()
    await subscribe_manager(sf, st)
    alerts, session, _ = service(sf, st)
    src = await add_source(sf, "@ishlar_kanal")
    await start(alerts)

    # 1) not a job ad according to the classifier
    await add_raw(
        sf, src, "Menejerlar uchun bepul trening!", status=RawPostStatus.NOT_JOB, external_id="11"
    )
    # 2) a duplicate of an ad that is still waiting in the queue, low tier
    queued = await add_job(sf, status=JobStatus.QUEUED, priority_tier=3)
    dup = await add_raw(sf, src, MANAGER_POST + " (nusxa)", external_id="12")
    await link_job(sf, dup, queued, RawPostStatus.DUPLICATE)
    # 3) too old: its job became skipped_old (never published)
    old_job = await add_job(sf, status=JobStatus.SKIPPED_OLD, last_error="24 soatdan eski")
    old = await add_raw(sf, src, "Manager kerak", posted_ago=timedelta(days=3), external_id="13")
    await link_job(sf, old, old_job, RawPostStatus.DONE)
    # 4) the worker never got to it (AI wait, crash ...): sent anyway after the wait
    await add_raw(sf, src, "Rahbar o'rinbosari kerak", fetched_ago=timedelta(minutes=5))
    # 5) published in our channel
    pub_job = await add_job(sf, status=JobStatus.PUBLISHED, channel_message_id=77)
    pub = await add_raw(sf, src, MANAGER_POST, external_id="15")
    async with sf() as s, s.begin():
        await s.execute(update(Job).where(Job.id == pub_job).values(raw_post_id=pub))
    await link_job(sf, pub, pub_job, RawPostStatus.DONE)
    # not about managers: nothing
    await add_raw(sf, src, "Oshpaz kerak", status=RawPostStatus.DONE, external_id="16")

    assert await alerts.process_once() == 5
    msgs = to(session, ADMIN)
    assert len(msgs) == 5 and all(m.startswith("🔓 <b>Filtrsiz obuna</b>") for m in msgs)
    assert "ish e'loni emas" in msgs[0]
    assert "dublikat" in msgs[1] and "navbatda (daraja 3)" in msgs[1]
    assert "eskirgan" in msgs[2] and "24 soatdan eski" in msgs[2]
    assert "hali ko'rib chiqilmagan" in msgs[3]
    assert T.ADM_ALERT_PUBLISHED in msgs[4] and "Kanalga chiqmadi" not in msgs[4]
    assert all("Oshpaz" not in m for m in msgs)

    # buttons: the original post and (when published) our channel post, and 🔄
    last = session.sent(SendMessage)[-1]
    urls = [b.url for row in last.reply_markup.inline_keyboard for b in row if b.url]
    assert "https://t.me/ishlar_kanal/15" in urls
    assert any(u.endswith("/77") for u in urls)
    assert last.parse_mode == "HTML"


async def test_waits_briefly_for_the_workers_decision(session_factory: SF) -> None:
    sf = session_factory
    st = settings(decision_wait_seconds=120)
    await subscribe_manager(sf, st)
    alerts, session, _ = service(sf, st)
    src = await add_source(sf)
    await start(alerts)
    raw = await add_raw(sf, src, "Menejer kerak", fetched_ago=timedelta(seconds=10))
    later = await add_raw(sf, src, "Menejer kerak 2", status=RawPostStatus.NOT_JOB)

    assert await alerts.process_once() == 0  # not decided yet: keep the order, wait
    async with sf() as s:
        assert await kv_repo.get(s, CURSOR_KEY) == str(raw - 1)
    async with sf() as s, s.begin():
        await s.execute(
            update(RawPost).where(RawPost.id == raw).values(status=RawPostStatus.NO_CONTACT)
        )
    assert await alerts.process_once() == 2
    assert "aloqa yo'q" in to(session, ADMIN)[0]
    async with sf() as s:
        assert await kv_repo.get(s, CURSOR_KEY) == str(later)


# ------------------------------------------------------------------ never twice
async def test_never_twice_after_restart_recollection_or_two_subscriptions(
    session_factory: SF,
) -> None:
    sf = session_factory
    st = settings()
    await subscribe_manager(sf, st)
    await subscribe(sf, ADMIN, st, keyword="sotuv menejeri")  # also matches: still ONE message
    alerts, session, _ = service(sf, st)
    src = await add_source(sf)
    await start(alerts)
    await add_raw(sf, src, MANAGER_POST, status=RawPostStatus.DUPLICATE)
    assert await alerts.process_once() == 1
    assert len(await deliveries(sf)) == 1

    # restart with a lost cursor (or the post collected again): nothing new is sent
    async with sf() as s, s.begin():
        await kv_repo.set_value(s, CURSOR_KEY, "0")
    again, session2, _ = service(sf, st)
    assert await again.process_once() == 0
    assert to(session2, ADMIN) == [] and len(to(session, ADMIN)) == 1


async def test_first_start_and_posts_before_the_subscription(session_factory: SF) -> None:
    sf = session_factory
    st = settings()
    src = await add_source(sf)
    await add_raw(sf, src, "Menejer kerak (eski)", status=RawPostStatus.DONE)
    sub = await subscribe_manager(sf, st)
    alerts, session, _ = service(sf, st)
    await start(alerts)  # the old post is not news
    # collected before the subscription was made (cursor behind, e.g. the worker was down)
    async with sf() as s, s.begin():
        await kv_repo.set_value(s, CURSOR_KEY, "0")
        await s.execute(
            update(Subscription).where(Subscription.id == sub.id).values(created_at=utcnow())
        )
    assert await alerts.process_once() == 0 and to(session, ADMIN) == []


# ------------------------------------------------------------------ normal users / mode off
async def test_normal_users_keep_filtered_alerts_and_admin_is_not_doubled(
    session_factory: SF,
) -> None:
    sf = session_factory
    st = settings()
    await subscribe_manager(sf, st)
    await subscribe_manager(sf, st, user_id=USER)
    admin_svc, admin_session, _ = service(sf, st)
    bot, normal_session = make_bot()
    normal = AlertService(st, sf, bot, render_alert, render_digest)
    src = await add_source(sf)
    await start(admin_svc)
    await normal.process_once(utcnow() - timedelta(minutes=5))

    raw = await add_raw(sf, src, MANAGER_POST)
    job_id = await add_job(
        sf,
        status=JobStatus.PUBLISHED,
        channel_message_id=5,
        title="Sotuv menejeri",
        category=category_of(st, "menejer"),
        profession="menejer",
        raw_post_id=raw,
        published_at=utcnow(),
    )
    await link_job(sf, raw, job_id, RawPostStatus.DONE)

    assert await admin_svc.process_once() == 1
    assert to(admin_session, USER) == []  # the unfiltered mode is admins only
    assert await normal.process_once() == 1
    assert len(to(normal_session, USER)) == 1  # the normal filtered alert, as before
    assert to(normal_session, ADMIN) == []  # the admin already has it (unfiltered)
    # the worker's Bot has no default parse mode: the HTML must be asked for explicitly
    assert normal_session.sent(SendMessage)[0].parse_mode == "HTML"


async def test_mode_off_admin_gets_normal_alerts_only(session_factory: SF) -> None:
    sf = session_factory
    st = settings(flag=False)
    await subscribe_manager(sf, st)
    alerts, session, _ = service(sf, st)
    src = await add_source(sf)
    assert await alerts.process_once() == 0
    await add_raw(sf, src, MANAGER_POST, status=RawPostStatus.NOT_JOB)
    assert await alerts.process_once() == 0 and to(session, ADMIN) == []
    async with sf() as s:
        assert await kv_repo.get(s, CURSOR_KEY) is None


# ------------------------------------------------------------------ flood protection
async def test_hourly_cap_then_one_digest(session_factory: SF) -> None:
    sf = session_factory
    st = settings(max_per_hour=2, digest_minutes=60)
    await subscribe_manager(sf, st)
    alerts, session, _ = service(sf, st)
    src = await add_source(sf, "@kanal_b")
    await start(alerts)
    for i in range(5):
        await add_raw(sf, src, f"Menejer kerak #{i}", status=RawPostStatus.NOT_JOB)

    assert await alerts.process_once() == 2
    statuses = sorted(r.status for r in await deliveries(sf))
    assert statuses == [AdminAlertStatus.DIGEST] * 3 + [AdminAlertStatus.SENT] * 2
    assert await alerts.send_digests() == 0  # not before digest_minutes
    assert await alerts.send_digests(utcnow() + timedelta(minutes=61)) == 1
    digest = to(session, ADMIN)[-1]
    assert digest.startswith("📬") and "3 ta post" in digest
    assert "Menejer kerak #4" in digest and "t.me/kanal_b/" in digest
    assert sorted(r.status for r in await deliveries(sf)) == (
        [AdminAlertStatus.DIGEST_SENT] * 3 + [AdminAlertStatus.SENT] * 2
    )
    assert await alerts.send_digests(force=True) == 0  # never twice
    assert len(to(session, ADMIN)) == 3


async def test_flood_wait_is_waited_and_network_error_is_retried_in_digest(
    session_factory: SF,
) -> None:
    sf = session_factory
    st = settings(send_delay_seconds=0.5)
    await subscribe_manager(sf, st)
    alerts, session, sleeps = service(sf, st)
    src = await add_source(sf)
    await start(alerts)
    await add_raw(sf, src, "Menejer kerak A", status=RawPostStatus.NOT_JOB)
    session.fail(429, "Too Many Requests: retry after 3", retry_after=3)
    assert await alerts.process_once() == 1
    assert sleeps.calls == [4, 0.5]  # retry_after + 1, then the normal pause
    assert len(to(session, ADMIN)) == 2  # the refused try + the retry

    await add_raw(sf, src, "Menejer kerak B", status=RawPostStatus.NOT_JOB)
    session.network_error()
    assert await alerts.process_once() == 0
    [row] = [r for r in await deliveries(sf) if r.status is not AdminAlertStatus.SENT]
    assert row.status is AdminAlertStatus.DIGEST  # not lost: it goes in the digest
    assert await alerts.send_digests(force=True) == 1
    assert "Menejer kerak B" in to(session, ADMIN)[-1]


def test_digest_is_split_into_parts_with_their_ids() -> None:
    st = settings()
    views = [
        svc.AlertView(
            raw=RawPost(id=i, source_id=1, external_id=str(i), text="Menejer " + "x" * 90),
            source=None,
            job=None,
            subscription=None,
            hits=(),
            state=svc.PostState(False, "ish e'loni emas deb topildi"),
            url=f"https://t.me/k/{i}",
        )
        for i in range(1, 61)
    ]
    parts = render_admin_digest(st, views)
    assert len(parts) > 1
    assert [i for _, ids in parts for i in ids] == list(range(1, 61))
    assert all(len(text) <= 3600 for text, _ in parts)


# ------------------------------------------------------------------ bot: /alerts, 🔄, wizard
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def test_alerts_command_lists_and_cancels(harness: BotHarness, session_factory: SF) -> None:
    sub = await subscribe_manager(session_factory, harness.settings)
    await harness.send(message_update("/alerts", uid=ADMIN))
    text = harness.texts()[-1]
    assert T.SUBS_UNFILTERED in text and "Filtrsiz" in text and "Menejer" in text
    await harness.send(callback_update(f"sub:del:{sub.id}", uid=ADMIN))
    async with session_factory() as s:
        assert (await s.scalars(select(Subscription))).all() == []


async def test_wizard_tells_the_admin_the_subscription_is_unfiltered(
    harness: BotHarness,
) -> None:
    cat = category_of(harness.settings, "menejer")
    for data in ("sub:new:0", f"al:cat:{cat}", "al:prof:menejer", "al:reg:*", "al:sal:0"):
        await harness.send(callback_update(data, uid=ADMIN))
    await harness.send(message_update(T.BTN_SKIP, uid=ADMIN))
    assert (
        harness.texts()[-1].startswith("✅ Obuna yaratildi") and "filtrsiz" in harness.texts()[-1]
    )


async def test_refresh_button_shows_the_current_state(
    harness: BotHarness, session_factory: SF
) -> None:
    sf = session_factory
    sub = await subscribe_manager(sf, harness.settings)
    src = await add_source(sf)
    raw = await add_raw(sf, src, MANAGER_POST)
    job_id = await add_job(sf, status=JobStatus.QUEUED, priority_tier=2)
    await link_job(sf, raw, job_id, RawPostStatus.DONE)
    async with sf() as s:
        view = await svc.view_for(s, raw, sub.id, harness.settings)
    assert (
        view is not None and "navbatda (daraja 2)" in render_admin_alert(harness.settings, view)[0]
    )

    async with sf() as s, s.begin():  # meanwhile it reached the channel
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.PUBLISHED, channel_message_id=9, raw_post_id=raw)
        )
    await harness.send(callback_update(f"aa:{raw}:{sub.id}", uid=ADMIN))
    [edit] = harness.session.sent(EditMessageText)
    assert T.ADM_ALERT_PUBLISHED in edit.text and "sotuv menejeri" in edit.text.lower()
