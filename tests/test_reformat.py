"""services/reformat.py (scripts/reformat_queued.py, worker start-up): queued / retry jobs get the
current caption and buttons; published / sending / failed jobs and the dedup data are never
touched."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select, update

from ayvona.apps.worker import run_worker
from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin, JobStatus, ParseMethod, RawPost
from ayvona.db.repositories import jobs_repo, kv_repo
from ayvona.processing.pipeline import Pipeline
from ayvona.services.backup import make_backup
from ayvona.services.reformat import (
    reformat_queued,
    worker_heartbeat_age,
    worker_seems_running,
)
from ayvona.timeutil import utcnow
from tests.worker_helpers import SF, add_raw, add_source, get_job, make_settings

OLD_BOT = "ayvonabot"
OLD_CHANNEL = "ayvona"
NEW_BOT = "ayvona_jobs_bot"


def old_settings() -> Settings:
    """The settings the queued jobs were formatted with (old usernames)."""
    s = make_settings()
    branding = s.app.branding.model_copy(
        update={"bot_username": OLD_BOT, "channel_username": OLD_CHANNEL}
    )
    return s.model_copy(update={"app": s.app.model_copy(update={"branding": branding})})


def ad(title: str, phone: str) -> str:
    return (
        f"{title} kerak\n"
        "Maosh: 5 000 000 so'm\n"
        "Manzil: Toshkent, Chilonzor tumani\n"
        "Talablar: mas'uliyatli, #Erkaklar\n"
        f"Murojaat uchun: {phone}"
    )


ADS = [
    ad("Sotuvchi", "+998901234567"),
    ad("Oshpaz", "+998911112233"),
    ad("Haydovchi", "+998935556677"),
    ad("Qorovul", "+998977778899"),
    ad("Farrosh", "+998990001122"),
]
STATUSES = [
    JobStatus.QUEUED,
    JobStatus.RETRY,
    JobStatus.PUBLISHED,
    JobStatus.SENDING,
    JobStatus.FAILED,
]


async def old_jobs(sf: SF) -> dict[JobStatus, int]:
    """One job per status, all formatted with the OLD branding by the real pipeline."""
    src = await add_source(sf, "@kanal_a")
    for i, text in enumerate(ADS):
        await add_raw(sf, src, text, external_id=str(100 + i))
    await Pipeline(old_settings(), sf).run_once()
    async with sf() as s:
        ids = list((await s.scalars(select(Job.id).order_by(Job.id))).all())
    assert len(ids) == len(ADS)
    async with sf() as s, s.begin():
        for job_id, status in zip(ids, STATUSES, strict=True):
            await s.execute(update(Job).where(Job.id == job_id).values(status=status))
    return dict(zip(STATUSES, ids, strict=True))


def urls(job: Job) -> list[str]:
    return [b["url"] for row in job.buttons or [] for b in row]


async def raw_snapshot(sf: SF) -> list[tuple]:
    async with sf() as s:
        rows = (await s.scalars(select(RawPost).order_by(RawPost.id))).all()
        return [
            (r.id, r.status, r.job_id, r.duplicate_of, r.dedup_text, r.fingerprint) for r in rows
        ]


# ------------------------------------------------------------------ main behaviour
async def test_queued_and_retry_get_new_footer_and_buttons(session_factory: SF) -> None:
    ids = await old_jobs(session_factory)
    before = {st: await get_job(session_factory, job_id) for st, job_id in ids.items()}
    for job in before.values():
        assert f"@{OLD_BOT}" in (job.formatted_text or "")
        assert any(OLD_BOT + "?" in u for u in urls(job))
    raw_before = await raw_snapshot(session_factory)

    report = await reformat_queued(make_settings(), session_factory)

    assert report.total == 2
    assert report.updated == 2 and not report.skipped and not report.taken
    for st in (JobStatus.QUEUED, JobStatus.RETRY):
        job = await get_job(session_factory, ids[st])
        text = job.formatted_text or ""
        assert f"🔍 Ish qidiryapsizmi? @{NEW_BOT}" in text
        assert "📢 @ayvonajobs — Ayvona Jobs" in text
        assert f"@{OLD_BOT}" not in text and "@ayvona " not in text
        assert f"https://t.me/{NEW_BOT}?start=save_{job.id}" in urls(job)
        assert f"https://t.me/{NEW_BOT}?start=search" in urls(job)
        assert not any(OLD_BOT in u for u in urls(job))
        assert "https://t.me/kanal_a/" in text  # the "manba" link is kept
        # the outbox state stays as it was
        assert job.status is st
        assert job.raw_post_id == before[st].raw_post_id
        assert job.next_retry_at == before[st].next_retry_at
        assert job.attempts == before[st].attempts

    # published / sending / failed: not a single byte changes
    for st in (JobStatus.PUBLISHED, JobStatus.SENDING, JobStatus.FAILED):
        job = await get_job(session_factory, ids[st])
        assert job.formatted_text == before[st].formatted_text
        assert job.buttons == before[st].buttons
        assert job.status is st

    # no new job, raw posts / dedup index untouched
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Job)) == len(ADS)
    assert await raw_snapshot(session_factory) == raw_before

    # running it again changes nothing
    again = await reformat_queued(make_settings(), session_factory)
    assert again.updated == 0 and again.unchanged == 2


async def test_dry_run_writes_nothing(session_factory: SF) -> None:
    ids = await old_jobs(session_factory)
    queued = await get_job(session_factory, ids[JobStatus.QUEUED])

    report = await reformat_queued(make_settings(), session_factory, dry_run=True)

    assert report.dry_run and len(report.changes) == 2 and report.total == 2
    change = next(c for c in report.changes if c.job_id == queued.id)
    assert change.before_text == queued.formatted_text
    assert f"@{NEW_BOT}" in change.after_text and f"@{OLD_BOT}" in change.before_text
    after = await get_job(session_factory, queued.id)
    assert after.formatted_text == queued.formatted_text
    assert after.buttons == queued.buttons


async def test_job_that_changed_meanwhile_is_not_overwritten(session_factory: SF) -> None:
    """A take-over (other raw post) or the publisher taking the job wins over the script."""
    ids = await old_jobs(session_factory)
    job = await get_job(session_factory, ids[JobStatus.QUEUED])
    async with session_factory() as s, s.begin():
        other = (job.raw_post_id or 0) + 1
        assert not await jobs_repo.update_if_sendable(
            s, job.id, {"formatted_text": "x"}, raw_post_id=other
        )
        assert not await jobs_repo.update_if_sendable(
            s, ids[JobStatus.PUBLISHED], {"formatted_text": "x"}, raw_post_id=job.raw_post_id
        )
        assert await jobs_repo.update_if_sendable(
            s, job.id, {"formatted_text": "x"}, raw_post_id=job.raw_post_id
        )


async def test_user_job_without_raw_post_is_skipped(session_factory: SF) -> None:
    async with session_factory() as s, s.begin():
        job = Job(
            origin=JobOrigin.USER,
            title="Sotuvchi",
            parse_method=ParseMethod.FORM,
            contact_phone="+998901234567",
            formatted_text="old @ayvonabot",
            status=JobStatus.QUEUED,
        )
        s.add(job)
        await s.flush()
        job_id = job.id

    report = await reformat_queued(make_settings(), session_factory)

    assert report.updated == 0 and [j for j, _ in report.skipped] == [job_id]
    assert (await get_job(session_factory, job_id)).formatted_text == "old @ayvonabot"


# ------------------------------------------------------------------ worker start-up
async def test_worker_start_reformats_the_queue(session_factory: SF) -> None:
    ids = await old_jobs(session_factory)
    published = await get_job(session_factory, ids[JobStatus.PUBLISHED])

    await run_worker(make_settings(), session_factory, asyncio.Event(), once=True)

    queued = await get_job(session_factory, ids[JobStatus.QUEUED])
    assert f"@{NEW_BOT}" in (queued.formatted_text or "")
    assert f"https://t.me/{NEW_BOT}?start=save_{queued.id}" in urls(queued)
    after = await get_job(session_factory, ids[JobStatus.PUBLISHED])
    assert after.formatted_text == published.formatted_text


async def test_worker_start_reformat_can_be_turned_off(session_factory: SF) -> None:
    ids = await old_jobs(session_factory)
    before = await get_job(session_factory, ids[JobStatus.QUEUED])
    s = make_settings(reformat_queued_on_start=False)

    await run_worker(s, session_factory, asyncio.Event(), once=True)

    assert (await get_job(session_factory, before.id)).formatted_text == before.formatted_text


# ------------------------------------------------------------------ safety checks
async def test_worker_heartbeat_check(session_factory: SF) -> None:
    settings = make_settings()
    assert await worker_heartbeat_age(session_factory) is None
    assert not worker_seems_running(settings, None)

    now = utcnow()
    async with session_factory() as s, s.begin():
        await kv_repo.write_heartbeat(s, "worker", now - timedelta(seconds=30))
    age = await worker_heartbeat_age(session_factory, now)
    assert age is not None and worker_seems_running(settings, age)
    assert not worker_seems_running(settings, timedelta(minutes=10))


def test_one_off_backup_has_its_own_name(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    con = sqlite3.connect(db)
    con.execute("create table t (x)")
    con.execute("insert into t values (1)")
    con.commit()
    con.close()
    path = make_backup(db, tmp_path / "reformat", date(2026, 9, 30), "before_reformat.db")
    assert path == tmp_path / "reformat" / "before_reformat.db"
    copy = sqlite3.connect(path)
    try:
        assert copy.execute("select x from t").fetchall() == [(1,)]
    finally:
        copy.close()
