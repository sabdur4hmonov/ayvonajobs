"""What kind of post is this?

``job | not_job | resume | closed | opportunity | suspicious | no_text``.

Order of rules (docs/SOURCE_ANALYSIS.md §3):
    no_text -> closed -> resume -> suspicious -> unpaid internship -> channel hashtags ->
    opportunity / not_job (only when job evidence is weak) -> job.

Only ``job`` goes to our channel. The rest stay in the DB with their kind as status.
A ``job`` without any contact gets ``has_contact=False``; the pipeline (Bosqich 7) turns it into
``no_contact`` instead of publishing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from ayvona.config import FiltersConfig, SourceRulesConfig
from ayvona.processing.boilerplate import BoilerplateRules, strip_boilerplate
from ayvona.processing.contacts import Contacts, find_contacts
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.language import Language, detect_language
from ayvona.processing.normalize import fold, normalize

# Job evidence thresholds (distinct job_markers found).
MIN_JOB_SCORE = 2
# With this much job evidence a stray "forum" / "chegirma" / "grant" word does not matter.
STRONG_JOB_SCORE = 4


class PostKind(StrEnum):
    JOB = "job"
    NOT_JOB = "not_job"
    RESUME = "resume"
    CLOSED = "closed"
    OPPORTUNITY = "opportunity"
    SUSPICIOUS = "suspicious"
    NO_TEXT = "no_text"


@dataclass(frozen=True, slots=True)
class PostInput:
    """What the classifier needs from a raw post (album parts already merged)."""

    text: str
    source: str | None = None
    extra: dict[str, Any] | None = None
    has_media: bool = False
    posted_at: datetime | None = None
    own_usernames: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class Classification:
    kind: PostKind
    reasons: tuple[str, ...] = ()
    job_score: int = 0
    has_contact: bool = False
    language: Language | None = None
    contacts: Contacts = field(default_factory=Contacts)
    # Normalized text without channel boilerplate — input for dedup (and later extract).
    clean_text: str = ""


def merge_album(parts: Sequence[PostInput]) -> PostInput:
    """Merge the parts of one album (same ``grouped_id``) into one post.

    Telegram puts the caption on one photo; the other parts have no text. Texts are joined in
    order, hidden links and buttons are combined.
    """
    if not parts:
        raise ValueError("empty album")
    texts = [p.text for p in parts if p.text.strip()]
    links: list[Any] = []
    buttons: list[Any] = []
    for p in parts:
        links.extend((p.extra or {}).get("links", []))
        buttons.extend((p.extra or {}).get("buttons", []))
    extra: dict[str, Any] = {}
    if links:
        extra["links"] = links
    if buttons:
        extra["buttons"] = buttons
    main = next((p for p in parts if p.text.strip()), parts[0])
    return replace(
        main,
        text="\n\n".join(texts),
        extra=extra or None,
        has_media=any(p.has_media for p in parts),
    )


# "Ariza muddati: 2026-09-19", "Deadline: 19.09.2026", "Oxirgi muddat: 19/09/2026"
_DEADLINE_RE = re.compile(
    r"(?:ariza muddati|ariza topshirish muddati|oxirgi muddat|qabul muddati|deadline"
    r"|srok podachi|priem zayavok do)\W{0,5}"
    r"(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[./](\d{1,2})[./](\d{4}))"
)
_HASHTAG_RE = re.compile(r"#[^\s#.,!?;:()]+")


def find_deadline(folded_text: str) -> date | None:
    m = _DEADLINE_RE.search(folded_text)
    if not m:
        return None
    y, mo, d = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m[6], m[5], m[4])
    try:
        return date(int(y), int(mo), int(d))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class _SourceRules:
    boilerplate: BoilerplateRules
    closed: KeywordSet
    job_tags: frozenset[str]
    non_job_tags: frozenset[str]
    require_job_tag: bool


class Classifier:
    """Build once from config (compiles keyword lists), call :meth:`classify` per post."""

    def __init__(self, filters: FiltersConfig, source_rules: SourceRulesConfig) -> None:
        self.source_rules = source_rules
        self.job = KeywordSet(filters.job_markers)
        self.not_job = KeywordSet(filters.not_job_markers)
        self.resume = KeywordSet(filters.resume_markers)
        self.closed = KeywordSet(filters.closed_markers)
        self.opportunity = KeywordSet(filters.opportunity_markers)
        self.opportunity_strong = KeywordSet(filters.opportunity_strong_markers)
        self.scam = KeywordSet(filters.scam)
        self.scam_exceptions = KeywordSet(filters.scam_exceptions)
        self._per_source: dict[str, _SourceRules] = {}

    def _source(self, source: str | None) -> _SourceRules:
        key = (source or "").lower()
        if key not in self._per_source:
            rule = self.source_rules.for_source(source)
            self._per_source[key] = _SourceRules(
                boilerplate=BoilerplateRules.build(rule, self.source_rules.defaults),
                closed=KeywordSet(rule.closed_markers),
                job_tags=frozenset(fold(t) for t in rule.job_hashtags),
                non_job_tags=frozenset(fold(t) for t in rule.non_job_hashtags),
                require_job_tag=rule.require_job_hashtag,
            )
        return self._per_source[key]

    def own_usernames(self, post: PostInput) -> list[str]:
        rule = self.source_rules.for_source(post.source)
        own = [*post.own_usernames, *rule.extra_own_usernames]
        if post.source:
            own.append(post.source)
        return own

    def classify(self, post: PostInput, now: datetime) -> Classification:
        if not post.text.strip():
            return Classification(PostKind.NO_TEXT, ("no_text",))

        src = self._source(post.source)
        norm = strip_boilerplate(normalize(post.text), src.boilerplate)
        folded = fold(norm)
        # Ad markers like "erid=" hide in link URLs, not in the text.
        urls = " ".join(
            str(i.get("url", "")).lower()
            for i in [*(post.extra or {}).get("links", []), *(post.extra or {}).get("buttons", [])]
        )
        haystack = f"{folded}\n{urls}"
        language = detect_language(post.text)
        defaults = self.source_rules.defaults
        contacts = find_contacts(
            norm,
            post.extra,
            own_usernames=self.own_usernames(post),
            drop_link_patterns=defaults.drop_link_patterns,
            drop_whitespace_text_links=defaults.drop_whitespace_text_links,
        )
        job_hits = self.job.find(folded)
        score = len(job_hits)

        def result(kind: PostKind, *reasons: str) -> Classification:
            return Classification(kind, reasons, score, bool(contacts), language, contacts, norm)

        # 1. closed: explicit marker or application deadline in the past
        if hits := self.closed.find(folded) | src.closed.find(folded):
            return result(PostKind.CLOSED, *sorted(f"closed:{h}" for h in hits))
        deadline = find_deadline(folded)
        if deadline and deadline < now.date():
            return result(PostKind.CLOSED, f"deadline:{deadline.isoformat()}")

        # 2. resume (job seeker's post)
        if hits := self.resume.find(folded):
            return result(PostKind.RESUME, *sorted(f"resume:{h}" for h in hits))

        # 3. scam markers
        if hits := self.scam.find(self.scam_exceptions.remove(folded)):
            return result(PostKind.SUSPICIOUS, *sorted(f"scam:{h}" for h in hits))

        # 4. unpaid internship etc. — decisive whatever the job score
        if hits := self.opportunity_strong.find(folded):
            return result(PostKind.OPPORTUNITY, *sorted(f"opportunity:{h}" for h in hits))

        # 5. the channel's own tags
        tags = set(_HASHTAG_RE.findall(folded))
        if hit := tags & src.non_job_tags:
            return result(PostKind.NOT_JOB, *sorted(f"tag:{t}" for t in hit))
        tagged_job = bool(tags & src.job_tags)
        if src.require_job_tag and not tagged_job:
            return result(PostKind.NOT_JOB, "no_job_hashtag")

        # 6. opportunity / advertisement, unless job evidence is strong.
        # Ads need at least as many ad markers as job markers: "xodimlarga 50% chegirma" in a real
        # job ad must not outweigh "talablar + maosh + ish vaqti".
        opp = self.opportunity.find(folded)
        ads = self.not_job.find(haystack)
        if not tagged_job and score < STRONG_JOB_SCORE:
            if opp:
                return result(PostKind.OPPORTUNITY, *sorted(f"opportunity:{h}" for h in opp))
            if ads and len(ads) >= score:
                return result(PostKind.NOT_JOB, *sorted(f"ad:{h}" for h in ads))

        # 7. job
        if tagged_job or score >= MIN_JOB_SCORE:
            reasons = [f"job:{h}" for h in sorted(job_hits)]
            if tagged_job:
                reasons.insert(0, "tag:job")
            if not contacts:
                reasons.append("no_contact")
            return result(PostKind.JOB, *reasons)
        return result(PostKind.NOT_JOB, f"weak_job_score:{score}")
