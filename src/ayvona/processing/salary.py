"""Salary parsing (docs/SOURCE_ANALYSIS.md §6).

Input: the salary "blocks" of a post (value of a "Maosh:" line plus its continuation lines, or a
line with money in it) in two forms — ``display`` (readable, original script) and ``folded``
(lower case, all Cyrillic -> Latin). Output: :class:`Salary`.

Handles "4 000 000 so'm", "3.000.000 Fix + KPI", "5 - 30 mln", "от 7 000 000 до 15 000 000 сум",
"2 mln+", "4million - 9 million", "6 000 000 so'mdan", "9 000 000 so'mgacha", "$500 – 800",
"Up to 3800 USD", "300$-2500$", "до 1000$", "Kunlik 250 000", typos like "10 00 0000" in a range,
keycap digits (already unified by normalize).

Sanity check: a number outside a sane range for its currency and period (a monthly salary under
500 000 so'm, ...) is not shown — only ``salary_text`` stays. "Depozit 200$" is never a salary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ayvona.config import ExtractConfig
from ayvona.processing.keywords import KeywordSet

UZS = "UZS"
USD = "USD"
EUR = "EUR"
RUB = "RUB"
DEFAULT_PERIOD = "month"

# Sane (min, max) per currency and period. Outside -> numbers are dropped, text is kept.
SANE_RANGES: dict[tuple[str, str], tuple[float, float]] = {
    (UZS, "month"): (500_000, 200_000_000),
    (UZS, "week"): (100_000, 50_000_000),
    (UZS, "day"): (30_000, 5_000_000),
    (UZS, "hour"): (5_000, 1_000_000),
    (USD, "month"): (50, 30_000),
    (USD, "week"): (20, 10_000),
    (USD, "day"): (5, 1_000),
    (USD, "hour"): (1, 200),
    (RUB, "month"): (5_000, 2_000_000),
}
SANE_RANGES[(EUR, "month")] = SANE_RANGES[(USD, "month")]
SANE_RANGES[(EUR, "week")] = SANE_RANGES[(USD, "week")]
SANE_RANGES[(EUR, "day")] = SANE_RANGES[(USD, "day")]
SANE_RANGES[(EUR, "hour")] = SANE_RANGES[(USD, "hour")]

# Numbers that are not money: times, percents, "6/1", ages, years, days, "3 mahal", "2026-yil".
_NOISE_RES = [
    re.compile(r"\b\d{1,2}[:.]\d{2}\s*[-–—]\s*\d{1,2}[:.]\d{2}\b"),  # 09.00-18.00
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\d+(?:[.,]\d+)?\s*%"),
    re.compile(r"\b\d{1,2}\s*/\s*\d{1,2}\b"),
    re.compile(r"\b(?:19|20)\d{2}\s*[-–]?\s*(?:yil|y\b|god|year)"),
    re.compile(
        r"(?<![\d.,])(?<!\d )\d{1,2}(?:\s*[-–]\s*\d{1,2})?\s*[-–]?\s*"
        r"(?:yosh|yil|oy\b|oyga|oyda|oydan|kun|soat|hafta|smena|mahal|marta|nafar|kishi|sana"
        r"|let\b|god|year|month|day|hour|ta\b|x\b|razryad|kurs|sinf)"
    ),
]
# A run of digits with single separators: "4 000 000", "3.000.000", "10 00 0000", "4.5", "1,000".
_NUMBER_RE = re.compile(r"\d+(?:[ .,]\d+)*")
_MULTIPLIER_RE = re.compile(
    r"\s*(?P<m>mln|million|millon|mlyon|mil\b|m\b|ming|k\b|tys|mlrd)", re.IGNORECASE
)
_FROM_AFTER_RE = re.compile(
    r"^\s*(?:mln|million|ming|k|tys)?\w*\s*(?:so'm|som|sum|usd|\$|dollar|y\.e\.?)?\s*"
    r"(?:dan\b|dan\s|\+|va undan|and more|and above)"
)
_TO_AFTER_RE = re.compile(
    r"^\s*(?:mln|million|ming|k|tys)?\w*?\s*(?:so'm|som|sum|usd|\$|dollar)?\s*gacha"
)
_SUFFIX_DAN_RE = re.compile(r"^(?:mln|million|ming|so'm|sum|som)?dan\b")
_SUFFIX_GACHA_RE = re.compile(r"^(?:mln|million|ming|so'm|sum|som)?gacha\b")
_FROM_BEFORE_RE = re.compile(
    r"(?:\bot|\bfrom|\bmin|\bminimum|\bkamida|\bat least|\bstarting)\s*\$?\s*$"
)
_TO_BEFORE_RE = re.compile(r"(?:\bdo|\bup to|\bupto|\bmax|\bmaximum|\buntil)\s*\$?\s*$")
_KPI_RE = re.compile(r"\bkpi\b|bonus|\+\s*%|premiya|премия|foiz")
_USD_RE = re.compile(r"\$|\busd\b|dollar|\by\.e\.|у\.е")
_EUR_RE = re.compile(r"€|\beur\b|\bevro\b|\beuro\b")
_RUB_RE = re.compile(r"₽|\brub\b|rubl")
# A number directly followed by a money unit ("5–15 mln so'm", "3800 USD") or "$300".
_MONEY_HINT_RE = re.compile(
    r"\d[\d .,]*\s*(?:so'm|som\b|sum\b|mln|million|ming\b|\$|usd\b|dollar|€|eur\b|rubl)"
    r"|(?:\$|\busd\b|€)\s*\d"
)


@dataclass(frozen=True, slots=True)
class SalaryBlock:
    display: str  # readable value text (original script)
    folded: str  # same text, fold()-ed
    labeled: bool = True  # came from a "Maosh:" label (else: a line that just has money in it)


@dataclass(frozen=True, slots=True)
class Salary:
    min: int | None = None
    max: int | None = None
    currency: str | None = None
    period: str | None = None
    text: str | None = None
    negotiable: bool = False

    @property
    def has_numbers(self) -> bool:
        return self.min is not None or self.max is not None

    def __bool__(self) -> bool:
        return self.has_numbers or bool(self.text)


@dataclass(slots=True)
class _Amount:
    value: float
    start: int
    end: int
    malformed: bool = False
    factor: float = 1.0  # "mln" -> 1e6, "ming" -> 1e3
    bound: str | None = None  # "from" | "to" | None


def has_usd_hint(folded_text: str) -> bool:
    """``$`` / ``usd`` / ``dollar`` / ``у.е.`` anywhere in the (folded) text."""
    return bool(_USD_RE.search(folded_text))


def looks_like_money(folded_line: str) -> bool:
    """A line without a salary label that still states an amount ("5–15 mln so'm", "$500")."""
    return bool(_MONEY_HINT_RE.search(folded_line))


def _parse_number(run: str) -> tuple[float, bool] | None:
    """``"4 000 000"`` -> (4000000, False); ``"4.5"`` -> (4.5, False); ``"10 00 0000"`` ->
    (100000000, True) (malformed grouping, fixed later by its range partner)."""
    groups = re.split(r"[ .,]", run)
    digits = "".join(groups)
    if not digits:
        return None
    if len(groups) == 1:
        return float(digits), False
    if len(groups) == 2 and len(groups[1]) in (1, 2) and re.search(r"\d[.,]\d", run):
        return float(f"{groups[0]}.{groups[1]}"), False  # decimal: 4.5 mln, 1,5 mln
    if len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:]):
        return float(digits), False
    return float(digits), True


def _amounts(text: str) -> list[_Amount]:
    for rx in _NOISE_RES:
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    out: list[_Amount] = []
    for m in _NUMBER_RE.finditer(text):
        parsed = _parse_number(m.group(0).rstrip(" .,"))
        if parsed is None:
            continue
        value, malformed = parsed
        a = _Amount(value, m.start(), m.end(), malformed)
        after = text[m.end() :]
        if mm := _MULTIPLIER_RE.match(after):
            unit = mm.group("m").lower()
            if unit in ("mln", "million", "millon", "mlyon", "mil", "m") and value < 1000:
                a.factor = 1_000_000
            elif unit in ("ming", "k", "tys") and value < 10_000:
                a.factor = 1_000
            elif unit == "mlrd" and value < 100:
                a.factor = 1_000_000_000
            a.value *= a.factor
        before = text[max(0, m.start() - 14) : m.start()]
        if (
            _FROM_AFTER_RE.match(after)
            or _SUFFIX_DAN_RE.match(after.lstrip())
            or _FROM_BEFORE_RE.search(before)
        ):
            a.bound = "from"
        elif (
            _TO_AFTER_RE.match(after)
            or _SUFFIX_GACHA_RE.match(after.lstrip())
            or _TO_BEFORE_RE.search(before)
        ):
            a.bound = "to"
        out.append(a)

    # "5–15 mln": the multiplier of the second number applies to the first one too.
    for a, b in zip(out, out[1:], strict=False):
        if b.factor > 1 and a.factor == 1 and a.value < 1000 and b.start - a.end <= 12:
            a.factor = b.factor
            a.value *= b.factor

    # "3 –7 000 000 so'm": a small lower bound written without its zeros takes the scale of
    # the upper one (3 -> 3 000 000), only if that makes a sane range.
    for a, b in zip(out, out[1:], strict=False):
        between = text[a.end : b.start]
        if (
            a.factor == 1
            and a.value < 1000
            and b.value >= 100_000
            and re.fullmatch(r"\s*[-–—]\s*", between)
        ):
            for scale in (1_000_000, 1_000):
                if b.value / 20 <= a.value * scale <= b.value:
                    a.value *= scale
                    a.factor = scale
                    break

    # A typo in one side of a range ("4 000 000-10 00 0000"): scale it next to its partner.
    for i, a in enumerate(out):
        if not a.malformed:
            continue
        partner = next(
            (
                o
                for o in (out[i - 1] if i else None, out[i + 1] if i + 1 < len(out) else None)
                if o is not None and not o.malformed and abs(o.start - a.start) <= 30
            ),
            None,
        )
        if partner is None:
            continue
        if partner.start < a.start:  # a is the upper bound
            while a.value / 10 >= partner.value:
                a.value /= 10
        else:  # a is the lower bound
            while a.value * 10 <= partner.value:
                a.value *= 10
    return out


class SalaryParser:
    """Build once from ``config/extract.yaml``, call :meth:`parse` per post."""

    def __init__(self, cfg: ExtractConfig) -> None:
        self.negotiable = KeywordSet(cfg.salary_negotiable)
        self.not_salary = KeywordSet(cfg.salary_not_salary)
        self.periods = {p: KeywordSet(words) for p, words in cfg.salary_periods.items()}

    def _period(self, folded: str) -> str | None:
        for period in ("hour", "day", "week", "month"):
            ks = self.periods.get(period)
            if ks and ks.find(folded):
                return period
        return None

    def parse(
        self, blocks: list[SalaryBlock], label_folded: str = "", default_currency: str = UZS
    ) -> Salary:
        """``blocks``: salary text pieces of one post; ``label_folded``: their labels
        ("kunlik maosh") — they may carry the period. ``default_currency``: when the amounts name
        none (a "$" elsewhere in the post -> USD)."""
        blocks = [b for b in blocks if b.folded.strip()]
        if not blocks:
            return Salary()
        texts = [b for b in blocks if not self.not_salary.find(b.folded)]
        text = " | ".join(_money_part(b.display) if not b.labeled else b.display for b in blocks)
        text = text.strip(" |;,")[:255] or None
        if not texts:
            return Salary(text=text)

        folded = " | ".join(b.folded for b in texts)
        amounts = _amounts(folded)
        if not amounts:
            return Salary(text=text, negotiable=bool(self.negotiable.find(folded)))

        if _EUR_RE.search(folded):
            currency = EUR
        elif _USD_RE.search(folded):
            currency = USD
        elif _RUB_RE.search(folded):
            currency = RUB
        else:
            currency = default_currency
        period = self._period(f"{label_folded} {folded}") or DEFAULT_PERIOD

        values = [a.value for a in amounts]
        if len(amounts) == 1:
            a = amounts[0]
            if a.bound == "from" or (a.bound is None and _KPI_RE.search(folded)):
                lo, hi = a.value, None
            elif a.bound == "to":
                lo, hi = None, a.value
            else:
                lo = hi = a.value
        elif all(a.bound == "from" for a in amounts):
            lo, hi = min(values), None
        elif all(a.bound == "to" for a in amounts):
            lo, hi = None, max(values)
        else:
            lo, hi = min(values), max(values)

        sane = SANE_RANGES.get((currency, period))
        if sane and not all(sane[0] <= v <= sane[1] for v in (lo, hi) if v is not None):
            return Salary(text=text)
        return Salary(
            min=None if lo is None else round(lo),
            max=None if hi is None else round(hi),
            currency=currency,
            period=period,
            text=text,
        )


def _money_part(display: str) -> str:
    """``"Sotuv agenti — 5–15 mln so'm"`` -> ``"5–15 mln so'm"`` (for unlabeled money lines)."""
    m = re.search(r"(?:\b(?:от|ot|do|до|up to)\s+)?[$\d]", display, re.IGNORECASE)
    return display[m.start() :].strip() if m else display
