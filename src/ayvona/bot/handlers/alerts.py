"""🔔 Obunalar: the user's job alerts — list, ⏸/▶️, 🗑, ➕ new (the search wizard's steps:
soha → kasb → hudud → maosh + optional keyword) and "🔔 Shu qidiruvga obuna bo'lish" from the
search results. Logic: services/alerts.py; delivery happens in the worker.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import AlertCb, SubCb
from ayvona.bot.cards import filters_summary
from ayvona.bot.handlers.search import ALL, category_kb, profession_kb, region_kb, salary_kb
from ayvona.bot.keyboards import main_menu
from ayvona.config import Settings
from ayvona.db.models import Subscription
from ayvona.services import alerts as alerts_svc
from ayvona.services.alerts import CreateResult
from ayvona.services.search import SearchFilters, fts_query
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_alerts")


class AlertStates(StatesGroup):
    keyword = State()


def _cb(step: str, value: str = "") -> str:
    return AlertCb(step=step, value=value).pack()


# ------------------------------------------------------------------ list
def list_view(subs: list[Subscription], settings: Settings) -> tuple[str, InlineKeyboardMarkup]:
    limit = settings.app.alerts.max_per_user
    rows: list[list[InlineKeyboardButton]] = []
    if not subs:
        text = T.SUBS_EMPTY
    else:
        lines = [T.SUBS_HEAD.format(n=len(subs), max=limit), ""]
        for n, sub in enumerate(subs, start=1):
            state = T.SUBS_ACTIVE if sub.is_active else T.SUBS_PAUSED
            summary = filters_summary(alerts_svc.filters_of(sub), settings)
            lines.append(T.SUBS_ITEM.format(n=n, summary=summary, state=state))
            toggle = (
                InlineKeyboardButton(
                    text=T.SUBS_PAUSE.format(n=n),
                    callback_data=SubCb(action="pause", id=sub.id).pack(),
                )
                if sub.is_active
                else InlineKeyboardButton(
                    text=T.SUBS_RESUME.format(n=n),
                    callback_data=SubCb(action="resume", id=sub.id).pack(),
                )
            )
            delete = InlineKeyboardButton(
                text=T.SUBS_DELETE.format(n=n), callback_data=SubCb(action="del", id=sub.id).pack()
            )
            rows.append([toggle, delete])
        text = "\n".join(lines)
    if len(subs) < limit:
        rows.append(
            [InlineKeyboardButton(text=T.SUBS_NEW, callback_data=SubCb(action="new").pack())]
        )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_list(
    sf: SessionFactory, settings: Settings, user_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    async with sf() as s:
        subs = await alerts_svc.list_subscriptions(s, user_id)
    return list_view(subs, settings)


@router.message(F.text == T.MENU_ALERTS)
async def alerts_menu(
    message: Message, state: FSMContext, sf: SessionFactory, settings: Settings
) -> None:
    await state.set_state(None)
    if message.from_user is None:
        return
    text, kb = await _render_list(sf, settings, message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(SubCb.filter(F.action.in_({"pause", "resume", "del"})))
async def change_subscription(
    query: CallbackQuery, callback_data: SubCb, sf: SessionFactory, settings: Settings
) -> None:
    user_id = query.from_user.id
    async with sf() as s, s.begin():
        if callback_data.action == "del":
            ok = await alerts_svc.delete_subscription(s, user_id, callback_data.id)
            note = T.SUBS_DELETED_OK
        else:
            active = callback_data.action == "resume"
            ok = await alerts_svc.set_active(s, user_id, callback_data.id, active)
            note = T.SUBS_RESUMED_OK if active else T.SUBS_PAUSED_OK
    await query.answer(note if ok else "")
    if not isinstance(query.message, Message):
        return
    text, kb = await _render_list(sf, settings, user_id)
    if query.message.text and query.message.text.startswith("🔔 Obunalar"):
        await query.message.edit_text(text, reply_markup=kb)
    else:  # "🔕 Obunani to'xtatish" under an alert: keep the alert, show the list below
        await query.message.answer(text, reply_markup=kb)


# ------------------------------------------------------------------ creating
async def _create(
    message: Message,
    state: FSMContext,
    sf: SessionFactory,
    settings: Settings,
    user_id: int,
    f: SearchFilters,
) -> None:
    async with sf() as s, s.begin():
        result, _ = await alerts_svc.create_subscription(s, user_id, f, utcnow(), settings)
    await state.set_state(None)
    text = {
        CreateResult.CREATED: T.SUBS_CREATED.format(summary=filters_summary(f, settings)),
        CreateResult.LIMIT: T.SUBS_LIMIT.format(max=settings.app.alerts.max_per_user),
        CreateResult.DUPLICATE: T.SUBS_DUPLICATE,
        CreateResult.EMPTY: T.SUBS_EMPTY_FILTERS,
    }[result]
    await message.answer(text, reply_markup=main_menu())


@router.callback_query(SubCb.filter(F.action == "new"))
async def new_subscription(
    query: CallbackQuery, state: FSMContext, sf: SessionFactory, settings: Settings
) -> None:
    await query.answer()
    async with sf() as s:
        n = len(await alerts_svc.list_subscriptions(s, query.from_user.id))
    if not isinstance(query.message, Message):
        return
    if n >= settings.app.alerts.max_per_user:
        await query.message.answer(T.SUBS_LIMIT.format(max=settings.app.alerts.max_per_user))
        return
    await state.update_data(alert=SearchFilters().to_dict())
    await query.message.answer(
        T.SUBS_ASK_CATEGORY, reply_markup=category_kb(settings, False, _cb, extras=False)
    )


@router.callback_query(SubCb.filter(F.action == "fromsearch"))
async def from_search(
    query: CallbackQuery, state: FSMContext, sf: SessionFactory, settings: Settings
) -> None:
    await query.answer()
    data = await state.get_data()
    if not isinstance(query.message, Message):
        return
    if "search" not in data:
        await query.message.answer(T.SEARCH_EXPIRED)
        return
    f = SearchFilters.from_dict(data["search"])
    await _create(query.message, state, sf, settings, query.from_user.id, f)


async def _alert_filters(state: FSMContext) -> SearchFilters:
    return SearchFilters.from_dict((await state.get_data()).get("alert"))


@router.callback_query(AlertCb.filter(F.step == "cat"))
async def alert_category(
    query: CallbackQuery, callback_data: AlertCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    category = None if callback_data.value == ALL else callback_data.value
    if category and category not in settings.categories:
        return
    f = SearchFilters(category=category)
    await state.update_data(alert=f.to_dict())
    summary = filters_summary(f, settings)
    if category and settings.categories[category].professions:
        await query.message.edit_text(
            T.SEARCH_ASK_PROFESSION.format(category=summary),
            reply_markup=profession_kb(settings, category, _cb),
        )
    else:
        await query.message.edit_text(
            T.SEARCH_ASK_REGION.format(summary=summary), reply_markup=region_kb(settings, _cb)
        )


@router.callback_query(AlertCb.filter(F.step == "prof"))
async def alert_profession(
    query: CallbackQuery, callback_data: AlertCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _alert_filters(state)
    f.profession = None if callback_data.value == ALL else callback_data.value
    await state.update_data(alert=f.to_dict())
    await query.message.edit_text(
        T.SEARCH_ASK_REGION.format(summary=filters_summary(f, settings)),
        reply_markup=region_kb(settings, _cb),
    )


@router.callback_query(AlertCb.filter(F.step == "reg"))
async def alert_region(
    query: CallbackQuery, callback_data: AlertCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _alert_filters(state)
    f.region = None if callback_data.value == ALL else callback_data.value
    await state.update_data(alert=f.to_dict())
    await query.message.edit_text(
        T.SEARCH_ASK_SALARY.format(summary=filters_summary(f, settings)),
        reply_markup=salary_kb(settings, _cb),
    )


@router.callback_query(AlertCb.filter(F.step == "sal"))
async def alert_salary(
    query: CallbackQuery, callback_data: AlertCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    f = await _alert_filters(state)
    f.min_salary = int(callback_data.value) if callback_data.value.isdigit() else None
    f.min_salary = f.min_salary or None
    await state.update_data(alert=f.to_dict())
    await state.set_state(AlertStates.keyword)
    await query.message.edit_text(f"🔔 {filters_summary(f, settings)}")
    await query.message.answer(
        T.SUBS_ASK_KEYWORD.format(summary=filters_summary(f, settings), skip=T.BTN_SKIP),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=T.BTN_SKIP)], [KeyboardButton(text=T.BTN_CANCEL)]],
            resize_keyboard=True,
        ),
    )


@router.message(StateFilter(AlertStates.keyword), F.text)
async def alert_keyword(
    message: Message, state: FSMContext, sf: SessionFactory, settings: Settings
) -> None:
    if message.from_user is None:
        return
    if message.text == T.BTN_CANCEL:
        await state.set_state(None)
        await message.answer(T.CANCELLED, reply_markup=main_menu())
        return
    f = await _alert_filters(state)
    if message.text != T.BTN_SKIP:
        keyword = (message.text or "").strip()[:100]
        if fts_query(keyword) is None:
            await message.answer(T.SEARCH_BAD_KEYWORD)
            return
        f.keyword = keyword
    await _create(message, state, sf, settings, message.from_user.id, f)
