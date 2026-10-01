"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ayvona.config import PROJECT_ROOT
from ayvona.db.session import create_engine, create_session_factory, sqlite_url
from ayvona.sources.web import base as web_base

_ENV_KEYS = (
    "API_ID",
    "API_HASH",
    "TELETHON_SESSION",
    "BOT_TOKEN",
    "CHANNEL_ID",
    "ADMIN_IDS",
    "ADMIN_CHAT_ID",
    "DB_PATH",
    "LOG_LEVEL",
    "TZ",
    "GEMINI_API_KEY",
    "GEMINI_API_KEYS",
    "GEMINI_ALLOW_KEY_ROTATION",
    "HH_ACCESS_TOKEN",
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never pick up the developer's real environment variables."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"test tried to reach the internet: {request.method} {request.url}")


@pytest.fixture(autouse=True)
def _offline_web(monkeypatch: pytest.MonkeyPatch) -> None:
    """Web sources / RSS probes go through ``sources.web.base.TRANSPORT``: in tests it fails on
    any request unless the test installs its own MockTransport with saved answers."""
    monkeypatch.setattr(web_base, "TRANSPORT", httpx.MockTransport(_no_network))


def alembic_config(db_file: Path) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", sqlite_url(db_file))
    cfg.attributes["configure_logger"] = False
    return cfg


def run_alembic(db_file: Path, action: str = "upgrade", revision: str = "head") -> None:
    """Run a migration through a plain sync connection (no event loop needed)."""
    cfg = alembic_config(db_file)
    engine = sa.create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            getattr(command, action)(cfg, revision)
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Migrate once per test run; each test gets a copy (much faster than migrating each time)."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    run_alembic(path, "upgrade", "head")
    return path


@pytest.fixture
def db_file(tmp_path: Path, _migrated_template: Path) -> Path:
    """A fresh temporary SQLite DB with all migrations applied."""
    path = tmp_path / "test.db"
    shutil.copyfile(_migrated_template, path)
    return path


@pytest.fixture
async def engine(db_file: Path) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(sqlite_url(db_file))
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
