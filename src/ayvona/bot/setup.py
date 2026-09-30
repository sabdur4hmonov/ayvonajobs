"""Builds the aiogram Dispatcher: routers, admin filter, shared objects for the handlers."""

from __future__ import annotations

from aiogram import Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, LinkPreviewOptions, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.filters import IsAdmin
from ayvona.bot.handlers import admin, admin_images, admin_sources
from ayvona.config import Settings

# Bot API defaults for every message the bot sends: HTML, no link previews.
BOT_DEFAULTS = DefaultBotProperties(
    parse_mode=ParseMode.HTML, link_preview=LinkPreviewOptions(is_disabled=True)
)

ADMIN_COMMANDS = [
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
    BotCommand(command="cancel", description="Bekor qilish"),
    BotCommand(command="help", description="Yordam"),
]

public = Router(name="public")


@public.message(CommandStart())
async def public_start(message: Message, settings: Settings) -> None:
    """Everyone else, until the public bot exists (Bosqich 10)."""
    await message.answer(T.PUBLIC_START.format(channel=settings.app.branding.channel_username))


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
    """MemoryStorage for FSM: a restart only forgets a half-finished /addimage (fine for admins).
    Bosqich 10 may switch to a persistent storage for the public forms."""
    dp = Dispatcher(storage=MemoryStorage())
    dp["sf"] = session_factory
    dp["settings"] = settings
    is_admin = IsAdmin(settings.env.admin_ids)
    admin_area = Router(name="admin_area")
    admin_area.message.filter(is_admin)
    admin_area.callback_query.filter(is_admin)
    admin_area.include_routers(*_detached(admin.router, admin_sources.router, admin_images.router))
    dp.include_routers(admin_area, *_detached(public))
    return dp
