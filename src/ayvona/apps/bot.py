"""Bot process (@ayvonabot). For now only the admin commands (Bosqich 8); the public menu
comes in Bosqich 10.

Also: ``heartbeat:bot`` every minute and a monitor that watches the worker (the worker watches
collector and bot, so every process is watched by another one).

Without ``BOT_TOKEN`` it does not crash: it explains in Uzbek what to do and exits.

Run:  uv run python -m ayvona.apps.bot
"""

from __future__ import annotations

import asyncio
import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.types import BotCommandScopeChat
from loguru import logger

from ayvona.apps.runtime import SessionFactory, heartbeat_loop, stop_aware_sleep
from ayvona.bot.setup import ADMIN_COMMANDS, BOT_DEFAULTS, build_dispatcher
from ayvona.botapi import BAD_TOKEN, BotConfigError, create_bot
from ayvona.config import Settings, get_settings
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.logging_setup import setup_logging
from ayvona.services.heartbeat import Monitor
from ayvona.services.notifier import Notifier

PROCESS_NAME = "bot"
NO_ADMINS = (
    "ADMIN_IDS .env faylida bo'sh — admin buyruqlari hech kimga ishlamaydi. "
    "O'z Telegram ID'ingizni @userinfobot dan bilib, .env ga yozing: ADMIN_IDS=123456789"
)


async def set_admin_commands(bot: Bot, admin_ids: list[int]) -> None:
    """The "/" menu shows the admin commands to admins only. Best effort."""
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:  # the admin has not started the bot yet, ...
            logger.info("Admin {} uchun buyruqlar menyusi qo'yilmadi: {}", admin_id, e)


async def run_bot(settings: Settings, sf: SessionFactory, bot: Bot) -> None:
    dp = build_dispatcher(settings, sf)
    stop = asyncio.Event()
    notifier = Notifier(bot, settings.env.admin_chat_id, sf)
    monitor = Monitor(settings, sf, notifier, ("worker",), watch_sources=False)
    tasks = [
        asyncio.create_task(
            heartbeat_loop(sf, PROCESS_NAME, settings.app.worker.heartbeat_interval_seconds, stop)
        ),
        asyncio.create_task(monitor.run(stop_aware_sleep(stop))),
    ]
    try:
        await dp.start_polling(bot, handle_signals=True, close_bot_session=False)
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> int:
    settings = get_settings()
    setup_logging(settings.env.log_level, settings.log_dir, PROCESS_NAME)
    logger.info("Bot ishga tushmoqda (baza: {})", settings.db_file)
    try:
        bot = create_bot(settings, default=BOT_DEFAULTS)
    except BotConfigError as e:
        logger.error("{} Bot ishga tushmadi.", e)
        return 1
    engine = create_engine(settings.db_url)
    try:
        if not await schema_is_ready(engine):
            logger.error(
                "Baza tayyor emas yoki eski versiyada. Avval: uv run alembic upgrade head"
            )
            return 1
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            logger.error("{} Telegram tokenni rad etdi.", BAD_TOKEN)
            return 1
        logger.info("Bot: @{}", me.username)
        if not settings.env.admin_ids:
            logger.warning(NO_ADMINS)
        await set_admin_commands(bot, settings.env.admin_ids)
        await run_bot(settings, create_session_factory(engine), bot)
        return 0
    finally:
        with contextlib.suppress(Exception):
            await bot.session.close()
        await engine.dispose()
        logger.info("Bot to'xtadi.")


def run() -> int:
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:  # Ctrl+C on Windows
        logger.info("Ctrl+C — to'xtatildi.")
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
