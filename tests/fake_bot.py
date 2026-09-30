"""Bot API mock: a real aiogram ``Bot`` whose HTTP session never touches the network.

Every request is recorded (``session.requests``). Answers come from a script (FIFO); an empty
script means "OK". Scripted errors are real Bot API error JSON pushed through aiogram's own
``check_response``, so the same exception classes are raised as in production.
"""

from __future__ import annotations

import io
import json
from collections.abc import AsyncGenerator
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import (
    EditMessageText,
    GetFile,
    GetMe,
    SendDocument,
    SendMessage,
    SendPhoto,
    TelegramMethod,
)

TEST_TOKEN = "123456789:TEST_TOKEN_never_sent_anywhere_000000"
CHANNEL = -1001234567890
ADMIN_CHAT = -1009876543210


class FakeBotSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self.script: list[Any] = []
        self._message_id = 1000
        self._photo_n = 0
        # bytes returned when the bot downloads a file (/addimage); a valid JPEG by default
        self.download_bytes: bytes = jpeg_bytes()

    # ------------------------------------------------------------------ scripting
    def fail(self, status: int, description: str, retry_after: int | None = None) -> None:
        body: dict[str, Any] = {"ok": False, "error_code": status, "description": description}
        if retry_after is not None:
            body["parameters"] = {"retry_after": retry_after}
        self.script.append((status, body))

    def network_error(self, message: str = "Cannot connect to host api.telegram.org") -> None:
        self.script.append(("network", message))

    def ok(self) -> None:
        self.script.append(None)

    # ------------------------------------------------------------------ inspection
    def sent(self, kind: type[TelegramMethod[Any]]) -> list[Any]:
        return [r for r in self.requests if isinstance(r, kind)]

    # ------------------------------------------------------------------ BaseSession
    def _result(self, method: TelegramMethod[Any]) -> Any:
        if isinstance(method, GetMe):
            return {"id": 42, "is_bot": True, "first_name": "Ayvona", "username": "ayvonatestbot"}
        if isinstance(method, GetFile):
            return {"file_id": method.file_id, "file_unique_id": "f", "file_path": "photos/x.jpg"}
        if getattr(method, "__returning__", None) is bool:  # answerCallbackQuery, setMyCommands
            return True
        self._message_id += 1
        msg: dict[str, Any] = {
            "message_id": self._message_id,
            "date": 1_790_000_000,
            "chat": {"id": getattr(method, "chat_id", CHANNEL), "type": "channel"},
        }
        if isinstance(method, SendPhoto):
            self._photo_n += 1
            fid = method.photo if isinstance(method.photo, str) else f"PHOTO_ID_{self._photo_n}"
            msg["photo"] = [
                {"file_id": "small", "file_unique_id": "s", "width": 90, "height": 51},
                {
                    "file_id": fid,
                    "file_unique_id": f"u{self._photo_n}",
                    "width": 1280,
                    "height": 720,
                },
            ]
            msg["caption"] = method.caption
        elif isinstance(method, SendDocument):
            msg["document"] = {"file_id": "DOC_ID", "file_unique_id": "d"}
        elif isinstance(method, SendMessage | EditMessageText):
            msg["text"] = method.text
        return msg

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 — aiogram's BaseSession signature
    ) -> Any:
        self.requests.append(method)
        action = self.script.pop(0) if self.script else None
        if isinstance(action, tuple) and action[0] == "network":
            raise TelegramNetworkError(method=method, message=action[1])
        if isinstance(action, tuple):
            status, body = action
        else:
            status, body = 200, {"ok": True, "result": self._result(method)}
        response = self.check_response(bot, method, status, json.dumps(body))
        return response.result

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        yield self.download_bytes

    async def close(self) -> None:
        return None


def make_bot() -> tuple[Bot, FakeBotSession]:
    session = FakeBotSession()
    return Bot(TEST_TOKEN, session=session), session


def jpeg_bytes(size: tuple[int, int] = (32, 18)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()
