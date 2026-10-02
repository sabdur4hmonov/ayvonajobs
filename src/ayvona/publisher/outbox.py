"""Publisher (outbox): ``jobs`` in ``queued``/``retry`` -> our channel through the Bot API.

One job at a time, ``publish_interval_seconds`` apart:

1. in ONE transaction: skip if ``kv_store.publisher_paused``; take the next due job
   (``next_retry_at`` <= now: collecting window / backoff over) and mark it ``sending``
   (conditional UPDATE); pick its picture (rotation, processing/images.py);
2. outside any transaction: ``sendPhoto`` (cached ``file_id`` or the file) with the HTML caption
   and the buttons; no picture -> ``sendMessage`` with the link preview OFF;
3. result in one transaction: ``published`` + ``channel_message_id`` + the photo ``file_id`` cache,
   or the error handling below.

Errors:
* ``TelegramRetryAfter`` -> the job goes back as it was (no attempt used), everything waits the time
  Telegram asked for;
* HTML parse error -> sent again as plain text; a stale cached ``file_id`` -> the file is uploaded;
  a too long caption -> sent as a text message (4096 limit);
* bad token / bot not in the channel / channel not found -> job back (no attempt used), admin
  notice, nothing is sent for ``config_error_pause_seconds``;
* network / server / other errors -> attempt + 1, ``retry`` after an exponential backoff;
  after ``max_publish_attempts`` -> ``failed`` + admin notice.

A crash while ``sending`` -> the job is queued again on the next start (at-least-once).

Too old: before taking a job, every waiting job whose source post appeared more than
``max_age_hours`` ago becomes ``skipped_old`` (kept in the DB, never sent; logged, no admin
notice). The worker does the same once on start, before re-rendering the queue.

Quiet hours (``publisher.quiet_hours``, e.g. "23:00-07:00" Asia/Tashkent): nothing is sent; the
queue keeps filling and publishing resumes when they end. The too-old rule above still applies.
After a restart the first post waits until ``publish_interval_seconds`` have passed since the last
one in the channel.
"""

from __future__ import annotations

import html
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    ClientDecodeError,
    TelegramBadRequest,
    TelegramConflictError,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot.texts import POST_PUBLISHED_USER
from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin, JobStatus
from ayvona.db.repositories import images_repo, jobs_repo, kv_repo
from ayvona.processing.images import PickedImage, pick_image
from ayvona.services.notifier import Notifier
from ayvona.timeutil import ensure_utc, to_local, utcnow

SleepFn = Callable[[float], Awaitable[bool]]  # returns True if we should stop
QUIET_RECHECK_SECONDS = 60.0  # during quiet hours the publisher looks at the clock this often

_PARSE_ERROR_RE = re.compile(r"can't parse entities|unsupported start tag|can't find end", re.I)
_FILE_ERROR_RE = re.compile(r"wrong file identifier|file reference|wrong remote file|file_id", re.I)
_CAPTION_LONG_RE = re.compile(r"caption is too long|message caption is too long", re.I)
_CONFIG_BAD_REQUEST_RE = re.compile(
    r"chat not found|not enough rights|need administrator rights|have no rights"
    r"|chat_write_forbidden|chat_admin_required|bot is not a member",
    re.I,
)
_TAG_RE = re.compile(r"<[^>]+>")
_ANCHOR_RE = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.I | re.S)


def plain_text(caption_html: str) -> str:
    """HTML caption -> plain text (links as ``text (url)``) for the parse-error fallback."""
    text = _ANCHOR_RE.sub(lambda m: f"{m.group(2)} ({html.unescape(m.group(1))})", caption_html)
    return html.unescape(_TAG_RE.sub("", text))


