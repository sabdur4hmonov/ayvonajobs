"""Post pictures from the bot (only ``ADMIN_IDS``), docs/IMAGES.md:

* /images           — per category: real / placeholder pictures, professions without any real one
* /images <kasb>    — files of that folder, each with [🗑]
* /addimage <kasb>  — the admin sends pictures, they are saved into the folder
* /images review   — go through every picture slot ONE BY ONE: the current picture and a proposed
                     new one, [✅ Tasdiqlash] [🔄 Boshqasi] [⏭ O'tkazish] [⏹ To'xtatish]; nothing is
                     replaced without ✅ (services/image_review.py). Never started automatically.

Only files in ``assets/images/<category>/[<profession>/]`` change; the picking rules
(processing/images.py) are untouched: a real picture automatically wins over the placeholders.
A deleted picture is moved to ``data/images_trash/`` (can be put back by hand), not destroyed.
"""

from __future__ import annotations

import asyncio
import html
import io
from dataclasses import dataclass, field
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from loguru import logger
from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.handlers.admin import chunks
from ayvona.config import Settings
from ayvona.processing.images import is_placeholder, list_images
from ayvona.services import image_review as review
from ayvona.timeutil import utcnow

router = Router(name="admin_images")
SessionFactory = async_sessionmaker[AsyncSession]

MIN_CATEGORY_IMAGES = 3
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class AddImage(StatesGroup):
    waiting = State()


class ImageDelCb(CallbackData, prefix="imd"):
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class Target:
    """A picture folder: a category, or a profession inside it."""

    key: str
    category: str
    profession: str | None
    title: str

    def folder(self, root: Path) -> Path:
        return root / self.category / self.profession if self.profession else root / self.category

    def rel(self) -> str:
        return f"{self.category}/{self.profession}" if self.profession else self.category


def resolve_target(settings: Settings, key: str) -> Target | None:
    """``oshpaz`` / ``#oshpaz`` -> profession folder; ``oshxona`` -> category folder."""
    k = key.strip().lstrip("#").lower()
    for cat_key, cat in settings.categories.items():
        if k in cat.professions:
            return Target(k, cat_key, k, cat.professions[k].title)
    if k in settings.categories:
        return Target(k, k, None, settings.categories[k].title)
    return None


def _counts(folder: Path) -> tuple[int, int]:
    files = list_images(folder)
    placeholders = sum(1 for f in files if is_placeholder(f))
    return len(files) - placeholders, placeholders


# ------------------------------------------------------------------ /images
@router.message(Command("images"))
async def images_cmd(
    message: Message, command: CommandObject, settings: Settings, sf: SessionFactory
) -> None:
    root = settings.images_dir
    words = (command.args or "").split()
    if words and words[0].lower() == "review":
        await start_review(message, settings, sf, reset=words[1:2] == ["reset"])
        return
    if command.args:
        target = resolve_target(settings, command.args)
        if target is None:
            await message.answer(T.IMAGES_UNKNOWN.format(key=html.escape(command.args.strip())))
            return
        await _send_folder(message, settings, target)
        return

    lines = [T.IMAGES_HEAD]
    for cat_key, cat in settings.categories.items():
        real, placeholder = _counts(root / cat_key)
        icon = "✅" if real >= MIN_CATEGORY_IMAGES else ("🟡" if real else "🔴")
        lines.append(
            T.IMAGES_CATEGORY.format(
                icon=icon,
                title=html.escape(cat.title),
                key=cat_key,
                real=real,
                placeholder=placeholder,
            )
        )
        empty = [p for p in cat.professions if _counts(root / cat_key / p)[0] == 0]
        if empty:
            lines.append(T.IMAGES_PROFESSIONS_EMPTY.format(names=", ".join(empty)))
    lines.append(T.IMAGES_FOOT)
    for part in chunks(lines):
        await message.answer(part)


