"""Remove channel boilerplate (signatures, ad footers) from *normalized* text.

Works on the matching form only — used before classification and dedup so that a channel's
footer ("E'lon joylash uchun: @...", "Agar vakansiya sizga mos bo'lmasa...") neither adds job
points nor makes two different posts look alike. Publishing-side cleaning of the original text
(Bosqich 6, clean.py) follows the same rules from ``config/source_rules.yaml``.

Advertising-contact lines ("Kanalda e'lon va rezyume joylashtirish uchun: @admin"): a line where a
phrase of ``defaults.ads_contact_phrases`` is directly followed by an account / link (or ends with
the phrase and the account is alone on the next line) belongs to the CHANNEL, not to the post: the
line is removed and :func:`ad_contact_usernames` lists the accounts so no part of the pipeline
takes them for the poster's contact.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ayvona.config import SourceRule, SourceRuleDefaults
from ayvona.processing.contacts import find_usernames
from ayvona.processing.normalize import fold, normalize, normalize_lines

# Safety (source_rules.yaml header): if cutting would leave less than this share of the text,
# don't cut — the rule probably matched something inside the real post.
MIN_KEEP_RATIO = 0.4

_HASHTAG_LINE_RE = re.compile(r"^(?:#[^\s#]+\s*)+$")
_SERIAL_RE = re.compile(r"^n\d{3,6}$")  # @kasbdoruz: "N3311"
# an account / link right after an advertising phrase: "...uchun: @admin", "- t.me/admin"
_AD_TARGET = r"(?:@[a-z]|https?://|(?:t|telegram)\.me/|www\.)"
_AD_GAP = r"[\W_]{0,8}"
_AD_NEXT_LINE_MAX = 60  # the account line after "Reklama uchun:" is short


def _norm_all(items: Iterable[str]) -> list[str]:
    return [n for n in (normalize(i) for i in items) if n]


def _fold_all(items: Iterable[str]) -> list[str]:
    return [n for n in (fold(i) for i in items) if n]


def ad_contact_lines(norm_lines: list[str], rules: BoilerplateRules) -> set[int]:
    """Indexes of the lines that hold the channel's advertising contact (see the module doc)."""
    out: set[int] = set()
    if rules.ads_inline_re is None or rules.ads_lead_re is None:
        return out
    for i, line in enumerate(norm_lines):
        if not line:
            continue
        if rules.ads_inline_re.search(line):
            out.add(i)
        elif rules.ads_lead_re.search(line):
            nxt = next((j for j in range(i + 1, len(norm_lines)) if norm_lines[j]), None)
            if (
                nxt is not None
                and len(norm_lines[nxt]) <= _AD_NEXT_LINE_MAX
                and re.match(rf"[\W_]*{_AD_TARGET}", norm_lines[nxt])
            ):
                out.update((i, nxt))
    return out


def ad_contact_usernames(text: str, rules: BoilerplateRules) -> list[str]:
    """The accounts of the post's advertising-contact lines (canonical ``@name``): the channel's
    own, so they are never the poster's contacts — a hidden link to them is dropped too."""
    if rules.ads_inline_re is None:
        return []
    lines = normalize_lines(text)
    return [u for i in sorted(ad_contact_lines(lines, rules)) for u in find_usernames(lines[i])]


@dataclass(frozen=True)
class BoilerplateRules:
    """``source_rules.yaml`` rules of one channel, pre-normalized."""

    cut_from: tuple[str, ...]
    strip_lines: tuple[str, ...]
    exact_lines: frozenset[str]
    header_junk_words: frozenset[str]
    drop_trailing_hashtags: bool
    ads_inline_re: re.Pattern[str] | None = None  # phrase + account on the same line
    ads_lead_re: re.Pattern[str] | None = None  # line ending with the phrase

    @classmethod
    def build(cls, rule: SourceRule, defaults: SourceRuleDefaults) -> BoilerplateRules:
        phrases = {
            re.escape(p).replace(r"\ ", r"\s+")
            for p in (
                *_norm_all(defaults.ads_contact_phrases),
                *_fold_all(defaults.ads_contact_phrases),
            )
        }
        group = "|".join(sorted(phrases, key=len, reverse=True))
        return cls(
            cut_from=tuple(_norm_all(rule.cut_from)),
            strip_lines=tuple(_norm_all([*defaults.strip_lines, *rule.strip_lines])),
            exact_lines=frozenset(_norm_all(rule.exact_lines)),
            header_junk_words=frozenset(_norm_all(rule.header_junk_words)),
            drop_trailing_hashtags=rule.drop_trailing_hashtags,
            ads_inline_re=re.compile(rf"(?:{group}){_AD_GAP}{_AD_TARGET}") if group else None,
            ads_lead_re=re.compile(rf"(?:{group})[\W_]*$") if group else None,
        )


def keep_mask(norm_lines: list[str], rules: BoilerplateRules) -> list[bool]:
    """For every normalized line: ``True`` if it is part of the post, ``False`` if boilerplate.

    Applies leading junk / cut_from (with the 40% safety rule) / exact_lines / strip_lines /
    serial numbers / trailing hashtags.
    """
    keep = [True] * len(norm_lines)
    idx = list(range(len(norm_lines)))  # indices still kept, in order

    # Leading junk: empty lines (emoji-only headers become empty) and "new"/"without" words.
    while idx and (not norm_lines[idx[0]] or norm_lines[idx[0]] in rules.header_junk_words):
        keep[idx.pop(0)] = False

    total = sum(len(norm_lines[i]) for i in idx) or 1
    for pos, i in enumerate(idx):
        if any(c in norm_lines[i] for c in rules.cut_from):
            if sum(len(norm_lines[j]) for j in idx[:pos]) / total >= MIN_KEEP_RATIO:
                for j in idx[pos:]:
                    keep[j] = False
                idx = idx[:pos]
            break

    ads = ad_contact_lines(norm_lines, rules)
    for i in idx:
        ln = norm_lines[i]
        if (
            ln in rules.exact_lines
            or _SERIAL_RE.match(ln)
            or any(s in ln for s in rules.strip_lines)
            or i in ads
        ):
            keep[i] = False
    idx = [i for i in idx if keep[i]]

    if rules.drop_trailing_hashtags:
        while idx and (not norm_lines[idx[-1]] or _HASHTAG_LINE_RE.match(norm_lines[idx[-1]])):
            keep[idx.pop()] = False
    return keep


def strip_boilerplate(norm_text: str, rules: BoilerplateRules) -> str:
    """Apply cut_from / strip_lines / exact_lines / header junk to normalized text."""
    lines = norm_text.split("\n")
    kept = [ln for ln, k in zip(lines, keep_mask(lines, rules), strict=True) if k]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
