"""Contact detection: phones, @usernames, emails, apply links (docs/SOURCE_ANALYSIS.md §4-5).

Contacts hide in 6 places: phone / @username / t.me link in the text, hidden links under words
("Aloqa uchun 👈", "Get the job.", "havola"), URL buttons ("Apply here"), ``t.me/+998...`` (a PHONE,
not an invite link), emails, and apply pages (forms, hh.uz, LinkedIn, telegra.ph).

Used by the classifier ("does the post have any contact?"), dedup (fingerprint, shared contacts)
and the extractor. Finders work on normalized *or* original text (matching is case-insensitive).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Operator codes + landline city codes (SOURCE_ANALYSIS §5).
MOBILE_CODES = frozenset(
    {"20", "33", "50", "55", "77", "78", "87", "88", "90", "91", "93", "94", "95", "97", "98", "99"}
)
CITY_CODES = frozenset(str(c) for c in range(61, 80))
PHONE_CODES = MOBILE_CODES | CITY_CODES

# 2-digit code + exactly 7 more digits, each optionally after one separator:
# "90 123 45 67", "(97) 137-16-94", "97.798 67 22", "953538444", "+998 333378888".
_PHONE_RE = re.compile(
    r"(?<![\w+])(?P<prefix>\+\s?998|998)?[ .\-]?"
    r"\(?(?P<code>\d{2})\)?(?P<rest>(?:[ .\-]?\d){7})(?!\d)"
)
_PHONE_LINK_RE = re.compile(r"t\.me/\+998(\d{9})\b", re.IGNORECASE)
# A number of an unknown code is a phone only next to one of these words.
_PHONE_CONTEXT_RE = re.compile(
    r"\b(?:tel|telefon|aloqa|bog'lan|murojaat|qo'ng'iroq|call|phone|contact|тел|телефон|звонит"
    r"|связ|алоқа|боғлан|мурожаат)",
    re.IGNORECASE,
)
# "(?<![\w@])": not part of an email (name@gmail.com); "xabar.@ainna_hr" is still a username.
_USERNAME_RE = re.compile(r"(?<![\w@])@([a-z][a-z0-9_]{3,31})\b", re.IGNORECASE)
_TME_USER_RE = re.compile(
    r"(?:https?://)?(?:t|telegram)\.me/([a-z][a-z0-9_]{3,31})(?![\w/+])", re.IGNORECASE
)
_EMAIL_RE = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>()\"']+|\b(?:t\.me|telegra\.ph|forms\.gle|lnkd\.in)/[^\s<>()\"']+",
    re.IGNORECASE,
)

# Apply links: pages where one applies. Score 3 = known apply site, 2 = hidden link / button whose
# text says "apply", 1 = a plain URL in the post text. Score 0 = not an apply link (footer "Jobs",
# "Platform", a t.me post link, ...) — not a contact.
_APPLY_URL_RE = re.compile(
    r"docs\.google\.com/forms|forms\.gle|forms\.office\.com|typeform\.com|hh\.uz/vacancy"
    r"|hh\.ru/vacancy|headhunter|lnkd\.in|linkedin\.com/(?:comm/)?jobs"
    r"|linkedin\.com/(?:posts|feed/update)"  # the vacancy is a LinkedIn post (@unilance)
    r"|telegra\.ph/|/apply|/vacanc|/career|/jobs/\w|t\.me/[a-z0-9_]+bot\?start=",
    re.IGNORECASE,
)
_APPLY_TEXT_RE = re.compile(
    r"\b(?:apply|ariza|havola|link\b|batafsil|qiziqish|so['’‘]?rovnoma|anketa|get the job|get a job"
    r"|cv\b|rezyume|resume|murojaat|aloqa|bog['’‘]?lan|описание|отклик|подробн|заявк|анкета)",
    re.IGNORECASE,
)
# Social pages are never apply links (the channel's own Instagram, ...).
_SOCIAL_RE = re.compile(
    r"instagram\.com|facebook\.com|fb\.com|youtube\.com|youtu\.be|tiktok\.com|twitter\.com"
    r"|//x\.com|linkedin\.com/(?:company|in)/|t\.me/addlist|t\.me/\+(?!998)",
    re.IGNORECASE,
)
_TME_POST_RE = re.compile(r"(?:t|telegram)\.me/(?:c/)?[\w]+/\d+", re.IGNORECASE)
# Tracking parameters removed from apply links.
_TRACKING_PREFIXES = ("utm_", "hhtm")


def canon_username(name: str) -> str:
    """``"@Foo_Bar"`` / ``"t.me/Foo_Bar"`` -> ``"@foo_bar"``."""
    name = name.strip().lower()
    for prefix in ("https://", "http://", "t.me/", "telegram.me/", "@"):
        name = name.removeprefix(prefix)
    return "@" + name.split("/")[0].split("?")[0]


def _without_urls(text: str) -> str:
    """Blank out URLs and emails (digits inside them are not phones), keep t.me/+998 links."""
    text = _EMAIL_RE.sub(" ", text)
    return _URL_RE.sub(lambda m: m.group(0) if _PHONE_LINK_RE.search(m.group(0)) else " ", text)


def find_phones(text: str) -> list[str]:
    """Uzbek phone numbers as ``+998XXXXXXXXX`` (order kept, no duplicates).

    A number is a phone when it has a +998 prefix or a known operator/city code; with an unknown
    code only when a word like "tel/aloqa/bog'lanish" is on the same line (else it may be a year,
    a price, ...). Numbers ending in 000000 are amounts, not phones.
    """
    out: list[str] = []
    for line in text.split("\n"):
        for digits in _PHONE_LINK_RE.findall(line):
            out.append("+998" + digits)
        clean = _without_urls(line)
        for m in _PHONE_RE.finditer(clean):
            code = m.group("code")
            rest = re.sub(r"\D", "", m.group("rest"))
            if rest.endswith("000000"):
                continue
            if m.group("prefix") or code in PHONE_CODES or _PHONE_CONTEXT_RE.search(line):
                out.append(f"+998{code}{rest}")
    return list(dict.fromkeys(out))


def find_usernames(text: str, own: Iterable[str] = (), *, keep_case: bool = False) -> list[str]:
    """``@username`` and ``t.me/username`` mentions, without the source's own accounts."""
    own_set = {canon_username(u) for u in own}
    found = [
        (m.start(), m.group(1)) for rx in (_USERNAME_RE, _TME_USER_RE) for m in rx.finditer(text)
    ]
    out: dict[str, str] = {}
    for _, name in sorted(found):
        canon = canon_username(name)
        if canon not in own_set and canon not in out:
            out[canon] = "@" + name if keep_case else canon
    return list(out.values())


