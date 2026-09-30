"""Callback data of the public bot's inline buttons (``prefix:field:field``, ≤ 64 bytes)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class JobCb(CallbackData, prefix="job"):
    action: str  # show | save | unsave
    id: int


class FavPageCb(CallbackData, prefix="favp"):
    page: int
