"""Text normalization for matching (keywords, dedup, classification).

``normalize()`` produces a *matching* form of a post; the original text is always kept separately
by the caller (it is what we clean and publish later).

Steps: NFKC (``𝗨𝗫`` -> ``UX``), keycap digits (``3️⃣`` -> ``3``), unified apostrophes
(``o‘ oʻ o’ o``` -> ``o'``), lower case, emoji/pictographs removed, Uzbek Cyrillic -> Latin
(Russian stays Cyrillic), whitespace collapsed. Line breaks are kept: rules work per line.
"""

from __future__ import annotations

import re
import unicodedata

from ayvona.processing.language import Language, cyrillic_scores, detect_language

# --------------------------------------------------------------------------- character tables
APOSTROPHES = "‘’ʻʼ`´′"
_APOSTROPHE_TABLE = str.maketrans({c: "'" for c in APOSTROPHES})

_KEYCAP_RE = re.compile("([0-9#*])️?⃣")
_HSPACE_RE = re.compile(r"[^\S\n]+")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")

# Uzbek Cyrillic -> Latin (official 1995 alphabet). Context-dependent letters handled in code:
#   е -> "ye" at word start / after a vowel, else "e";  ц -> "ts" after a vowel, else "s".
_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}  # fmt: skip
_CYR_VOWELS = frozenset("аеёиоуўэюяыъь")


def _is_cyr(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def to_latin(text: str) -> str:
    """Transliterate every Cyrillic letter to Uzbek Latin. Keeps case (``Ш`` -> ``Sh``/``SH``)."""
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        low = ch.lower()
        if low not in _CYR2LAT and low != "е" and low != "ц":
            out.append(ch)
            continue
        prev = text[i - 1].lower() if i else ""
        if low == "е":
            lat = "ye" if (not prev or not prev.isalpha() or prev in _CYR_VOWELS) else "e"
        elif low == "ц":
            lat = "ts" if prev in _CYR_VOWELS else "s"
        else:
            lat = _CYR2LAT[low]
        if ch != low and lat:  # upper case letter
            nxt = text[i + 1] if i + 1 < n else ""
            whole_word_upper = (nxt.isalpha() and nxt.isupper()) or (
                prev.isalpha() and text[i - 1].isupper() and not nxt.isalpha()
            )
            lat = lat.upper() if whole_word_upper else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def _strip_symbols(text: str) -> str:
    """Emoji, pictographs, variation selectors, ZWJ -> space. Letters, digits, punctuation stay."""
    out: list[str] = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk", "Cs", "Co", "Cn", "Me", "Mn") or (cat == "Cf" and ch != "\n"):
            # "Mn" after NFKC here is only variation selectors / emoji modifiers in practice;
            # Uzbek/Russian letters are precomposed.
            out.append(" " if cat in ("So", "Sk") else "")
        else:
            out.append(ch)
    return "".join(out)


def unify(text: str) -> str:
    """NFKC + keycaps + apostrophes (no case change, no transliteration)."""
    text = unicodedata.normalize("NFKC", text)
    text = _KEYCAP_RE.sub(r"\1", text)
    return text.translate(_APOSTROPHE_TABLE)


def _collapse(text: str) -> str:
    lines = [_HSPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    return _MANY_NEWLINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _transliterate_uzbek(text: str, language: Language) -> str:
    """Uzbek Cyrillic lines -> Latin; Russian lines stay as they are (lower-cased input).

    Decided per line (posts mix both languages); a line without evidence either way follows
    the language of the whole post.
    """
    if not any(_is_cyr(ch) for ch in text):
        return text
    out = []
    for line in text.split("\n"):
        if any(_is_cyr(ch) for ch in line):
            uz, ru = cyrillic_scores(line)
            if uz > ru or (uz == ru and language is Language.UZ_CYRILLIC):
                line = to_latin(line)
        out.append(line)
    return "\n".join(out)


def normalize(text: str) -> str:
    """Matching form of a post (see module docstring)."""
    if not text:
        return ""
    text = unify(text)
    language = detect_language(text)
    text = _strip_symbols(text.lower())
    text = _transliterate_uzbek(text, language)
    return _collapse(text)


def fold(text: str) -> str:
    """Like :func:`normalize`, but *all* Cyrillic -> Latin. Only for keyword matching.

    Keywords are folded the same way, so a Russian keyword still matches Russian text,
    and Uzbek keywords written in Cyrillic match posts written in Latin (and vice versa).
    """
    if not text:
        return ""
    return _collapse(to_latin(_strip_symbols(unify(text).lower())))
