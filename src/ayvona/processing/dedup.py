"""Near-duplicate detection (docs/SOURCE_ANALYSIS.md §8).

Channels repost their own ads and copy each other. Within a 14-day window a post is a duplicate
of an earlier one when:

1. ``hash``        — the cleaned text is identical (sha256), or
2. ``fingerprint`` — same title + same first contact, and the texts are at least similar
                     (:data:`FINGERPRINT_MIN_TEXT`), or
3. ``fuzzy``       — rapidfuzz text similarity >= 90 **and** a second signal: similar titles
                     (>= 85) or at least one shared phone/username. A shared contact does not
                     count when both titles are known and clearly different (< 50): channels like
                     @jobs_fba put the same admin contact under every ad.

The second signal in (3) matters: template channels (@huntmejob, @NextHireX, @kasbdoruz) post
short ads that are 90%+ alike but are different vacancies. When in doubt we say "not a duplicate":
a rare double post is better than a lost job (hard rule 2).

The first post stays; later ones are duplicates and remember which post they repeat.
Works on the matching form of the text (normalized + channel boilerplate removed).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Hashable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from rapidfuzz import fuzz, process

from ayvona.processing.contacts import canon_username

WINDOW = timedelta(days=14)
TEXT_THRESHOLD = 90.0
TITLE_THRESHOLD = 85.0
# Below this the titles name different positions -> never a duplicate via a shared contact.
TITLE_CONFLICT = 50.0
FINGERPRINT_MIN_TEXT = 70.0
# Very short texts ("Results speak in @x") are too weak for fuzzy matching.
MIN_FUZZY_LEN = 40

_TITLE_KEY_RE = re.compile(
    r"^(?:lavozim(?: nomi)?|position|job title|vakansiya|vacancy|вакансия|должность|kasb)"
    r"\s*[:\-—]\s*(.+)$"
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:t\.me|telegra\.ph)/\S+")
_HASHTAG_RE = re.compile(r"#[^\s#]+")
_USERNAME_RE = re.compile(r"@[a-z][a-z0-9_]{3,31}")
_NON_WORD_RE = re.compile(r"[^\w' ]+")
_SPACES_RE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _SPACES_RE.sub(" ", _NON_WORD_RE.sub(" ", text)).strip()


def guess_title(norm_text: str) -> str:
    """Rough job title from normalized text: a "Lavozim:/Position:" line, else the first line.

    Bosqich 5 (extract.py) gives the real title; dedup accepts it via ``make_entry(title=...)``.
    """
    lines = [ln.strip() for ln in norm_text.split("\n")]
    for line in lines:
        if m := _TITLE_KEY_RE.match(line):
            if title := _squash(_HASHTAG_RE.sub(lambda h: h.group(0)[1:], m.group(1))):
                return title[:120]
    for line in lines:
        rest = _squash(_HASHTAG_RE.sub(" ", line))
        if sum(ch.isalpha() for ch in rest) >= 3:
            return rest[:120]
    return ""


def dedup_text(norm_text: str, ignore_usernames: Iterable[str] = ()) -> str:
    """Text used for comparing: no links, hashtags, channel accounts, punctuation or line breaks."""
    ignore = {canon_username(u) for u in ignore_usernames}
    text = _URL_RE.sub(" ", norm_text)
    text = _HASHTAG_RE.sub(" ", text)
    text = _USERNAME_RE.sub(lambda m: " " if m.group(0) in ignore else m.group(0), text)
    return _squash(text)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DedupEntry:
    key: Hashable  # raw_post id in the pipeline; "channel/id" in reports
    posted_at: datetime
    text: str
    content_hash: str
    title: str
    contacts: frozenset[str]
    fingerprint: str | None


def make_entry(
    key: Hashable,
    posted_at: datetime,
    norm_text: str,
    contacts: Iterable[str] = (),
    *,
    title: str | None = None,
    ignore_usernames: Iterable[str] = (),
) -> DedupEntry:
    """Build a comparable entry. ``contacts`` = phones/usernames in order (first one counts)."""
    text = dedup_text(norm_text, ignore_usernames)
    title = _squash(title.lower()) if title else guess_title(norm_text)
    contact_list = [c.lower() for c in contacts]
    fingerprint = _sha(f"{title}|{contact_list[0]}")[:32] if title and contact_list else None
    return DedupEntry(
        key=key,
        posted_at=posted_at,
        text=text,
        content_hash=_sha(text),
        title=title,
        contacts=frozenset(contact_list),
        fingerprint=fingerprint,
    )


@dataclass(frozen=True, slots=True)
class DedupMatch:
    original: Hashable  # key of the first post of the group
    matched: Hashable  # key of the entry that actually matched (may itself be a duplicate)
    layer: str  # "hash" | "fingerprint" | "fuzzy"
    score: float
    title_score: float = 0.0
    shared_contacts: frozenset[str] = field(default_factory=frozenset)


class DedupIndex:
    """Posts seen so far. Feed posts oldest first with :meth:`check`."""

    def __init__(
        self,
        window: timedelta = WINDOW,
        text_threshold: float = TEXT_THRESHOLD,
        title_threshold: float = TITLE_THRESHOLD,
    ) -> None:
        self.window = window
        self.text_threshold = text_threshold
        self.title_threshold = title_threshold
        self._entries: list[DedupEntry] = []
        self._root: dict[Hashable, Hashable] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def _candidates(self, entry: DedupEntry) -> list[DedupEntry]:
        lo = entry.posted_at - self.window
        return [e for e in self._entries if lo <= e.posted_at <= entry.posted_at]

    def _match(self, entry: DedupEntry, cand: DedupEntry, layer: str, score: float) -> DedupMatch:
        return DedupMatch(
            original=self._root.get(cand.key, cand.key),
            matched=cand.key,
            layer=layer,
            score=round(score, 1),
            title_score=round(fuzz.token_sort_ratio(entry.title, cand.title), 1),
            shared_contacts=entry.contacts & cand.contacts,
        )

    def find(self, entry: DedupEntry) -> DedupMatch | None:
        """The earlier post ``entry`` repeats, or ``None``."""
        cands = self._candidates(entry)
        if not cands or not entry.text:
            return None

        for c in cands:
            if c.content_hash == entry.content_hash:
                return self._match(entry, c, "hash", 100.0)

        if entry.fingerprint:
            for c in cands:
                if c.fingerprint == entry.fingerprint:
                    score = fuzz.ratio(entry.text, c.text)
                    if score >= FINGERPRINT_MIN_TEXT:
                        return self._match(entry, c, "fingerprint", score)

        if len(entry.text) < MIN_FUZZY_LEN:
            return None
        hits = process.extract(
            entry.text,
            [c.text for c in cands],
            scorer=fuzz.ratio,
            score_cutoff=self.text_threshold,
            limit=None,
        )
        for _, score, idx in sorted(hits, key=lambda h: -h[1]):
            c = cands[idx]
            both_titles = bool(entry.title and c.title)
            title_score = fuzz.token_sort_ratio(entry.title, c.title) if both_titles else 0.0
            if both_titles and title_score >= self.title_threshold:
                return self._match(entry, c, "fuzzy", score)
            conflict = both_titles and title_score < TITLE_CONFLICT
            if entry.contacts & c.contacts and not conflict:
                return self._match(entry, c, "fuzzy", score)
        return None

    def add(self, entry: DedupEntry, duplicate_of: Hashable | None = None) -> None:
        self._entries.append(entry)
        if duplicate_of is not None:
            self._root[entry.key] = duplicate_of

    def check(self, entry: DedupEntry) -> DedupMatch | None:
        """:meth:`find`, then remember the entry (duplicates too, so chains of reposts connect)."""
        match = self.find(entry)
        self.add(entry, match.original if match else None)
        return match
