"""Polite, calm text for the channel: no shouting, no insults, no emoji / "!!!" spam.

``config/settings.yaml → tone:``

* a sentence that contains a rude phrase ("AYOLLAR BEZOVTA QILMANG!") is dropped — the factual
  part of the line stays ("FAQAT ERKAKLAR UCHUN ISH." -> "Faqat erkaklar uchun ish.");
* a shouted line (``shout_ratio`` of its letters upper case, at least ``shout_min_letters``)
  becomes sentence case; short acronyms (``keep_upper``: HR, KPI, IT ...) and words with digits
  ("E-7") keep their case;
* "!!!", "!!️", "??" -> one mark; a run of 3+ emoji -> the first one; spam marks at the start
  of a line go.
"""

from __future__ import annotations

import re

from ayvona.config import ToneConfig
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold

_SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")
_MARKS_RE = re.compile(r"([!?])[!?️‼❗❕]+")
_EMOJI = "[\U0001f000-\U0001faff☀-➿⬀-⯿‼⁉❗]️?"
_EMOJI_RUN_RE = re.compile(rf"({_EMOJI})(?:\s*{_EMOJI}){{2,}}")
_LEAD_SPAM_RE = re.compile(r"^[\s!?️‼❗❕]+(?=\w)")
_WORD_RE = re.compile(r"[^\W\d_][\w'ʻ’`-]*|\S*\d\S*")


class Tone:
    """Build once from :class:`ToneConfig`, call :meth:`normalize` on any text shown in a post."""

    def __init__(self, cfg: ToneConfig) -> None:
        self.cfg = cfg
        self.rude = KeywordSet(cfg.rude_phrases)
        self.keep_upper = {w.upper() for w in cfg.keep_upper}

    def normalize(self, text: str | None) -> str | None:
        if not text or not self.cfg.enabled:
            return text
        lines = [self._line(ln) for ln in text.split("\n")]
        out = "\n".join(ln for ln in lines if ln is not None)
        return re.sub(r"\n{3,}", "\n\n", out).strip("\n") or None

    def _line(self, line: str) -> str | None:
        if not line.strip():
            return line
        original = line
        if self.rude.find(fold(line)):
            kept = [
                s for s in _SENTENCE_RE.findall(line) if s.strip() and not self.rude.find(fold(s))
            ]
            line = " ".join(s.strip() for s in kept)
            if not line.strip():
                return None
        line = _MARKS_RE.sub(r"\1", line)
        line = _EMOJI_RUN_RE.sub(r"\1", line)
        if line != original:
            line = _LEAD_SPAM_RE.sub("", line)
        if self._shouting(line):
            line = self._sentence_case(line)
        return line

    def _shouting(self, line: str) -> bool:
        letters = [c for c in line if c.isalpha()]
        if len(letters) < self.cfg.shout_min_letters:
            return False
        upper = sum(c.isupper() for c in letters)
        return upper / len(letters) >= self.cfg.shout_ratio

    def _sentence_case(self, line: str) -> str:
        def word(m: re.Match[str]) -> str:
            w = m.group(0)
            core = re.sub(r"[^\w]", "", w)
            if any(ch.isdigit() for ch in w) or core.upper() in self.keep_upper:
                return w
            return w.lower()

        lowered = _WORD_RE.sub(word, line)
        # a capital letter at the start of every sentence
        return re.sub(
            r"(^[^\w]*|[.!?]\s+)([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), lowered
        )
