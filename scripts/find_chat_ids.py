"""Find the IDs for .env: CHANNEL_ID (test channel) and ADMIN_CHAT_ID (admin group), ADMIN_IDS.

How:
1. Put BOT_TOKEN into .env.
2. Add the bot to the test channel as ADMIN, post anything there.
3. Add the bot to the admin group, send /start@<bot_username> there.
4. Write /start to the bot in private.
5. Run (the bot process must NOT be running at the same time):
       uv run python scripts/find_chat_ids.py

Only reads the bot's recent updates (getUpdates); sends nothing.
"""

from __future__ import annotations

import asyncio
import sys

from ayvona.botapi import BotConfigError, create_bot
from ayvona.config import get_settings


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    try:
        bot = create_bot(get_settings())
    except BotConfigError as e:
        print(e)
        return 1
    try:
        me = await bot.get_me()
        updates = await bot.get_updates(limit=100, timeout=0)
    finally:
        await bot.session.close()
    print(f"Bot: @{me.username}\n")
    seen: dict[int, str] = {}
    for u in updates:
        for msg in (u.message, u.channel_post, u.my_chat_member):
            chat = getattr(msg, "chat", None)
            if chat is None:
                continue
            title = chat.title or chat.username or chat.full_name or ""
            seen[chat.id] = f"{chat.type:<10} {title}"
            user = getattr(msg, "from_user", None)
            if user is not None and chat.type == "private":
                seen[user.id] = f"{'SIZ':<10} {user.full_name} (@{user.username}) -> ADMIN_IDS"
    if not seen:
        print(
            "Hech narsa topilmadi. Kanalga post yozing / guruhda /start yuboring va qayta urining."
        )
        return 1
    for chat_id, what in seen.items():
        print(f"{chat_id:>16}  {what}")
    print("\nchannel -> CHANNEL_ID, group/supergroup -> ADMIN_CHAT_ID, SIZ -> ADMIN_IDS (.env)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
