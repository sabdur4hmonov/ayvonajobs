"""Keyword lists matched on :func:`~ayvona.processing.normalize.fold` text.

Matching rule: a keyword must start at a word boundary ("grant" does not match "emigrant"),
but may be followed by Uzbek/Russian suffixes ("vakansiya" matches "vakansiyalar",
"forum" matches "forumga"). The left boundary is only checked when the keyword itself starts
with a letter or digit, so "#reklama" and "erid=" work too.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ayvona.processing.normalize import fold

_STARTS_WITH_WORD = re.compile(r"[^\W_]")
_LEFT_BOUNDARY = r"(?<![^\W_])(?<!')"  # not preceded by a letter/digit or an apostrophe (o'qish)


class KeywordSet:
    """A list of keywords. ``find(folded_text)`` returns the keywords (as in config) that occur."""

    def __init__(self, keywords: Iterable[str]) -> None:
        self._patterns: list[tuple[str, re.Pattern[str]]] = []
        seen: set[str] = set()
        for kw in keywords:
            folded = fold(kw)
            if not folded or folded in seen:
                continue
            seen.add(folded)
            left = _LEFT_BOUNDARY if _STARTS_WITH_WORD.match(folded) else ""
            self._patterns.append((kw, re.compile(left + re.escape(folded))))

    def __bool__(self) -> bool:
        return bool(self._patterns)

    def __len__(self) -> int:
        return len(self._patterns)

    def find(self, folded_text: str) -> set[str]:
        return {kw for kw, pat in self._patterns if pat.search(folded_text)}
