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
    images_root: Path | None = None,
    *,
    publisher: dict[str, Any] | None = None,
    db_file: Path | None = None,
    backup_dir: Path | None = None,
    **worker: Any,
) -> Settings:
    """Test settings. Never points at the real data/ayvona.db: the backup is off unless
    ``db_file`` + ``backup_dir`` (temporary paths) are given."""
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    env = s.env.model_copy(update={"db_path": str(db_file or "/nonexistent/test.db")})
    app = s.app.model_copy(
        update={
            "backup": s.app.backup.model_copy(
                update={
                    "enabled": backup_dir is not None,
                    "dir": str(backup_dir or "/nonexistent/backups"),
                }
            ),
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
    return s.model_copy(update={"app": app, "env": env})


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
    raw_post_id: int | None = None,
) -> int:
    async with sf() as s, s.begin():
        job = Job(
            origin=JobOrigin.AGGREGATOR,
            raw_post_id=raw_post_id,
            title="Sotuvchi",
            category=category,
            parse_method=ParseMethod.REGEX,
            confidence=0.9,
            contact_phone="+998901234567",
            formatted_text=text,
            buttons=buttons
            if buttons is not None
            else [[{"text": "⭐ Saqlash", "url": "https://t.me/ayvona_jobs_bot?start=save_1"}]],
            status=status,
            attempts=attempts,
            next_retry_at=next_retry_at,
        )
        s.add(job)
        await s.flush()
        return job.id


_src_names = iter(range(1, 10**6))


async def add_job_from_post(
    sf: SF,
    posted_ago: timedelta | None,
    *,
    fetched_ago: timedelta = timedelta(minutes=2),
    now: datetime | None = None,
    **job: Any,
) -> int:
    """A job made from a source post that appeared ``posted_ago`` before ``now``
    (``None``: the post has no ``posted_at``, only ``fetched_at``)."""
    src = await add_source(sf, f"@kanal_{next(_src_names)}")
    raw_id = await add_raw(
        sf,
        src,
        JOB_TEXT,
        posted_ago=posted_ago or timedelta(0),
        fetched_ago=fetched_ago,
        status=RawPostStatus.DONE,
        now=now,
    )
    if posted_ago is None:
        async with sf() as s, s.begin():
            row = await s.get(RawPost, raw_id)
            assert row is not None
            row.posted_at = None
    return await add_job(sf, raw_post_id=raw_id, **job)


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
        self.targets: list[int | str | None] = []

    async def send(
        self, text: str, *, key: str | None = None, chat_id: int | str | None = None
    ) -> bool:
        self.messages.append(text)
        self.targets.append(chat_id)
        return True
