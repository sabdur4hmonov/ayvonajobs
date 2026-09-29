"""Bosqich 2: models, migration, pragmas, constraints, FTS, repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ayvona.config import SourceConfig
from ayvona.db.models import (
    FTS_TABLE_PREFIX,
    Base,
    Job,
    JobOrigin,
    JobStatus,
    ParseMethod,
    RawPost,
    RawPostStatus,
    Source,
    SourceType,
)
from ayvona.db.repositories import kv_repo, raw_posts_repo, sources_repo
from ayvona.db.session import schema_is_ready
from ayvona.sources.base import RawItem
from ayvona.timeutil import utcnow
from tests.conftest import run_alembic

EXPECTED_TABLES = {
    "sources",
    "raw_posts",
    "jobs",
    "users",
    "favorites",
    "subscriptions",
    "alert_deliveries",
    "search_logs",
    "category_images",
    "filter_words",
    "ai_cache",
    "kv_store",
    "jobs_fts",
}


def _item(ext_id: str, text_: str = "Sotuvchi kerak") -> RawItem:
    return RawItem(external_id=ext_id, text=text_, has_media=False, posted_at=utcnow())


async def _add_source(session: AsyncSession, identifier: str = "@test") -> Source:
    src = Source(identifier=identifier, type=SourceType.TELEGRAM)
    session.add(src)
    await session.commit()
    return src


# ------------------------------------------------------------------ migration / schema
async def test_migration_creates_all_tables(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
    assert tables >= EXPECTED_TABLES
    assert await schema_is_ready(engine)


async def test_schema_not_ready_on_empty_db(tmp_path: Path) -> None:
    from ayvona.db.session import create_engine, sqlite_url

    eng = create_engine(sqlite_url(tmp_path / "empty.db"))
    try:
        assert not await schema_is_ready(eng)
    finally:
        await eng.dispose()


def test_migration_matches_models(db_file: Path) -> None:
    """If a model changes without a new migration, this test fails."""

    def include(obj, name, type_, reflected, compare_to) -> bool:
        if type_ != "table" or not name:
            return True
        return not name.startswith(FTS_TABLE_PREFIX) and name != "alembic_version"

    eng = sa.create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with eng.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={"include_object": include, "compare_type": True}
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        eng.dispose()
    assert diff == []


def test_downgrade_and_upgrade_again(db_file: Path) -> None:
    run_alembic(db_file, "downgrade", "base")
    eng = sa.create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with eng.connect() as conn:
            assert set(sa.inspect(conn).get_table_names()) <= {"alembic_version"}
    finally:
        eng.dispose()
    run_alembic(db_file, "upgrade", "head")


async def test_sqlite_pragmas(session: AsyncSession) -> None:
    assert (await session.scalar(text("PRAGMA journal_mode"))) == "wal"
    assert (await session.scalar(text("PRAGMA foreign_keys"))) == 1
    assert (await session.scalar(text("PRAGMA busy_timeout"))) == 5000


# ------------------------------------------------------------------ constraints
async def test_unique_source_external_id_rejects_duplicate(session: AsyncSession) -> None:
    src = await _add_source(session)
    session.add(RawPost(source_id=src.id, external_id="10", text="a"))
    await session.commit()

    session.add(RawPost(source_id=src.id, external_id="10", text="b"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_same_external_id_in_other_source_is_fine(session: AsyncSession) -> None:
    a = await _add_source(session, "@a")
    b = await _add_source(session, "@b")
    session.add_all(
        [RawPost(source_id=a.id, external_id="1"), RawPost(source_id=b.id, external_id="1")]
    )
    await session.commit()
    assert await raw_posts_repo.count(session) == 2


async def test_foreign_key_enforced(session: AsyncSession) -> None:
    session.add(RawPost(source_id=999, external_id="1"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_user_job_requires_contact(session: AsyncSession) -> None:
    session.add(Job(origin=JobOrigin.USER, parse_method=ParseMethod.FORM, title="Oshpaz"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    session.add(
        Job(
            origin=JobOrigin.USER,
            parse_method=ParseMethod.FORM,
            title="Oshpaz",
            contact_username="@hr",
        )
    )
    # aggregator fallback posts may lack a contact
    session.add(Job(origin=JobOrigin.AGGREGATOR, parse_method=ParseMethod.FALLBACK))
    await session.commit()


async def test_defaults_and_enums_roundtrip(session: AsyncSession) -> None:
    src = await _add_source(session)
    session.add(RawPost(source_id=src.id, external_id="5"))
    await session.commit()

    post = (await session.scalars(select(RawPost))).one()
    assert post.status is RawPostStatus.NEW
    assert post.text == ""
    assert post.has_media is False
    # stored as the plain value, not the enum name
    raw = await session.scalar(text("SELECT status FROM raw_posts"))
    assert raw == "new"


async def test_datetimes_come_back_utc_aware(session: AsyncSession) -> None:
    tashkent = datetime(2026, 1, 1, 12, 0, tzinfo=UTC) + timedelta(hours=5)
    src = await _add_source(session)
    session.add(RawPost(source_id=src.id, external_id="1", posted_at=tashkent))
    await session.commit()
    session.expunge_all()

    post = (await session.scalars(select(RawPost))).one()
    assert post.posted_at is not None
    assert post.posted_at.tzinfo is UTC
    assert post.posted_at == tashkent


async def test_naive_datetime_rejected(session: AsyncSession) -> None:
    src = await _add_source(session)
    session.add(RawPost(source_id=src.id, external_id="1", posted_at=datetime(2026, 1, 1)))
    with pytest.raises(Exception, match="naive datetime"):
        await session.commit()


# ------------------------------------------------------------------ FTS
async def _fts(session: AsyncSession, query: str) -> list[int]:
    rows = await session.execute(
        text("SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH :q ORDER BY rowid"), {"q": query}
    )
    return [r[0] for r in rows]


async def test_fts_follows_jobs_via_triggers(session: AsyncSession) -> None:
    job = Job(
        origin=JobOrigin.AGGREGATOR,
        parse_method=ParseMethod.REGEX,
        title="Sotuvchi-konsultant",
        company="Texnomart",
        city="Toshkent",
        status=JobStatus.PUBLISHED,
    )
    session.add(job)
    await session.commit()
    assert await _fts(session, "texnomart") == [job.id]
    assert await _fts(session, "sotuvchi") == [job.id]

    job.title = "Haydovchi"
    await session.commit()
    assert await _fts(session, "sotuvchi") == []
    assert await _fts(session, "haydovchi") == [job.id]

    await session.delete(job)
    await session.commit()
    assert await _fts(session, "haydovchi") == []


# ------------------------------------------------------------------ repositories
async def test_insert_ignore_duplicates(session: AsyncSession) -> None:
    src = await _add_source(session)
    now = utcnow()

    assert await raw_posts_repo.insert_ignore_duplicates(session, src.id, [], now) == 0
    n1 = await raw_posts_repo.insert_ignore_duplicates(
        session, src.id, [_item("1"), _item("2")], now
    )
    n2 = await raw_posts_repo.insert_ignore_duplicates(
        session, src.id, [_item("2"), _item("3")], now
    )
    await session.commit()

    assert (n1, n2) == (2, 1)
    assert await raw_posts_repo.count(session, src.id) == 3


async def test_insert_many_is_chunked(session: AsyncSession) -> None:
    src = await _add_source(session)
    items = [_item(str(i)) for i in range(raw_posts_repo.INSERT_CHUNK * 2 + 7)]
    n = await raw_posts_repo.insert_ignore_duplicates(session, src.id, items, utcnow())
    await session.commit()
    assert n == len(items)


async def test_status_helpers(session: AsyncSession) -> None:
    src = await _add_source(session)
    await raw_posts_repo.insert_ignore_duplicates(
        session, src.id, [_item("1"), _item("2")], utcnow() - timedelta(minutes=5)
    )
    await session.commit()

    new = await raw_posts_repo.list_by_status(
        session, RawPostStatus.NEW, fetched_before=utcnow() - timedelta(seconds=60)
    )
    assert [p.external_id for p in new] == ["1", "2"]

    await raw_posts_repo.set_status(session, [new[0].id], RawPostStatus.PROCESSING)
    await session.commit()
    assert await raw_posts_repo.reset_stuck_processing(session) == 1
    await session.commit()
    session.expunge_all()
    again = await raw_posts_repo.list_by_status(session, RawPostStatus.NEW)
    assert len(again) == 2


async def test_sources_sync_from_config(session: AsyncSession) -> None:
    await sources_repo.sync_from_config(
        session,
        [SourceConfig(identifier="@a", title="A"), SourceConfig(identifier="@b")],
    )
    await session.commit()
    a = (await session.scalars(select(Source).where(Source.identifier == "@a"))).one()
    await sources_repo.mark_success(session, a.id, "42", utcnow())
    await session.commit()

    # @a updated, @b removed from config, @c added
    enabled = await sources_repo.sync_from_config(
        session,
        [
            SourceConfig(identifier="@a", title="A2", own_usernames=["@a"]),
            SourceConfig(identifier="@c", enabled=False),
        ],
    )
    await session.commit()
    session.expunge_all()

    rows = {s.identifier: s for s in (await session.scalars(select(Source))).all()}
    assert [s.identifier for s in enabled] == ["@a"]
    assert rows["@a"].title == "A2"
    assert rows["@a"].own_usernames == ["@a"]
    assert rows["@a"].last_seen_id == "42"  # cursor survives a config sync
    assert rows["@b"].enabled is False  # kept, not deleted
    assert rows["@c"].enabled is False


async def test_sources_mark_error_and_success(session: AsyncSession) -> None:
    src = await _add_source(session)
    await sources_repo.mark_error(session, src.id, "boom" * 1000, utcnow())
    await sources_repo.mark_error(session, src.id, "boom2", utcnow())
    await session.commit()
    await session.refresh(src)
    assert src.error_count == 2
    assert src.last_error == "boom2"
    assert src.last_seen_id is None

    await sources_repo.mark_success(session, src.id, None, utcnow())
    await session.commit()
    await session.refresh(src)
    assert (src.error_count, src.last_error, src.last_seen_id) == (0, None, None)
    assert src.last_success_at is not None


async def test_kv_and_heartbeat(session: AsyncSession) -> None:
    assert await kv_repo.get(session, "x") is None
    await kv_repo.set_value(session, "x", "1")
    await kv_repo.set_value(session, "x", "2")
    await session.commit()
    assert await kv_repo.get(session, "x") == "2"

    t = datetime(2026, 9, 29, 7, 0, tzinfo=UTC)
    await kv_repo.write_heartbeat(session, "collector", t)
    await session.commit()
    assert await kv_repo.read_heartbeat(session, "collector") == t
