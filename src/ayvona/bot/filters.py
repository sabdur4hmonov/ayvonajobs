"""Bot filters."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message


class IsAdmin(Filter):
    """Passes only for Telegram ids in ``ADMIN_IDS`` (.env). Empty list -> nobody is admin."""

    def __init__(self, admin_ids: Iterable[int]) -> None:
        self.admin_ids = frozenset(admin_ids)

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id in self.admin_ids
