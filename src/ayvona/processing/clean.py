"""Clean the *original* text of a job post for publishing (config/source_rules.yaml).

``boilerplate.py`` decides which lines are the channel's signature / ads (on the normalized text,
used by classify / dedup / extract). This module applies the same line decisions to the original
text, so the fallback template can show the post itself without the source channel's footer:

* ``defaults`` + the channel's rules: cut_from, strip_lines, exact_lines, header_lines,
  header_junk_words, drop_trailing_hashtags, extra_own_usernames. A channel added by the admin
  from the bot (not in the YAML) gets only ``defaults``.
* Safety: if a ``cut_from`` cut would leave less than 40% of the text, nothing is cut (logged).
* Tracking parameters (``utm_*``, ``text=``, ... — ``strip_url_params``) are removed from URLs,
  in the text and in hidden links.
* Contacts are never removed: a dropped line that holds a phone or a (not own) @username which is
  nowhere else in the kept text is put back.
* Hidden links: only those whose text is still in the post, not ads (``drop_link_patterns``,
  whitespace-only text) and not the channel's own accounts. URL buttons are kept.

The text keeps its emoji and script (NFKC, keycap digits and apostrophes are unified): the
formatter transliterates / escapes it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from ayvona.config import SourceRule, SourceRulesConfig
from ayvona.processing.boilerplate import BoilerplateRules, keep_mask
from ayvona.processing.contacts import (
    canon_username,
    clean_url,
    find_phones,
    find_urls,
    find_usernames,
)
from ayvona.processing.normalize import normalize, normalize_lines, unify

_MANY_BLANKS_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[^\S\n]+$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Link:
    """A hidden link (text in the post, URL behind it) or a URL button."""

    text: str
    url: str
    button: bool = False


@dataclass(frozen=True, slots=True)
class CleanedText:
    text: str  # original post without boilerplate; emoji and script as written
    links: tuple[Link, ...] = ()
    removed_lines: int = 0
    cut_skipped: bool = False  # a cut_from rule matched, but the 40% safety rule kept the text
    restored_lines: int = 0  # dropped lines put back because they hold a contact


class Cleaner:
    """Build once from ``source_rules.yaml``, call :meth:`clean` per post."""

    def __init__(self, source_rules: SourceRulesConfig) -> None:
        self.source_rules = source_rules
        self.defaults = source_rules.defaults
        self._rules: dict[tuple[str, bool], tuple[SourceRule, BoilerplateRules]] = {}

    def _rules_for(
        self, source: str | None, only_defaults: bool
    ) -> tuple[SourceRule, BoilerplateRules]:
        key = ((source or "").lower(), only_defaults)
        if key not in self._rules:
            rule = SourceRule() if only_defaults else self.source_rules.for_source(source)
            self._rules[key] = (rule, BoilerplateRules.build(rule, self.defaults))
        return self._rules[key]

    def own_usernames(
        self, source: str | None, own_usernames: Iterable[str] = (), only_defaults: bool = False
    ) -> list[str]:
        rule, _ = self._rules_for(source, only_defaults)
        own = [*own_usernames, *rule.extra_own_usernames, *self.defaults.extra_own_usernames]
        if source:
            own.append(source)
        return own

    def clean_url(self, url: str) -> str:
        return clean_url(url, self.defaults.strip_url_params)

    def _clean_urls(self, line: str) -> str:
        for url in find_urls(line):
            cleaned = self.clean_url(url)
            if cleaned != url:
                line = line.replace(url, cleaned)
        return line

    def _is_ad_link(self, url: str, text: str, own: set[str]) -> bool:
        low = url.lower()
        if re.search(r"t\.me/\+998\d{9}", low):  # a phone, not an invite link
            return False
        if self.defaults.drop_whitespace_text_links and not text.strip():
            return True
        if any(p.lower() in low for p in self.defaults.drop_link_patterns):
            return True
        users = find_usernames(url)  # the channel's own account
        return bool(users) and canon_username(users[0]) in own

    def clean(
        self,
        text: str,
        extra: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        own_usernames: Iterable[str] = (),
        only_defaults: bool = False,
    ) -> CleanedText:
        """Clean one post. ``only_defaults``: ignore the channel's rules (a bot-added source)."""
        rule, rules = self._rules_for(source, only_defaults)
        own = {canon_username(u) for u in self.own_usernames(source, own_usernames, only_defaults)}
        raw = unify(text).split("\n")
        norm = normalize_lines(text)
        keep = keep_mask(norm, rules)
        headers = {h.strip() for h in rule.header_lines if h.strip()}
        for i, line in enumerate(raw[:3]):
            if line.strip() in headers:
                keep[i] = False

        cut_skipped = False
        if rules.cut_from:
            hit = next((i for i, n in enumerate(norm) if any(c in n for c in rules.cut_from)), None)
            if hit is not None and keep[hit]:
                cut_skipped = True
                logger.warning(
                    "clean: {} — cut_from topildi, lekin matnning 40% dan kami qolardi, kesilmadi",
                    source,
                )

        # Contacts are never removed (hard rule): put back dropped lines with a phone or a
        # username that the kept text does not already have.
        kept_text = "\n".join(r for r, k in zip(raw, keep, strict=True) if k)
        have_phones = set(find_phones(kept_text))
        have_users = {canon_username(u) for u in find_usernames(kept_text, own)}
        restored = 0
        for i, (line, k) in enumerate(zip(raw, keep, strict=True)):
            if k or not norm[i]:
                continue
            phones = set(find_phones(line)) - have_phones
            users = {canon_username(u) for u in find_usernames(line, own)} - have_users
            if phones or users:
                keep[i] = True
                restored += 1
                have_phones |= phones
                have_users |= users
                logger.info("clean: {} — aloqali qator qoldirildi: {!r}", source, line[:80])

        lines = [self._clean_urls(r.rstrip()) for r, k in zip(raw, keep, strict=True) if k]
        body = _MANY_BLANKS_RE.sub("\n\n", _TRAILING_SPACE_RE.sub("", "\n".join(lines))).strip()

        links: list[Link] = []
        folded_body = normalize(body)
        for kind in ("links", "buttons"):
            for item in (extra or {}).get(kind, []):
                url, link_text = str(item.get("url") or ""), str(item.get("text") or "")
                if not url or self._is_ad_link(url, link_text, own):
                    continue
                is_button = kind == "buttons"
                if not is_button and normalize(link_text) not in folded_body:
                    continue  # the link was in a removed line (footer ad)
                links.append(Link(unify(link_text).strip(), self.clean_url(url), is_button))

        return CleanedText(
            text=body,
            links=tuple(links),
            removed_lines=sum(1 for k, n in zip(keep, norm, strict=True) if not k and n),
            cut_skipped=cut_skipped,
            restored_lines=restored,
        )
