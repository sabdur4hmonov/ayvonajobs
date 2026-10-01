"""Rebuild the caption and buttons of jobs still waiting in the outbox with the CURRENT formatter.

The pipeline formats a job once and stores the result (``jobs.formatted_text`` / ``buttons``).
After a formatter or ``branding`` change, the ``queued`` / ``retry`` jobs would still go out with
the old text. This service re-renders them (scripts/reformat_queued.py):

* only ``queued`` / ``retry`` jobs; ``sending`` / ``published`` / ``failed`` are never touched —
  the UPDATE is conditional on the status and the raw post, so a job the publisher takes (or a
  fuller copy takes over) meanwhile is left alone. Still, run it with the worker stopped;
* ``jobs`` does not keep everything the formatter needs (language, positions, emails, address
  parts, ...), so the job is rebuilt from its raw post(s): extract -> clean -> format, exactly as
  the pipeline does (``Pipeline.render``). Dedup is NOT run (the index is not touched) and no new
  job is created: the existing row gets the new caption, buttons and the extracted columns;
* a job whose post today would have no contact / be low quality keeps its old text (reported);
  a user job (no raw post) is skipped;
* one transaction per job, so stopping half way leaves every job either old or new.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.ai.helper import AIHelper
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.db.repositories import jobs_repo, kv_repo
from ayvona.processing.pipeline import Pipeline, buttons_json
from ayvona.timeutil import ensure_utc, utcnow

WORKER = "worker"


@dataclass(frozen=True, slots=True)
class JobChange:
    """One job whose stored version differs from what the formatter makes now."""

    job_id: int
    status: str
    before_text: str
    after_text: str
    before_buttons: list[Any]
    after_buttons: list[Any]
    changed_fields: tuple[str, ...]  # other ``jobs`` columns that change too

    @property
    def text_changed(self) -> bool:
        return self.before_text != self.after_text or self.before_buttons != self.after_buttons


@dataclass(slots=True)
class ReformatReport:
    total: int = 0
    changes: list[JobChange] = field(default_factory=list)  # would change (dry run) / changed
    unchanged: int = 0
    skipped: list[tuple[int, str]] = field(default_factory=list)  # (job id, reason)
    taken: list[int] = field(default_factory=list)  # changed by the worker before our UPDATE
    dry_run: bool = False

    @property
    def updated(self) -> int:
        return len(self.changes) - len(self.taken)


async def worker_heartbeat_age(
    sf: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> timedelta | None:
    """How long ago the worker said "alive", or ``None`` if it never ran."""
    async with sf() as s:
        beat = await kv_repo.read_heartbeat(s, WORKER)
    return None if beat is None else (now or utcnow()) - ensure_utc(beat)


def worker_seems_running(settings: Settings, age: timedelta | None) -> bool:
    """A heartbeat newer than two intervals (+ a margin) = the worker is probably on."""
    if age is None:
        return False
    return age < timedelta(seconds=2 * settings.app.worker.heartbeat_interval_seconds + 30)


def _diff_fields(job: Job, fields: dict[str, Any]) -> tuple[str, ...]:
    return tuple(k for k, v in fields.items() if k != "formatted_text" and getattr(job, k) != v)


async def _rebuild(pipeline: Pipeline, s: AsyncSession, job: Job) -> dict[str, Any] | str:
    """New column values of ``job``, or the reason it cannot be rebuilt."""
    post = await pipeline.post_of_job(s, job)
    if post is None:
        return "asl post topilmadi (foydalanuvchi e'loni yoki raw_post yo'q)"
    ex = pipeline.extractor.extract(post.input)
    if not ex.has_contact:
        return "hozirgi qoidalar bo'yicha aloqa topilmadi — eski matn qoldi"
    ex = await pipeline.enhance(post, ex, cache_only=True)  # AI answers kept (cache, no API call)
    if ex.low_quality:
        return "hozirgi qoidalar bo'yicha sifatsiz (low_quality) — eski matn qoldi"
    out, fields = pipeline.render(post, ex)
    return {**fields, "buttons": buttons_json(out, job.id)}


async def reformat_queued(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool = False,
    ai: AIHelper | None = None,
) -> ReformatReport:
    """Re-render every ``queued`` / ``retry`` job. ``dry_run``: only report, write nothing.
    ``ai``: reuse cached Gemini answers (never a new request)."""
    pipeline = Pipeline(settings, sf, ai=ai)  # no notifier; its dedup index is never loaded
    report = ReformatReport(dry_run=dry_run)
    async with sf() as s:
        jobs = await jobs_repo.list_sendable(s)
    report.total = len(jobs)

    for job in jobs:
        try:
            async with sf() as s:
                new = await _rebuild(pipeline, s, job)
        except Exception as e:  # one bad post must not stop the rest
            logger.opt(exception=e).error("job #{}: qayta formatlanmadi", job.id)
            report.skipped.append((job.id, f"xato: {type(e).__name__}: {e}"))
            continue
        if isinstance(new, str):
            report.skipped.append((job.id, new))
            continue

        fields = {k: v for k, v in new.items() if k != "buttons"}
        change = JobChange(
            job_id=job.id,
            status=str(job.status),
            before_text=job.formatted_text or "",
            after_text=new["formatted_text"] or "",
            before_buttons=job.buttons or [],
            after_buttons=new["buttons"],
            changed_fields=_diff_fields(job, fields),
        )
        if not change.text_changed and not change.changed_fields:
            report.unchanged += 1
            continue
        report.changes.append(change)
        if dry_run:
            continue
        async with sf() as s, s.begin():
            if not await jobs_repo.update_if_sendable(s, job.id, new, raw_post_id=job.raw_post_id):
                report.taken.append(job.id)
                logger.warning("job #{}: shu orada o'zgardi (publisher/worker) — tegilmadi", job.id)
    return report
