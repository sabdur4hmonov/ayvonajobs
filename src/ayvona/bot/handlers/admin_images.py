"""Post pictures from the bot (only ``ADMIN_IDS``), docs/IMAGES.md:

* /images           — per category: real / placeholder pictures, professions without any real one
* /images <kasb>    — files of that folder, each with [🗑]
* /addimage <kasb>  — the admin sends pictures, they are saved into the folder

Only files in ``assets/images/<category>/[<profession>/]`` change; the picking rules
(processing/images.py) are untouched: a real picture automatically wins over the placeholders.
A deleted picture is moved to ``data/images_trash/`` (can be put back by hand), not destroyed.
"""

from __future__ import annotations

import html
import io
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from PIL import Image as PILImage

from ayvona.bot import texts as T
from ayvona.bot.handlers.admin import chunks
from ayvona.config import Settings
from ayvona.processing.images import is_placeholder, list_images
from ayvona.timeutil import utcnow

router = Router(name="admin_images")

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
async def images_cmd(message: Message, command: CommandObject, settings: Settings) -> None:
    root = settings.images_dir
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
