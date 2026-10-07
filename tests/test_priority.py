"""Priority ranking: office / high-pay jobs first, junk last, nothing important lost.

Scoring rules (config driven), the publishing order, anti-starvation, the bottom tier's daily cap,
per-tier staleness, search order, the pipeline / reformat / backfill, the admin's /why."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select

from ayvona.config import PriorityConfig, Settings
from ayvona.db.models import Job, JobOrigin, JobStatus
from ayvona.db.repositories import jobs_repo
from ayvona.processing.pipeline import Pipeline
from ayvona.processing.priority import BOTTOM, NORMAL, TOP, PriorityScorer, monthly_uzs
from ayvona.publisher.outbox import (
    ChannelSender,
    Outcome,
    Publisher,
    skip_old_jobs,
    tier_age_limits,
)
from ayvona.services import search as search_svc
from ayvona.services.priority_backfill import backfill_priority, backfill_priority_step
from ayvona.services.reformat import reformat_queued
from ayvona.services.search import SearchFilters
from ayvona.timeutil import utcnow
from tests.fake_bot import CHANNEL, make_bot
from tests.test_admin_bot import ADMIN, STRANGER, BotHarness, message_update
from tests.test_public_bot import bot_settings
from tests.test_search import job as published_job
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


def with_priority(settings: Settings, **changes: Any) -> Settings:
    pri = settings.app.priority.model_copy(update=changes)
    return settings.model_copy(update={"app": settings.app.model_copy(update={"priority": pri})})


@pytest.fixture(scope="module")
def scorer() -> PriorityScorer:
    return PriorityScorer(make_settings())


# ------------------------------------------------------------------ scoring rules
@pytest.mark.parametrize(
    ("title", "extra", "tier"),
    [
        # --- tier 1: office / professional roles, in every spelling
        ("Buxgalter", {"profession": "buxgalter", "category": "moliya"}, TOP),
        ("Bosh buxgalter kerak", {}, TOP),
        ("Бухгалтер", {}, TOP),
        ("Менеджер по продажам", {}, TOP),
        ("Sotuv menejeri", {"profession": "sotuv_menejeri", "category": "sotuv"}, TOP),
        ("Software engineer", {}, TOP),
        ("Python developer", {"category": "it"}, TOP),
        ("Marketolog", {"profession": "marketolog"}, TOP),
        ("Grafik dizayner", {}, TOP),
        ("Юрист", {}, TOP),
        ("Ingliz tili o'qituvchisi", {}, TOP),
        ("HR menejer", {}, TOP),
        ("Data analyst", {}, TOP),
        # --- clearly high pay is tier 1 on its own
        ("Haydovchi", {"salary_min": 10_000_000, "currency": "UZS", "salary_period": "month"}, TOP),
        ("Haydovchi", {"salary_min": 700, "currency": "USD", "salary_period": "month"}, TOP),
        # --- tier 3: low-skill small jobs
        ("Ishchi kerak", {"profession": "ishchi", "category": "ombor"}, BOTTOM),
        ("Ishchilar", {}, BOTTOM),
        ("Рабочий", {}, BOTTOM),
        ("Worker", {}, BOTTOM),
        ("Kuryer", {"profession": "kuryer", "category": "transport"}, BOTTOM),
        ("Курьер", {}, BOTTOM),
        ("Yuk tashuvchi", {"profession": "yuk_tashuvchi"}, BOTTOM),
        ("Грузчик", {}, BOTTOM),
        ("Call operator", {"profession": "operator", "category": "operator"}, BOTTOM),
        ("Sotuvchi-kassir", {"profession": "sotuvchi", "category": "sotuv"}, BOTTOM),
        ("Продавец-кассир", {}, BOTTOM),
        ("Farrosh", {}, BOTTOM),
        ("Уборщица", {}, BOTTOM),
        ("Idish yuvuvchi", {"profession": "idish_yuvuvchi"}, BOTTOM),
        # --- everything else is normal
        ("Haydovchi", {}, NORMAL),
        ("Oshpaz", {"profession": "oshpaz", "category": "oshxona"}, NORMAL),
        ("Sotuvchi", {"profession": "sotuvchi", "category": "sotuv"}, NORMAL),
        ("Kassir", {"profession": "kassir"}, NORMAL),
        ("Elektrik", {}, NORMAL),
        (None, {}, NORMAL),
    ],
)
def test_tiers(scorer: PriorityScorer, title: str | None, extra: dict[str, Any], tier: int) -> None:
    got = scorer.score(title=title, **extra)
    assert got.tier == tier, got.reason


def test_a_well_paid_low_skill_job_is_not_junk_and_not_top(scorer: PriorityScorer) -> None:
    """Courier at 12 mln: the "low" rule and the high pay cancel out -> normal, not tier 3."""
    p = scorer.score(
        title="Kuryer",
        profession="kuryer",
        salary_min=12_000_000,
        currency="UZS",
        salary_period="month",
    )
    assert p.tier == NORMAL and p.score == 0


def test_low_pay_pushes_a_mild_role_down(scorer: PriorityScorer) -> None:
    assert scorer.score(title="Sotuvchi", profession="sotuvchi").tier == NORMAL
    cheap = scorer.score(
        title="Sotuvchi",
        profession="sotuvchi",
        salary_min=2_000_000,
        currency="UZS",
        salary_period="month",
    )
    assert cheap.tier == BOTTOM


def test_only_a_wholly_high_range_counts_as_high_pay(scorer: PriorityScorer) -> None:
    mixed = scorer.score(
        title="Haydovchi",
        salary_min=6_000_000,
        salary_max=12_000_000,
        currency="UZS",
        salary_period="month",
    )
    assert mixed.tier == NORMAL  # the bottom of the range is not "clearly high"


def test_strongest_rule_counts_once(scorer: PriorityScorer) -> None:
    """Profession, title word and category all say "accountant": +3, not +6."""
    p = scorer.score(title="Buxgalter", profession="buxgalter", category="moliya")
    assert p.score == 3 and "kasb buxgalter" in p.reason


def test_reason_explains_the_score(scorer: PriorityScorer) -> None:
    p = scorer.score(
        title="Software engineer",
        category="it",
        salary_min=900,
        currency="USD",
        salary_period="month",
    )
    assert p.reason.startswith("daraja 1 (ball +5):")
    assert "sarlavha:" in p.reason and "maosh" in p.reason
    assert p.fields() == {
        "priority_tier": 1,
        "priority_score": 5,
        "priority_reason": p.reason,
    }


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((5_000_000, None, "UZS", "month"), (5_000_000, 5_000_000)),
        ((None, 3_000_000, "UZS", None), (3_000_000, 3_000_000)),
        ((500, 700, "USD", "month"), (6_400_000, 8_960_000)),
        ((300_000, None, "UZS", "day"), (6_600_000, 6_600_000)),
        ((50_000, None, "UZS", "hour"), (8_800_000, 8_800_000)),
        ((1_000_000, None, "UZS", "week"), (4_300_000, 4_300_000)),
        ((1000, None, "XYZ", "month"), (None, None)),
        ((None, None, "UZS", "month"), (None, None)),
        ((1000, None, "UZS", "year"), (None, None)),
    ],
)
def test_monthly_uzs(args: tuple[Any, ...], expected: tuple[float | None, float | None]) -> None:
    assert monthly_uzs(*args, usd_rate=12_800) == expected


def test_word_lists_come_from_the_config_not_the_code() -> None:
    custom = with_priority(
        make_settings(),
        high_keywords=["sirk"],
        low_keywords=["bog'bon"],
        high_professions=[],
        low_professions=[],
        mild_low_professions=[],
        high_categories=[],
    )
    s = PriorityScorer(custom)
    assert s.score(title="Sirk artisti").tier == TOP
    assert s.score(title="Bog'bon kerak").tier == BOTTOM
    assert s.score(title="Buxgalter").tier == NORMAL  # not in the edited list any more


def test_disabled_ranking_is_all_normal() -> None:
    off = PriorityScorer(with_priority(make_settings(), enabled=False))
    assert off.score(title="Buxgalter").tier == NORMAL
    assert off.score(title="Ishchi").tier == NORMAL


def test_bad_tier_limits_are_refused() -> None:
    with pytest.raises(ValueError, match="tier3_at"):
        PriorityConfig(tier1_at=0, tier3_at=1)


# ------------------------------------------------------------------ publishing order
def publisher(sf: SF, tmp_path: Path, **priority: Any) -> tuple[Publisher, Any]:
    make_image(tmp_path / "images", "boshqa/1.jpg")
    bot, session = make_bot()
    settings = with_priority(make_settings(tmp_path / "images"), **priority)
    return Publisher(settings, sf, ChannelSender(bot, CHANNEL), None), session


async def queued(sf: SF, tier: int | None, minutes_old: int, **kw: Any) -> int:
    return await add_job(
        sf,
        priority_tier=tier,
        created_at=utcnow() - timedelta(minutes=minutes_old),
        title=f"T{tier}-{minutes_old}",
        **kw,
    )


async def publish_all(pub: Publisher, n: int) -> list[int | None]:
    out: list[int | None] = []
    for _ in range(n):
        res = await pub.publish_next()
        out.append(res.job_id if res.outcome is Outcome.PUBLISHED else None)
    return out


async def test_best_tier_first_then_newest(session_factory: SF, tmp_path: Path) -> None:
    sf = session_factory
    low_old = await queued(sf, 3, 300)
    normal_old = await queued(sf, 2, 200)
    top_old = await queued(sf, 1, 100)
    low_new = await queued(sf, 3, 5)
    normal_new = await queued(sf, 2, 10)
    top_new = await queued(sf, 1, 20)
    unscored = await queued(sf, None, 50)  # not scored yet = normal
    pub, _ = publisher(sf, tmp_path)
    got = await publish_all(pub, 8)
    # tier 1 first: the one created 20 minutes ago is newer than the one from 100 minutes ago
    assert got[:2] == [top_new, top_old]
    assert got[2:5] == [normal_new, unscored, normal_old]
    assert got[5:7] == [low_new, low_old]
    assert got[7] is None  # nothing left


async def test_oldest_first_within_a_tier_when_configured(
    session_factory: SF, tmp_path: Path
) -> None:
    sf = session_factory
    a = await queued(sf, 2, 100)
    b = await queued(sf, 2, 10)
    top = await queued(sf, 1, 5)
    pub, _ = publisher(sf, tmp_path, within_tier="oldest")
    assert await publish_all(pub, 3) == [top, a, b]


async def test_ranking_off_keeps_the_old_order(session_factory: SF, tmp_path: Path) -> None:
    sf = session_factory
    first = await add_job(sf, priority_tier=3, next_retry_at=utcnow() - timedelta(minutes=30))
    second = await add_job(sf, priority_tier=1, next_retry_at=utcnow() - timedelta(minutes=10))
    pub, _ = publisher(sf, tmp_path, enabled=False)
    assert await publish_all(pub, 2) == [first, second]  # by due time, tiers ignored


async def test_a_flood_of_junk_never_pushes_out_a_top_job(
    session_factory: SF, tmp_path: Path
) -> None:
    """Anti-starvation: 60 low-tier jobs queued first, then one tier-1 job -> it goes next."""
    sf = session_factory
    for i in range(60):
        await queued(sf, 3, 600 - i)
    top = await queued(sf, 1, 1)
    pub, _ = publisher(sf, tmp_path, tier3_max_per_day=0)
    res = await pub.publish_next()
    assert res.outcome is Outcome.PUBLISHED and res.job_id == top


async def test_bottom_tier_daily_cap_never_blocks_better_jobs(
    session_factory: SF, tmp_path: Path
) -> None:
    sf = session_factory
    lows = [await queued(sf, 3, 100 - i) for i in range(4)]
    pub, _ = publisher(sf, tmp_path, tier3_max_per_day=2)

    first = await publish_all(pub, 4)
    assert [j for j in first if j] == [lows[3], lows[2]]  # newest first, then the cap is used up
    assert first[2:] == [None, None]  # the other two wait: nothing is sent

    normal = await queued(sf, 2, 1)  # a better job arrives: not held back by the cap
    assert (await pub.publish_next()).job_id == normal
    assert (await pub.publish_next()).outcome is Outcome.IDLE

    # 24 hours later the cap is free again
    async with session_factory() as s:
        done = await jobs_repo.count_published_tier(s, 3, utcnow() - timedelta(hours=24))
        later = await jobs_repo.count_published_tier(s, 3, utcnow() + timedelta(hours=1))
    assert done == 2 and later == 0


async def test_cap_off_with_zero(session_factory: SF, tmp_path: Path) -> None:
    sf = session_factory
    for i in range(3):
        await queued(sf, 3, 10 + i)
    pub, _ = publisher(sf, tmp_path, tier3_max_per_day=0)
    assert all(j is not None for j in await publish_all(pub, 3))


# ------------------------------------------------------------------ staleness per tier
def test_age_limits_per_tier() -> None:
    s = make_settings()  # publisher.max_age_hours = 24
    assert tier_age_limits(s) == {1: 48, 2: 24, 3: 12}
    assert tier_age_limits(with_priority(s, enabled=False)) == {1: 24, 2: 24, 3: 24}
    short = with_priority(s, tier3_max_age_hours=100)  # never longer than the normal limit
    assert tier_age_limits(short)[3] == 24
    assert tier_age_limits(with_priority(s, tier1_max_age_hours=0))[1] == 24


async def test_long_queue_costs_the_cheapest_jobs_first(session_factory: SF) -> None:
    sf = session_factory
    now = utcnow()
    settings = make_settings()
    top_30h = await add_job_from_post(sf, timedelta(hours=30), now=now, priority_tier=1)
    normal_30h = await add_job_from_post(sf, timedelta(hours=30), now=now, priority_tier=2)
    unscored_30h = await add_job_from_post(sf, timedelta(hours=30), now=now)
    low_13h = await add_job_from_post(sf, timedelta(hours=13), now=now, priority_tier=3)
    low_11h = await add_job_from_post(sf, timedelta(hours=11), now=now, priority_tier=3)
    normal_13h = await add_job_from_post(sf, timedelta(hours=13), now=now, priority_tier=2)
    top_50h = await add_job_from_post(sf, timedelta(hours=50), now=now, priority_tier=1)

    skipped = await skip_old_jobs(settings, sf, now)
    assert sorted(skipped) == sorted([normal_30h, unscored_30h, low_13h, top_50h])
    for kept in (top_30h, low_11h, normal_13h):
        assert (await get_job(sf, kept)).status is JobStatus.QUEUED
    assert "12 soatdan" in ((await get_job(sf, low_13h)).last_error or "")
    assert "48 soatdan" in ((await get_job(sf, top_50h)).last_error or "")


async def test_user_ads_are_never_aged_out_by_tier(session_factory: SF) -> None:
    ad = await add_job(session_factory, priority_tier=3, origin=JobOrigin.USER)
    assert await skip_old_jobs(make_settings(), session_factory, utcnow() + timedelta(days=9)) == []
    assert (await get_job(session_factory, ad)).status is JobStatus.QUEUED


# ------------------------------------------------------------------ search order
async def test_search_shows_the_best_tier_first(session_factory: SF) -> None:
    sf = session_factory
    low_new = await published_job(sf, "Kuryer", minutes_ago=1, priority_tier=3)
    top_old = await published_job(sf, "Buxgalter", minutes_ago=500, priority_tier=1)
    normal = await published_job(sf, "Haydovchi", minutes_ago=50, priority_tier=2)
    unscored = await published_job(sf, "Oshpaz", minutes_ago=20)
    top_new = await published_job(sf, "Dasturchi", minutes_ago=100, priority_tier=1)
    async with sf() as s:
        found, total = await search_svc.search(
            s, SearchFilters(), utcnow(), usd_rate=12_800, limit=10
        )
    assert total == 5
    assert [j.id for j in found] == [top_new, top_old, unscored, normal, low_new]


# ------------------------------------------------------------------ the pipeline scores new jobs
BUX = (
    "Buxgalter kerak\nMaosh: 6 000 000 so'm\nManzil: Toshkent, Chilonzor tumani\n"
    "Talablar: tajriba, 1C bilimi\nMurojaat uchun: +998901234567"
)
COURIER = (
    "Kuryer kerak\nMaosh: 3 000 000 so'm\nManzil: Toshkent, Yunusobod tumani\n"
    "Talablar: mas'uliyatli\nMurojaat uchun: +998907654321"
)


async def test_pipeline_gives_every_new_job_its_tier(session_factory: SF) -> None:
    sf = session_factory
    src = await add_source(sf)
    await add_raw(sf, src, BUX)
    await add_raw(sf, src, COURIER)
    await Pipeline(make_settings(), sf, None).run_once()  # type: ignore[arg-type]
    async with sf() as s:
        jobs = {j.title: j for j in (await s.scalars(select(Job))).all()}
    bux = next(j for t, j in jobs.items() if "uxgalter" in t)
    courier = next(j for t, j in jobs.items() if "uryer" in t)
    assert bux.priority_tier == TOP and "kasb buxgalter" in (bux.priority_reason or "")
    assert courier.priority_tier == BOTTOM and courier.priority_score is not None


async def test_editing_the_word_lists_rescores_the_waiting_queue(session_factory: SF) -> None:
    """The start-up re-render (reformat) applies the CURRENT settings.yaml to queued jobs."""
    sf = session_factory
    src = await add_source(sf)
    await add_raw(sf, src, COURIER)
    await Pipeline(make_settings(), sf, None).run_once()  # type: ignore[arg-type]
    [job] = await _all(sf)
    assert job.priority_tier == BOTTOM

    edited = with_priority(make_settings(), low_keywords=[], low_professions=[])
    report = await reformat_queued(edited, sf)
    assert report.updated == 1
    assert (await get_job(sf, job.id)).priority_tier == NORMAL


async def _all(sf: SF) -> list[Job]:
    async with sf() as s:
        return list((await s.scalars(select(Job).order_by(Job.id))).all())


# ------------------------------------------------------------------ backfill
async def test_backfill_scores_old_jobs_once_and_is_safe(session_factory: SF) -> None:
    sf = session_factory
    settings = make_settings()
    a = await add_job(sf, title="Bosh buxgalter", status=JobStatus.PUBLISHED)
    b = await add_job(sf, title="Kuryer", profession="kuryer", status=JobStatus.QUEUED)
    c = await add_job(sf, title="Haydovchi", status=JobStatus.EXPIRED)
    done = await add_job(sf, title="Ishchi", priority_tier=1, priority_score=9)  # already scored

    dry = await backfill_priority(settings, sf, dry_run=True)
    assert dry.scored == 3 and (await get_job(sf, a)).priority_tier is None  # nothing written

    report = await backfill_priority(settings, sf)
    assert (report.scored, report.tiers[1], report.tiers[2], report.tiers[3]) == (3, 1, 1, 1)
    assert [(await get_job(sf, j)).priority_tier for j in (a, b, c)] == [1, 3, 2]
    assert (await get_job(sf, done)).priority_tier == 1  # untouched without --all
    assert (await backfill_priority(settings, sf)).scored == 0  # idempotent

    redo = await backfill_priority(settings, sf, rescore_all=True)
    assert redo.scored == 4 and (await get_job(sf, done)).priority_tier == BOTTOM


async def test_backfill_step_never_stops_the_worker(session_factory: SF) -> None:
    await add_job(session_factory, title="Buxgalter")
    assert await backfill_priority_step(make_settings(), session_factory) == 1
    broken = make_settings().model_copy(update={"app": None})  # any failure inside is swallowed
    assert await backfill_priority_step(broken, session_factory) == 0  # type: ignore[arg-type]


# ------------------------------------------------------------------ admin: /why and /queue
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def test_why_explains_a_job_to_the_admin_only(
    harness: BotHarness, session_factory: SF
) -> None:
    ad = await add_job(
        session_factory,
        title="Bosh buxgalter",
        priority_tier=1,
        priority_score=5,
        priority_reason="daraja 1 (ball +5): sarlavha: buxgalter (+2)",
    )
    await harness.send(message_update(f"/why {ad}", uid=ADMIN))
    text = harness.texts()[-1]
    assert "Bosh buxgalter" in text and "daraja 1 (ball +5)" in text
    assert "Hozirgi qoidalar bo'yicha" in text

    await harness.send(message_update("/why", uid=ADMIN))
    assert harness.texts()[-1].startswith("Ishlatish")
    await harness.send(message_update("/why 99999", uid=ADMIN))
    assert "topilmadi" in harness.texts()[-1]

    before = len(harness.session.sent(SendMessage))
    await harness.send(message_update(f"/why {ad}", uid=STRANGER))  # not an admin: no answer
    assert len(harness.session.sent(SendMessage)) == before


async def test_queue_lists_the_best_tier_first(harness: BotHarness, session_factory: SF) -> None:
    await add_job(session_factory, title="Past", priority_tier=3)
    await add_job(session_factory, title="Yuqori", priority_tier=1)
    await harness.send(message_update("/queue", uid=ADMIN))
    text = harness.texts()[-1]
    assert text.index("Yuqori") < text.index("Past") and "1-daraja" in text
