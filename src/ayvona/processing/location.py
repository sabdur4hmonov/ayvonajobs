"""Region / district / remote detection (docs/SOURCE_ANALYSIS.md §7, config/regions.yaml).

Every region name, district and landmark spelling is matched on folded text (all Cyrillic ->
Latin), keyword at a word start ("Chilonzorda" matches "chilonzor"). Overlapping matches: the
longest wins ("Toshkent viloyati" -> toshkent_vil, "Samarqand Darvoza" -> a Tashkent landmark).
A region name followed by "ko'chasi / street" is a street, not a region.

Result: the region with most mentions; 2+ different regions (Tashkent city + Tashkent region count
as one area) -> ``multi_region`` ("kop_hudud").
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from ayvona.config import RegionsConfig
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold

_LEFT_BOUNDARY = r"(?<![^\W_])(?<!')"
# Tashkent city and region are one job market: together they are not "many regions".
_TASHKENT_AREA = frozenset({"toshkent_sh", "toshkent_vil"})
# Accounts and links are not places: "@Kvartira_uylar_Tashkent", "t.me/ish_toshkent".
_NOT_PLACE_RE = re.compile(
    r"\S+@\S+|@\w+|(?:https?://|www\.)\S+|\b[\w.-]+\.(?:me|uz|com|ph|ru|in)/\S*"
)


@dataclass(frozen=True, slots=True)
class _Entry:
    pattern: re.Pattern[str]
    length: int
    region: str
    district: str | None
    kind: str  # "region" | "district" | "landmark"


@dataclass(frozen=True, slots=True)
class Location:
    region: str | None = None  # regions.yaml key, or multi_region
    regions: tuple[str, ...] = ()  # every region found (for hashtags)
    district: str | None = None  # display name ("Yunusobod")
    is_remote: bool = False
    hits: tuple[str, ...] = field(default=())  # matched spellings, for debugging


class LocationFinder:
    """Build once from ``config/regions.yaml``, call :meth:`find` per post."""

    def __init__(self, cfg: RegionsConfig) -> None:
        self.cfg = cfg
        self.multi_region = cfg.multi_region
        entries: list[_Entry] = []

        def add(words: list[str], region: str, district: str | None, kind: str) -> None:
            for w in words:
                f = fold(w)
                if f:
                    entries.append(
                        _Entry(
                            re.compile(_LEFT_BOUNDARY + re.escape(f)),
                            len(f),
                            region,
                            district,
                            kind,
                        )
                    )

        for key, reg in cfg.regions.items():
            add(reg.keywords, key, None, "region")
            for name, words in reg.districts.items():
                add([name, *words], key, name, "district")
            for lm in reg.landmarks:
                add(lm.keywords, key, lm.district, "landmark")
        entries.sort(key=lambda e: -e.length)
        self._entries = entries
        street = "|".join(re.escape(fold(w)) for w in cfg.street_words if fold(w))
        self._street_after = re.compile(rf"^\w*\s*(?:{street})") if street else None
        self.remote = KeywordSet(cfg.remote_keywords)
        self.office = KeywordSet(cfg.office_keywords)

    def find(self, folded_lines: list[str]) -> Location:
        """``folded_lines``: the post's lines (boilerplate removed), each :func:`fold`-ed."""
        text = _NOT_PLACE_RE.sub(lambda m: " " * len(m.group(0)), "\n".join(folded_lines))
        taken = [False] * len(text)
        found: list[tuple[int, _Entry, str]] = []
        for e in self._entries:
            for m in e.pattern.finditer(text):
                if any(taken[m.start() : m.end()]):
                    continue
                if (
                    e.kind == "region"
                    and self._street_after
                    and self._street_after.match(text[m.end() :])
                ):
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                found.append((m.start(), e, m.group(0)))
        found.sort(key=lambda f: f[0])

        is_remote = any(
            self.remote.find(line) and not self.office.find(line) for line in folded_lines
        )
        if not found:
            return Location(is_remote=is_remote)

        votes = Counter(e.region for _, e, _ in found)
        regions = tuple(dict.fromkeys(e.region for _, e, _ in found))
        areas = {"toshkent" if r in _TASHKENT_AREA else r for r in regions}
        if len(areas) > 1:
            region = self.multi_region
        else:
            # Most mentions; a tie -> the first mentioned.
            best = max(votes.values())
            region = next(r for r in regions if votes[r] == best)
        district = next(
            (e.district for _, e, _ in found if e.district and e.region == region), None
        )
        return Location(
            region=region,
            regions=regions,
            district=district,
            is_remote=is_remote,
            hits=tuple(h for _, _, h in found),
        )
