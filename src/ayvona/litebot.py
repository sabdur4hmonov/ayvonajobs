"""A tiny Bot API client (``sendMessage`` only) over httpx — for the collector.

Why: the collector only sends admin notices (results of ``/addsource``), but ``aiogram`` costs
~130 MB of RAM just to be imported, which is a lot on a 1 GB server. This class has the same
``send_message`` shape the :class:`~ayvona.services.notifier.Notifier` uses, and nothing else.
The worker and the bot keep using aiogram.

The token never appears in an exception message or a log line.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

API_URL = "https://api.telegram.org/bot{token}/{method}"
_TOKEN_RE = re.compile(r"^\d{3,}:[\w-]{20,}$")


class LiteBotError(Exception):
    """Bot API said no, or the network failed. The message never contains the token."""


class LiteBot:
    def __init__(
        self,
        token: str,
        *,
        timeout: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        token = token.strip()
        if not _TOKEN_RE.match(token):
            raise ValueError("BOT_TOKEN noto'g'ri ko'rinishda")
        self._token = token
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport)

    @property
    def session(self) -> LiteBot:
        """aiogram's ``bot.session.close()`` call sites work unchanged."""
        return self

    async def close(self) -> None:
        await self._http.aclose()

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: str | None = None,
        link_preview_options: dict[str, Any] | None = None,
    ) -> None:
        body: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            body["parse_mode"] = parse_mode
        if link_preview_options:
            body["link_preview_options"] = link_preview_options
        try:
            resp = await self._http.post(
                API_URL.format(token=self._token, method="sendMessage"), json=body
            )
        except httpx.HTTPError as e:
            # type name only: some httpx messages contain the request URL (= the token)
            raise LiteBotError(f"network: {type(e).__name__}") from None
        if resp.status_code != 200:
            try:
                desc = str(resp.json().get("description", ""))[:200]
            except ValueError:
                desc = ""
            raise LiteBotError(f"Bot API HTTP {resp.status_code}: {desc}")
