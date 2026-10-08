"""🔓 The admin's UNFILTERED alerts: every collected post that names the admin's profession.

A subscription of an admin (``ADMIN_IDS``) is "unfiltered" while ``ADMIN_UNFILTERED_ALERTS`` is on
(default) and the subscription has words to look for (:func:`words_of`: the profession's words
from categories.yaml + ``admin_alerts.keywords``; a category subscription takes all its
professions' words; the subscription's own keyword too). Region / salary are ignored.

Matching works on ``raw_posts`` — what the collector stored, from every source — so nothing the
pipeline does later can hide a post: not a job ad, duplicate, too old, low tier, no contact, AI
failure, still in the queue, never published. Words only (:class:`KeywordSet` on the folded
text, Latin / Cyrillic / Russian / English): no Gemini, no quota.

Delivery (:class:`AdminAlertService`, a worker task, every ``admin_alerts.poll_seconds``):
* raw posts after the cursor (``kv_store admin_alerts:cursor``; the first start begins "now") in
  id order. A post the worker has not decided on yet is waited for at most
  ``decision_wait_seconds`` (the alert shows WHY it was not published), then it goes anyway;
* posts collected before the subscription was made are not news and are skipped;
* the ``admin_alert_deliveries`` row (PK admin + post) is written FIRST, so a post is never sent
  twice to one admin — not after a restart, not after re-collection, not for two subscriptions.
  A crash between that write and the send loses that one alert (never twice wins);
* at most ``max_per_hour`` messages per admin; the rest wait as ``digest`` and go out as ONE list
  ``digest_minutes`` after the first of them. A message Telegram could not take now (network,
  5xx) also goes into the digest, so it is retried once instead of lost;
* ``send_delay_seconds`` after each message; Telegram "retry after" is waited and retried.

This is the one exception to "the admin gets only approval requests": the admin asked for these by
subscribing; ``/alerts`` lists them and 🗑 removes them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import (
    AdminAlertDelivery,
    AdminAlertStatus,
    Job,
    JobStatus,
    RawPost,
    RawPostStatus,
    Source,
    Subscription,
)
from ayvona.db.repositories import kv_repo
from ayvona.processing.formatter import telegram_post_url
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold
from ayvona.timeutil import ensure_utc, utcnow

SessionFactory = async_sessionmaker[AsyncSession]
SleepFn = Callable[[float], Awaitable[None]]
CURSOR_KEY = "admin_alerts:cursor"
BATCH = 200
UNDECIDED = (RawPostStatus.NEW, RawPostStatus.PROCESSING)
MAX_REASON = 160

# why a collected post is not (yet) in our channel — the alert's status line
RAW_REASONS: dict[RawPostStatus, str] = {
    RawPostStatus.NEW: "hali ko'rib chiqilmagan",
    RawPostStatus.PROCESSING: "hali ko'rib chiqilmagan",
    RawPostStatus.NOT_JOB: "ish e'loni emas deb topildi",
    RawPostStatus.RESUME: "rezyume (ish izlovchi posti)",
    RawPostStatus.CLOSED: "vakansiya yopilgan",
    RawPostStatus.OPPORTUNITY: "kurs / grant / tanlov (ish emas)",
    RawPostStatus.SUSPICIOUS: "shubhali (firibgarlik belgilari)",
    RawPostStatus.NO_TEXT: "matn yo'q",
    RawPostStatus.NO_CONTACT: "aloqa yo'q (telefon / @username / havola)",
    RawPostStatus.LOW_QUALITY: "sarlavha ham, maosh ham topilmadi",
    RawPostStatus.SKIPPED_BACKFILL: "kanal tarixidan olingan eski post",
    RawPostStatus.SKIPPED_LIMIT: "xalqaro e'lonlar kunlik limiti to'lgan",
    RawPostStatus.ERROR: "ishlashda xato",
    RawPostStatus.DUPLICATE: "dublikat",
}
# raw statuses whose stored note (``raw_posts.error``) says more
_WITH_NOTE = (
    RawPostStatus.NOT_JOB,
    RawPostStatus.SUSPICIOUS,
    RawPostStatus.LOW_QUALITY,
    RawPostStatus.ERROR,
)
JOB_REASONS: dict[JobStatus, str] = {
    JobStatus.QUEUED: "navbatda (daraja {tier})",
    JobStatus.RETRY: "navbatda (daraja {tier}, qayta urinish)",
    JobStatus.SENDING: "hozir yuborilmoqda",
    JobStatus.PENDING_REVIEW: "admin tekshiruvida",
    JobStatus.FAILED: "yuborishda xato",
    JobStatus.SKIPPED_OLD: "eskirgan",
    JobStatus.REJECTED: "rad etilgan",
    JobStatus.CLOSED: "yopilgan",
    JobStatus.EXPIRED: "muddati tugagan",
}
_PUBLISHED = (JobStatus.PUBLISHED, JobStatus.EXPIRED, JobStatus.CLOSED)


# --------------------------------------------------------------------------- who / which words
def enabled(settings: Settings) -> bool:
    return settings.env.admin_unfiltered_alerts and bool(settings.env.admin_ids)


def _dedup(words: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        key = fold(w)
        if key and key not in seen:
            seen.add(key)
            out.append(w)
    return out


def words_of(sub: Subscription, settings: Settings) -> list[str]:
    """The words an unfiltered subscription looks for (empty: nothing to match on)."""
    extra = settings.app.admin_alerts.keywords
    words: list[str] = []
    if sub.profession:
        for key, cat in settings.categories.items():
            if (sub.category is None or key == sub.category) and sub.profession in cat.professions:
                prof = cat.professions[sub.profession]
                words += [prof.title, *prof.keywords]
                break
        words += extra.get(sub.profession, [])
    elif sub.category and (cat := settings.categories.get(sub.category)):
        words += cat.keywords
        for prof in cat.professions.values():
            words += [prof.title, *prof.keywords]
        words += extra.get(sub.category, [])
    if sub.keyword:
        words.append(sub.keyword)
    return _dedup(words)


def is_unfiltered(sub: Subscription, settings: Settings) -> bool:
    """An admin's subscription with words, while the mode is on. The normal (filtered) alerts
    skip these: the unfiltered ones already bring everything."""
    return (
        enabled(settings)
        and sub.user_id in settings.env.admin_ids
        and bool(words_of(sub, settings))
    )


@dataclass(slots=True)
class _Rule:
    sub: Subscription
    words: KeywordSet


class Matcher:
    """The admins' active unfiltered subscriptions, compiled once per round."""

    def __init__(self, subs: Iterable[Subscription], settings: Settings) -> None:
        self.rules = [
            _Rule(s, KeywordSet(words_of(s, settings))) for s in subs if is_unfiltered(s, settings)
        ]

    def __bool__(self) -> bool:
        return bool(self.rules)

    def match(self, text: str) -> dict[int, tuple[Subscription, set[str]]]:
        """admin id -> (first matching subscription, the words found)."""
        out: dict[int, tuple[Subscription, set[str]]] = {}
        if not text.strip():
            return out
        folded = fold(text)
        for rule in self.rules:
            if rule.sub.user_id in out:
                continue
            if hits := rule.words.find(folded):
                out[rule.sub.user_id] = (rule.sub, hits)
        return out