def _folder_view(settings: Settings, target: Target) -> tuple[str, InlineKeyboardMarkup | None]:
    files = list_images(target.folder(settings.images_dir))
    lines = [
        T.IMAGES_FILE.format(
            n=i,
            name=html.escape(f.name),
            mark=T.IMAGES_PLACEHOLDER_MARK if is_placeholder(f) else "",
        )
        for i, f in enumerate(files, 1)
    ]
    buttons = []
    for f in files:
        cb = ImageDelCb(key=target.key, name=f.name)
        if len(cb.pack()) <= 64:
            buttons.append([InlineKeyboardButton(text=f"🗑 {f.name}", callback_data=cb.pack())])
    text = T.IMAGES_FOLDER.format(
        title=html.escape(target.title),
        folder=html.escape(target.rel()),
        lines="\n".join(lines) or T.IMAGES_FOLDER_EMPTY,
    )
    return text, InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


async def _send_folder(message: Message, settings: Settings, target: Target) -> None:
    text, keyboard = _folder_view(settings, target)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(ImageDelCb.filter())
async def image_delete_cb(
    query: CallbackQuery, callback_data: ImageDelCb, settings: Settings
) -> None:
    target = resolve_target(settings, callback_data.key)
    name = Path(callback_data.name).name  # never a path from outside the folder
    path = target.folder(settings.images_dir) / name if target else None
    if target is None or path is None or not path.is_file():
        await query.answer(T.IMAGE_NOT_FOUND, show_alert=True)
        return
    trash = settings.data_dir / "images_trash" / target.rel()
    trash.mkdir(parents=True, exist_ok=True)
    dest = trash / f"{utcnow():%Y%m%d%H%M%S}_{name}"
    path.replace(dest)
    logger.info("admin {}: rasm o'chirildi {} -> {}", query.from_user.id, path, dest)
    text, keyboard = _folder_view(settings, target)
    note = T.IMAGE_DELETED.format(name=html.escape(name), trash=html.escape(str(dest)))
    if isinstance(query.message, Message):
        await query.message.edit_text(f"{note}\n\n{text}", reply_markup=keyboard)
    await query.answer()


# ------------------------------------------------------------------ /addimage
@router.message(Command("addimage"))
async def addimage_cmd(
    message: Message, command: CommandObject, settings: Settings, state: FSMContext
) -> None:
    if not command.args:
        await message.answer(T.ADDIMAGE_USAGE)
        return
    target = resolve_target(settings, command.args)
    if target is None:
        await message.answer(T.IMAGES_UNKNOWN.format(key=html.escape(command.args.strip())))
        return
    await state.set_state(AddImage.waiting)
    await state.update_data(key=target.key)
    await message.answer(
        T.ADDIMAGE_WAIT.format(title=html.escape(target.title), folder=html.escape(target.rel()))
    )


def _next_name(folder: Path, ext: str) -> Path:
    n = 1
    while any((folder / f"{n}{e}").exists() for e in (".jpg", ".jpeg", ".png", ".webp")):
        n += 1
    return folder / f"{n}{ext}"


