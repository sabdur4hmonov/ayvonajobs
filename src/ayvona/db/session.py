"""Async engine + session factory. The only place that knows how we connect to the DB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BUSY_TIMEOUT_MS = 5000


def sqlite_url(db_path: Path | str) -> str:
    return f"sqlite+aiosqlite:///{Path(db_path).as_posix()}"


def _set_sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    """Run on every new connection (pragmas are per-connection in SQLite, except WAL)."""
    cur = dbapi_conn.cursor()
    try:
        # WAL: readers don't block the writer (3 processes share one DB file).
        cur.execute("PRAGMA journal_mode=WAL")
        # Wait up to 5 s for a lock instead of failing with "database is locked".
        cur.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, much faster than FULL
    finally:
        cur.close()


def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create the async engine. Creates the DB file's parent folder if needed."""
    if url.startswith("sqlite"):
        db_file = url.split("///", 1)[-1]
        if db_file and db_file != ":memory:":
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(url, echo=echo)
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def head_revision() -> str | None:
    """The newest migration in ``migrations/versions`` (what ``alembic upgrade head`` gives)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from ayvona.config import PROJECT_ROOT

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


async def schema_is_ready(engine: AsyncEngine, *, require_head: bool = True) -> bool:
    """True if Alembic migrations were applied — by default up to the newest one, so a process
    never runs on an old DB (missing columns) after ``git pull`` without ``alembic upgrade``."""

    def _check(sync_conn: Any) -> str | None:
        if not inspect(sync_conn).has_table("alembic_version"):
            return None
        row = sync_conn.exec_driver_sql("SELECT version_num FROM alembic_version").first()
        return row[0] if row else None

    async with engine.connect() as conn:
        version = await conn.run_sync(_check)
    if version is None:
        return False
    return not require_head or version == head_revision()
