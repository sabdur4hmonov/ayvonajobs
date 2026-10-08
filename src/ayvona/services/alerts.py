"""🔔 Job alerts: subscriptions (bot, later the website) and their delivery (worker).

Subscriptions: the search filters (category → profession → region → salary [+ keyword]),
at most ``alerts.max_per_user`` per user, paused / resumed / deleted by the user.

Delivery (:class:`AlertService`, a worker task):
* every ``alerts.poll_seconds``: jobs published after the cursor (``kv_store alerts:cursor``;
  the first start begins "now", old jobs are never alerted) are matched with the active
  subscriptions (:func:`services.search.job_matches` — the same rules as the search);
* the ``alert_deliveries`` row is written FIRST (composite PK: never twice for one subscription)
  and one message per user is sent even if several of their subscriptions match;
* at most ``alerts.daily_limit`` messages per user per 24 h — the rest are marked ``digest`` and
  sent as ONE list at ``alerts.digest_hour`` (Tashkent);
* an admin's unfiltered subscription is skipped here: services/admin_alerts.py already sends
  every matching collected post;
* ≤ ``alerts.per_second`` messages per second; Telegram "retry after" is waited; a user who
  blocked the bot (Forbidden) gets all subscriptions switched off.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import AlertDelivery, AlertStatus, Job, JobStatus, Subscription, User
from ayvona.db.repositories import kv_repo
from ayvona.services import admin_alerts
from ayvona.services import search as search_svc
from ayvona.services.search import SearchFilters
from ayvona.timeutil import to_local, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
SleepFn = Callable[[float], Awaitable[bool]]
CURSOR_KEY = "alerts:cursor"
DIGEST_KEY = "alerts:digest_date"
BATCH = 50


# --------------------------------------------------------------------------- subscriptions
def filters_of(sub: Subscription) -> SearchFilters:
    return SearchFilters(
        category=sub.category,
        profession=sub.profession,
        region=sub.region,
        min_salary=sub.min_salary,
        keyword=sub.keyword,
    )


class CreateResult(StrEnum):
    CREATED = "created"
    LIMIT = "limit"
    DUPLICATE = "duplicate"
    EMPTY = "empty"  # no filter at all: every job would be an alert


async def list_subscriptions(session: AsyncSession, user_id: int) -> list[Subscription]:
    rows = await session.scalars(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.id)
    )
    return list(rows.all())


async def create_subscription(
    session: AsyncSession, user_id: int, f: SearchFilters, now: datetime, settings: Settings
) -> tuple[CreateResult, Subscription | None]:
    """Does not commit."""
    if f.empty:
        return CreateResult.EMPTY, None
    subs = await list_subscriptions(session, user_id)
    if any(filters_of(s) == f for s in subs):
        return CreateResult.DUPLICATE, None
    if len(subs) >= settings.app.alerts.max_per_user:
        return CreateResult.LIMIT, None
    sub = Subscription(
        user_id=user_id,
        category=f.category,
        profession=f.profession,
        region=f.region,
        min_salary=f.min_salary,
        keyword=f.keyword,
        is_active=True,
        created_at=now,
    )
    session.add(sub)
    await session.flush()
    return CreateResult.CREATED, sub


async def set_active(session: AsyncSession, user_id: int, sub_id: int, active: bool) -> bool:
    """Pause / resume one of the user's subscriptions. Does not commit."""
    result = await session.execute(
        update(Subscription)
        .where(Subscription.id == sub_id, Subscription.user_id == user_id)
        .values(is_active=active)
    )
    return (result.rowcount or 0) == 1


async def delete_subscription(session: AsyncSession, user_id: int, sub_id: int) -> bool:
    """Does not commit (deliveries go with it: ON DELETE CASCADE)."""
    sub = await session.get(Subscription, sub_id)
    if sub is None or sub.user_id != user_id:
        return False
    await session.delete(sub)
    return True


async def deactivate_user(session: AsyncSession, user_id: int) -> int:
    """The user blocked the bot: all their subscriptions off. Does not commit."""
    result = await session.execute(
        update(Subscription).where(Subscription.user_id == user_id).values(is_active=False)
    )
    return result.rowcount or 0


# --------------------------------------------------------------------------- planning
@dataclass(slots=True)
class Delivery:
    user_id: int
    job: Job
    subscriptions: list[Subscription] = field(default_factory=list)
    digest: bool = False


async def sent_today(session: AsyncSession, user_id: int, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(AlertDelivery)
            .join(Subscription, Subscription.id == AlertDelivery.subscription_id)
            .where(
                Subscription.user_id == user_id,
                AlertDelivery.status == AlertStatus.SENT,
                AlertDelivery.sent_at >= now - timedelta(hours=24),
            )
        )
        or 0
    )


async def plan_job(
    session: AsyncSession, job: Job, now: datetime, settings: Settings, usd_rate: float
) -> list[Delivery]:
    """Match ``job`` with every active subscription, write the ``alert_deliveries`` rows (only
    new ones) and return one :class:`Delivery` per user. Does not commit."""
    subs = (
        await session.scalars(
            select(Subscription)
            .join(User, User.tg_id == Subscription.user_id)
            .where(Subscription.is_active.is_(True), User.is_banned.is_(False))
        )
    ).all()
    by_user: dict[int, Delivery] = {}
    for sub in subs:
        if admin_alerts.is_unfiltered(sub, settings):
            continue  # an admin's unfiltered subscription: services/admin_alerts.py sends it all
        if search_svc.job_matches(filters_of(sub), job, now, usd_rate):
            by_user.setdefault(sub.user_id, Delivery(sub.user_id, job)).subscriptions.append(sub)
    out: list[Delivery] = []
    for user_id, d in by_user.items():
        d.digest = await sent_today(session, user_id, now) >= settings.app.alerts.daily_limit
        status = AlertStatus.DIGEST if d.digest else AlertStatus.SENT
        fresh: list[Subscription] = []
        for sub in d.subscriptions:
            result = await session.execute(
                sqlite_insert(AlertDelivery)
                .values(subscription_id=sub.id, job_id=job.id, sent_at=now, status=status)
                .on_conflict_do_nothing()
            )
            if (result.rowcount or 0) == 1:
                fresh.append(sub)
        if fresh:
            d.subscriptions = fresh
            out.append(d)
    return out


