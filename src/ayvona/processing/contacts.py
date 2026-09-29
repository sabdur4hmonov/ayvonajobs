"""Basic contact detection: phones, @usernames, emails, useful links.

Used by the classifier ("does the post have any contact?") and by dedup (fingerprint, shared
contacts). Bosqich 5 (extract.py) builds the full version on top (all phone spellings from
SOURCE_ANALYSIS §5 with context rules, apply_url choice, ...).
All finders expect *normalized* text (lower case, emoji removed).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

# Operator codes + landline city codes (SOURCE_ANALYSIS §5).
MOBILE_CODES = frozenset(
    {"20", "33", "50", "55", "77", "78", "87", "88", "90", "91", "93", "94", "95", "97", "98", "99"}
)
CITY_CODES = frozenset(str(c) for c in range(61, 80))
PHONE_CODES = MOBILE_CODES | CITY_CODES

_SEP = r"[ .\-]?"
_PHONE_RE = re.compile(
    r"(?<![\d+])"
    r"(?:\+?998" + _SEP + r")?"
    r"\(?(\d{2})\)?" + _SEP + r"(\d{3})" + _SEP + r"(\d{2})" + _SEP + r"(\d{2})"
    r"(?!\d)"
)
_PHONE_LINK_RE = re.compile(r"t\.me/\+998(\d{9})\b")
# "(?<![\w@])": not part of an email (name@gmail.com); "xabar.@ainna_hr" is still a username.
_USERNAME_RE = re.compile(r"(?<![\w@])@([a-z][a-z0-9_]{3,31})\b")
_TME_USER_RE = re.compile(r"(?:https?://)?(?:t|telegram)\.me/([a-z][a-z0-9_]{3,31})(?![\w/+])")
_EMAIL_RE = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\"']+|\b(?:t\.me|telegra\.ph)/[^\s<>()\"']+")


def canon_username(name: str) -> str:
    """``"@Foo_Bar"`` / ``"t.me/Foo_Bar"`` -> ``"@foo_bar"``."""
    name = name.strip().lower()
    for prefix in ("https://", "http://", "t.me/", "telegram.me/", "@"):
        name = name.removeprefix(prefix)
    return "@" + name.split("/")[0].split("?")[0]


def find_phones(text: str) -> list[str]:
    """Uzbek phone numbers as ``+998XXXXXXXXX`` (order kept, no duplicates)."""
    out: list[str] = []
    for digits in _PHONE_LINK_RE.findall(text):
        out.append("+998" + digits)
    for m in _PHONE_RE.finditer(text):
        if m.group(1) in PHONE_CODES:
            out.append("+998" + "".join(m.groups()))
    return list(dict.fromkeys(out))


def find_usernames(text: str, own: Iterable[str] = ()) -> list[str]:
    """``@username`` and ``t.me/username`` mentions, without the source's own accounts."""
    own_set = {canon_username(u) for u in own}
    names = [*_USERNAME_RE.findall(text), *_TME_USER_RE.findall(text)]
    out = [canon_username(n) for n in names]
    return list(dict.fromkeys(u for u in out if u not in own_set))


def find_emails(text: str) -> list[str]:
    return list(dict.fromkeys(_EMAIL_RE.findall(text)))


def find_urls(text: str) -> list[str]:
    return list(dict.fromkeys(u.rstrip(".,;:!") for u in _URL_RE.findall(text)))


@dataclass(frozen=True, slots=True)
class Contacts:
    phones: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # possible apply links (forms, hh.uz, ...)

    def __bool__(self) -> bool:
        return bool(self.phones or self.usernames or self.emails or self.urls)

    @property
    def keys(self) -> frozenset[str]:
        """Phones + usernames, for "do two posts share a contact?"."""
        return frozenset(self.phones) | frozenset(self.usernames)

    @property
    def first(self) -> str | None:
        return (self.phones or self.usernames or [None])[0]


def _is_dropped(url: str, drop_patterns: Sequence[str]) -> bool:
    low = url.lower()
    if _PHONE_LINK_RE.search(low):  # t.me/+998... is a phone, not an invite link
        return False
    return any(p.lower() in low for p in drop_patterns)


def _own_link(url: str, own: set[str]) -> bool:
    m = _TME_USER_RE.search(url.lower())
    return bool(m) and canon_username(m.group(1)) in own


def find_contacts(
    text: str,
    extra: dict[str, Any] | None = None,
    *,
    own_usernames: Iterable[str] = (),
    drop_link_patterns: Sequence[str] = (),
    drop_whitespace_text_links: bool = True,
) -> Contacts:
    """All contacts in normalized ``text`` plus hidden links and URL buttons from ``extra``."""
    own = {canon_username(u) for u in own_usernames}
    phones = find_phones(text)
    usernames = find_usernames(text, own)
    emails = find_emails(text)
    urls: list[str] = []

    candidates = find_urls(text)
    for item in [*(extra or {}).get("links", []), *(extra or {}).get("buttons", [])]:
        url = item.get("url")
        if not url:
            continue
        if drop_whitespace_text_links and not str(item.get("text", "")).strip():
            continue
        candidates.append(url)

    for url in candidates:
        low = url.lower()
        if _is_dropped(low, drop_link_patterns) or _own_link(low, own):
            continue
        if m := _PHONE_LINK_RE.search(low):
            phones.append("+998" + m.group(1))
            continue
        user = _TME_USER_RE.search(low)
        # t.me/<user> is a contact; t.me/<bot>?start=... is an apply link.
        if user and not low[user.end() : user.end() + 1] == "?":
            usernames.append(canon_username(user.group(1)))
        else:
            urls.append(url)

    return Contacts(
        phones=list(dict.fromkeys(phones)),
        usernames=list(dict.fromkeys(usernames)),
        emails=emails,
        urls=list(dict.fromkeys(urls)),
    )
