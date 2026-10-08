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
                     Between 85 and 90 (the same ad re-typed in another channel's template)
                     BOTH signals are required: similar titles AND a shared contact.

4. ``contact``     — the same vacancy re-typed in another channel's template (2026-10-07: "Sotuv
                     menejer" and '"HUNTER" sotuv menejeri', 45 minutes apart): a shared phone /
                     @username AND the same position (the titles without generic role words —
                     "specialist", "o'qituvchi", "menejer" ... — and quoted names, token set >=
                     ``contact_title_threshold``: "Safety Specialist" is not "Update Specialist")
                     AND a similar text (token set >= ``contact_text_threshold``). Spelling
                     variants of names count as equal (Begimqulov = Begimkulov: q/k, x/h,
                     apostrophes, doubled letters). Two different known companies are never one
                     vacancy.

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
# 85..90: only with similar titles AND a shared contact (both).
STRICT_TEXT_THRESHOLD = 85.0
TITLE_THRESHOLD = 85.0
# Below this the titles name different positions -> never a duplicate via a shared contact.
TITLE_CONFLICT = 50.0
FINGERPRINT_MIN_TEXT = 70.0
# Very short texts ("Results speak in @x") are too weak for fuzzy matching.
MIN_FUZZY_LEN = 40
CONTACT_TEXT_THRESHOLD = 75.0
CONTACT_TITLE_THRESHOLD = 85.0
# role words every second title has: compared without them, "Fizika ustozi" != "Biologiya ustozi"
_ROLE_WORDS = (
    "mutaxassis", "specialist", "spesialist", "menejer", "manager", "menedjer", "o'qituvchi",
    "ustoz", "teacher", "ishchi", "xodim", "operator", "lavozim", "vakansiya", "kerak",
)  # fmt: skip
_TITLE_FILLER = frozenset(("va", "and", "ham", "uchun", "for", "the", "of", "bo'yicha", "boyicha"))
_QUOTED_RE = re.compile(r"[«\"“„][^»\"”“]{1,40}[»\"”]")
COMPANY_CONFLICT = 80.0  # two companies less alike than this are different employers
_VARIANT_RES = (
    (re.compile(r"[ʻʼ’'`]"), ""),
    (re.compile(r"x"), "h"),
    (re.compile(r"q"), "k"),
    (re.compile(r"(\w)\1+"), r"\1"),
)


def variants(text: str) -> str:
    """Spelling variants folded together: "Ilxom Begimqulov" == "Ilhom Begimkulov"."""
    out = text.lower()
    for rx, repl in _VARIANT_RES:
        out = rx.sub(repl, out)
    return out


_ROLE_STEMS = tuple(variants(w) for w in _ROLE_WORDS)


def title_core(title: str) -> str:
    """The distinctive words of a title: no quoted names, role words or fillers
    ('"HUNTER" sotuv menejeri' -> "sotuv"); ``""`` if only role words are left ("O'qituvchi" —
    then two titles cannot tell two positions apart)."""
    words = [
        w
        for w in variants(_QUOTED_RE.sub(" ", title)).replace("/", " ").split()
        if w not in _TITLE_FILLER and not w.startswith(_ROLE_STEMS)
    ]
    return " ".join(words)


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
        m = _TITLE_KEY_RE.match(line)
        if m and (title := _squash(_HASHTAG_RE.sub(lambda h: h.group(0)[1:], m.group(1)))):
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
    company: str = ""  # known only for entries of this process run (not stored in raw_posts)


def make_entry(
    key: Hashable,
    posted_at: datetime,
    norm_text: str,
    contacts: Iterable[str] = (),
    *,
    title: str | None = None,
    ignore_usernames: Iterable[str] = (),
    company: str | None = None,
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
        company=_squash(company.lower()) if company else "",
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
        strict_text_threshold: float = STRICT_TEXT_THRESHOLD,
        contact_text_threshold: float = CONTACT_TEXT_THRESHOLD,
        contact_title_threshold: float = CONTACT_TITLE_THRESHOLD,
    ) -> None:
        self.window = window
        self.contact_text_threshold = contact_text_threshold
        self.contact_title_threshold = contact_title_threshold
        self.text_threshold = text_threshold
        self.strict_text_threshold = strict_text_threshold
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
            score_cutoff=min(self.strict_text_threshold, self.text_threshold),
            limit=None,
        )
        for _, score, idx in sorted(hits, key=lambda h: -h[1]):
            c = cands[idx]
            both_titles = bool(entry.title and c.title)
            title_score = fuzz.token_sort_ratio(entry.title, c.title) if both_titles else 0.0
            title_ok = both_titles and title_score >= self.title_threshold
            shared = bool(entry.contacts & c.contacts)
            if score < self.text_threshold:
                if title_ok and shared:
                    return self._match(entry, c, "fuzzy", score)
                continue
            if title_ok or (shared and not (both_titles and title_score < TITLE_CONFLICT)):
                return self._match(entry, c, "fuzzy", score)
        return self._contact_match(entry, cands)

    def _contact_match(self, entry: DedupEntry, cands: list[DedupEntry]) -> DedupMatch | None:
        """Layer 4: the same contact + a similar title + a similar text (any channel)."""
        if not entry.contacts or not entry.title:
            return None
        title = title_core(entry.title)
        if not title:
            return None
        text = variants(entry.text)
        company = variants(entry.company)
        best: tuple[float, DedupEntry] | None = None
        for c in cands:
            if not (entry.contacts & c.contacts) or not (c_title := title_core(c.title)):
                continue
            if (
                company
                and c.company
                and fuzz.ratio(company, variants(c.company)) < COMPANY_CONFLICT
            ):
                continue  # two different employers behind one recruiter
            if fuzz.token_set_ratio(title, c_title) < self.contact_title_threshold:
                continue
            score = fuzz.token_set_ratio(text, variants(c.text))
            if score >= self.contact_text_threshold and (best is None or score > best[0]):
                best = (score, c)
        return self._match(entry, best[1], "contact", best[0]) if best else None

    def add(self, entry: DedupEntry, duplicate_of: Hashable | None = None) -> None:
        self._entries.append(entry)
        if duplicate_of is not None:
            self._root[entry.key] = duplicate_of

    def check(self, entry: DedupEntry) -> DedupMatch | None:
        """:meth:`find`, then remember the entry (duplicates too, so chains of reposts connect)."""
        match = self.find(entry)
        self.add(entry, match.original if match else None)
        return match
