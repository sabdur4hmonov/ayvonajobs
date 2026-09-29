"""Pick the picture for a channel post (docs/IMAGES.md).

Folders: ``assets/images/<category>/<profession>/`` -> ``assets/images/<category>/`` ->
``assets/images/boshqa/``. Real pictures always win over placeholders (``placeholder_*.jpg`` from
scripts/make_placeholder_images.py): a placeholder is used only if none of the three folders has a
real picture. The files of the chosen folder are used in turn (1 -> 2 -> 3 -> 1): the least recently
used goes next; the counters live in the ``images`` table, so the order survives restarts. Folders
are re-read on every pick — a picture added or removed works without a restart.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import Settings
from ayvona.db.models import Image
from ayvona.db.repositories import images_repo
from ayvona.db.repositories.images_repo import ImageFileInfo

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
PLACEHOLDER_PREFIX = "placeholder_"
_NEVER = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PickedImage:
    id: int
    path: Path  # absolute
    file_hash: str | None
    telegram_file_id: str | None  # reuse instead of uploading, if set
    is_placeholder: bool


def is_placeholder(path: Path) -> bool:
    return path.name.lower().startswith(PLACEHOLDER_PREFIX)


def list_images(folder: Path) -> list[Path]:
    """Picture files directly in ``folder`` (not in sub-folders), sorted by name."""
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ImagePicker:
    """``pick_image(category, profession)`` over an images root folder."""

    def __init__(self, root: Path, fallback_category: str = "boshqa") -> None:
        self.root = root
        self.fallback_category = fallback_category

    @classmethod
    def from_settings(cls, settings: Settings) -> ImagePicker:
        return cls(settings.images_dir, settings.app.images.fallback_category)

    def _tiers(self, category: str | None, profession: str | None) -> list[tuple[str, str | None]]:
        tiers: list[tuple[str, str | None]] = []
        if category and profession:
            tiers.append((category, profession))
        if category:
            tiers.append((category, None))
        tiers.append((self.fallback_category, None))
        return list(dict.fromkeys(tiers))

    def candidates(
        self, category: str | None, profession: str | None
    ) -> list[tuple[Path, str, str | None]]:
        """Files of the folder that will be used: ``(path, category, profession)``."""
        tiers = self._tiers(category, profession)
        found = [
            (cat, prof, list_images(self.root / cat / prof if prof else self.root / cat))
            for cat, prof in tiers
        ]
        for want_placeholder in (False, True):
            for cat, prof, files in found:
                chosen = [f for f in files if is_placeholder(f) == want_placeholder]
                if chosen:
                    return [(f, cat, prof) for f in chosen]
        return []

    async def pick(
        self,
        session: AsyncSession,
        category: str | None,
        profession: str | None,
        now: datetime | None = None,
    ) -> PickedImage | None:
        """Next picture in turn (marks it used; the caller commits). ``None``: no picture at all."""
        files = self.candidates(category, profession)
        if not files:
            return None
        infos = [
            ImageFileInfo(
                file_path=path.relative_to(self.root).as_posix(),
                category=cat,
                profession=prof,
                file_hash=file_hash(path),
                is_placeholder=is_placeholder(path),
            )
            for path, cat, prof in files
        ]
        rows = await images_repo.sync_files(session, infos)
        row: Image = min(rows, key=lambda r: (r.last_used_at or _NEVER, r.file_path))
        images_repo.mark_used(row, now)
        await session.flush()
        return PickedImage(
            id=row.id,
            path=self.root / row.file_path,
            file_hash=row.file_hash,
            telegram_file_id=row.telegram_file_id,
            is_placeholder=row.is_placeholder,
        )


async def pick_image(
    session: AsyncSession,
    settings: Settings,
    category: str | None,
    profession: str | None,
    now: datetime | None = None,
) -> PickedImage | None:
    """Shortcut: :meth:`ImagePicker.pick` with the configured images folder."""
    return await ImagePicker.from_settings(settings).pick(session, category, profession, now)