def find_emails(text: str) -> list[str]:
    return list(dict.fromkeys(e.lower() for e in _EMAIL_RE.findall(text)))


def find_urls(text: str) -> list[str]:
    return list(dict.fromkeys(u.rstrip(".,;:!") for u in _URL_RE.findall(text)))


def clean_url(url: str, strip_params: Iterable[str] = ()) -> str:
    """Remove tracking parameters (utm_*, hhtm*, and ``strip_params``) from a URL."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    drop = {p.lower() for p in strip_params}
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in drop and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


def apply_score(url: str, link_text: str | None) -> int:
    """How much ``url`` looks like an apply link (see module constants). ``link_text``: the
    hidden link / button text, ``None`` for a URL written in the post text."""
    if _TME_POST_RE.search(url) or _SOCIAL_RE.search(url):
        return 0
    if _APPLY_URL_RE.search(url):
        return 3
    if link_text is not None:
        return 2 if _APPLY_TEXT_RE.search(link_text) else 0
    return 1


@dataclass(frozen=True, slots=True)
class Contacts:
    phones: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # apply links, best first

    def __bool__(self) -> bool:
        return bool(self.phones or self.usernames or self.emails or self.urls)

    @property
    def keys(self) -> frozenset[str]:
        """Phones + usernames, for "do two posts share a contact?"."""
        return frozenset(self.phones) | frozenset(u.lower() for u in self.usernames)

    @property
    def first(self) -> str | None:
        return (self.phones or [u.lower() for u in self.usernames] or [None])[0]

    @property
    def apply_url(self) -> str | None:
        return self.urls[0] if self.urls else None


def _is_dropped(url: str, drop_patterns: Sequence[str]) -> bool:
    low = url.lower()
    if _PHONE_LINK_RE.search(low):  # t.me/+998... is a phone, not an invite link
        return False
    return any(p.lower() in low for p in drop_patterns)


def _own_link(url: str, own: set[str]) -> bool:
    m = _TME_USER_RE.search(url)
    return bool(m) and canon_username(m.group(1)) in own


_WORD_RE = re.compile(r"[^\W\d_]{2,}")


def linked_positions(text: str, extra: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Lines of a vacancy list where each line carries its own apply link.

    ``"🔗 Tarmoq administratori (havola)"`` with a hidden link under "(havola)" to hh.uz, or
    ``"Java developer — https://hh.uz/vacancy/1"``. Returns ``(line_without_link_text, url)``;
    a line qualifies when the link is an apply link (score >= 2) and at least two words remain.
    """
    links = [
        (str(i.get("text", "")).strip(), str(i.get("url", "")))
        for i in [*(extra or {}).get("links", []), *(extra or {}).get("buttons", [])]
        if i.get("url") and str(i.get("text", "")).strip()
    ]
    out: list[tuple[str, str]] = []
    next_link = 0  # hidden links come in text order; each one belongs to one line
    for line in text.split("\n"):
        hit: tuple[str, str] | None = None
        for k in range(next_link, len(links)):
            link_text, url = links[k]
            if link_text in line:
                next_link = k + 1
                if apply_score(url, link_text) >= 2:
                    hit = (line.replace(link_text, " "), url)
                break
        if hit is None:
            for url in find_urls(line):
                if apply_score(url, None) >= 3:
                    hit = (line.replace(url, " "), url)
                    break
        if hit and len(_WORD_RE.findall(hit[0])) >= 2:
            out.append(hit)
    return out