def keyboard(buttons: list[Any] | None) -> InlineKeyboardMarkup | None:
    rows = [
        [InlineKeyboardButton(text=b["text"], url=b["url"]) for b in row if b.get("url")]
        for row in (buttons or [])
    ]
    rows = [r for r in rows if r]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def backoff_seconds(attempts: int, base: float, cap: float) -> float:
    """1st failure -> base, 2nd -> 2*base, 3rd -> 4*base ... never more than ``cap``."""
    return min(base * 2 ** max(attempts - 1, 0), cap)


# --------------------------------------------------------------------------- sending
@dataclass(frozen=True, slots=True)
class SendResult:
    message_id: int
    photo_file_id: str | None = None  # Telegram's id of the uploaded picture (cache it)
    plain: bool = False  # sent without HTML (parse error)


class ChannelSender:
    """Sends one post to our channel. Only this class calls the Bot API for the channel."""

    def __init__(self, bot: Bot, chat_id: int | str) -> None:
        self.bot = bot
        self.chat_id = chat_id

    async def _photo(
        self, photo: Any, caption: str, parse_mode: str | None, markup: Any
    ) -> Message:
        return await self.bot.send_photo(
            self.chat_id, photo, caption=caption, parse_mode=parse_mode, reply_markup=markup
        )

    async def _message(self, text: str, parse_mode: str | None, markup: Any) -> Message:
        return await self.bot.send_message(
            self.chat_id,
            text,
            parse_mode=parse_mode,
            reply_markup=markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    async def send(
        self, caption_html: str, buttons: list[Any] | None, image: PickedImage | None
    ) -> SendResult:
        markup = keyboard(buttons)
        photo: Any = None
        if image is not None:
            if image.telegram_file_id:
                photo = image.telegram_file_id
            elif image.path.is_file():
                photo = FSInputFile(image.path)
            else:
                logger.warning("Rasm fayli topilmadi: {} — matn rasmsiz yuboriladi", image.path)

        async def attempt(parse_mode: str | None, text: str) -> Message:
            nonlocal photo
            if photo is None:
                return await self._message(text, parse_mode, markup)
            try:
                return await self._photo(photo, text, parse_mode, markup)
            except TelegramBadRequest as e:
                if isinstance(photo, str) and _FILE_ERROR_RE.search(e.message) and image:
                    logger.warning("Eskirgan file_id ({}) — rasm qayta yuklanadi", image.path.name)
                    photo = FSInputFile(image.path)
                    return await self._photo(photo, text, parse_mode, markup)
                if _CAPTION_LONG_RE.search(e.message):
                    logger.warning("Caption juda uzun — rasmsiz matn sifatida yuboriladi")
                    photo = None
                    return await self._message(text, parse_mode, markup)
                raise

        plain = False
        try:
            msg = await attempt(ParseMode.HTML, caption_html)
        except TelegramBadRequest as e:
            if not _PARSE_ERROR_RE.search(e.message):
                raise
            logger.warning("HTML xatosi ({}) — oddiy matn bilan qayta yuboriladi", e.message)
            plain = True
            msg = await attempt(None, plain_text(caption_html))
        file_id = msg.photo[-1].file_id if msg.photo else None
        return SendResult(msg.message_id, file_id, plain)


# --------------------------------------------------------------------------- outbox
class Outcome(StrEnum):
    IDLE = "idle"  # nothing due
    PAUSED = "paused"  # admin /pause
    PUBLISHED = "published"
    RETRY = "retry"  # attempt failed, will be retried
    FAILED = "failed"  # attempts used up
    FLOOD = "flood"  # Telegram asked to wait
    CONFIG = "config"  # token / channel / rights problem
    QUIET = "quiet"  # quiet hours (night)


@dataclass(frozen=True, slots=True)
class PublishResult:
    outcome: Outcome
    job_id: int | None = None
    wait_seconds: float = 0.0


def _is_config_error(e: Exception) -> bool:
    if isinstance(
        e,
        TelegramUnauthorizedError
        | TelegramForbiddenError
        | TelegramNotFound
        | TelegramMigrateToChat
        | TelegramConflictError,
    ):
        return True
    return isinstance(e, TelegramBadRequest) and bool(_CONFIG_BAD_REQUEST_RE.search(e.message))


def too_old_reason(max_age_hours: float) -> str:
    """``last_error`` of a ``skipped_old`` job (the admin sees it in /retry too)."""
    return f"eskirgan: {max_age_hours:g} soatdan eski"


async def skip_old_jobs(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
    now: datetime | None = None,
    *,
    statuses: Sequence[JobStatus] = jobs_repo.SENDABLE,
    job_ids: Sequence[int] | None = None,
) -> list[int]:
    """Waiting jobs whose source post is older than ``publisher.max_age_hours`` ->
    ``skipped_old`` (one transaction). Returns their ids; logs them. Rule off (0) -> nothing."""
    cfg = settings.app.publisher
    cutoff = cfg.too_old_before(now or utcnow())
    if cutoff is None:
        return []
    async with sf() as s, s.begin():
        ids = await jobs_repo.skip_old(
            s, cutoff, too_old_reason(cfg.max_age_hours), statuses=statuses, job_ids=job_ids
        )
    if ids:
        shown = ", ".join(f"#{i}" for i in ids[:20]) + (" ..." if len(ids) > 20 else "")
        logger.info(
            "{} ta e'lon kanalga chiqmaydi — manbada {:g} soatdan oldin chiqqan (skipped_old): {}",
            len(ids),
            cfg.max_age_hours,
            shown,
        )
    return ids


CONFIG_HELP = (
    "Tekshiring: 1) BOT_TOKEN to'g'rimi; 2) bot kanalga ADMIN qilinganmi (post joylash huquqi); "
    "3) CHANNEL_ID to'g'rimi (@kanal yoki -100...)."
)


class Publisher:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        sender: ChannelSender,
        notifier: Notifier | None = None,
    ) -> None:
        self.settings = settings
        self.cfg = settings.app.publisher
        self.sf = session_factory
        self.sender = sender
        self.notifier = notifier
        self._quiet = False  # inside quiet hours (logged once when they start / end)

    async def _notify(self, text: str, key: str | None = None) -> None:
        if self.notifier is not None:
            await self.notifier.send(text, key=key)

    async def requeue_stuck(self, now: datetime | None = None) -> int:
        """Start-up: ``sending`` jobs left by a crash go back to the queue."""
        async with self.sf() as s, s.begin():
            ids = await jobs_repo.reset_stuck_sending(s, now or utcnow())
        if ids:
            logger.warning(
                "{} ta e'lon 'sending' holatida qolgan edi (to'xtab qolish) — qayta navbatga "
                "qo'yildi: {}. Ehtimol bittasi kanalda ikki marta chiqadi.",
                len(ids),
                ids,
            )
        return len(ids)

    async def _take(self, now: datetime) -> tuple[PublishResult | None, Job | None, Any]:
        async with self.sf() as s, s.begin():
            if await kv_repo.get_bool(s, kv_repo.PUBLISHER_PAUSED):
                return PublishResult(Outcome.PAUSED), None, None
            job = await jobs_repo.next_due(s, now)
            if job is None:
                return PublishResult(Outcome.IDLE), None, None
            if not await jobs_repo.claim(s, job):
                return PublishResult(Outcome.IDLE, job.id), None, None
            image: PickedImage | None = None
            try:
                image = await pick_image(s, self.settings, job.category, job.profession, now)
            except Exception:
                logger.exception("job #{}: rasm tanlanmadi — rasmsiz yuboriladi", job.id)
            return None, job, image

    async def publish_next(self, now: datetime | None = None) -> PublishResult:
        """Publish (or try) the next due job."""
        now = now or utcnow()
        await skip_old_jobs(self.settings, self.sf, now)
        quiet = self._quiet_hours(now)
        if quiet is not None:
            return quiet
        early, job, image = await self._take(now)
        if early is not None:
            return early
        assert job is not None
        previous = job.status  # queued | retry (claim() saw it)

        if not job.formatted_text:
            return await self._attempt_failed(job, "formatted_text bo'sh", final=True)

        try:
            result = await self.sender.send(job.formatted_text, job.buttons, image)
        except TelegramRetryAfter as e:
            wait = float(e.retry_after) + 1
            await self._release(job, previous, now + timedelta(seconds=wait), None)
            logger.warning("Telegram kutishni so'radi: {} s (job #{})", e.retry_after, job.id)
            return PublishResult(Outcome.FLOOD, job.id, wait)
        except Exception as e:
            if _is_config_error(e):
                pause = self.cfg.config_error_pause_seconds
                error = f"{type(e).__name__}: {e}"
                await self._release(job, previous, now + timedelta(seconds=pause), error)
                logger.error(
                    "Kanalga yuborib bo'lmadi (sozlama xatosi): {}. {}", error, CONFIG_HELP
                )
                await self._notify(
                    "🚫 <b>Kanalga joylab bo'lmayapti</b> (e'lonlar navbatda kutadi)\n"
                    f"<code>{html.escape(error[:400])}</code>\n{CONFIG_HELP}",
                    key=f"publish_config:{type(e).__name__}",
                )
                return PublishResult(Outcome.CONFIG, job.id, pause)
            return await self._attempt_failed(job, f"{type(e).__name__}: {e}", exc=e)

        async with self.sf() as s, s.begin():
            published = utcnow()
            exp = self.settings.app.expiry
            days = exp.user_days if job.origin == JobOrigin.USER else exp.aggregator_days
            await jobs_repo.mark_published(
                s, job.id, result.message_id, published, published + timedelta(days=days)
            )
            if (
                image is not None
                and result.photo_file_id
                and (result.photo_file_id != image.telegram_file_id)
            ):
                await images_repo.set_telegram_file_id(
                    s, image.id, result.photo_file_id, image.file_hash
                )
        logger.info(
            "Kanalga chiqdi: job #{} -> xabar {}{}",
            job.id,
            result.message_id,
            " (oddiy matn — HTML xatosi)" if result.plain else "",
        )
        if job.origin == JobOrigin.USER and job.author_id:
            await self._tell_author(job.author_id, result.message_id)
        return PublishResult(Outcome.PUBLISHED, job.id)

    def _quiet_hours(self, now: datetime) -> PublishResult | None:
        """Inside ``quiet_hours``: a QUIET result (wait = time until they end), else ``None``."""
        tz = self.settings.timezone
        until = self.cfg.quiet_until(now, tz)
        if until is None:
            if self._quiet:
                self._quiet = False
                logger.info("Tungi tanaffus tugadi — kanalga joylash davom etadi")
            return None
        if not self._quiet:
            self._quiet = True
            logger.info(
                "Tungi tanaffus ({}): {} gacha kanalga chiqmaydi, navbat kutadi",
                self.cfg.quiet_hours,
                to_local(until, tz).strftime("%H:%M"),
            )
        return PublishResult(Outcome.QUIET, None, (until - now).total_seconds())

    async def spacing_wait(self, now: datetime | None = None) -> float:
        """Seconds until ``publish_interval_seconds`` have passed since the last channel post
        (so a restart does not post sooner than the interval)."""
        interval = self.cfg.publish_interval_seconds
        if interval <= 0:
            return 0.0
        async with self.sf() as s:
            last = await jobs_repo.last_published_at(s)
        if last is None:
            return 0.0
        passed = ((now or utcnow()) - ensure_utc(last)).total_seconds()
        return max(interval - passed, 0.0)

    async def _tell_author(self, author_id: int, message_id: int) -> None:
        """A user's job is in the channel: send them the link. Never fails the publishing."""
        url = f"https://t.me/{self.settings.app.branding.channel_username}/{message_id}"
        try:
            await self.sender.bot.send_message(
                author_id,
                POST_PUBLISHED_USER.format(url=url),
                link_preview_options=LinkPreviewOptions(is_disabled=False),
            )
        except Exception as e:  # blocked the bot, flood, ...
            logger.info("Muallif {} ga havola yuborilmadi: {}", author_id, e)

    async def _release(
        self, job: Job, status: JobStatus, not_before: datetime, error: str | None
    ) -> None:
        async with self.sf() as s, s.begin():
            await jobs_repo.release(s, job.id, status, not_before=not_before, error=error)

    async def _attempt_failed(
        self, job: Job, error: str, *, final: bool = False, exc: Exception | None = None
    ) -> PublishResult:
        attempts = (job.attempts or 0) + 1
        final = final or attempts >= self.cfg.max_publish_attempts
        wait = backoff_seconds(attempts, self.cfg.retry_base_seconds, self.cfg.retry_max_seconds)
        next_at = None if final else utcnow() + timedelta(seconds=wait)
        async with self.sf() as s, s.begin():
            await jobs_repo.mark_attempt_failed(
                s, job.id, error, attempts=attempts, next_retry_at=next_at
            )
        title = html.escape(job.title or "—")
        if final:
            logger.error("job #{} kanalga chiqmadi ({} urinish): {}", job.id, attempts, error)
            await self._notify(
                f"❌ <b>E'lon kanalga chiqmadi</b> ({attempts} urinishdan keyin)\n"
                f"#{job.id} — {title}\n<code>{html.escape(error[:400])}</code>\n"
                "Qayta urinish: /retry " + str(job.id)
            )
            return PublishResult(Outcome.FAILED, job.id)
        transient = isinstance(
            exc, TelegramNetworkError | TelegramServerError | ClientDecodeError | OSError
        )
        logger.warning(
            "job #{}: yuborilmadi ({}-urinish, {} s dan keyin qayta): {}",
            job.id,
            attempts,
            round(wait),
            error,
        )
        await self._notify(
            f"⚠️ Kanalga yuborishda {'tarmoq ' if transient else ''}xatosi, qayta urinadi\n"
            f"<code>{html.escape(error[:300])}</code>",
            key=f"publish_error:{type(exc).__name__ if exc else 'none'}",
        )
        return PublishResult(Outcome.RETRY, job.id, wait)

    async def run(self, sleep: SleepFn, *, once: bool = False) -> None:
        """Loop until ``sleep`` reports stop. ``once``: publish what is due now, then return."""
        if not once:
            try:
                first = await self.spacing_wait()
            except Exception:
                logger.exception("publisher: oxirgi post vaqti o'qilmadi")
                first = 0.0
            if first > 0:
                logger.info("Oxirgi postdan beri interval o'tmagan — {} s kutiladi", round(first))
                if await sleep(first):
                    return
        while True:
            try:
                res = await self.publish_next()
            except Exception:  # DB locked etc. — never kill the loop
                logger.exception("publisher: kutilmagan xato")
                res = PublishResult(Outcome.RETRY, None, self.cfg.idle_poll_seconds)
            if once and res.outcome is not Outcome.PUBLISHED:
                return
            if res.outcome is Outcome.PUBLISHED:
                wait = self.cfg.publish_interval_seconds
            elif res.outcome in (Outcome.IDLE, Outcome.PAUSED, Outcome.FAILED):
                wait = self.cfg.idle_poll_seconds
            elif res.outcome is Outcome.QUIET:  # re-check now and then (clock, laptop sleep)
                wait = max(min(res.wait_seconds, QUIET_RECHECK_SECONDS), self.cfg.idle_poll_seconds)
            else:  # RETRY / FLOOD / CONFIG: wait as computed (a network error hits every job)
                wait = max(res.wait_seconds, self.cfg.idle_poll_seconds)
            if await sleep(wait):
                return
