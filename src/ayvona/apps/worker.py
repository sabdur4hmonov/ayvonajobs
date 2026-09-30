"""Worker process: turns new raw posts into jobs (pipeline) and publishes them (outbox).

Tasks running side by side:
* pipeline  — every ``worker.poll_interval_seconds``: raw_posts(new) -> jobs(queued)
  (processing/pipeline.py);
* publisher — jobs(queued/retry) -> our channel, ``publish_interval_seconds`` apart
  (publisher/outbox.py);
* heartbeat — ``kv_store`` ``heartbeat:worker`` every minute;
* monitoring — every 5 min: collector / bot silent? sources silent or failing?
  (services/heartbeat.py);
* backup — daily 03:00 Asia/Tashkent copy of the DB, sent to the admin chat (services/backup.py).

Step 0 (first start only): every post already in the DB becomes ``skipped_backfill`` — the test
posts collected before the worker existed never reach the channel (``kv_store`` flag
``worker:backfill_skipped_at``).

Every start, before publishing: ``queued`` / ``retry`` jobs whose source post is older than
``publisher.max_age_hours`` become ``skipped_old``; the rest are re-rendered with the current
formatter and ``branding`` (services/reformat.py; ``worker.reformat_queued_on_start``).

Without ``BOT_TOKEN`` / ``CHANNEL_ID`` the worker still runs: the pipeline fills the queue, the
publisher is off and says why. Nothing is ever sent to Telegram in that case.

Run:  uv run python -m ayvona.apps.worker              (forever)
      uv run python -m ayvona.apps.worker --once       (process + publish what is due, then exit)
      uv run python -m ayvona.apps.worker --no-publish (pipeline only, the channel is not touched)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from collections.abc import Coroutine
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError
from loguru import logger

from ayvona.apps.runtime import (
    SessionFactory,
    heartbeat_loop,
    install_signal_handlers,
    stop_aware_sleep,
    write_heartbeat,
)
from ayvona.botapi import (
    BAD_TOKEN,
    NO_ADMIN_CHAT,
    NO_CHANNEL,
    BotConfigError,
    create_bot,
    parse_chat_id,
)
from ayvona.config import Settings, get_settings
from ayvona.db.repositories import kv_repo, raw_posts_repo
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.logging_setup import setup_logging
from ayvona.processing.pipeline import Pipeline
from ayvona.publisher.outbox import ChannelSender, Publisher, skip_old_jobs
from ayvona.services.backup import BackupService
from ayvona.services.heartbeat import Monitor
from ayvona.services.notifier import Notifier
from ayvona.services.reformat import ReformatReport, reformat_queued
from ayvona.timeutil import utcnow

PROCESS_NAME = "worker"
BACKFILL_FLAG = "worker:backfill_skipped_at"
SHUTDOWN_GRACE_SECONDS = 20


async def skip_existing_posts(sf: SessionFactory) -> int | None:
    """ROADMAP Bosqich 7, step 0 — once per DB: posts collected before the worker's first start
    never go to the channel. Returns how many were skipped, ``None`` if already done earlier."""
    async with sf() as s, s.begin():
        if await kv_repo.get(s, BACKFILL_FLAG):
            return None
        now = utcnow()
        n = await raw_posts_repo.skip_existing_new(s, now)
        await kv_repo.set_value(s, BACKFILL_FLAG, json.dumps({"at": now.isoformat(), "count": n}))
    logger.warning(
        "Birinchi ishga tushish: bazadagi {} ta eski post 'skipped_backfill' qilindi — ular "
        "kanalga chiqmaydi. Bundan keyin kelgan postlar odatdagidek ishlanadi.",
        n,
    )
    return n


async def reset_stuck_processing(sf: SessionFactory) -> int:
    async with sf() as s, s.begin():
        n = await raw_posts_repo.reset_stuck_processing(s)
    if n:
        logger.warning("{} ta post 'processing' da qolgan edi — qayta 'new' qilindi", n)
    return n


async def skip_old_queue(settings: Settings, sf: SessionFactory) -> list[int]:
    """Start-up, before re-rendering: waiting jobs older than ``publisher.max_age_hours`` ->
    ``skipped_old`` (the publisher checks again before every post). Never stops the worker."""
    try:
        return await skip_old_jobs(settings, sf)
    except Exception:
        logger.exception(
            "Eskirgan e'lonlarni belgilashda xato — publisher keyinroq qayta tekshiradi"
        )
        return []


async def reformat_queue(settings: Settings, sf: SessionFactory) -> ReformatReport | None:
    """Start-up, before the publisher: the queue gets the current formatter / branding.

    Formatter code and ``branding`` only change with a restart (deploy, settings.yaml), so doing
    it here keeps every job still waiting in step with them. Never stops the worker: on an error
    the jobs keep their stored text."""
    if not settings.app.worker.reformat_queued_on_start:
        return None
    try:
        report = await reformat_queued(settings, sf)
    except Exception:
        logger.exception("Navbatni qayta formatlashda xato — e'lonlar eski matn bilan qoladi")
        return None
    if report.updated or report.skipped or report.taken:
        logger.info(
            "Navbat hozirgi formatter bilan yangilandi: {} ta e'londan {} tasi o'zgardi, "
            "{} tasi o'tkazib yuborildi",
            report.total,
            report.updated,
            len(report.skipped),
        )
    for job_id, reason in report.skipped:
        logger.warning("job #{}: qayta formatlanmadi — {}", job_id, reason)
    return report


async def pipeline_loop(
    pipeline: Pipeline, interval: float, stop: asyncio.Event, *, once: bool = False
) -> None:
    sleep = stop_aware_sleep(stop)
    while not stop.is_set():
        try:
            stats = await pipeline.run_once()
        except Exception:  # never kill the loop (DB locked for too long, ...)
            logger.exception("pipeline: kutilmagan xato")
            stats = None
        if once:
            if stats is None or stats.posts == 0 or stats.db_errors:
                return
            continue  # drain everything that is ready
        if await sleep(interval):
            return


async def run_worker(
    settings: Settings,
    sf: SessionFactory,
    stop: asyncio.Event,
    *,
    bot: Bot | None = None,
    channel: int | str | None = None,
    admin_chat: int | str | None = None,
    publish: bool = True,
    once: bool = False,
    monitor: bool = True,
) -> None:
    """Everything after the process setup (tests call this with a mocked Bot API).

    ``monitor``: also run the monitoring and the daily backup (not in ``once`` mode).
    """
    await skip_existing_posts(sf)
    await reset_stuck_processing(sf)
    notifier = Notifier(bot, admin_chat, sf)
    pipeline = Pipeline(settings, sf, notifier)

    publisher: Publisher | None = None
    if publish and bot is not None and channel is not None:
        publisher = Publisher(settings, sf, ChannelSender(bot, channel), notifier)
        await publisher.requeue_stuck()
    elif publish:
        logger.warning(
            "Kanalga joylash O'CHIQ ({}). E'lonlar 'queued' holatida navbatda kutadi.",
            "BOT_TOKEN yo'q" if bot is None else "CHANNEL_ID yo'q",
        )
    else:
        logger.info("--no-publish: kanalga hech narsa yuborilmaydi, faqat qayta ishlash.")
    await skip_old_queue(settings, sf)
    await reformat_queue(settings, sf)

    cfg = settings.app.worker
    if once:
        await pipeline_loop(pipeline, cfg.poll_interval_seconds, stop, once=True)
        if publisher is not None:
            await publisher.run(stop_aware_sleep(stop), once=True)
        await write_heartbeat(sf, PROCESS_NAME)
        return

    jobs: list[Coroutine[Any, Any, None]] = [
        heartbeat_loop(sf, PROCESS_NAME, cfg.heartbeat_interval_seconds, stop),
        pipeline_loop(pipeline, cfg.poll_interval_seconds, stop),
    ]
    if publisher is not None:
        jobs.append(publisher.run(stop_aware_sleep(stop)))
    if monitor:
        jobs.append(
            Monitor(settings, sf, notifier, ("collector", "bot")).run(stop_aware_sleep(stop))
        )
        jobs.append(BackupService(settings, sf, notifier).run(stop_aware_sleep(stop)))
    tasks = [asyncio.create_task(j) for j in jobs]
    try:
        await stop.wait()
    finally:
        stop.set()
        # Let a Bot API call in flight finish (it would be retried anyway), then cancel.
        _, pending = await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_SECONDS)
        for t in pending:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _setup_bot(settings: Settings) -> Bot | None:
    """The Bot, or ``None`` with a clear Uzbek message (missing / bad token)."""
    try:
        bot = create_bot(settings)
    except BotConfigError as e:
        logger.warning("{} Kanalga joylash va admin xabarlari o'chirilgan.", e)
        return None
    try:
        me = await bot.get_me()
        logger.info("Bot: @{}", me.username)
    except TelegramUnauthorizedError:
        logger.error("{} Telegram tokenni rad etdi.", BAD_TOKEN)
        await bot.session.close()
        return None
    except Exception as e:  # no network now — the publisher will retry later
        logger.warning(
            "Bot API'ga ulanib bo'lmadi ({}: {}) — keyinroq qayta uriniladi", type(e).__name__, e
        )
    return bot


async def main(*, once: bool = False, publish: bool = True) -> int:
    settings = get_settings()
    setup_logging(settings.env.log_level, settings.log_dir, PROCESS_NAME)
    logger.info("Worker ishga tushmoqda (baza: {})", settings.db_file)

    engine = create_engine(settings.db_url)
    bot: Bot | None = None
    try:
        if not await schema_is_ready(engine):
            logger.error(
                "Baza tayyor emas yoki eski versiyada. Avval: uv run alembic upgrade head"
            )
            return 1
        sf = create_session_factory(engine)
        bot = await _setup_bot(settings)
        channel = parse_chat_id(settings.env.channel_id)
        if channel is None and publish:
            logger.warning(NO_CHANNEL)
        admin_chat = settings.env.admin_chat_id
        if admin_chat is None:
            logger.warning(NO_ADMIN_CHAT)

        stop = asyncio.Event()
        install_signal_handlers(stop)
        await run_worker(
            settings,
            sf,
            stop,
            bot=bot,
            channel=channel,
            admin_chat=admin_chat,
            publish=publish,
            once=once,
        )
        return 0
    finally:
        if bot is not None:
            with contextlib.suppress(Exception):
                await bot.session.close()
        await engine.dispose()
        logger.info("Worker to'xtadi.")


def run() -> int:
    parser = argparse.ArgumentParser(description="Ayvona worker (pipeline + publisher)")
    parser.add_argument("--once", action="store_true", help="bir marta ishlab, chiqish")
    parser.add_argument(
        "--no-publish", action="store_true", help="kanalga yubormaslik (faqat qayta ishlash)"
    )
    args = parser.parse_args()
    try:
        return asyncio.run(main(once=args.once, publish=not args.no_publish))
    except KeyboardInterrupt:  # Ctrl+C on Windows
        logger.info("Ctrl+C — to'xtatildi.")
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
