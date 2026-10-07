"""🧩 Loyihalar: the open one-time paid projects, 5 per page, newest first.

Logic: services/projects.py. A project's details open with the same "N. Batafsil" button as a job
(``JobCb show``): the channel caption, [📩 Murojaat] [⭐ Saqlash] [📤 Ulashish].
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import ProjPageCb
from ayvona.bot.cards import project_line
from ayvona.bot.keyboards import list_keyboard, main_menu, proj_page
from ayvona.services import projects
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_projects")
PAGE_SIZE = 5


async def render_page(sf: SessionFactory, page: int) -> tuple[str, object | None]:
    now = utcnow()
    async with sf() as s:
        _, total = await projects.list_open(s, now, limit=0)
        pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(max(page, 1), pages)
        offset = (page - 1) * PAGE_SIZE
        jobs, total = await projects.list_open(s, now, offset=offset, limit=PAGE_SIZE)
    if not total:
        return T.PROJECTS_EMPTY, None
    lines = [T.PROJECTS_HEAD.format(total=total), ""]
    lines += [project_line(j, i) for i, j in enumerate(jobs, start=offset + 1)]
    return "\n".join(lines), list_keyboard(jobs, offset, page, pages, proj_page)


async def open_projects(message: Message, sf: SessionFactory) -> None:
    text, kb = await render_page(sf, 1)
    await message.answer(text, reply_markup=kb)  # type: ignore[arg-type]


@router.message(F.text == T.MENU_PROJECTS)
async def projects_menu(message: Message, state: FSMContext, sf: SessionFactory) -> None:
    await state.clear()  # the menu button leaves a half-filled form
    await message.answer(T.MENU_PROJECTS, reply_markup=main_menu())
    await open_projects(message, sf)


@router.callback_query(ProjPageCb.filter())
async def projects_page(
    query: CallbackQuery, callback_data: ProjPageCb, sf: SessionFactory
) -> None:
    await query.answer()
    text, kb = await render_page(sf, callback_data.page)
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=kb)  # type: ignore[arg-type]
