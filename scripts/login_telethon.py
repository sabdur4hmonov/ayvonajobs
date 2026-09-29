"""One-time Telegram login for the collector (Telethon user account).

    uv run python scripts/login_telethon.py

Asks for: phone number, the code Telegram sends you, and your 2FA password (if you have one).
Result: data/ayvona.session (path from TELETHON_SESSION in .env).
That file gives FULL access to the account — never commit it, never send it to anyone.
"""

from __future__ import annotations

import asyncio
import getpass
import sys

from telethon import TelegramClient

from ayvona.config import get_settings


def _ask(prompt: str) -> str:
    return input(prompt).strip()


async def main() -> int:
    settings = get_settings()
    env = settings.env
    if env.api_id is None or env.api_hash is None:
        print("XATO: .env faylida API_ID va API_HASH to'ldirilmagan.")
        print("  1) my.telegram.org -> API development tools -> App yarating")
        print("  2) .env ga API_ID=... va API_HASH=... yozing, keyin qayta ishga tushiring.")
        return 1

    session = settings.session_file
    session.parent.mkdir(parents=True, exist_ok=True)
    print(f"Session fayli: {session}.session")

    client = TelegramClient(str(session), env.api_id, env.api_hash.get_secret_value())
    try:
        await client.start(
            phone=lambda: _ask("Telefon raqamingiz (+998...): "),
            code_callback=lambda: _ask("Telegram yuborgan kod: "),
            password=lambda: getpass.getpass("2FA parol (ekranda ko'rinmaydi): "),
        )
        me = await client.get_me()
        name = " ".join(filter(None, [me.first_name, me.last_name]))
        print(f"\nMuvaffaqiyatli! Akkaunt: {name} (@{me.username or '-'}, id={me.id})")
        print("Endi collector'ni ishga tushirishingiz mumkin:")
        print("  uv run python -m ayvona.apps.collector --once")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
