"""Alembic environment (async, SQLite-friendly)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.engine import Connection

from ayvona.db.models import FTS_TABLE_PREFIX, Base
from ayvona.db.session import create_engine
from ayvona.db.types import UTCDateTime

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from ayvona.config import get_settings

    return get_settings().db_url


def _render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Render our custom column type as plain ``sa.DateTime()`` in generated migrations."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


def _include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Autogenerate must not try to drop the FTS5 table and its shadow tables (not ORM models)."""
    return not (type_ == "table" and name is not None and name.startswith(FTS_TABLE_PREFIX))


def _configure(connection: Connection | None = None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite can't ALTER most things; batch mode rebuilds the table
        render_item=_render_item,
        include_object=_include_object,
        compare_type=True,
        literal_binds=url is not None,
        dialect_opts={"paramstyle": "named"} if url is not None else {},
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of touching a DB (``alembic upgrade head --sql``)."""
    _configure(url=_database_url())
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = create_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # called programmatically with an existing (sync) connection
        _do_run_migrations(connection)
    else:
        asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
