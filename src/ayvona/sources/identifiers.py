"""Channel identifier parsing without importing Telethon (the bot process uses it too, and
Telethon costs ~45 MB of RAM that the bot does not need)."""

from __future__ import annotations

import re

_TME_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)/?$")


def normalize_identifier(identifier: str) -> str | int:
    """``t.me/kanal``, ``https://t.me/s/kanal``, ``kanal`` -> ``@kanal``; ``-100123`` -> int."""
    ident = identifier.strip()
    if re.fullmatch(r"-?\d+", ident):
        return int(ident)
    m = _TME_RE.match(ident)
    if m:
        return "@" + m.group(1)
    return ident if ident.startswith("@") else "@" + ident