def find_contacts(
    text: str,
    extra: dict[str, Any] | None = None,
    *,
    own_usernames: Iterable[str] = (),
    drop_link_patterns: Sequence[str] = (),
    drop_whitespace_text_links: bool = True,
    strip_url_params: Iterable[str] = (),
    keep_case: bool = False,
) -> Contacts:
    """All contacts in ``text`` plus hidden links and URL buttons from ``extra``.

    ``keep_case``: usernames as written (``@HR_Konida``) instead of canonical lower case.
    """
    own = {canon_username(u) for u in own_usernames}
    phones = find_phones(text)
    usernames = find_usernames(text, own, keep_case=keep_case)
    emails = find_emails(text)
    scored: dict[str, int] = {}

    candidates: list[tuple[str, str | None]] = [(u, None) for u in find_urls(text)]
    for item in [*(extra or {}).get("links", []), *(extra or {}).get("buttons", [])]:
        url = item.get("url")
        if not url:
            continue
        link_text = str(item.get("text", ""))
        if drop_whitespace_text_links and not link_text.strip():
            continue
        candidates.append((url, link_text))

    for url, link_text in candidates:
        if _is_dropped(url, drop_link_patterns) or _own_link(url, own):
            continue
        if m := _PHONE_LINK_RE.search(url):
            phones.append("+998" + m.group(1))
            continue
        user = _TME_USER_RE.search(url)
        # t.me/<user> (also t.me/<user>?text=... — a DM with a prefilled message) is a contact;
        # t.me/<bot>?start=... is an apply link.
        if user and "start=" not in url[user.end() :]:
            name = "@" + user.group(1)
            if canon_username(name) not in {canon_username(u) for u in usernames}:
                usernames.append(name if keep_case else canon_username(name))
            continue
        score = apply_score(url, link_text)
        if score:
            url = clean_url(url, strip_url_params)
            scored[url] = max(score, scored.get(url, 0))

    urls = sorted(scored, key=lambda u: -scored[u])  # stable: equal scores keep post order
    return Contacts(
        phones=list(dict.fromkeys(phones)),
        usernames=usernames,
        emails=emails,
        urls=urls,
    )
