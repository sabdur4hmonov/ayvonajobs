"""Job life time in search (worker task, every ``expiry.check_minutes``):

1. published jobs without ``expires_at`` (published before Bosqich 14) get
   ``published_at + aggregator_days / user_days``;
2. user jobs expiring within ``remind_days_before`` days: "⏳ Uzaytirasizmi?" once
   (``jobs.reminded_at``) with [🔄 Uzaytirish] [✅ Yopish];
3. ``expires_at`` passed → ``expired``: out of search, the channel post is NOT touched.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin, JobStatus
from ayvona.timeutil import ensure_utc, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
SleepFn = Callable[[float], Awaitable[bool]]
RenderReminder = Callable[[Settings, Job], tuple[str, InlineKeyboardMarkup]]


@dataclass(slots=True)
class ExpiryReport:
    backfilled: int = 0
    reminded: int = 0
    expired: int = 0


async def backfill_expires_at(session: AsyncSession, settings: Settings) -> int:
    """Does not commit."""
    exp = settings.app.expiry
    rows = (
        await session.execute(
            select(Job.id, Job.origin, Job.published_at).where(
                Job.status == JobStatus.PUBLISHED,
                Job.expires_at.is_(None),
                Job.published_at.is_not(None),
            )
        )
    ).all()
    for job_id, origin, published_at in rows:
        days = exp.user_days if origin == JobOrigin.USER else exp.aggregator_days
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(expires_at=ensure_utc(published_at) + timedelta(days=days))
            .execution_options(synchronize_session=False)
        )
    return len(rows)


async def expire(session: AsyncSession, now: datetime) -> list[int]:
    """``published`` with ``expires_at`` <= now → ``expired``. Does not commit."""
    ids = list(
        (
            await session.scalars(
                select(Job.id).where(
                    Job.status == JobStatus.PUBLISHED,
                    Job.expires_at.is_not(None),
                    Job.expires_at <= now,
                )
            )
        ).all()
    )
    if ids:
        await session.execute(
            update(Job)
            .where(Job.id.in_(ids), Job.status == JobStatus.PUBLISHED)
            .values(status=JobStatus.EXPIRED)
            .execution_options(synchronize_session=False)
        )
    return ids


async def due_reminders(session: AsyncSession, now: datetime, settings: Settings) -> list[Job]:
    """User jobs that expire soon and were not reminded yet."""
    soon = now + timedelta(days=settings.app.expiry.remind_days_before)
    rows = await session.scalars(
        select(Job).where(
            Job.origin == JobOrigin.USER,
            Job.status == JobStatus.PUBLISHED,
            Job.author_id.is_not(None),
            Job.reminded_at.is_(None),
            Job.expires_at.is_not(None),
            Job.expires_at > now,
            Job.expires_at <= soon,
        )
    )
    return list(rows.all())


class ExpiryService:
    def __init__(
        self,
        settings: Settings,
        sf: SessionFactory,
        bot: Bot | None,
        render_reminder: RenderReminder,
    ) -> None:
        self.settings = settings
        self.sf = sf
        self.bot = bot
        self.render_reminder = render_reminder

    async def check(self, now: datetime | None = None) -> ExpiryReport:
        now = now or utcnow()
        report = ExpiryReport()
        async with self.sf() as s, s.begin():
            report.backfilled = await backfill_expires_at(s, self.settings)
        async with self.sf() as s:
            jobs = await due_reminders(s, now, self.settings)
        for job in jobs:
            if self.bot is not None and job.author_id is not None:
                text, markup = self.render_reminder(self.settings, job)
                try:
                    await self.bot.send_message(job.author_id, text, reply_markup=markup)
                    report.reminded += 1
                except Exception as e:  # blocked the bot, ...
                    logger.info("expiry: {} ga eslatma yuborilmadi: {}", job.author_id, e)
            async with self.sf() as s, s.begin():  # once, even if the message failed
                await s.execute(update(Job).where(Job.id == job.id).values(reminded_at=now))
        async with self.sf() as s, s.begin():
            report.expired = len(await expire(s, now))
        if report.backfilled or report.reminded or report.expired:
            logger.info(
                "Muddat: {} ta e'longa muddat qo'yildi, {} ta eslatma, "
                "{} ta e'lon qidiruvdan chiqdi",
                report.backfilled,
                report.reminded,
                report.expired,
            )
        return report

    async def run(self, sleep: SleepFn) -> None:
        while True:
            try:
                await self.check()
            except Exception:
                logger.exception("expiry: kutilmagan xato")
            if await sleep(self.settings.app.expiry.check_minutes * 60):
                return
