"""Callback data of the public bot's inline buttons (``prefix:field:field``, ≤ 64 bytes)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class JobCb(CallbackData, prefix="job"):
    action: str  # show | save | unsave
    id: int


class FavPageCb(CallbackData, prefix="favp"):
    page: int


class PostCb(CallbackData, prefix="pj"):
    """📢 E'lon joylash form: cat <key> | reg <key> | send | edit | field <name> | cancel."""

    action: str
    value: str = ""


class ModCb(CallbackData, prefix="mod"):
    """Admin decision on a user job waiting for review: ok | no | ban."""

    action: str
    id: int
