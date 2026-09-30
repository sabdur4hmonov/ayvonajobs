"""🔍 Ish qidirish — the wizard (soha → kasb → hudud → maosh) or a keyword, then the results
(5 per page, newest first) with [N. Batafsil] [⭐] [📤] per job. The search itself:
services/search.py. The filters of the current search live in the FSM data (``search``);
after a restart the pages fall back to the user's last search (``search_logs``).
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import JobCb, SearchCb
from ayvona.bot.cards import filters_summary, short_line
from ayvona.bot.keyboards import main_menu, share_url
from ayvona.config import Settings
from ayvona.db.models import Job, User
from ayvona.services import search as search_svc
from ayvona.services.jobs_public import channel_post_url
from ayvona.services.search import REMOTE, SearchFilters
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_search")
ALL = "*"


class SearchStates(StatesGroup):
    keyword = State()


def _cb(step: str, value: str = "") -> str:
    return SearchCb(step=step, value=value).pack()


def _grid(buttons: list[InlineKeyboardButton], width: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + width] for i in range(0, len(buttons), width)]


# ------------------------------------------------------------------ wizard keyboards
def category_kb(settings: Settings, has_last: bool) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=cat.title, callback_data=_cb("cat", key))
        for key, cat in settings.categories.items()
    ]
    rows = _grid(buttons)
    rows.append([InlineKeyboardButton(text=T.SEARCH_ALL, callback_data=_cb("cat", ALL))])
    rows.append([InlineKeyboardButton(text=T.SEARCH_BY_WORD, callback_data=_cb("kw"))])
    if has_last:
        rows.append([InlineKeyboardButton(text=T.SEARCH_LAST, callback_data=_cb("last"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profession_kb(settings: Settings, category: str) -> InlineKeyboardMarkup:
    profs = settings.categories[category].professions
    buttons = [
        InlineKeyboardButton(text=p.title, callback_data=_cb("prof", key))
        for key, p in profs.items()
    ]
    rows = [
        [InlineKeyboardButton(text=T.SEARCH_ALL, callback_data=_cb("prof", ALL))],
        *_grid(buttons),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_kb(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=reg.title, callback_data=_cb("reg", key))
        for key, reg in settings.regions.regions.items()
    ]
    rows = [
        [
            InlineKeyboardButton(text=T.SEARCH_ALL, callback_data=_cb("reg", ALL)),
            InlineKeyboardButton(text=T.BTN_REMOTE, callback_data=_cb("reg", REMOTE)),
        ],
        *_grid(buttons),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def salary_kb(settings: Settings) -> InlineKeyboardMarkup:
    steps = [
        InlineKeyboardButton(
            text=T.SEARCH_SALARY_STEP.format(mln=f"{v / 1_000_000:g}"),
            callback_data=_cb("sal", str(v)),
        )
        for v in settings.app.search.salary_steps
    ]
    rows = [
        [InlineKeyboardButton(text=T.SEARCH_ANY_SALARY, callback_data=_cb("sal", "0"))],
        *_grid(steps),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_kb(
    jobs: list[Job], offset: int, page: int, pages: int, settings: Settings, extra: list[Any]
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i, job in enumerate(jobs, start=offset + 1):
        row = [
            InlineKeyboardButton(
                text=f"{i}. {T.BTN_DETAILS}", callback_data=JobCb(action="show", id=job.id).pack()
            ),
            InlineKeyboardButton(
                text=f"{T.BTN_SAVE}", callback_data=JobCb(action="save", id=job.id).pack()
            ),
        ]
        if post := channel_post_url(settings, job):
            row.append(InlineKeyboardButton(text=T.BTN_SHARE, url=share_url(post)))
        rows.append(row)
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=T.BTN_PREV, callback_data=_cb("page", str(page - 1))))
    if page < pages:
        nav.append(InlineKeyboardButton(text=T.BTN_NEXT, callback_data=_cb("page", str(page + 1))))
    if nav:
        rows.append(nav)
    rows.extend(extra)
    rows.append([InlineKeyboardButton(text=T.SEARCH_NEW, callback_data=_cb("new"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_extra_buttons(f: SearchFilters) -> list[Any]:
    """Rows added under the results (Bosqich 13: "🔔 Shu qidiruvga obuna bo'lish")."""
    return []


# ------------------------------------------------------------------ results
async def render_results(
    sf: SessionFactory,
    settings: Settings,
    f: SearchFilters,
    page: int,
    *,
    user_id: int | None,
    log: bool,
) -> tuple[str, InlineKeyboardMarkup]:
    now = utcnow()
    size = settings.app.search.page_size
    async with sf() as s, s.begin():
        rate = await search_svc.usd_rate(s, settings.app.search.usd_rate_fallback)
        _, total = await search_svc.search(s, f, now, usd_rate=rate, limit=0)
        pages = max((total + size - 1) // size, 1)
        page = min(max(page, 1), pages)
        offset = (page - 1) * size
        jobs, total = await search_svc.search(s, f, now, usd_rate=rate, offset=offset, limit=size)
        if log:
            await search_svc.log_search(s, user_id, f, total, now)
    summary = filters_summary(f, settings)
    extra = results_extra_buttons(f)
    if not total:
        return T.SEARCH_EMPTY.format(summary=summary), results_kb([], 0, 1, 1, settings, extra)
    lines = [T.SEARCH_HEAD.format(total=total, summary=summary, page=page, pages=pages), ""]
    lines += [short_line(j, settings, i, now) for i, j in enumerate(jobs, start=offset + 1)]
    return "\n".join(lines), results_kb(jobs, offset, page, pages, settings, extra)


async def _filters(state: FSMContext) -> SearchFilters:
    return SearchFilters.from_dict((await state.get_data()).get("search"))


async def _set_filters(state: FSMContext, f: SearchFilters) -> None:
    await state.update_data(search=f.to_dict())


# ------------------------------------------------------------------ entry
async def open_search(
    message: Message,
    state: FSMContext,
    *,
    sf: SessionFactory,
    settings: Settings,
    db_user: User,
    **_: object,
) -> None:
    """Menu button and ``?start=search``."""
    await state.set_state(None)
    await _set_filters(state, SearchFilters())
    async with sf() as s:
        last = await search_svc.last_filters(s, db_user.tg_id)
    await message.answer(
        T.SEARCH_ASK_CATEGORY,
        reply_markup=category_kb(settings, last is not None and not last.empty),
    )


# ------------------------------------------------------------------ wizard steps
@router.callback_query(SearchCb.filter(F.step == "cat"))
async def pick_category(
    query: CallbackQuery, callback_data: SearchCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = SearchFilters(category=None if callback_data.value == ALL else callback_data.value)
    if f.category and f.category not in settings.categories:
        return
    await _set_filters(state, f)
    if f.category and settings.categories[f.category].professions:
        await query.message.edit_text(
            T.SEARCH_ASK_PROFESSION.format(category=filters_summary(f, settings)),
            reply_markup=profession_kb(settings, f.category),
        )
    else:
        await query.message.edit_text(
            T.SEARCH_ASK_REGION.format(summary=filters_summary(f, settings)),
            reply_markup=region_kb(settings),
        )


@router.callback_query(SearchCb.filter(F.step == "prof"))
async def pick_profession(
    query: CallbackQuery, callback_data: SearchCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _filters(state)
    f.profession = None if callback_data.value == ALL else callback_data.value
    await _set_filters(state, f)
    await query.message.edit_text(
        T.SEARCH_ASK_REGION.format(summary=filters_summary(f, settings)),
        reply_markup=region_kb(settings),
    )


@router.callback_query(SearchCb.filter(F.step == "reg"))
async def pick_region(
    query: CallbackQuery, callback_data: SearchCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _filters(state)
    f.region = None if callback_data.value == ALL else callback_data.value
    await _set_filters(state, f)
    await query.message.edit_text(
        T.SEARCH_ASK_SALARY.format(summary=filters_summary(f, settings)),
        reply_markup=salary_kb(settings),
    )


@router.callback_query(SearchCb.filter(F.step == "sal"))
async def pick_salary(
    query: CallbackQuery,
    callback_data: SearchCb,
    state: FSMContext,
    settings: Settings,
    sf: SessionFactory,
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _filters(state)
    f.min_salary = int(callback_data.value) if callback_data.value.isdigit() else None
    f.min_salary = f.min_salary or None
    await _set_filters(state, f)
    text, kb = await render_results(sf, settings, f, 1, user_id=query.from_user.id, log=True)
    await query.message.edit_text(text, reply_markup=kb)


@router.callback_query(SearchCb.filter(F.step == "page"))
async def turn_page(
    query: CallbackQuery,
    callback_data: SearchCb,
    state: FSMContext,
    settings: Settings,
    sf: SessionFactory,
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    data = await state.get_data()
    f = SearchFilters.from_dict(data["search"]) if "search" in data else None
    if f is None:  # the bot was restarted: the user's last search
        async with sf() as s:
            f = await search_svc.last_filters(s, query.from_user.id)
        if f is None:
            await query.message.answer(T.SEARCH_EXPIRED)
            return
        await _set_filters(state, f)
    page = int(callback_data.value) if callback_data.value.isdigit() else 1
    text, kb = await render_results(sf, settings, f, page, user_id=query.from_user.id, log=False)
    await query.message.edit_text(text, reply_markup=kb)


@router.callback_query(SearchCb.filter(F.step == "last"))
async def repeat_last(
    query: CallbackQuery, state: FSMContext, settings: Settings, sf: SessionFactory
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    async with sf() as s:
        f = await search_svc.last_filters(s, query.from_user.id)
    if f is None:
        await query.message.answer(T.SEARCH_EXPIRED)
        return
    await _set_filters(state, f)
    text, kb = await render_results(sf, settings, f, 1, user_id=query.from_user.id, log=True)
    await query.message.edit_text(text, reply_markup=kb)


@router.callback_query(SearchCb.filter(F.step == "new"))
async def new_search(
    query: CallbackQuery, state: FSMContext, settings: Settings, sf: SessionFactory, db_user: User
) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await open_search(query.message, state, sf=sf, settings=settings, db_user=db_user)


# ------------------------------------------------------------------ keyword
@router.callback_query(SearchCb.filter(F.step == "kw"))
async def ask_keyword(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SearchStates.keyword)
    if isinstance(query.message, Message):
        await query.message.answer(T.SEARCH_ASK_KEYWORD, reply_markup=main_menu())


@router.message(StateFilter(SearchStates.keyword), F.text)
async def keyword_msg(
    message: Message, state: FSMContext, settings: Settings, sf: SessionFactory
) -> None:
    keyword = (message.text or "").strip()[:100]
    if search_svc.fts_query(keyword) is None:
        await message.answer(T.SEARCH_BAD_KEYWORD)
        return
    await state.set_state(None)
    f = SearchFilters(keyword=keyword)
    await _set_filters(state, f)
    user_id = message.from_user.id if message.from_user else None
    text, kb = await render_results(sf, settings, f, 1, user_id=user_id, log=True)
    await message.answer(text, reply_markup=kb)
