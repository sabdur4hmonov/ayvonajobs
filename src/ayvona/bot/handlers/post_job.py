"""📢 E'lon joylash — the step-by-step form (FSM). Every decision is in
services/job_submission.py; this module only asks, stores the answers and shows the result.

First the TYPE: 💼 Ish (a salaried job) or 🧩 Loyiha (a one-time paid project).

Ish: 1 soha (buttons) → 2 lavozim → 3 kompaniya (skip) → 4 maosh ("Kelishiladi" / text) →
5 hudud (buttons, "Masofaviy") + manzil (skip) → 6 ish vaqti (skip) → 7 talablar (skip) →
8 ALOQA (required: "📱 Raqamni yuborish", own @username or typed) → 9 MUDDAT (how many days the
ad stays active: buttons) → preview (the channel caption) → ✅ Yuborish / ✏️ Tahrirlash.

Loyiha: 1 nomi → 2 tavsif → 3 byudjet (bir martalik; "Kelishiladi" / text) → 4 muddat (skip) →
5 ALOQA (required) → 6 MUDDAT (how many days it stays active) → preview → Yuborish.

"⬅️ Orqaga" and "❌ Bekor qilish" work on every step; a menu button leaves the form.
"""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
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
from ayvona.bot.callbacks import PostCb
from ayvona.bot.keyboards import main_menu
from ayvona.bot.moderation import notify_review
from ayvona.config import Settings
from ayvona.db.models import JobKind, User
from ayvona.services import job_submission as js
from ayvona.services.job_submission import Draft, LimitHit, LimitReason, Outcome
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="public_post_job")


class PostJob(StatesGroup):
    kind = State()
    category = State()
    title = State()
    description = State()
    budget = State()
    deadline = State()
    company = State()
    salary = State()
    region = State()
    city = State()
    schedule = State()
    requirements = State()
    contact = State()
    duration = State()
    preview = State()


STEPS_JOB = [
    "kind",
    "category",
    "title",
    "company",
    "salary",
    "region",
    "city",
    "schedule",
    "requirements",
    "contact",
    "duration",
]
STEPS_PROJECT = ["kind", "title", "description", "budget", "deadline", "contact", "duration"]
STATE_OF = {name: getattr(PostJob, name) for name in dict.fromkeys(STEPS_JOB + STEPS_PROJECT)}
STEP_OF_STATE = {state.state: name for name, state in STATE_OF.items()}
SKIPPABLE = {"company", "city", "schedule", "requirements", "deadline"}
NO_NUMBER = {"kind", "city"}  # the type question / a follow-up of "region"
FORM_STATES = StateFilter(*STATE_OF.values(), PostJob.preview)


# ------------------------------------------------------------------ keyboards
def _nav(*extra: list[KeyboardButton]) -> ReplyKeyboardMarkup:
    rows = [*extra, [KeyboardButton(text=T.BTN_BACK), KeyboardButton(text=T.BTN_CANCEL)]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=False)


def _category_kb(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=cat.title, callback_data=PostCb(action="cat", value=key).pack())
        for key, cat in settings.categories.items()
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )


def _region_kb(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=reg.title, callback_data=PostCb(action="reg", value=key).pack())
        for key, reg in settings.regions.regions.items()
    ]
    buttons.append(
        InlineKeyboardButton(
            text=T.BTN_REMOTE, callback_data=PostCb(action="reg", value=js.REMOTE).pack()
        )
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )


def _duration_kb(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=T.BTN_DAYS.format(n=d), callback_data=PostCb(action="days", value=str(d)).pack()
        )
        for d in settings.app.posting.duration_options
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    )


def _kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.BTN_KIND_JOB, callback_data=PostCb(action="kind", value="job").pack()
                ),
                InlineKeyboardButton(
                    text=T.BTN_KIND_PROJECT,
                    callback_data=PostCb(action="kind", value="project").pack(),
                ),
            ]
        ]
    )


