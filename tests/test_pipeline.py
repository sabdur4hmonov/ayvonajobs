"""processing/pipeline.py: raw_posts(new) -> jobs(queued) with statuses, dedup and the collecting
window (ROADMAP Bosqich 7, 0 / 1 / 1b)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from ayvona.apps.worker import skip_existing_posts
from ayvona.db.models import Job, JobStatus, RawPostStatus
from ayvona.processing.pipeline import Completeness, Pipeline
from ayvona.timeutil import utcnow
from tests.worker_helpers import (
    JOB_TEXT,
    JOB_TEXT_FULL,
    SF,
    RecordingNotifier,
    add_raw,
    add_source,
    fixture_text,
    get_job,
    get_raw,
    make_settings,
)


def pipeline(sf: SF, **kw) -> tuple[Pipeline, RecordingNotifier]:
    notifier = RecordingNotifier()
    return Pipeline(make_settings(**kw), sf, notifier), notifier  # type: ignore[arg-type]


async def job_count(sf: SF) -> int:
    async with sf() as s:
        return int(await s.scalar(select(func.count()).select_from(Job)) or 0)


# ------------------------------------------------------------------ step 0: backfill
async def test_first_start_skips_posts_already_in_the_db(session_factory: SF) -> None:
    src = await add_source(session_factory)
    old = [await add_raw(session_factory, src, JOB_TEXT) for _ in range(3)]
    done = await add_raw(session_factory, src, "x", status=RawPostStatus.NOT_JOB)

    assert await skip_existing_posts(session_factory) == 3
    for raw_id in old:
        assert (await get_raw(session_factory, raw_id)).status is RawPostStatus.SKIPPED_BACKFILL
    assert (await get_raw(session_factory, done)).status is RawPostStatus.NOT_JOB

    # only once: posts collected after the first start are processed normally
    later = await add_raw(session_factory, src, JOB_TEXT)
    assert await skip_existing_posts(session_factory) is None
    assert (await get_raw(session_factory, later)).status is RawPostStatus.NEW


async def test_backfill_posts_are_skipped_unless_enabled(session_factory: SF) -> None:
    src = await add_source(session_factory)
    raw = await add_raw(session_factory, src, JOB_TEXT, is_backfill=True)
    p, _ = pipeline(session_factory)
    await p.run_once()
    assert (await get_raw(session_factory, raw)).status is RawPostStatus.SKIPPED_BACKFILL
    assert await job_count(session_factory) == 0

    raw2 = await add_raw(session_factory, src, JOB_TEXT_FULL, is_backfill=True)
    p2, _ = pipeline(session_factory, publisher={"publish_backfill": True})
    await p2.run_once()
    assert (await get_raw(session_factory, raw2)).status is RawPostStatus.DONE
    assert await job_count(session_factory) == 1


# ------------------------------------------------------------------ step 1: pipeline
async def test_job_post_becomes_a_queued_job(session_factory: SF) -> None:
    fx = fixture_text("Buxgalteriyaishorinlarii_5469")
    src = await add_source(session_factory, fx["source"])
    raw = await add_raw(session_factory, src, fx["text"], external_id=fx["external_id"])
    p, _ = pipeline(session_factory)
    stats = await p.run_once()
    assert stats.new_jobs == 1

    row = await get_raw(session_factory, raw)
    assert row.status is RawPostStatus.DONE
    assert row.job_id is not None and row.dedup_text and row.content_hash
    job = await get_job(session_factory, row.job_id)
    assert job.status is JobStatus.QUEUED
    assert job.raw_post_id == raw
    assert job.contact_phone == "+998977986722"
    assert job.formatted_text and "Moddiy ashyoviy" in job.formatted_text
    assert f"https://t.me/Buxgalteriyaishorinlarii/{fx['external_id']}" in job.formatted_text
    urls = [b["url"] for r in job.buttons or [] for b in r]
    assert f"https://t.me/ayvonabot?start=save_{job.id}" in urls
    # collecting window: 20 minutes after it was posted (5 minutes ago)
    assert job.next_retry_at is not None
    wait = job.next_retry_at - utcnow()
    assert timedelta(minutes=14) < wait <= timedelta(minutes=15, seconds=5)


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("Buxgalteriyaishorinlarii_5475", RawPostStatus.RESUME),
        ("jobs_fba_60", RawPostStatus.CLOSED),
        ("Ish_Toshkent_6737", RawPostStatus.NOT_JOB),
        ("jobmakon_1444", RawPostStatus.OPPORTUNITY),
        ("ishtopuz_rasmiy_40829", RawPostStatus.LOW_QUALITY),
    ],
)
async def test_other_kinds_get_their_status(session_factory: SF, name: str, status) -> None:
    fx = fixture_text(name)
    src = await add_source(session_factory, fx["source"])
    raw = await add_raw(session_factory, src, fx["text"], extra=fx.get("extra") or None)
    p, notifier = pipeline(session_factory)
    await p.run_once()
    assert (await get_raw(session_factory, raw)).status is status
    assert await job_count(session_factory) == 0
    assert notifier.messages == []


async def test_suspicious_and_media_only_posts_go_to_the_admin(session_factory: SF) -> None:
    fx = fixture_text("ishlaUZ_rasmiy_11778")
    src = await add_source(session_factory, fx["source"])
    sus = await add_raw(session_factory, src, fx["text"], external_id="11778")
    pic = await add_raw(session_factory, src, "", has_media=True, external_id="11779")
    p, notifier = pipeline(session_factory)
    await p.run_once()
    assert (await get_raw(session_factory, sus)).status is RawPostStatus.SUSPICIOUS
    assert (await get_raw(session_factory, pic)).status is RawPostStatus.NO_TEXT
    assert len(notifier.messages) == 2
    assert (
        "Shubhali" in notifier.messages[0] and "t.me/ishlaUZ_rasmiy/11778" in notifier.messages[0]
    )
    assert "Matnsiz" in notifier.messages[1]


async def test_job_without_contact_is_not_queued(session_factory: SF) -> None:
    src = await add_source(session_factory)
    text = "Sotuvchi kerak\nMaosh: 5 000 000 so'm\nTalablar: mas'uliyatli"
    raw = await add_raw(session_factory, src, text)
    p, _ = pipeline(session_factory)
    await p.run_once()
    assert (await get_raw(session_factory, raw)).status is RawPostStatus.NO_CONTACT
    assert await job_count(session_factory) == 0


async def test_fresh_posts_wait_for_album_parts(session_factory: SF) -> None:
    src = await add_source(session_factory)
    first = await add_raw(session_factory, src, JOB_TEXT, grouped_id=7, has_media=True)
    second = await add_raw(
        session_factory, src, "", grouped_id=7, has_media=True, fetched_ago=timedelta(seconds=5)
    )
    p, _ = pipeline(session_factory)
    stats = await p.run_once()
    assert stats.posts == 0  # one part came 5 s ago -> the whole album waits
    assert (await get_raw(session_factory, first)).status is RawPostStatus.NEW

    stats = await p.run_once(utcnow() + timedelta(minutes=2))
    assert stats.posts == 1 and stats.new_jobs == 1
    a, b = await get_raw(session_factory, first), await get_raw(session_factory, second)
    assert a.status is b.status is RawPostStatus.DONE
    assert a.job_id == b.job_id is not None


async def test_late_album_part_without_text_is_quiet(session_factory: SF) -> None:
    src = await add_source(session_factory)
    await add_raw(session_factory, src, JOB_TEXT, grouped_id=9, status=RawPostStatus.DONE)
    late = await add_raw(session_factory, src, "", grouped_id=9, has_media=True)
    p, notifier = pipeline(session_factory)
    await p.run_once()
    assert (await get_raw(session_factory, late)).status is RawPostStatus.NO_TEXT
    assert notifier.messages == []


async def test_a_bug_on_one_post_does_not_stop_the_others(
    session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = await add_source(session_factory)
    bad = await add_raw(session_factory, src, JOB_TEXT)
    good = await add_raw(session_factory, src, fixture_text("ishtoparuz_kanal_25030")["text"])
    p, notifier = pipeline(session_factory)
    real = p.extractor.extract

    def extract(post):
        if post.text == JOB_TEXT:
            raise ValueError("regex bug")
        return real(post)

    monkeypatch.setattr(p.extractor, "extract", extract)
    stats = await p.run_once()
    assert stats.statuses == {"error": 1, "done": 1}
    row = await get_raw(session_factory, bad)
    assert row.status is RawPostStatus.ERROR and "regex bug" in (row.error or "")
    assert (await get_raw(session_factory, good)).status is RawPostStatus.DONE
    assert any("xato" in m and "regex bug" in m for m in notifier.messages)


# ------------------------------------------------------------------ dedup + collecting window
async def test_repost_of_a_published_job_is_a_duplicate(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    b = await add_source(session_factory, "@kanal_b")
    first = await add_raw(session_factory, a, JOB_TEXT_FULL, posted_ago=timedelta(hours=2))
    p, _ = pipeline(session_factory)
    await p.run_once()
    job_id = (await get_raw(session_factory, first)).job_id
    assert job_id is not None
    async with session_factory() as s, s.begin():
        (await s.get(Job, job_id)).status = JobStatus.PUBLISHED  # type: ignore[union-attr]

    # a fuller copy, but the job is already in the channel -> untouched
    copy = await add_raw(session_factory, b, JOB_TEXT_FULL + "\nTelegram: @hr_sotuv")
    await p.run_once()
    row = await get_raw(session_factory, copy)
    assert row.status is RawPostStatus.DUPLICATE
    assert row.job_id == job_id and row.duplicate_of == first
    assert await job_count(session_factory) == 1
    assert (await get_job(session_factory, job_id)).raw_post_id == first


async def test_fuller_copy_within_the_window_takes_over(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    b = await add_source(session_factory, "@kanal_b")
    first = await add_raw(session_factory, a, JOB_TEXT, external_id="11")
    p, _ = pipeline(session_factory)
    await p.run_once()
    job_id = (await get_raw(session_factory, first)).job_id
    assert job_id is not None
    before = await get_job(session_factory, job_id)
    assert before.salary_min is None

    fuller = await add_raw(session_factory, b, JOB_TEXT_FULL, external_id="22")
    stats = await p.run_once()
    assert stats.replaced == 1 and stats.new_jobs == 0
    job = await get_job(session_factory, job_id)
    assert job.raw_post_id == fuller
    assert job.salary_min == 5_000_000 and job.region
    assert "https://t.me/kanal_b/22" in (job.formatted_text or "")
    assert job.next_retry_at == before.next_retry_at  # the window is not extended
    old, new = await get_raw(session_factory, first), await get_raw(session_factory, fuller)
    assert old.status is RawPostStatus.DUPLICATE and old.duplicate_of == fuller
    assert new.status is RawPostStatus.DONE and new.job_id == job_id
    assert await job_count(session_factory) == 1


async def test_poorer_copy_does_not_take_over(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    b = await add_source(session_factory, "@kanal_b")
    first = await add_raw(session_factory, a, JOB_TEXT_FULL)
    p, _ = pipeline(session_factory)
    await p.run_once()
    poorer = await add_raw(session_factory, b, JOB_TEXT)
    stats = await p.run_once()
    assert stats.replaced == 0
    job_id = (await get_raw(session_factory, first)).job_id
    assert (await get_job(session_factory, job_id)).raw_post_id == first  # type: ignore[arg-type]
    assert (await get_raw(session_factory, poorer)).status is RawPostStatus.DUPLICATE


async def test_job_being_sent_is_never_replaced(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    b = await add_source(session_factory, "@kanal_b")
    first = await add_raw(session_factory, a, JOB_TEXT)
    p, _ = pipeline(session_factory)
    await p.run_once()
    job_id = (await get_raw(session_factory, first)).job_id
    async with session_factory() as s, s.begin():
        (await s.get(Job, job_id)).status = JobStatus.SENDING  # type: ignore[union-attr]
    fuller = await add_raw(session_factory, b, JOB_TEXT_FULL)
    await p.run_once()
    assert (await get_raw(session_factory, fuller)).status is RawPostStatus.DUPLICATE
    assert (await get_job(session_factory, job_id)).raw_post_id == first  # type: ignore[arg-type]


async def test_dedup_index_survives_a_restart(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    b = await add_source(session_factory, "@kanal_b")
    await add_raw(session_factory, a, JOB_TEXT_FULL)
    p, _ = pipeline(session_factory)
    await p.run_once()

    copy = await add_raw(session_factory, b, JOB_TEXT_FULL)
    restarted, _ = pipeline(session_factory)  # new process: index rebuilt from the DB
    await restarted.run_once()
    assert (await get_raw(session_factory, copy)).status is RawPostStatus.DUPLICATE
    assert await job_count(session_factory) == 1


async def test_same_ad_after_14_days_is_a_new_job(session_factory: SF) -> None:
    a = await add_source(session_factory, "@kanal_a")
    await add_raw(session_factory, a, JOB_TEXT_FULL, posted_ago=timedelta(days=15))
    p, _ = pipeline(session_factory)
    await p.run_once()
    again = await add_raw(session_factory, a, JOB_TEXT_FULL)
    await p.run_once()
    assert (await get_raw(session_factory, again)).status is RawPostStatus.DONE
    assert await job_count(session_factory) == 2


def test_completeness_prefers_contact_salary_and_place() -> None:
    base = Completeness(True, False, False, False, False, True, 0.55)
    assert Completeness(True, True, False, True, True, True, 0.75).score > base.score
    assert Completeness(False, True, False, True, True, True, 0.75).score < (
        Completeness(True, True, False, True, True, True, 0.75).score
    )
