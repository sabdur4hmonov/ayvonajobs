"""⭐ Saqlanganlar: the user's saved jobs, 5 per page, closed ones marked.

Logic: services/favorites.py."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import FavPageCb
from ayvona.bot.cards import short_line
from ayvona.bot.keyboards import fav_page, list_keyboard
from ayvona.config import Settings
from ayvona.services import favorites
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_favorites")
PAGE_SIZE = 5


async def render_page(
    sf: SessionFactory, settings: Settings, user_id: int, page: int
) -> tuple[str, object | None]:
    now = utcnow()
    async with sf() as s:
        _, total = await favorites.list_saved(s, user_id, limit=0)
        pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(max(page, 1), pages)
        offset = (page - 1) * PAGE_SIZE
        jobs, total = await favorites.list_saved(s, user_id, offset=offset, limit=PAGE_SIZE)
    if not total:
        return T.FAV_EMPTY, None
    lines = [T.FAV_HEAD.format(total=total, page=page, pages=pages), ""]
    lines += [short_line(j, settings, i, now) for i, j in enumerate(jobs, start=offset + 1)]
    return "\n".join(lines), list_keyboard(jobs, offset, page, pages, fav_page)


@router.message(F.text == T.MENU_FAVORITES)
async def favorites_menu(message: Message, sf: SessionFactory, settings: Settings) -> None:
    if message.from_user is None:
        return
    text, kb = await render_page(sf, settings, message.from_user.id, 1)
    await message.answer(text, reply_markup=kb)  # type: ignore[arg-type]


@router.callback_query(FavPageCb.filter())
async def favorites_page(
    query: CallbackQuery, callback_data: FavPageCb, sf: SessionFactory, settings: Settings
) -> None:
    await query.answer()
    text, kb = await render_page(sf, settings, query.from_user.id, callback_data.page)
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=kb)  # type: ignore[arg-type]
