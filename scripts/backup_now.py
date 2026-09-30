"""Make the DB backup right now (normally the worker does it daily at 03:00 Asia/Tashkent).

    uv run python scripts/backup_now.py            # data/backups/ayvona_YYYY-MM-DD.db
    uv run python scripts/backup_now.py --send     # + send it to the admin chat (needs BOT_TOKEN)

Keeps the newest ``backup.keep`` (7) daily files; nothing else in data/backups/ is touched.
"""

from __future__ import annotations

import argparse
import asyncio

from ayvona.botapi import BotConfigError, create_bot
from ayvona.config import get_settings
from ayvona.db.session import create_engine, create_session_factory
from ayvona.services.backup import BackupService
from ayvona.services.notifier import Notifier


async def main(send: bool) -> int:
    settings = get_settings()
    if not settings.db_file.exists():
        print(f"Baza topilmadi: {settings.db_file}")
        return 1
    engine = create_engine(settings.db_url)
    bot = None
    try:
        notifier = None
        if send:
            try:
                bot = create_bot(settings)
                notifier = Notifier(bot, settings.env.admin_chat_id, create_session_factory(engine))
            except BotConfigError as e:
                print(e)
        path = await BackupService(settings, create_session_factory(engine), notifier).run_backup()
        print(f"Tayyor: {path}")
        return 0
    finally:
        if bot is not None:
            await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="admin chatga ham yuborish")
    raise SystemExit(asyncio.run(main(parser.parse_args().send)))
