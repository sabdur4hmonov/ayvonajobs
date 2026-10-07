"""Admin review of user jobs: the notice with [✅ Tasdiqlash] [❌ Rad etish] [🚫 Ban] and the
buttons' handler (admins only). The decision itself: services/job_submission.approve / reject.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot import texts as T
from ayvona.bot.callbacks import ModCb
from ayvona.botapi import parse_chat_id
from ayvona.config import Settings
from ayvona.db.models import Job, JobStatus, User
from ayvona.db.repositories import kv_repo
from ayvona.publisher.outbox import ChannelSender, Outcome, Publisher
from ayvona.services import job_submission as js
from ayvona.services import users as users_svc
from ayvona.timeutil import utcnow

SessionFactory = async_sessionmaker[AsyncSession]
router = Router(name="admin_moderation")


def author_label(user: User | None, user_id: int | None) -> str:
    if user is None:
        return str(user_id or "—")
    name = html.escape(user.full_name or "")
    at = f" @{html.escape(user.username)}" if user.username else ""
    return f'<a href="tg://user?id={user.tg_id}">{name or user.tg_id}</a>{at} (id {user.tg_id})'


def review_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.MOD_OK, callback_data=ModCb(action="ok", id=job_id).pack()
                ),
                InlineKeyboardButton(
                    text=T.MOD_NO, callback_data=ModCb(action="no", id=job_id).pack()
                ),
                InlineKeyboardButton(
                    text=T.MOD_BAN, callback_data=ModCb(action="ban", id=job_id).pack()
                ),
            ]
        ]
    )


def review_targets(settings: Settings) -> list[int | str]:
    """The admin group if set, else every admin in private."""
    if settings.env.admin_chat_id is not None:
        return [settings.env.admin_chat_id]
    return list(settings.env.admin_ids)


async def notify_review(
    bot: Bot,
    settings: Settings,
    sf: SessionFactory,
    job_id: int,
    author: User,
    reasons: Sequence[str],
) -> int:
    """Send the job to the admins for a decision. Returns how many chats got it."""
    async with sf() as s:
        job = await s.get(Job, job_id)
    if job is None:
        return 0
    text = T.MOD_HEAD.format(
        id=job.id,
        author=author_label(author, author.tg_id),
        reasons=html.escape("; ".join(reasons) or "—"),
    ) + (job.formatted_text or "")
    sent = 0
    for chat in review_targets(settings):
        try:
            await bot.send_message(chat, text, reply_markup=review_keyboard(job.id))
            sent += 1
        except Exception as e:  # admin never started the bot, ...
            logger.warning("Tekshiruv xabari {} ga yuborilmadi: {}", chat, e)
    if not sent:
        logger.error(
            "job #{}: tekshiruvga hech kimga yuborilmadi (ADMIN_CHAT_ID / ADMIN_IDS)", job.id
        )
    return sent


async def _tell(bot: Bot, user_id: int | None, text: str) -> None:
    if user_id is None:
        return
    try:
        await bot.send_message(user_id, text)
    except Exception as e:  # the user blocked the bot
        logger.info("Foydalanuvchi {} ga xabar yuborilmadi: {}", user_id, e)


async def publish_approved(
    bot: Bot, settings: Settings, sf: SessionFactory, job_id: int
) -> Outcome | None:
    """Send a job the admin just approved (claimed as ``sending``) to the channel, RIGHT NOW.

    Returns the publisher's outcome, or ``None`` if the channel is not configured. When Telegram
    refuses (flood, network, rights) the publisher hands the job back to the queue, so the worker
    finishes it — an approved ad is never lost. No admin message is sent from here: the admin
    sees the result on the approval message itself.
    """
    chat = parse_chat_id(settings.env.channel_id)
    if chat is None:
        async with sf() as s, s.begin():  # nobody can send it: back to the queue
            await js.requeue_claimed(s, job_id, utcnow())
        return None
    publisher = Publisher(settings, sf, ChannelSender(bot, chat), notifier=None)
    return (await publisher.publish_claimed(job_id)).outcome


@router.callback_query(ModCb.filter())
async def decide(
    query: CallbackQuery,
    callback_data: ModCb,
    sf: SessionFactory,
    bot: Bot,
    settings: Settings,
) -> None:
    now = utcnow()
    admin = query.from_user
    who = f"@{admin.username}" if admin.username else str(admin.id)
    async with sf() as s, s.begin():
        if callback_data.action == "ok":
            # /pause also holds back approved ads: they wait in the queue until /resume.
            paused = await kv_repo.get_bool(s, kv_repo.PUBLISHER_PAUSED)
            job = await js.approve(s, callback_data.id, now, publish_now=not paused)
        else:
            job = await js.reject(s, callback_data.id, f"admin {admin.id}")
            if job is not None and callback_data.action == "ban" and job.author_id:
                await users_svc.set_banned(s, job.author_id, True, now)
    if job is None:
        await query.answer(T.MOD_ALREADY, show_alert=True)
        return
    await query.answer()
    logger.info("admin {}: job #{} -> {}", admin.id, job.id, callback_data.action)

    published = False
    mark_key = callback_data.action
    if callback_data.action == "ok" and job.status == JobStatus.SENDING:
        outcome = await publish_approved(bot, settings, sf, job.id)
        published = outcome is Outcome.PUBLISHED
        mark_key = "ok_published" if published else "ok_queued"
    elif callback_data.action == "ok":
        mark_key = "ok_queued"  # publisher paused: waits in the queue
    mark = {
        "ok_published": T.MOD_DONE_PUBLISHED,
        "ok_queued": T.MOD_DONE_QUEUED,
        "no": T.MOD_DONE_NO,
        "ban": T.MOD_DONE_BAN,
    }[mark_key]
    if isinstance(query.message, Message):
        await query.message.edit_text(
            (query.message.html_text or "") + mark.format(admin=html.escape(who)),
            reply_markup=None,
        )
    if published:
        return  # the publisher already sent the author the link to the channel post
    user_text = {
        "ok_queued": T.POST_APPROVED_USER,
        "no": T.POST_REJECTED_USER,
        "ban": T.BANNED,
    }[mark_key]
    await _tell(bot, job.author_id, user_text)