def _preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=T.BTN_SUBMIT, callback_data=PostCb(action="send").pack()),
                InlineKeyboardButton(text=T.BTN_EDIT, callback_data=PostCb(action="edit").pack()),
            ],
            [InlineKeyboardButton(text=T.BTN_CANCEL, callback_data=PostCb(action="cancel").pack())],
        ]
    )


def _edit_kb(draft: Draft) -> InlineKeyboardMarkup:
    fields = T.PROJECT_FIELDS if draft.is_project else T.POST_FIELDS
    buttons = [
        InlineKeyboardButton(text=label, callback_data=PostCb(action="field", value=name).pack())
        for name, label in fields.items()
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    )


# ------------------------------------------------------------------ helpers
async def _draft(state: FSMContext) -> Draft:
    return Draft.from_dict((await state.get_data()).get("draft") or {})


async def _save(state: FSMContext, draft: Draft) -> None:
    await state.update_data(draft=draft.to_dict())


def limit_text(hit: LimitHit, settings: Settings) -> str:
    cfg = settings.app.posting
    if hit.reason is LimitReason.DAILY:
        return T.POST_LIMIT_DAILY.format(n=cfg.max_per_day)
    if hit.reason is LimitReason.INTERVAL:
        return T.POST_LIMIT_INTERVAL.format(total=round(cfg.min_interval_minutes), left=hit.minutes)
    return T.POST_LIMIT_WAITING


def steps_of(draft: Draft) -> list[str]:
    """The questions of this ad type, in order (the first one is the type itself)."""
    return STEPS_PROJECT if draft.is_project else STEPS_JOB


def numbered(step: str, text: str, draft: Draft) -> str:
    """``"3/9. <question>"`` — the number of the step among the numbered ones."""
    steps = [s for s in steps_of(draft) if s not in NO_NUMBER]
    if step in NO_NUMBER:
        return text
    return f"{steps.index(step) + 1}/{len(steps)}. {text}"


async def ask(step: str, message: Message, state: FSMContext, settings: Settings) -> None:
    """Show the question of ``step`` and wait for its answer."""
    await state.set_state(STATE_OF[step])
    draft = await _draft(state)
    skip = [KeyboardButton(text=T.BTN_SKIP)] if step in SKIPPABLE else None
    if step == "kind":
        await message.answer(T.POST_ASK_KIND, reply_markup=_nav())
        await message.answer(T.POST_NEED_BUTTON, reply_markup=_kind_kb())
    elif step == "description":
        await message.answer(numbered(step, T.POST_ASK_DESCRIPTION, draft), reply_markup=_nav())
    elif step == "budget":
        await message.answer(
            numbered(step, T.POST_ASK_BUDGET.format(negotiable=T.BTN_NEGOTIABLE), draft),
            reply_markup=_nav([KeyboardButton(text=T.BTN_NEGOTIABLE)]),
        )
    elif step == "deadline":
        await message.answer(
            numbered(step, T.POST_ASK_DEADLINE, draft), reply_markup=_nav(skip or [])
        )
    elif step == "category":
        await message.answer(numbered(step, T.POST_ASK_CATEGORY, draft), reply_markup=_nav())
        await message.answer(T.POST_NEED_BUTTON, reply_markup=_category_kb(settings))
    elif step == "title":
        question = T.POST_ASK_PROJECT_TITLE if draft.is_project else T.POST_ASK_TITLE
        await message.answer(numbered(step, question, draft), reply_markup=_nav())
    elif step == "company":
        await message.answer(
            numbered(step, T.POST_ASK_COMPANY, draft), reply_markup=_nav(skip or [])
        )
    elif step == "salary":
        await message.answer(
            numbered(step, T.POST_ASK_SALARY.format(negotiable=T.BTN_NEGOTIABLE), draft),
            reply_markup=_nav([KeyboardButton(text=T.BTN_NEGOTIABLE)]),
        )
    elif step == "region":
        await message.answer(numbered(step, T.POST_ASK_REGION, draft), reply_markup=_nav())
        await message.answer(T.POST_NEED_BUTTON, reply_markup=_region_kb(settings))
    elif step == "city":
        await message.answer(T.POST_ASK_CITY, reply_markup=_nav(skip or []))
    elif step == "schedule":
        await message.answer(
            numbered(step, T.POST_ASK_SCHEDULE, draft), reply_markup=_nav(skip or [])
        )
    elif step == "requirements":
        await message.answer(
            numbered(step, T.POST_ASK_REQUIREMENTS, draft), reply_markup=_nav(skip or [])
        )
    elif step == "duration":
        await message.answer(numbered(step, T.POST_ASK_DURATION, draft), reply_markup=_nav())
        await message.answer(T.POST_NEED_BUTTON, reply_markup=_duration_kb(settings))
    elif step == "contact":
        row = [KeyboardButton(text=T.BTN_SEND_PHONE, request_contact=True)]
        user = message.chat  # private chat: the chat is the user
        own = js.username_of(getattr(user, "username", None))
        if own:
            row.append(KeyboardButton(text=T.BTN_MY_USERNAME.format(username=own)))
        await message.answer(
            numbered(step, T.POST_ASK_CONTACT.format(phone=T.BTN_SEND_PHONE), draft),
            reply_markup=_nav(row),
        )