# --------------------------------------------------------------------------- the status line
@dataclass(frozen=True, slots=True)
class PostState:
    published: bool
    reason: str | None = None  # why not (None when published)
    other_copy: bool = False  # published, but from another source's copy of the same ad


def post_state(raw: RawPost, job: Job | None) -> PostState:
    """Is the post (or the ad it repeats) in our channel, and if not, why."""
    if job is not None and job.status in _PUBLISHED and job.channel_message_id is not None:
        return PostState(True, other_copy=job.raw_post_id != raw.id)
    if raw.status in (RawPostStatus.DONE, RawPostStatus.DUPLICATE) and job is not None:
        reason = JOB_REASONS.get(job.status, str(job.status)).format(tier=job.priority_tier or 2)
        if job.status is JobStatus.SKIPPED_OLD and job.last_error:
            reason += f" — {job.last_error}"
        if raw.status is RawPostStatus.DUPLICATE:
            reason = f"dublikat (e'lon #{job.id}: {reason})"
        return PostState(False, reason[:MAX_REASON])
    reason = RAW_REASONS.get(raw.status, str(raw.status))
    if raw.status in _WITH_NOTE and raw.error:
        reason += f" — {raw.error}"
    return PostState(False, reason[:MAX_REASON])


def source_post_url(raw: RawPost, source: Source | None) -> str | None:
    """The original post: a web source's own URL, else ``t.me/<channel>/<id>``."""
    extra = raw.extra or {}
    if isinstance(extra.get("url"), str) and extra["url"]:
        return str(extra["url"])
    return telegram_post_url(source.identifier if source else None, raw.external_id)


