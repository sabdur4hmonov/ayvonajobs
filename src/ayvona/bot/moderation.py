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
from ayvona.config import Settings
from ayvona.db.models import Job, User
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


@router.callback_query(ModCb.filter())
async def decide(query: CallbackQuery, callback_data: ModCb, sf: SessionFactory, bot: Bot) -> None:
    now = utcnow()
    admin = query.from_user
    who = f"@{admin.username}" if admin.username else str(admin.id)
    async with sf() as s, s.begin():
        if callback_data.action == "ok":
            job = await js.approve(s, callback_data.id, now)
        else:
            job = await js.reject(s, callback_data.id, f"admin {admin.id}")
            if job is not None and callback_data.action == "ban" and job.author_id:
                await users_svc.set_banned(s, job.author_id, True, now)
    if job is None:
        await query.answer(T.MOD_ALREADY, show_alert=True)
        return
    await query.answer()
    logger.info("admin {}: job #{} -> {}", admin.id, job.id, callback_data.action)
    mark = {"ok": T.MOD_DONE_OK, "no": T.MOD_DONE_NO, "ban": T.MOD_DONE_BAN}[callback_data.action]
    if isinstance(query.message, Message):
        await query.message.edit_text(
            (query.message.html_text or "") + mark.format(admin=html.escape(who)),
            reply_markup=None,
        )
    user_text = {
        "ok": T.POST_APPROVED_USER,
        "no": T.POST_REJECTED_USER,
        "ban": T.BANNED,
    }[callback_data.action]
    await _tell(bot, job.author_id, user_text)