async def advance(step: str, message: Message, state: FSMContext, settings: Settings) -> None:
    """After an answer: back to the preview when editing, else the next question."""
    data = await state.get_data()
    if data.get("editing") and step != "region":  # region is followed by its city question
        await show_preview(message, state, settings)
        return
    steps = steps_of(await _draft(state))
    nxt = steps[steps.index(step) + 1] if step != steps[-1] else None
    if nxt is None:
        await show_preview(message, state, settings)
    else:
        await ask(nxt, message, state, settings)


async def show_preview(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.update_data(editing=False)
    await state.set_state(PostJob.preview)
    draft = await _draft(state)
    out, _ = js.render(draft, settings)
    await message.answer(T.POST_PREVIEW_HEAD, reply_markup=main_menu())
    await message.answer(out.html)
    if draft.days:
        await message.answer(T.POST_PREVIEW_DAYS.format(n=draft.days))
    await message.answer(T.POST_PREVIEW_ASK, reply_markup=_preview_kb())


async def cancel_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(T.CANCELLED, reply_markup=main_menu())


# ------------------------------------------------------------------ entry
@router.message(F.text == T.MENU_POST)
async def start_form(
    message: Message, state: FSMContext, sf: SessionFactory, settings: Settings, db_user: User
) -> None:
    await state.clear()
    async with sf() as s:
        hit = await js.check_limits(s, db_user, utcnow(), settings)
    if hit is not None:
        await message.answer(limit_text(hit, settings), reply_markup=main_menu())
        return
    await state.update_data(draft=Draft().to_dict(), editing=False)
    await message.answer(T.POST_INTRO.format(back=T.BTN_BACK, cancel=T.BTN_CANCEL))
    await ask("kind", message, state, settings)


# ------------------------------------------------------------------ navigation
@router.message(FORM_STATES, F.text == T.BTN_CANCEL)
async def cancel_btn(message: Message, state: FSMContext) -> None:
    await cancel_form(message, state)


@router.message(FORM_STATES, F.text == T.BTN_BACK)
async def back_btn(message: Message, state: FSMContext, settings: Settings) -> None:
    current = await state.get_state()
    steps = steps_of(await _draft(state))
    if current == PostJob.preview.state:
        await ask(steps[-1], message, state, settings)
        return
    step = STEP_OF_STATE.get(current or "", steps[0])
    idx = steps.index(step) if step in steps else 0
    if idx == 0:  # "Orqaga" on the first question = leave the form
        await cancel_form(message, state)
        return
    await state.update_data(editing=False)
    await ask(steps[idx - 1], message, state, settings)


@router.callback_query(PostCb.filter(F.action == "cancel"))
async def cancel_cb(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await cancel_form(query.message, state)


# ------------------------------------------------------------------ choice steps
@router.callback_query(StateFilter(PostJob.kind), PostCb.filter(F.action == "kind"))
async def kind_cb(
    query: CallbackQuery, callback_data: PostCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if callback_data.value not in (JobKind.JOB.value, JobKind.PROJECT.value) or not isinstance(
        query.message, Message
    ):
        return
    draft = await _draft(state)
    if draft.kind != callback_data.value:  # another type: the answers of the first one do not fit
        draft = Draft(kind=callback_data.value)
        await _save(state, draft)
    label = T.BTN_KIND_PROJECT if draft.is_project else T.BTN_KIND_JOB
    await query.message.edit_text(f"✅ {label}")
    await advance("kind", query.message, state, settings)


@router.callback_query(StateFilter(PostJob.category), PostCb.filter(F.action == "cat"))
async def category_cb(
    query: CallbackQuery, callback_data: PostCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    if callback_data.value not in settings.categories or not isinstance(query.message, Message):
        return
    draft = await _draft(state)
    draft.category = callback_data.value
    await _save(state, draft)
    await query.message.edit_text(f"✅ {html.escape(settings.categories[draft.category].title)}")
    await advance("category", query.message, state, settings)


@router.callback_query(StateFilter(PostJob.region), PostCb.filter(F.action == "reg"))
async def region_cb(
    query: CallbackQuery, callback_data: PostCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    value = callback_data.value
    if (value != js.REMOTE and value not in settings.regions.regions) or not isinstance(
        query.message, Message
    ):
        return
    draft = await _draft(state)
    draft.region = value
    await _save(state, draft)
    title = T.BTN_REMOTE if value == js.REMOTE else settings.regions.regions[value].title
    await query.message.edit_text(f"✅ {html.escape(title)}")
    await advance("region", query.message, state, settings)


@router.callback_query(StateFilter(PostJob.duration), PostCb.filter(F.action == "days"))
async def days_cb(
    query: CallbackQuery, callback_data: PostCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    try:
        days = int(callback_data.value)
    except ValueError:
        return
    if days not in settings.app.posting.duration_options or not isinstance(query.message, Message):
        return
    draft = await _draft(state)
    draft.days = days
    await _save(state, draft)
    await query.message.edit_text(f"✅ {T.BTN_DAYS.format(n=days)}")
    await advance("duration", query.message, state, settings)


@router.message(StateFilter(PostJob.kind, PostJob.category, PostJob.region, PostJob.duration))
async def need_button(message: Message) -> None:
    await message.answer(T.POST_NEED_BUTTON)


# ------------------------------------------------------------------ text steps
async def _text_step(
    step: str, message: Message, state: FSMContext, settings: Settings, limit: int
) -> None:
    draft = await _draft(state)
    if (
        step in SKIPPABLE
        and message.text == T.BTN_SKIP
        or step in ("salary", "budget")
        and message.text == T.BTN_NEGOTIABLE
    ):
        setattr(draft, step, None)
    else:
        value = js.clean_field(message.text, limit)
        if value is None:
            await message.answer(T.POST_TOO_LONG.format(limit=limit))
            return
        if step == "title" and sum(ch.isalpha() for ch in value) < 3:
            await message.answer(T.POST_TOO_SHORT)
            return
        setattr(draft, step, value)
    await _save(state, draft)
    await advance(step, message, state, settings)


@router.message(StateFilter(PostJob.title), F.text)
async def title_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("title", message, state, settings, settings.app.posting.max_title)


@router.message(StateFilter(PostJob.company), F.text)
async def company_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("company", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.salary), F.text)
async def salary_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("salary", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.description), F.text)
async def description_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("description", message, state, settings, settings.app.posting.max_description)


@router.message(StateFilter(PostJob.budget), F.text)
async def budget_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("budget", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.deadline), F.text)
async def deadline_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("deadline", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.city), F.text)
async def city_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("city", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.schedule), F.text)
async def schedule_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step("schedule", message, state, settings, settings.app.posting.max_short_field)


@router.message(StateFilter(PostJob.requirements), F.text)
async def requirements_msg(message: Message, state: FSMContext, settings: Settings) -> None:
    await _text_step(
        "requirements", message, state, settings, settings.app.posting.max_requirements
    )


# ------------------------------------------------------------------ contact (required)
@router.message(StateFilter(PostJob.contact), F.contact)
async def contact_shared(message: Message, state: FSMContext, settings: Settings) -> None:
    phone = js.phone_from_contact(message.contact.phone_number if message.contact else "")
    if phone is None:
        await message.answer(T.POST_NO_CONTACT)
        return
    draft = await _draft(state)
    draft.phone = phone
    await _save(state, draft)
    await advance("contact", message, state, settings)


@router.message(StateFilter(PostJob.contact), F.text)
async def contact_typed(message: Message, state: FSMContext, settings: Settings) -> None:
    own = js.username_of(message.from_user.username if message.from_user else None)
    if own and message.text == T.BTN_MY_USERNAME.format(username=own):
        phone, username = None, own
    else:
        phone, username = js.parse_contact(message.text or "")
    if not (phone or username):
        await message.answer(T.POST_NO_CONTACT)
        return
    draft = await _draft(state)
    draft.phone, draft.username = phone, username
    await _save(state, draft)
    await advance("contact", message, state, settings)


@router.message(StateFilter(PostJob.contact))
async def contact_other(message: Message) -> None:
    await message.answer(T.POST_NO_CONTACT)


# ------------------------------------------------------------------ preview: edit / send
@router.callback_query(StateFilter(PostJob.preview), PostCb.filter(F.action == "edit"))
async def edit_cb(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.answer(T.POST_EDIT_WHICH, reply_markup=_edit_kb(await _draft(state)))


@router.callback_query(StateFilter(PostJob.preview), PostCb.filter(F.action == "field"))
async def edit_field_cb(
    query: CallbackQuery, callback_data: PostCb, state: FSMContext, settings: Settings
) -> None:
    await query.answer()
    steps = steps_of(await _draft(state))
    if callback_data.value in steps[1:] and isinstance(query.message, Message):
        await state.update_data(editing=True)
        await ask(callback_data.value, query.message, state, settings)


@router.callback_query(PostCb.filter(F.action == "send"))
async def send_cb(
    query: CallbackQuery,
    state: FSMContext,
    sf: SessionFactory,
    settings: Settings,
    db_user: User,
    bot: Bot,
) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    message = query.message
    if await state.get_state() != PostJob.preview.state:
        await message.answer(T.POST_EXPIRED, reply_markup=main_menu())
        return
    draft = await _draft(state)
    async with sf() as s, s.begin():
        result = await js.submit(s, draft, db_user, utcnow(), settings)
    await message.edit_reply_markup(reply_markup=None)
    if result.outcome is Outcome.NO_CONTACT:
        await ask("contact", message, state, settings)
        return
    await state.clear()
    if result.outcome is Outcome.LIMIT and result.limit is not None:
        text = limit_text(result.limit, settings)
    else:
        text = {
            Outcome.QUEUED: T.POST_QUEUED,
            Outcome.REVIEW: T.POST_REVIEW,
            Outcome.REJECTED: T.POST_REJECTED,
            Outcome.DUPLICATE: T.POST_DUPLICATE,
        }[result.outcome]
    await message.answer(text, reply_markup=main_menu())
    if result.outcome is Outcome.REVIEW and result.job_id is not None:
        await notify_review(bot, settings, sf, result.job_id, db_user, result.review_reasons)