@dataclass(slots=True)
class AlertView:
    """Everything one alert message shows (bot/alerts_render.py turns it into text)."""

    raw: RawPost
    source: Source | None
    job: Job | None
    subscription: Subscription | None
    hits: tuple[str, ...]
    state: PostState
    url: str | None


async def load_view(
    session: AsyncSession,
    raw: RawPost,
    sub: Subscription | None,
    hits: Iterable[str],
) -> AlertView:
    source = await session.get(Source, raw.source_id)
    job = await session.get(Job, raw.job_id) if raw.job_id else None
    return AlertView(
        raw=raw,
        source=source,
        job=job,
        subscription=sub,
        hits=tuple(sorted(hits)),
        state=post_state(raw, job),
        url=source_post_url(raw, source),
    )


async def view_for(
    session: AsyncSession, raw_post_id: int, sub_id: int, settings: Settings
) -> AlertView | None:
    """The CURRENT state of an alert (the 🔄 button). ``None`` if the post is gone."""
    raw = await session.get(RawPost, raw_post_id)
    if raw is None:
        return None
    sub = await session.get(Subscription, sub_id) if sub_id else None
    hits: set[str] = set()
    if sub is not None:
        hits = KeywordSet(words_of(sub, settings)).find(fold(raw.text or ""))
    return await load_view(session, raw, sub, hits)


# --------------------------------------------------------------------------- /alerts
async def admin_subscriptions(session: AsyncSession, settings: Settings) -> list[Subscription]:
    if not enabled(settings):
        return []
    rows = await session.scalars(
        select(Subscription)
        .where(
            Subscription.is_active.is_(True),
            Subscription.user_id.in_(list(settings.env.admin_ids)),
        )
        .order_by(Subscription.id)
    )
    return list(rows.all())


async def sent_last_hour(session: AsyncSession, user_id: int, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(AdminAlertDelivery)
            .where(
                AdminAlertDelivery.user_id == user_id,
                AdminAlertDelivery.status == AdminAlertStatus.SENT,
                AdminAlertDelivery.created_at >= now - timedelta(hours=1),
            )
        )
        or 0
    )


# --------------------------------------------------------------------------- delivery (worker)
class Sent(StrEnum):
    OK = "ok"
    LATER = "later"  # network / Telegram 5xx: try again later (in the digest)
    GAVE_UP = "gave_up"  # Telegram refused it (bad request, the admin blocked the bot)


RenderAlert = Callable[[Settings, AlertView], tuple[str, InlineKeyboardMarkup]]
# -> the digest's messages: (text, the raw post ids listed in it)
RenderDigest = Callable[[Settings, Sequence[AlertView]], list[tuple[str, list[int]]]]


