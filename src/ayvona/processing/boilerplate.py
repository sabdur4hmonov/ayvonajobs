"""Remove channel boilerplate (signatures, ad footers) from *normalized* text.

Works on the matching form only — used before classification and dedup so that a channel's
footer ("E'lon joylash uchun: @...", "Agar vakansiya sizga mos bo'lmasa...") neither adds job
points nor makes two different posts look alike. Publishing-side cleaning of the original text
(Bosqich 6, clean.py) follows the same rules from ``config/source_rules.yaml``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ayvona.config import SourceRule, SourceRuleDefaults
from ayvona.processing.normalize import normalize

# Safety (source_rules.yaml header): if cutting would leave less than this share of the text,
# don't cut — the rule probably matched something inside the real post.
MIN_KEEP_RATIO = 0.4

_HASHTAG_LINE_RE = re.compile(r"^(?:#[^\s#]+\s*)+$")
_SERIAL_RE = re.compile(r"^n\d{3,6}$")  # @kasbdoruz: "N3311"


def _norm_all(items: Iterable[str]) -> list[str]:
    return [n for n in (normalize(i) for i in items) if n]


@dataclass(frozen=True)
class BoilerplateRules:
    """``source_rules.yaml`` rules of one channel, pre-normalized."""

    cut_from: tuple[str, ...]
    strip_lines: tuple[str, ...]
    exact_lines: frozenset[str]
    header_junk_words: frozenset[str]
    drop_trailing_hashtags: bool

    @classmethod
    def build(cls, rule: SourceRule, defaults: SourceRuleDefaults) -> BoilerplateRules:
        return cls(
            cut_from=tuple(_norm_all(rule.cut_from)),
            strip_lines=tuple(_norm_all([*defaults.strip_lines, *rule.strip_lines])),
            exact_lines=frozenset(_norm_all(rule.exact_lines)),
            header_junk_words=frozenset(_norm_all(rule.header_junk_words)),
            drop_trailing_hashtags=rule.drop_trailing_hashtags,
        )


def strip_boilerplate(norm_text: str, rules: BoilerplateRules) -> str:
    """Apply cut_from / strip_lines / exact_lines / header junk to normalized text."""
    lines = norm_text.split("\n")

    # Leading junk: empty lines (emoji-only headers become empty) and "new"/"without" words.
    while lines and (not lines[0] or lines[0] in rules.header_junk_words):
        lines.pop(0)

    total = sum(len(x) for x in lines) or 1
    for i, line in enumerate(lines):
        if any(c in line for c in rules.cut_from):
            if sum(len(x) for x in lines[:i]) / total >= MIN_KEEP_RATIO:
                lines = lines[:i]
            break

    lines = [
        ln
        for ln in lines
        if ln not in rules.exact_lines
        and not _SERIAL_RE.match(ln)
        and not any(s in ln for s in rules.strip_lines)
    ]

    if rules.drop_trailing_hashtags:
        while lines and (not lines[-1] or _HASHTAG_LINE_RE.match(lines[-1])):
            lines.pop()

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
