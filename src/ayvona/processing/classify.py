"""What kind of post is this?

``job | not_job | resume | closed | opportunity | suspicious | no_text``.

Order of rules (docs/SOURCE_ANALYSIS.md §3):
    no_text -> closed -> resume -> suspicious -> unpaid internship -> channel hashtags ->
    vacancy list with apply links -> opportunity / not_job (only when job evidence is weak) -> job.

A job SEEKER's post (``resume``) is recognised three ways: a marker word / hashtag
(``filters.resume_markers``: "#rezyume", "ish qidiryapman" ...), a header line that is only a
marker (``resume_line_markers``: "REZYUME"), or its shape (``resume_structure``: several profile
labels "Xodim: / Yosh: / Tajriba: / Portfolio:" and nothing an employer writes) — see
:meth:`Classifier._seeker_shape`. A bare word "rezyume" is NOT a marker: vacancies say "Rezyume
yuborish uchun".

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

from ayvona.config import CategoryConfig, FiltersConfig, SourceRulesConfig
from ayvona.processing.boilerplate import (
    BoilerplateRules,
    ad_contact_usernames,
    strip_boilerplate,
)
from ayvona.processing.contacts import Contacts, find_contacts, linked_positions
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.language import Language, detect_language
from ayvona.processing.normalize import fold, normalize, unify

# Job evidence thresholds (distinct job_markers found).
MIN_JOB_SCORE = 2
# With this much job evidence a stray "forum" / "chegirma" / "grant" word does not matter.
STRONG_JOB_SCORE = 4
# This many positions with their own apply links make a vacancy list (a job ad).
MIN_LINKED_POSITIONS = 2
_NAME_TOKEN_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|['’ʻ-](?=[^\W\d_]))*")
_MIN_NAME_WORDS, _MAX_NAME_WORDS = 2, 4
# NOT ":" - a line "Rezyume:" opens a contact line of a vacancy, it is not a header
_LINE_PUNCT = " \t.!•*-—–()[]«»\"'"


def _label_regex(labels: Sequence[str], *, colon: bool) -> re.Pattern[str] | None:
    """``^<label>:`` (``colon=False``: ``^<label>\\b``) on a folded line, bullets in front."""
    words = sorted({fold(w) for w in labels if fold(w)}, key=len, reverse=True)
    if not words:
        return None
    body = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words)
    tail = r"\s*[:：]" if colon else r"(?![\w'])"
    return re.compile(rf"^[\W_]*(?P<label>{body}){tail}")


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

    def __init__(
        self,
        filters: FiltersConfig,
        source_rules: SourceRulesConfig,
        categories: dict[str, CategoryConfig] | None = None,
    ) -> None:
        self.source_rules = source_rules
        self.job = KeywordSet(filters.job_markers)
        self.not_job = KeywordSet(filters.not_job_markers)
        self.not_job_strong = KeywordSet(filters.not_job_strong_markers)
        self.resume = KeywordSet(filters.resume_markers)
        self._resume_lines = {fold(m).strip(_LINE_PUNCT) for m in filters.resume_line_markers}
        self._resume_lines.discard("")
        rs = filters.resume_structure
        self._rs = rs
        self._seeker_re = _label_regex(rs.seeker_labels, colon=True)
        self._seeker_only = {fold(w) for w in rs.seeker_only_labels}
        self._seeker_only_re = _label_regex(rs.seeker_only_labels, colon=True)
        self._name_re = _label_regex(rs.name_labels, colon=True)
        self._employer_re = _label_regex(rs.employer_labels, colon=False)
        self._employer = KeywordSet(rs.employer_markers)
        # a name field holding a profession ("Xodim: Sotuv menejeri") is an employer's template
        self._profession_words = frozenset(
            fold(w)
            for cat in (categories or {}).values()
            for prof in cat.professions.values()
            for phrase in (prof.title, *prof.keywords)
            for w in phrase.split()
            if len(fold(w)) >= 4
        )
        self.closed = KeywordSet(filters.closed_markers)
        self.opportunity = KeywordSet(filters.opportunity_markers)
        self.opportunity_strong = KeywordSet(filters.opportunity_strong_markers)
        self.opportunity_strong_exceptions = KeywordSet(filters.opportunity_strong_exceptions)
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
        own = [
            *post.own_usernames,
            *rule.extra_own_usernames,
            *self.source_rules.defaults.extra_own_usernames,
        ]
        if post.source:
            own.append(post.source)
        own.extend(ad_contact_usernames(post.text, self._source(post.source).boilerplate))
        return own

    def _resume_header(self, folded: str) -> str | None:
        """A line that is only "REZYUME" / "Ish kerak!" ..."""
        for line in folded.split("\n"):
            if line.strip(_LINE_PUNCT) in self._resume_lines:
                return f"resume:line:{line.strip(_LINE_PUNCT)}"
        return None

    def _is_person_name(self, value: str) -> bool:
        """``Ali Valiyev`` / ``Dilnoza Karimova``: 2-4 capitalized words, no digits, no
        profession. One word is not enough ("Xodim: Sotuvchi" is an employer's template)."""
        value = re.sub(r"\([^)]*\)", " ", value)
        if re.search(r"\d|[@#/:]", value):
            return False
        words = _NAME_TOKEN_RE.findall(value)
        if not (_MIN_NAME_WORDS <= len(words) <= _MAX_NAME_WORDS):
            return False
        if not all(w[0].isupper() and len(w) >= 2 for w in words):
            return False
        return not any(self._is_profession_word(fold(w)) for w in words)

    def _is_profession_word(self, folded: str) -> bool:
        """``menejer`` / ``menejeri`` / ``montajchi`` — a whole word of a profession name (a name
        like "Qahramon" must not match the keyword "qa")."""
        return folded in self._profession_words or any(
            len(w) >= 5 and folded.startswith(w) for w in self._profession_words
        )

    def _seeker_shape(self, original: str, folded: str) -> str | None:
        """A resume by its shape: >= ``min_labels`` profile labels + seeker-only evidence (a
        "Portfolio:" label, or a "Xodim:" field holding a person's name) + nothing an employer
        writes (Talablar / Vazifalar / Kompaniya / Vakansiya / "ishga taklif" ...)."""
        if self._seeker_re is None:
            return None
        if self._employer.find(folded):
            return None
        labels: set[str] = set()
        evidence = ""
        for line in unify(original).split("\n"):
            fl = fold(line)
            if not fl:
                continue
            if self._employer_re and self._employer_re.match(fl):
                return None
            m = self._seeker_re.match(fl)
            if m is None and self._name_re:
                m = self._name_re.match(fl)
            if m is None:
                continue
            label = m.group("label")
            labels.add(label)
            if label in self._seeker_only:
                evidence = evidence or f"label:{label}"
            elif self._name_re and self._name_re.match(fl) and ":" in line:
                value = line.split(":", 1)[1]
                if self._is_person_name(value):
                    evidence = evidence or f"name:{label}"
        if len(labels) >= self._rs.min_labels and evidence:
            return f"resume:shape:{evidence}+{len(labels)}labels"
        return None

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
        if why := self._resume_header(folded) or self._seeker_shape(post.text, folded):
            return result(PostKind.RESUME, why)

        # 3. scam markers
        if hits := self.scam.find(self.scam_exceptions.remove(folded)):
            return result(PostKind.SUSPICIOUS, *sorted(f"scam:{h}" for h in hits))

        # 4. unpaid internship etc. — decisive whatever the job score
        # (unless paid later: "dastlabki 2 oy bepul amaliyot, 3-oydan haq to'lanadi")
        if (hits := self.opportunity_strong.find(folded)) and not (
            self.opportunity_strong_exceptions.find(folded)
        ):
            return result(PostKind.OPPORTUNITY, *sorted(f"opportunity:{h}" for h in hits))

        # 4b. a course / video-lesson topic list — decisive: lesson names ("oylik ish haqini
        # hisoblash", "ish grafigini to'ldirish") look like job evidence
        # (@Buxgalteriyaishorinlarii/5450)
        if hits := self.not_job_strong.find(folded):
            return result(PostKind.NOT_JOB, *sorted(f"ad_strong:{h}" for h in hits))

        # 5. the channel's own tags
        tags = set(_HASHTAG_RE.findall(folded))
        if hit := tags & src.non_job_tags:
            return result(PostKind.NOT_JOB, *sorted(f"tag:{t}" for t in hit))
        tagged_job = bool(tags & src.job_tags)
        if src.require_job_tag and not tagged_job:
            return result(PostKind.NOT_JOB, "no_job_hashtag")

        # 5b. a list of positions, each with its own apply link (@digitalitvacancy/735: Anorbank,
        # 11 vacancies, every one a hidden "(havola)" to hh.uz) — a job ad even with few markers.
        linked = linked_positions(post.text, post.extra)
        if len({url for _, url in linked}) >= MIN_LINKED_POSITIONS:
            reasons = [
                f"positions_with_links:{len(linked)}",
                *(f"job:{h}" for h in sorted(job_hits)),
            ]
            return result(PostKind.JOB, *reasons)

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
