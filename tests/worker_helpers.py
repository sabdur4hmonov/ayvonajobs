"""Helpers for pipeline / publisher / worker tests: settings, DB rows, a notifier that records."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import DEFAULT_CONFIG_DIR, Settings, load_settings
from ayvona.db.models import Job, JobOrigin, JobStatus, ParseMethod, RawPost, RawPostStatus, Source
from ayvona.timeutil import utcnow
from tests.post_fixtures import POSTS_DIR, load

SF = async_sessionmaker[AsyncSession]

JOB_TEXT = "Sotuvchi kerak\nTalablar: mas'uliyatli, xushmuomala\nMurojaat uchun: +998901234567"
JOB_TEXT_FULL = (
    "Sotuvchi kerak\n"
    "Maosh: 5 000 000 so'm\n"
    "Manzil: Toshkent, Chilonzor tumani\n"
    "Talablar: mas'uliyatli, xushmuomala\n"
    "Murojaat uchun: +998901234567"
)


def make_settings(
    images_root: Path | None = None, *, publisher: dict[str, Any] | None = None, **worker: Any
) -> Settings:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    app = s.app.model_copy(
        update={
            "publisher": s.app.publisher.model_copy(
                update={
                    "publish_interval_seconds": 0,
                    "idle_poll_seconds": 0.01,
                    **(publisher or {}),
                }
            ),
            "worker": s.app.worker.model_copy(update={"album_wait_seconds": 60, **worker}),
            "images": s.app.images.model_copy(
                update={"root": str(images_root) if images_root else "/nonexistent-images"}
            ),
        }
    )
    return s.model_copy(update={"app": app})


def make_image(root: Path, rel: str = "boshqa/1.jpg") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (64, 36), (40, 90, 160)).save(path, "JPEG")
    return path


def fixture_text(name: str) -> dict[str, Any]:
    return load(POSTS_DIR / f"{name}.json")


async def add_source(sf: SF, identifier: str = "@kanal_a", own: list[str] | None = None) -> int:
    async with sf() as s, s.begin():
        src = Source(identifier=identifier, own_usernames=own or [identifier])
        s.add(src)
        await s.flush()
        return src.id


_ext = iter(range(10_000, 10**9))


async def add_raw(
    sf: SF,
    source_id: int,
    text: str,
    *,
    external_id: str | None = None,
    grouped_id: int | None = None,
    has_media: bool = False,
    extra: dict[str, Any] | None = None,
    posted_ago: timedelta = timedelta(minutes=5),
    fetched_ago: timedelta = timedelta(minutes=2),
    is_backfill: bool = False,
    status: RawPostStatus = RawPostStatus.NEW,
    now: datetime | None = None,
) -> int:
    now = now or utcnow()
    async with sf() as s, s.begin():
        row = RawPost(
            source_id=source_id,
            external_id=external_id or str(next(_ext)),
            grouped_id=grouped_id,
            text=text,
            has_media=has_media,
            extra=extra,
            posted_at=now - posted_ago,
            fetched_at=now - fetched_ago,
            is_backfill=is_backfill,
            status=status,
        )
        s.add(row)
        await s.flush()
        return row.id


async def add_job(
    sf: SF,
    *,
    status: JobStatus = JobStatus.QUEUED,
    next_retry_at: datetime | None = None,
    attempts: int = 0,
    text: str = "💼 <b>Sotuvchi</b>\n📞 Aloqa: +998 90 123 45 67",
    category: str = "savdo",
    buttons: list[Any] | None = None,
) -> int:
    async with sf() as s, s.begin():
        job = Job(
            origin=JobOrigin.AGGREGATOR,
            title="Sotuvchi",
            category=category,
            parse_method=ParseMethod.REGEX,
            confidence=0.9,
            contact_phone="+998901234567",
            formatted_text=text,
            buttons=buttons
            if buttons is not None
            else [[{"text": "⭐ Saqlash", "url": "https://t.me/ayvonabot?start=save_1"}]],
            status=status,
            attempts=attempts,
            next_retry_at=next_retry_at,
        )
        s.add(job)
        await s.flush()
        return job.id


async def get_raw(sf: SF, raw_id: int) -> RawPost:
    async with sf() as s:
        row = await s.get(RawPost, raw_id)
        assert row is not None
        return row


async def get_job(sf: SF, job_id: int) -> Job:
    async with sf() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        return job


class RecordingNotifier:
    """Stands in for services.notifier.Notifier: remembers what would go to the admin chat."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, text: str, *, key: str | None = None) -> bool:
        self.messages.append(text)
        return True
