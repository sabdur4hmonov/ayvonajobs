"""Queries for the ``images`` table (post pictures, rotation, Telegram file_id cache)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import Image
from ayvona.timeutil import utcnow


@dataclass(frozen=True, slots=True)
class ImageFileInfo:
    """A picture file found on disk (see processing/images.py)."""

    file_path: str  # relative to the images root, "/" separators
    category: str
    profession: str | None
    file_hash: str
    is_placeholder: bool


async def sync_files(session: AsyncSession, files: Sequence[ImageFileInfo]) -> list[Image]:
    """Rows for ``files`` (same order); new files are inserted. A changed file (other hash) loses
    its cached ``telegram_file_id`` — it must be uploaded again. Does not commit."""
    if not files:
        return []
    paths = [f.file_path for f in files]
    rows = {
        r.file_path: r
        for r in (await session.scalars(select(Image).where(Image.file_path.in_(paths)))).all()
    }
    out: list[Image] = []
    for f in files:
        row = rows.get(f.file_path)
        if row is None:
            row = Image(
                category=f.category,
                profession=f.profession,
                file_path=f.file_path,
                file_hash=f.file_hash,
                is_placeholder=f.is_placeholder,
                times_used=0,
            )
            session.add(row)
        elif row.file_hash != f.file_hash:
            row.file_hash = f.file_hash
            row.telegram_file_id = None
            row.is_placeholder = f.is_placeholder
        out.append(row)
    await session.flush()
    return out


def mark_used(image: Image, now: datetime | None = None) -> None:
    """Rotation bookkeeping. Does not commit."""
    image.times_used = (image.times_used or 0) + 1
    image.last_used_at = now or utcnow()


async def set_telegram_file_id(
    session: AsyncSession, image_id: int, file_id: str, file_hash: str | None = None
) -> None:
    """Remember Telegram's ``file_id`` after the first upload (only if the file is unchanged).
    Does not commit."""
    stmt = update(Image).where(Image.id == image_id).values(telegram_file_id=file_id)
    if file_hash is not None:
        stmt = stmt.where(Image.file_hash == file_hash)
    await session.execute(stmt)