# --------------------------------------------------------------------------- delivery (worker)
class AlertService:
    """Worker task. ``render(settings, job, filters) -> (text, keyboard)`` builds a message
    (bot presentation is injected so this module has no UI texts)."""

    def __init__(
        self,
        settings: Settings,
        sf: SessionFactory,
        bot: Bot,
        render_alert: Callable[
            [Settings, Job, SearchFilters, int], tuple[str, InlineKeyboardMarkup]
        ],
        render_digest: Callable[[Settings, list[Job], datetime], tuple[str, InlineKeyboardMarkup]],
    ) -> None:
        self.settings = settings
        self.cfg = settings.app.alerts
        self.sf = sf
        self.bot = bot
        self.render_alert = render_alert
        self.render_digest = render_digest

    async def _send(self, user_id: int, text: str, markup: InlineKeyboardMarkup | None) -> bool:
        """One message, ≤ per_second. False if the user blocked the bot (subscriptions off)."""
        for _ in range(2):
            try:
                await self.bot.send_message(
                    user_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
                )
                await asyncio.sleep(1 / self.cfg.per_second)
                return True
            except TelegramRetryAfter as e:
                logger.warning("alerts: Telegram kutishni so'radi {} s", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                async with self.sf() as s, s.begin():
                    n = await deactivate_user(s, user_id)
                logger.info("alerts: {} botni bloklagan — {} ta obuna o'chirildi", user_id, n)
                return False
            except Exception as e:
                logger.warning("alerts: {} ga yuborilmadi: {}", user_id, e)
                return False
        return False

    async def process_once(self, now: datetime | None = None) -> int:
        """Alert about jobs published since the cursor. Returns how many messages were sent."""
        now = now or utcnow()
        async with self.sf() as s, s.begin():
            cursor = await kv_repo.get_time(s, CURSOR_KEY)
            if cursor is None:  # first start: from now on (old jobs are not news)
                await kv_repo.set_value(s, CURSOR_KEY, now.isoformat())
                return 0
            jobs = list(
                (
                    await s.scalars(
                        select(Job)
                        .where(Job.status == JobStatus.PUBLISHED, Job.published_at > cursor)
                        .order_by(Job.published_at, Job.id)
                        .limit(BATCH)
                    )
                ).all()
            )
            rate = await search_svc.usd_rate(s, self.settings.app.search.usd_rate_fallback)
        sent = 0
        for job in jobs:
            async with self.sf() as s, s.begin():
                deliveries = await plan_job(s, job, now, self.settings, rate)
                assert job.published_at is not None
                await kv_repo.set_value(s, CURSOR_KEY, job.published_at.isoformat())
            for d in deliveries:
                if d.digest:
                    continue
                sub = d.subscriptions[0]
                text, markup = self.render_alert(self.settings, job, filters_of(sub), sub.id)
                if await self._send(d.user_id, text, markup):
                    sent += 1
        if sent:
            logger.info("alerts: {} ta xabar yuborildi", sent)
        return sent

    async def send_digests(self, now: datetime | None = None, *, force: bool = False) -> int:
        """Once a day at ``digest_hour``: one list per user of the jobs over the daily limit."""
        now = now or utcnow()
        local = to_local(now, self.settings.timezone)
        today = local.date().isoformat()
        async with self.sf() as s:
            done = await kv_repo.get(s, DIGEST_KEY)
        if not force and (local.hour < self.cfg.digest_hour or done == today):
            return 0
        async with self.sf() as s:
            rows = (
                await s.execute(
                    select(Subscription.user_id, Job)
                    .join(AlertDelivery, AlertDelivery.subscription_id == Subscription.id)
                    .join(Job, Job.id == AlertDelivery.job_id)
                    .where(AlertDelivery.status == AlertStatus.DIGEST)
                    .order_by(Job.published_at.desc())
                )
            ).all()
        per_user: dict[int, dict[int, Job]] = {}
        for user_id, job in rows:
            per_user.setdefault(user_id, {})[job.id] = job
        sent = 0
        for user_id, jobs in per_user.items():
            open_jobs = [
                j for j in jobs.values() if search_svc.job_matches(SearchFilters(), j, now, 1)
            ][: self.cfg.digest_max_items]
            if open_jobs:
                text, markup = self.render_digest(self.settings, open_jobs, now)
                if await self._send(user_id, text, markup):
                    sent += 1
        async with self.sf() as s, s.begin():
            await s.execute(
                update(AlertDelivery)
                .where(AlertDelivery.status == AlertStatus.DIGEST)
                .values(status=AlertStatus.DIGEST_SENT)
            )
            await kv_repo.set_value(s, DIGEST_KEY, today)
        if sent:
            logger.info("alerts: {} ta dayjest yuborildi", sent)
        return sent

    async def run(self, sleep: SleepFn) -> None:
        while True:
            try:
                await self.process_once()
                await self.send_digests()
            except Exception:
                logger.exception("alerts: kutilmagan xato")
            if await sleep(self.cfg.poll_seconds):
                return
