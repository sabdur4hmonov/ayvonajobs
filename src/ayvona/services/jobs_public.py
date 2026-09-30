"""What the public (bot, later the website) may see of ``jobs``.

Only jobs that reached the channel are shown: ``published`` (open) and ``closed`` / ``expired``
(still visible in someone's favorites, marked as closed; never in search results).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import Settings
from ayvona.db.models import Job, JobStatus

VISIBLE = (JobStatus.PUBLISHED, JobStatus.CLOSED, JobStatus.EXPIRED)


async def get_visible_job(session: AsyncSession, job_id: int) -> Job | None:
    """A job anyone may look at, or ``None`` (unknown, still in the queue, skipped...)."""
    job = await session.get(Job, job_id)
    return job if job is not None and job.status in VISIBLE else None


def is_open(job: Job, now: datetime) -> bool:
    """Published and not past ``expires_at``."""
    if job.status != JobStatus.PUBLISHED:
        return False
    return job.expires_at is None or job.expires_at > now


def channel_post_url(settings: Settings, job: Job) -> str | None:
    """Link to the job's post in our channel (for "📤 Ulashish")."""
    if not job.channel_message_id:
        return None
    return f"https://t.me/{settings.app.branding.channel_username}/{job.channel_message_id}"
