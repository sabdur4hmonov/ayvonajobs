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


class SearchCb(CallbackData, prefix="sq"):
    """🔍 search wizard: cat | prof | reg | sal <value> ("*" = all), kw, last, new, page <n>."""

    step: str
    value: str = ""


class AlertCb(CallbackData, prefix="al"):
    """🔔 new-subscription wizard: cat | prof | reg | sal <value> ("*" = all)."""

    step: str
    value: str = ""


class SubCb(CallbackData, prefix="sub"):
    """🔔 subscription list: new | fromsearch | pause | resume | del | list <id>."""

    action: str
    id: int = 0


class ModCb(CallbackData, prefix="mod"):
    """Admin decision on a user job waiting for review: ok | no | ban."""

    action: str
    id: int