@router.message(AddImage.waiting, F.photo | F.document)
async def addimage_file(message: Message, bot: Bot, settings: Settings, state: FSMContext) -> None:
    data = await state.get_data()
    target = resolve_target(settings, str(data.get("key", "")))
    if target is None:
        await state.clear()
        await message.answer(T.CANCELLED)
        return
    if message.photo:
        file_id, size, ext = message.photo[-1].file_id, message.photo[-1].file_size, ".jpg"
    else:
        doc = message.document
        assert doc is not None
        ext = IMAGE_MIME.get(doc.mime_type or "", "")
        if not ext:
            await message.answer(T.ADDIMAGE_NOT_IMAGE)
            return
        file_id, size = doc.file_id, doc.file_size
    if size and size > MAX_IMAGE_BYTES:
        await message.answer(T.ADDIMAGE_TOO_BIG.format(mb=size / 1024 / 1024))
        return

    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    raw = buf.getvalue()
    try:
        with PILImage.open(io.BytesIO(raw)) as img:
            img.verify()
    except Exception:
        await message.answer(T.ADDIMAGE_NOT_IMAGE)
        return

    folder = target.folder(settings.images_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = _next_name(folder, ext)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(raw)
    tmp.replace(path)
    real, _ = _counts(folder)
    user = message.from_user
    logger.info("admin {}: rasm qo'shildi {}", user.id if user else "?", path)
    rel = path.relative_to(settings.images_dir).as_posix()
    await message.answer(T.ADDIMAGE_SAVED.format(path=html.escape(rel), real=real))


@router.message(AddImage.waiting)
async def addimage_wrong(message: Message) -> None:
    await message.answer(T.ADDIMAGE_NOT_IMAGE)


# ------------------------------------------------------------------ /images review
class ImgRevCb(CallbackData, prefix="imr"):
    """A button of ONE proposal: ``n`` is the number of the proposal it was shown with, so a late
    or repeated click can never approve a picture the admin has not seen."""

    action: str  # ok | more | skip | stop
    n: int = 0


@dataclass(slots=True)
class ReviewSession:
    """One admin's walk through the slots (in memory; the progress itself is in ``kv_store``)."""

    slots: list[review.Slot]
    done: dict[str, str]
    used: set[str]
    source: review.CandidateSource | None = None
    candidate: review.Candidate | None = None
    proposal: Message | None = None
    serial: int = 0  # the number of the proposal on screen (grows with every new one)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def current(self) -> review.Slot | None:
        return next((sl for sl in self.slots if sl.key not in self.done), None)

    def counts(self) -> tuple[int, int]:
        values = list(self.done.values())
        return values.count("approved"), values.count("skipped")


REVIEWS: dict[int, ReviewSession] = {}
# Tests replace this with a factory that has a mocked transport (nothing leaves the machine).
HTTP_FACTORY: review.HttpFactory = review.default_http


def _review_kb(serial: int) -> InlineKeyboardMarkup:
    def b(text: str, action: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=text, callback_data=ImgRevCb(action=action, n=serial).pack()
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b(T.BTN_IMGREV_OK, "ok")],
            [b(T.BTN_IMGREV_MORE, "more"), b(T.BTN_IMGREV_SKIP, "skip")],
            [b(T.BTN_IMGREV_STOP, "stop")],
        ]
    )


async def start_review(
    message: Message, settings: Settings, sf: SessionFactory, *, reset: bool
) -> None:
    admin = message.from_user.id if message.from_user else 0
    async with sf() as s, s.begin():
        if reset:
            await review.reset_progress(s)
            await message.answer(T.IMGREV_RESET)
        progress = await review.load_progress(s)
    slots = review.build_slots(settings)
    rs = ReviewSession(slots, dict(progress["done"]), set(progress["used"]))
    REVIEWS[admin] = rs
    pending = sum(1 for sl in slots if sl.key not in rs.done)
    if not pending:
        await message.answer(T.IMGREV_NOTHING)
        return
    providers = review.configured_providers(settings)
    sources = (
        T.IMGREV_SOURCES_STOCK.format(names=", ".join(p.capitalize() for p in providers))
        if providers
        else T.IMGREV_SOURCES_OWN
    )
    await message.answer(
        T.IMGREV_INTRO.format(pending=pending, done=len(slots) - pending, sources=sources)
    )
    await _present(message, rs, settings)


def _current_text(slot: review.Slot) -> str:
    if slot.current is None:
        return T.IMGREV_CURRENT_NONE
    return T.IMGREV_CURRENT_PLACEHOLDER if is_placeholder(slot.current) else T.IMGREV_CURRENT_REAL


def _proposal_caption(cand: review.Candidate) -> str:
    return T.IMGREV_PROPOSAL.format(
        label=html.escape(cand.label), license=html.escape(cand.license)
    )


