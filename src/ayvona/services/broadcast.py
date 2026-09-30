"""/broadcast: one message to every (not banned) user of the bot, slowly (``broadcast.per_second``).
Users who blocked the bot are skipped (Forbidden) — nothing else changes for them."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.db.models import User


@dataclass(slots=True)
class BroadcastReport:
    ok: int = 0
    failed: int = 0


async def recipients(session: AsyncSession) -> list[int]:
    rows = await session.scalars(select(User.tg_id).where(User.is_banned.is_(False)))
    return list(rows.all())


async def count_recipients(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned.is_(False))
        )
        or 0
    )


async def send_broadcast(
    bot: Bot, sf: async_sessionmaker[AsyncSession], text: str, per_second: float
) -> BroadcastReport:
    async with sf() as s:
        ids = await recipients(s)
    report = BroadcastReport()
    for user_id in ids:
        for _ in range(2):
            try:
                await bot.send_message(user_id, text)
                report.ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:  # blocked the bot, deleted account, ...
                logger.debug("broadcast: {} ga yetmadi: {}", user_id, e)
                report.failed += 1
                break
        else:
            report.failed += 1
        await asyncio.sleep(1 / per_second)
    logger.info("broadcast: {} ta yuborildi, {} tasiga yetmadi", report.ok, report.failed)
    return report
