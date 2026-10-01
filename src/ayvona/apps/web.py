"""Web process (4th process, Bosqich 17): the read-only website on ``website.host:port``.

On the server Caddy is in front of it (HTTPS, deploy/Caddyfile.example). It only reads the DB,
so it can crash or restart without touching collector / worker / bot.

Run:  uv run python -m ayvona.apps.web          (http://127.0.0.1:8080)
"""

from __future__ import annotations

import asyncio

import uvicorn
from loguru import logger

from ayvona.config import get_settings
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.logging_setup import setup_logging
from ayvona.web.app import create_app

PROCESS_NAME = "web"


async def main() -> int:
    settings = get_settings()
    setup_logging(settings.env.log_level, settings.log_dir, PROCESS_NAME)
    cfg = settings.app.website
    engine = create_engine(settings.db_url)
    try:
        if not await schema_is_ready(engine):
            logger.error("Baza tayyor emas yoki eski versiyada. Avval: uv run alembic upgrade head")
            return 1
        app = create_app(settings, create_session_factory(engine))
        logger.info("Veb-sayt: http://{}:{} (baza: {})", cfg.host, cfg.port, settings.db_file)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=cfg.host,
                port=cfg.port,
                log_level="warning",
                proxy_headers=True,
                forwarded_allow_ips="127.0.0.1",
            )
        )
        await server.serve()
        return 0
    finally:
        await engine.dispose()
        logger.info("Veb-sayt to'xtadi.")


def run() -> int:
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