async def _present(message: Message, rs: ReviewSession, settings: Settings) -> None:
    """The next pending slot: its current picture, then the first proposal with the buttons."""
    slot = rs.current()
    if slot is None:
        approved, skipped = rs.counts()
        await message.answer(T.IMGREV_FINISHED.format(approved=approved, skipped=skipped))
        return
    pos = len(rs.done) + 1
    head = T.IMGREV_CURRENT.format(
        title=html.escape(slot.title),
        n=pos,
        total=len(rs.slots),
        slot=html.escape(slot.key),
        current=_current_text(slot),
    )
    if slot.current is not None and slot.current.is_file():
        await message.answer_photo(FSInputFile(slot.current), caption=head)
    else:
        await message.answer(head)
    rs.source = review.CandidateSource(settings, slot, used=rs.used, http_factory=HTTP_FACTORY)
    rs.candidate = await rs.source.next()
    rs.serial += 1
    rs.proposal = await message.answer_photo(
        BufferedInputFile(rs.candidate.jpeg, filename="yangi.jpg"),
        caption=_proposal_caption(rs.candidate),
        reply_markup=_review_kb(rs.serial),
    )


@router.callback_query(ImgRevCb.filter())
async def review_cb(
    query: CallbackQuery, callback_data: ImgRevCb, settings: Settings, sf: SessionFactory
) -> None:
    rs = REVIEWS.get(query.from_user.id)
    if rs is None or rs.source is None or not isinstance(query.message, Message):
        await query.answer(T.IMGREV_NO_SESSION, show_alert=True)
        return
    async with rs.lock:  # one action at a time: a double click cannot apply a picture twice
        cand, slot = rs.candidate, rs.current()
        if cand is None or slot is None or callback_data.n != rs.serial:
            await query.answer()  # a repeated / late click of a proposal that is already decided
            return
        action = callback_data.action
        if action == "more":
            await query.answer()
            rs.candidate = await rs.source.next()
            rs.serial += 1
            await query.message.edit_media(
                InputMediaPhoto(
                    media=BufferedInputFile(rs.candidate.jpeg, filename="yangi.jpg"),
                    caption=_proposal_caption(rs.candidate),
                    parse_mode="HTML",
                ),
                reply_markup=_review_kb(rs.serial),
            )
            return
        if action == "ok":
            now = utcnow()
            try:
                applied = review.apply_candidate(
                    settings, slot, cand, admin_id=query.from_user.id, now=now
                )
            except OSError as e:
                logger.error("rasm saqlanmadi ({}): {}", slot.key, e)
                await query.answer(T.IMGREV_WRITE_FAILED, show_alert=True)
                return
            await query.answer()
            if cand.stock is not None:
                async with HTTP_FACTORY() as http:
                    await review.ping_unsplash_download(settings, cand.stock, http)
                rs.used.add(cand.stock.uid)
            outcome = "approved"
            root = settings.images_dir
            note = T.IMGREV_APPLIED.format(
                path=html.escape(applied.path.relative_to(root).as_posix()),
                backup=T.IMGREV_BACKUP.format(backup=html.escape(applied.backup.name))
                if applied.backup
                else "",
                sidecar=html.escape(applied.sidecar.name),
            )
            logger.info(
                "admin {}: rasm tasdiqlandi {} <- {} ({})",
                query.from_user.id,
                applied.path,
                cand.source,
                slot.key,
            )
        elif action == "skip":
            await query.answer()
            outcome, note = "skipped", T.IMGREV_SKIPPED
        else:  # stop
            await query.answer()
            approved, skipped = rs.counts()
            await query.message.edit_reply_markup(reply_markup=None)
            await query.message.answer(T.IMGREV_STOPPED.format(approved=approved, skipped=skipped))
            REVIEWS.pop(query.from_user.id, None)
            return
        rs.done[slot.key] = outcome
        async with sf() as s, s.begin():
            progress = await review.load_progress(s)
            progress["done"][slot.key] = outcome
            progress["used"] = sorted(rs.used)
            await review.save_progress(s, progress)
        rs.candidate = None
        await query.message.edit_caption(caption=note, reply_markup=None)
        await _present(query.message, rs, settings)
