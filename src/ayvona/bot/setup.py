"""Builds the aiogram Dispatcher: routers, admin filter, middlewares, shared objects.

Order: the admin routers first (only ``ADMIN_IDS``; /help, /stats ...), then the public ones
(private chats only). Admins use the public menu and deep links like everyone else.
"""

from __future__ import annotations

from aiogram import Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import moderation
from ayvona.bot.filters import IsAdmin
from ayvona.bot.handlers import (
    admin,
    admin_extra,
    admin_images,
    admin_sources,
    alerts,
    favorites,
    my_jobs,
    post_job,
    search,
    start,
)
from ayvona.bot.middlewares import UserMiddleware
from ayvona.config import Settings

# Bot API defaults for every message the bot sends: HTML, no link previews.
BOT_DEFAULTS = DefaultBotProperties(
    parse_mode=ParseMode.HTML, link_preview=LinkPreviewOptions(is_disabled=True)
)

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Bosh menyu"),
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="cancel", description="Bekor qilish"),
]

ADMIN_COMMANDS = [
    BotCommand(command="start", description="Bosh menyu"),
    BotCommand(command="stats", description="Statistika"),
    BotCommand(command="queue", description="Navbat"),
    BotCommand(command="failed", description="Chiqmay qolganlar"),
    BotCommand(command="retry", description="Qayta navbatga: /retry <id|all>"),
    BotCommand(command="pause", description="Kanalga joylashni to'xtatish"),
    BotCommand(command="resume", description="Davom ettirish"),
    BotCommand(command="sources", description="Manbalar"),
    BotCommand(command="addsource", description="Manba qo'shish"),
    BotCommand(command="images", description="Rasmlar"),
    BotCommand(command="addimage", description="Rasm qo'shish"),
    BotCommand(command="addword", description="Filtr so'zi qo'shish"),
    BotCommand(command="delword", description="Filtr so'zini o'chirish"),
    BotCommand(command="words", description="Filtr so'zlari"),
    BotCommand(command="ban", description="Bloklash: /ban <id|@username>"),
    BotCommand(command="unban", description="Blokdan chiqarish"),
    BotCommand(command="broadcast", description="Hammaga xabar"),
    BotCommand(command="ai", description="Gemini yordamchi"),
    BotCommand(command="cancel", description="Bekor qilish"),
    BotCommand(command="help", description="Admin yordami"),
]


def _detached(*routers: Router) -> tuple[Router, ...]:
    """Handler modules keep one module-level Router each; a Router can have only one parent, so
    a new Dispatcher (tests build many) first takes them off the previous one."""
    for r in routers:
        if r.parent_router is not None:
            r.parent_router.sub_routers.remove(r)
            r._parent_router = None  # aiogram has no public "detach"
    return routers


def build_dispatcher(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    """FSM storage: MemoryStorage — simple and fast; a restart forgets half-filled forms (the user
    just presses the menu button again; nothing that was submitted is lost, it is in the DB).
    When the bot runs on more than one process/server, switch to a shared storage (aiogram's
    RedisStorage, or a small SQLite storage on ``kv_store``)."""
    dp = Dispatcher(storage=MemoryStorage())
    dp["sf"] = session_factory
    dp["settings"] = settings
    users = UserMiddleware(settings, session_factory)
    dp.message.outer_middleware(users)
    dp.callback_query.outer_middleware(users)

    is_admin = IsAdmin(settings.env.admin_ids)
    admin_area = Router(name="admin_area")
    admin_area.message.filter(is_admin)
    admin_area.callback_query.filter(is_admin)
    admin_area.include_routers(
        *_detached(
            admin.router,
            admin_sources.router,
            admin_images.router,
            admin_extra.router,
            moderation.router,
        )
    )

    public_area = Router(name="public_area")
    public_area.message.filter(F.chat.type == "private")
    # start first: its menu buttons work from any step (they leave a half-filled form)
    public_area.include_routers(
        *_detached(
            start.router,
            favorites.router,
            search.router,
            alerts.router,
            my_jobs.router,
            post_job.router,
        )
    )

    dp.include_routers(*_detached(admin_area, public_area))
    return dp