class AdminAlertService:
    """Worker task. The message layout is injected (bot/alerts_render.py) like AlertService's."""

    def __init__(
        self,
        settings: Settings,
        sf: SessionFactory,
        bot: Bot,
        render_alert: RenderAlert,
        render_digest: RenderDigest,
        *,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.cfg = settings.app.admin_alerts
        self.sf = sf
        self.bot = bot
        self.render_alert = render_alert
        self.render_digest = render_digest
        self.sleep = sleep

    async def _send(self, chat_id: int, text: str, markup: InlineKeyboardMarkup | None) -> Sent:
        for _ in range(3):
            try:
                await self.bot.send_message(
                    chat_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
                )
            except TelegramRetryAfter as e:
                logger.warning("admin alerts: Telegram kutishni so'radi {} s", e.retry_after)
                await self.sleep(e.retry_after + 1)
                continue
            except (TelegramNetworkError, TelegramServerError) as e:
                logger.warning("admin alerts: {} ga hozir yuborilmadi (keyinroq): {}", chat_id, e)
                return Sent.LATER
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                logger.warning("admin alerts: {} ga yuborilmadi: {}", chat_id, e)
                return Sent.GAVE_UP
            except Exception as e:  # never kill the loop
                logger.warning("admin alerts: {} ga yuborilmadi: {}", chat_id, e)
                return Sent.LATER
            if self.cfg.send_delay_seconds:
                await self.sleep(self.cfg.send_delay_seconds)
            return Sent.OK
        return Sent.LATER

    async def _set_status(
        self, user_id: int, raw_post_id: int, status: AdminAlertStatus, now: datetime | None = None
    ) -> None:
        values: dict[str, object] = {"status": status}
        if now is not None:
            values["created_at"] = now
        async with self.sf() as s, s.begin():
            await s.execute(
                update(AdminAlertDelivery)
                .where(
                    AdminAlertDelivery.user_id == user_id,
                    AdminAlertDelivery.raw_post_id == raw_post_id,
                )
                .values(**values)
            )

    async def process_once(self, now: datetime | None = None) -> int:
        """Alert about the posts collected since the cursor. Returns how many messages went out."""
        if not enabled(self.settings):
            return 0
        now = now or utcnow()
        wait = timedelta(seconds=self.cfg.decision_wait_seconds)
        views: list[tuple[int, AlertView]] = []
        async with self.sf() as s, s.begin():
            cursor_text = await kv_repo.get(s, CURSOR_KEY)
            top = int(await s.scalar(select(func.max(RawPost.id))) or 0)
            if cursor_text is None:  # first start: from now on (old posts are not news)
                await kv_repo.set_value(s, CURSOR_KEY, str(top))
                return 0
            cursor = int(cursor_text)
            matcher = Matcher(await admin_subscriptions(s, self.settings), self.settings)
            if not matcher:  # nobody to alert: just keep up
                if top > cursor:
                    await kv_repo.set_value(s, CURSOR_KEY, str(top))
                return 0
            rows = (
                await s.scalars(
                    select(RawPost).where(RawPost.id > cursor).order_by(RawPost.id).limit(BATCH)
                )
            ).all()
            done = cursor
            used: dict[int, int] = {}  # admin -> messages in the last hour (incl. this round)
            for raw in rows:
                if raw.status in UNDECIDED and ensure_utc(raw.fetched_at) > now - wait:
                    break  # the worker decides in a moment; keep the order, come back later
                done = raw.id
                for user_id, (sub, hits) in matcher.match(raw.text or "").items():
                    if ensure_utc(raw.fetched_at) < ensure_utc(sub.created_at):
                        continue  # collected before the subscription existed
                    if user_id not in used:
                        used[user_id] = await sent_last_hour(s, user_id, now)
                    over = used[user_id] >= self.cfg.max_per_hour
                    result = await s.execute(
                        sqlite_insert(AdminAlertDelivery)
                        .values(
                            user_id=user_id,
                            raw_post_id=raw.id,
                            subscription_id=sub.id,
                            status=AdminAlertStatus.DIGEST if over else AdminAlertStatus.SENT,
                            created_at=now,
                        )
                        .on_conflict_do_nothing()
                    )
                    if (result.rowcount or 0) != 1:
                        continue  # already sent to this admin (restart, re-collection)
                    if over:
                        logger.info(
                            "admin alerts: post #{} -> dayjest (soatiga {} ta limit)",
                            raw.id,
                            self.cfg.max_per_hour,
                        )
                        continue
                    used[user_id] += 1
                    views.append((user_id, await load_view(s, raw, sub, hits)))
            if done != cursor:
                await kv_repo.set_value(s, CURSOR_KEY, str(done))
        sent = 0
        for user_id, view in views:
            text, markup = self.render_alert(self.settings, view)
            outcome = await self._send(user_id, text, markup)
            if outcome is Sent.OK:
                sent += 1
            elif outcome is Sent.LATER:  # retried once, in the digest
                await self._set_status(user_id, view.raw.id, AdminAlertStatus.DIGEST, now)
            else:
                await self._set_status(user_id, view.raw.id, AdminAlertStatus.FAILED)
        if sent:
            logger.info("admin alerts: {} ta xabar yuborildi", sent)
        return sent

    async def send_digests(self, now: datetime | None = None, *, force: bool = False) -> int:
        """One list per admin of the posts over the hourly cap, ``digest_minutes`` after the
        first of them. Returns how many admins got one."""
        if not enabled(self.settings):
            return 0
        now = now or utcnow()
        async with self.sf() as s:
            rows = (
                await s.execute(
                    select(AdminAlertDelivery, RawPost)
                    .join(RawPost, RawPost.id == AdminAlertDelivery.raw_post_id)
                    .where(AdminAlertDelivery.status == AdminAlertStatus.DIGEST)
                    .order_by(AdminAlertDelivery.user_id, RawPost.id)
                )
            ).all()
            per_user: dict[int, list[tuple[AdminAlertDelivery, RawPost]]] = {}
            for row, raw in rows:
                per_user.setdefault(row.user_id, []).append((row, raw))
            due: dict[int, list[AlertView]] = {}
            for user_id, items in per_user.items():
                first = min(ensure_utc(r.created_at) for r, _ in items)
                if not force and first > now - timedelta(minutes=self.cfg.digest_minutes):
                    continue
                subs = {
                    r.subscription_id: await s.get(Subscription, r.subscription_id)
                    for r, _ in items
                    if r.subscription_id
                }
                due[user_id] = [
                    await load_view(s, raw, subs.get(r.subscription_id), ()) for r, raw in items
                ]
        admins = 0
        for user_id, views in due.items():
            delivered = 0
            # one message per part; each part's posts are marked as soon as it went out, so a
            # failure in the middle never sends the earlier parts again
            for text, raw_ids in self.render_digest(self.settings, views):
                outcome = await self._send(user_id, text, None)
                if outcome is Sent.LATER:
                    break  # the rest next round
                status = (
                    AdminAlertStatus.DIGEST_SENT if outcome is Sent.OK else AdminAlertStatus.FAILED
                )
                async with self.sf() as s, s.begin():
                    await s.execute(
                        update(AdminAlertDelivery)
                        .where(
                            AdminAlertDelivery.user_id == user_id,
                            AdminAlertDelivery.raw_post_id.in_(raw_ids),
                            AdminAlertDelivery.status == AdminAlertStatus.DIGEST,
                        )
                        .values(status=status)
                    )
                if outcome is Sent.OK:
                    delivered += len(raw_ids)
            if delivered:
                admins += 1
                logger.info("admin alerts: {} ga {} ta postli dayjest", user_id, delivered)
        return admins

    async def run(self, sleep: Callable[[float], Awaitable[bool]]) -> None:
        logger.info(
            "Admin filtrsiz obunalari: yoqilgan (soatiga {} ta, keyin dayjest)",
            self.cfg.max_per_hour,
        )
        while True:
            try:
                await self.process_once()
                await self.send_digests()
            except Exception:
                logger.exception("admin alerts: kutilmagan xato")
            if await sleep(self.cfg.poll_seconds):
                return
