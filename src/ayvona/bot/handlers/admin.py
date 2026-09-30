"""Admin commands (only ``ADMIN_IDS``): /stats /queue /failed /retry /pause /resume /help /cancel.

Sources (/sources, /addsource) are in ``admin_sources.py``, pictures (/images, /addimage) in
``admin_images.py``. Every change is logged with the admin's id.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.config import Settings
from ayvona.db.models import JobStatus
from ayvona.db.repositories import jobs_repo, kv_repo
from ayvona.publisher.outbox import skip_old_jobs, too_old_reason
from ayvona.services.stats import day_start, failed_jobs, period_stats, queue_overview
from ayvona.timeutil import ensure_utc, to_local, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="admin")

PROCESSES = (("collector", "Collector"), ("worker", "Worker"), ("bot", "Bot"))
MAX_MESSAGE = 4000


def ago(delta: timedelta) -> str:
    """``timedelta`` -> "5 daq" / "3 soat" / "2 kun"."""
    minutes = max(int(delta.total_seconds() // 60), 0)
    if minutes < 60:
        return f"{minutes} daq"
    if minutes < 48 * 60:
        return f"{minutes // 60} soat"
    return f"{minutes // 1440} kun"


def local_time(dt: datetime | None, settings: Settings) -> str:
    return to_local(dt, settings.timezone).strftime("%d.%m %H:%M") if dt else "—"


def chunks(lines: list[str], limit: int = MAX_MESSAGE) -> list[str]:
    """Join lines into messages under Telegram's 4096 limit."""
    out: list[str] = []
    cur = ""
    for line in lines:
        if cur and len(cur) + len(line) + 1 > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


def log_admin(message: Message, action: str) -> None:
    user = message.from_user
    logger.info(
        "admin {} (@{}): {}", user.id if user else "?", user.username if user else "?", action
    )


# ------------------------------------------------------------------ general
@router.message(CommandStart())
@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(T.ADMIN_HELP)


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(T.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(T.CANCELLED)


# ------------------------------------------------------------------ /stats
@router.message(Command("stats"))
async def stats_cmd(message: Message, sf: SessionFactory, settings: Settings) -> None:
    now = utcnow()
    tz = settings.timezone
    stale = timedelta(minutes=settings.app.monitoring.heartbeat_stale_minutes)
    async with sf() as s:
        today = await period_stats(s, day_start(now, tz))
        week = await period_stats(s, now - timedelta(days=7))
        queue = await queue_overview(s, now, limit=0)
        processes: list[str] = []
        for key, name in PROCESSES:
            beat = await kv_repo.read_heartbeat(s, key)
            if beat is None:
                processes.append(T.PROCESS_NEVER.format(name=name))
                continue
            age = now - ensure_utc(beat)
            tpl = T.PROCESS_STALE if age > stale else T.PROCESS_OK
            processes.append(tpl.format(name=name, ago=ago(age)))
    cats = "\n".join(
        f"  {html.escape(settings.categories[c].title if c in settings.categories else c)}: {n}"
        for c, n in week.categories[:12]
    )
    queued = queue.counts.get("queued", 0) + queue.counts.get("retry", 0)
    await message.answer(
        T.STATS.format(
            now=local_time(now, settings),
            d=today,
            w=week,
            queue=queued,
            paused=T.PAUSED_MARK if queue.paused else "",
            categories=cats or T.STATS_NO_CATEGORIES,
            processes=", ".join(processes),
        )
    )


# ------------------------------------------------------------------ /queue, /failed, /retry
@router.message(Command("queue"))
async def queue_cmd(message: Message, sf: SessionFactory, settings: Settings) -> None:
    now = utcnow()
    async with sf() as s:
        q = await queue_overview(s, now, limit=15)
    lines = [
        T.QUEUE_HEAD.format(
            paused=T.PAUSED_MARK if q.paused else "",
            queued=q.counts.get("queued", 0),
            retry=q.counts.get("retry", 0),
            sending=q.counts.get("sending", 0),
            failed=q.counts.get("failed", 0),
            due=q.due_now,
        ),
        "",
    ]
    for job in q.upcoming:
        at = job.next_retry_at
        when = T.QUEUE_NOW if at is None or at <= now else local_time(at, settings)
        lines.append(T.QUEUE_ITEM.format(id=job.id, title=html.escape(job.title or "—"), when=when))
    if not q.upcoming:
        lines.append(T.QUEUE_EMPTY)
    for part in chunks(lines):
        await message.answer(part)


@router.message(Command("failed"))
async def failed_cmd(message: Message, sf: SessionFactory) -> None:
    async with sf() as s:
        jobs = await failed_jobs(s, limit=20)
    if not jobs:
        await message.answer(T.FAILED_EMPTY)
        return
    lines = [T.FAILED_HEAD.format(n=len(jobs))]
    for job in jobs:
        lines.append(
            T.FAILED_ITEM.format(
                id=job.id,
                title=html.escape(job.title or "—"),
                attempts=job.attempts,
                error=html.escape((job.last_error or "—")[:200]),
            )
        )
    lines.append(T.FAILED_FOOT)
    for part in chunks(lines):
        await message.answer(part)


@router.message(Command("retry"))
async def retry_cmd(
    message: Message, command: CommandObject, sf: SessionFactory, settings: Settings
) -> None:
    arg = (command.args or "").strip().lower()
    if arg == "all":
        ids = None
    else:
        ids = [int(x) for x in re.findall(r"\d+", arg)]
        if not ids:
            await message.answer(T.RETRY_USAGE)
            return
    now = utcnow()
    # Too old for the channel (publisher.max_age_hours): skipped_old instead of the queue.
    old = await skip_old_jobs(
        settings, sf, now, statuses=(JobStatus.FAILED, JobStatus.RETRY), job_ids=ids
    )
    async with sf() as s, s.begin():
        n = await jobs_repo.retry_failed(s, now, ids)
    log_admin(message, f"/retry {arg} -> {n}, eskirgan {len(old)}")
    parts = [T.RETRY_DONE.format(n=n)] if n else []
    if old:
        parts.append(
            T.RETRY_TOO_OLD.format(
                n=len(old),
                reason=too_old_reason(settings.app.publisher.max_age_hours),
                ids=", ".join(f"#{i}" for i in old[:30]) + (" ..." if len(old) > 30 else ""),
            )
        )
    await message.answer("\n".join(parts) if parts else T.RETRY_NONE)


# ------------------------------------------------------------------ /pause, /resume
@router.message(Command("pause"))
async def pause_cmd(message: Message, sf: SessionFactory) -> None:
    async with sf() as s, s.begin():
        await kv_repo.set_bool(s, kv_repo.PUBLISHER_PAUSED, True)
    log_admin(message, "/pause")
    await message.answer(T.PAUSED)


@router.message(Command("resume"))
async def resume_cmd(message: Message, sf: SessionFactory) -> None:
    async with sf() as s, s.begin():
        await kv_repo.set_bool(s, kv_repo.PUBLISHER_PAUSED, False)
    log_admin(message, "/resume")
    await message.answer(T.RESUMED)
