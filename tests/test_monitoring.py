"""services/heartbeat.py (monitoring), services/backup.py, services/stats.py."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ayvona.db.models import Source
from ayvona.db.repositories import kv_repo
from ayvona.services.backup import BackupService, due, make_backup, prune_backups
from ayvona.services.heartbeat import Monitor
from ayvona.services.stats import day_start, period_stats
from ayvona.timeutil import utcnow
from tests.worker_helpers import SF, RecordingNotifier, add_job, add_raw, add_source, make_settings


# ------------------------------------------------------------------ monitoring
async def test_silent_process_alerts_once_and_recovers(session_factory: SF) -> None:
    notifier = RecordingNotifier()
    mon = Monitor(make_settings(), session_factory, notifier, ("collector", "bot"))  # type: ignore[arg-type]
    now = utcnow()
    async with session_factory() as s, s.begin():
        await kv_repo.write_heartbeat(s, "collector", now - timedelta(minutes=30))
    # "bot" never wrote a heartbeat (not deployed yet) -> ignored
    first = await mon.check(now)
    assert len(first) == 1 and "Collector jim" in first[0] and "30 daqiqa" in first[0]
    assert await mon.check(now) == []  # not repeated every 5 minutes

    async with session_factory() as s, s.begin():
        await kv_repo.write_heartbeat(s, "collector", now)
    back = await mon.check(now)
    assert back == ["✅ Collector yana ishlayapti."]
    assert notifier.messages == [first[0], back[0]]


async def test_silent_and_failing_sources(session_factory: SF) -> None:
    notifier = RecordingNotifier()
    mon = Monitor(make_settings(), session_factory, notifier, ())  # type: ignore[arg-type]
    quiet = await add_source(session_factory, "@jim_kanal")
    busy = await add_source(session_factory, "@faol_kanal")
    await add_raw(session_factory, quiet, "eski", posted_ago=timedelta(hours=30))
    await add_raw(session_factory, busy, "yangi", posted_ago=timedelta(hours=1))
    async with session_factory() as s, s.begin():
        src = await s.get(Source, busy)
        src.error_count = 6  # type: ignore[union-attr]
        src.last_error = "ChannelPrivateError"  # type: ignore[union-attr]

    sent = await mon.check()
    assert any("@jim_kanal" in m and "30 soat" in m for m in sent)
    assert any("@faol_kanal" in m and "6 marta" in m for m in sent)
    assert not any("@faol_kanal" in m and "post kelmadi" in m for m in sent)
    assert await mon.check() == []


async def test_new_source_without_posts_is_not_silent_yet(session_factory: SF) -> None:
    mon = Monitor(make_settings(), session_factory, RecordingNotifier(), ())  # type: ignore[arg-type]
    await add_source(session_factory, "@yangi")
    assert await mon.check() == []
    assert len(await mon.check(utcnow() + timedelta(hours=25))) == 1


# ------------------------------------------------------------------ backup
def _db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute("create table t (x int)")
    conn.execute("insert into t values (42)")
    conn.commit()
    conn.close()
    return path


def test_make_backup_copies_consistently(tmp_path: Path) -> None:
    db = _db(tmp_path / "ayvona.db")
    path = make_backup(db, tmp_path / "backups", date(2026, 9, 30))
    assert path.name == "ayvona_2026-09-30.db"
    assert sqlite3.connect(path).execute("select x from t").fetchone() == (42,)
    assert not list((tmp_path / "backups").glob("*.tmp"))


def test_prune_keeps_newest_and_never_touches_other_files(tmp_path: Path) -> None:
    d = tmp_path / "backups"
    (d / "deploy").mkdir(parents=True)
    (d / "deploy" / "ayvona-20260901-120000.db").write_text("deploy.sh")
    (d / "notes.txt").write_text("x")
    for day in range(1, 11):
        (d / f"ayvona_2026-09-{day:02d}.db").write_text("x")
    removed = prune_backups(d, keep=7)
    assert [p.name for p in removed] == [f"ayvona_2026-09-0{n}.db" for n in (1, 2, 3)]
    left = sorted(p.name for p in d.iterdir())
    assert left == [*(f"ayvona_2026-09-{n:02d}.db" for n in range(4, 11)), "deploy", "notes.txt"]
    assert (d / "deploy" / "ayvona-20260901-120000.db").exists()


def test_backup_is_due_after_3am_once_a_day() -> None:
    tz_now = datetime(2026, 9, 30, 2, 59, tzinfo=UTC)
    assert not due(tz_now, None, 3, 0)
    assert due(tz_now.replace(hour=3), None, 3, 0)
    assert due(tz_now.replace(hour=15), date(2026, 9, 29), 3, 0)  # missed at night -> catch up
    assert not due(tz_now.replace(hour=15), date(2026, 9, 30), 3, 0)


async def test_backup_service_runs_once_and_sends_file(
    session_factory: SF, tmp_path: Path, db_file: Path
) -> None:
    settings = make_settings(db_file=db_file, backup_dir=tmp_path / "backups")
    sent: list[Path] = []

    class DocNotifier(RecordingNotifier):
        async def send_document(self, path: Path, caption: str = "") -> bool:
            sent.append(path)
            return True

    svc = BackupService(settings, session_factory, DocNotifier())  # type: ignore[arg-type]
    at_4am_tashkent = datetime(2026, 9, 29, 23, 0, tzinfo=UTC)  # 04:00 in UTC+5
    path = await svc.tick(at_4am_tashkent)
    assert path is not None and path.name == "ayvona_2026-09-30.db" and sent == [path]
    assert await svc.tick(at_4am_tashkent + timedelta(hours=1)) is None  # once a day
    async with session_factory() as s:
        assert await kv_repo.get(s, "backup:last_date") == "2026-09-30"


async def test_failed_backup_is_reported_not_raised(session_factory: SF, tmp_path: Path) -> None:
    notifier = RecordingNotifier()
    settings = make_settings(db_file=tmp_path / "missing.db", backup_dir=tmp_path / "b")
    svc = BackupService(settings, session_factory, notifier)  # type: ignore[arg-type]
    assert await svc.tick(datetime(2026, 9, 30, 10, 0, tzinfo=UTC)) is None
    assert "Backup qilinmadi" in notifier.messages[0]


# ------------------------------------------------------------------ stats
async def test_period_stats(session_factory: SF) -> None:
    from ayvona.db.models import Job, JobStatus, RawPostStatus

    src = await add_source(session_factory)
    await add_raw(session_factory, src, "a", status=RawPostStatus.DONE)
    await add_raw(session_factory, src, "b", status=RawPostStatus.DUPLICATE)
    await add_raw(session_factory, src, "c", status=RawPostStatus.NOT_JOB)
    job_id = await add_job(session_factory, status=JobStatus.PUBLISHED)
    async with session_factory() as s, s.begin():
        (await s.get(Job, job_id)).published_at = utcnow()  # type: ignore[union-attr]
    async with session_factory() as s:
        st = await period_stats(s, utcnow() - timedelta(days=1))
    assert (st.fetched, st.duplicates, st.not_ads, st.published) == (3, 1, 1, 1)
    assert st.categories == [("savdo", 1)]


def test_day_start_is_tashkent_midnight() -> None:
    from zoneinfo import ZoneInfo

    start = day_start(datetime(2026, 9, 29, 20, 30, tzinfo=UTC), ZoneInfo("Asia/Tashkent"))
    assert start.isoformat() == "2026-09-30T00:00:00+05:00"
