"""Category, profession and feature tags of a job post (config/categories.yaml).

Scoring (all on folded text, keyword at a word start, suffixes allowed):
* a profession gets 3 points per distinct keyword found in the title and 1 point per distinct
  keyword found anywhere in the post;
* a category = its best profession + its own category-level keywords (same 3/1 points);
* overlapping matches: the longest keyword wins ("marketing manager" hides "manager");
* best category wins; a tie goes to the one mentioned first (in a multi-vacancy post: the first
  position). Profession = best profession of that category, if any. Nothing found -> ``boshqa``.

Feature tags (masofaviy, tajribasiz, ...) respect negations: "yotoqxona yo'q" gives no tag.

Before matching, ``ignore_words`` (categories.yaml) are blanked out — words that look like a keyword
but are not ("temir banka" is a jar, not a bank; "texnologiyalar" is not a "texnolog") — and a
name in quotes in the title is not a position ('"HUNTER" sotuv menejeri' is a sales manager).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ayvona.config import FALLBACK_CATEGORY, CategoryConfig, FeatureTagConfig
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold

TITLE_WEIGHT = 3
_LEFT_BOUNDARY = r"(?<![^\W_])(?<!')"
_RIGHT_BOUNDARY = r"(?![^\W_])"
SHORT_KEYWORD = 2  # keywords this short must match a whole word ("qa", "hr", "it")
# How far after a feature keyword a negation word may stand ("yotoqxona mavjud emas").
_NEGATION_WINDOW = 25
_QUOTED_RE = re.compile(r"[«\"“„][^»\"”“]{1,40}[»\"”]")


@dataclass(frozen=True, slots=True)
class _Kw:
    pattern: re.Pattern[str]
    length: int
    category: str
    profession: str | None  # None = category-level keyword
    word: str


@dataclass(frozen=True, slots=True)
class Categorization:
    category: str = FALLBACK_CATEGORY
    profession: str | None = None
    feature_tags: tuple[str, ...] = ()
    scores: dict[str, int] = field(default_factory=dict)  # category -> score, for debugging


class Categorizer:
    """Build once from config, call :meth:`categorize` per post."""

    def __init__(
        self,
        categories: dict[str, CategoryConfig],
        feature_tags: dict[str, FeatureTagConfig] | None = None,
        negation_words: list[str] | None = None,
        ignore_words: list[str] | None = None,
    ) -> None:
        self.categories = categories
        self._ignore = KeywordSet(ignore_words or [])
        kws: list[_Kw] = []

        def add(words: list[str], cat: str, prof: str | None) -> None:
            for w in words:
                f = fold(w)
                if f:
                    # Short keywords are whole words: "qa" is not "qarashga", "it" not "itoat".
                    right = _RIGHT_BOUNDARY if len(f) <= SHORT_KEYWORD else ""
                    pattern = re.compile(_LEFT_BOUNDARY + re.escape(f) + right)
                    kws.append(_Kw(pattern, len(f), cat, prof, f))

        for cat_key, cat in categories.items():
            add(cat.keywords, cat_key, None)
            for prof_key, prof in cat.professions.items():
                add(prof.keywords, cat_key, prof_key)
        kws.sort(key=lambda k: -k.length)
        self._kws = kws
        self._features = {
            name: (KeywordSet(ft.keywords), KeywordSet(ft.negations))
            for name, ft in (feature_tags or {}).items()
        }
        words = "|".join(re.escape(fold(w)) for w in (negation_words or []) if fold(w))
        self._negation_after = re.compile(rf"(?:{words})") if words else None

    def _matches(self, text: str) -> list[tuple[int, _Kw]]:
        """Non-overlapping keyword matches, the longest keyword first."""
        taken = [False] * len(text)
        out: list[tuple[int, _Kw]] = []
        for kw in self._kws:
            for m in kw.pattern.finditer(text):
                if any(taken[m.start() : m.end()]):
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                out.append((m.start(), kw))
        return out

    def _prepare(self, text: str) -> str:
        folded = fold(text)
        return self._ignore.remove(folded) if self._ignore else folded

    def has_profession(self, text: str) -> bool:
        """Does ``text`` name a profession ("Call operator", "TAJRIBALI OSHPAZ")?"""
        return any(kw.profession for _, kw in self._matches(self._prepare(text)))

    def categorize(self, title: str | None, text: str) -> Categorization:
        """``title`` (or the list of positions) and the whole post ``text`` — raw or folded."""
        title_f = self._prepare(_QUOTED_RE.sub(" ", title or ""))
        text_f = self._prepare(text)
        prof_score: dict[tuple[str, str], int] = {}
        cat_own: dict[str, int] = {}
        first_seen: dict[str, float] = {}
        prof_first: dict[str, float] = {}

        for weight, source, offset in ((TITLE_WEIGHT, title_f, -1_000_000), (1, text_f, 0)):
            seen: set[tuple[str, str | None, str]] = set()
            for pos, kw in self._matches(source):
                key = (kw.category, kw.profession, kw.word)
                if key in seen:
                    continue
                seen.add(key)
                first_seen[kw.category] = min(first_seen.get(kw.category, 1e18), offset + pos)
                if kw.profession is None:
                    cat_own[kw.category] = cat_own.get(kw.category, 0) + weight
                else:
                    pk = (kw.category, kw.profession)
                    prof_score[pk] = prof_score.get(pk, 0) + weight
                    prof_first[kw.profession] = min(
                        prof_first.get(kw.profession, 1e18), offset + pos
                    )

        scores: dict[str, int] = {}
        for cat in first_seen:
            best = max((s for (c, _), s in prof_score.items() if c == cat), default=0)
            scores[cat] = best + cat_own.get(cat, 0)
        features = self.feature_tags(text_f)
        if not scores:
            return Categorization(FALLBACK_CATEGORY, None, features, {})

        category = min(scores, key=lambda c: (-scores[c], first_seen[c]))
        profs = {p: s for (c, p), s in prof_score.items() if c == category}
        profession = min(profs, key=lambda p: (-profs[p], prof_first[p])) if profs else None
        return Categorization(category, profession, features, scores)

    def feature_tags(self, folded: str) -> tuple[str, ...]:
        """Feature tags present and not negated, in config order."""
        out: list[str] = []
        for name, (keywords, negations) in self._features.items():
            text = negations.remove(folded)
            for kw in keywords.find(text):
                for m in re.finditer(_LEFT_BOUNDARY + re.escape(fold(kw)), text):
                    after = text[m.end() : m.end() + _NEGATION_WINDOW].split("\n")[0]
                    if not (self._negation_after and self._negation_after.search(after)):
                        out.append(name)
                        break
                if name in out:
                    break
        return tuple(out)
