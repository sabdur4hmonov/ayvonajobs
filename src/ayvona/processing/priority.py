"""Priority of a job: which ads go to the channel first and come first in the bot's search.

Rule based, no AI (so it costs nothing and gives the same answer every time). Everything that can be
tuned — the word lists, the salary limits, the points — lives in ``config/settings.yaml`` →
``priority:`` (Uzbek Latin / Cyrillic, Russian and English words).

Tiers: **1** = top (office / professional roles, clearly high pay), **2** = normal,
**3** = bottom (low-skill small jobs). Within the title the strongest matching rule counts once per
side, so "Kuryer, 12 mln" is not counted as "kuryer" twice:

    score = best "high" role points (profession 3 / title word 2 / category 1)
          + worst "low" role points (low profession or word -3 / mild -1)
          + salary points (high monthly pay +3 / known low pay -1)

    score >= tier1_at -> tier 1,   score <= tier3_at -> tier 3,   otherwise tier 2.

``Priority.reason`` is the one-line "why" (stored in ``jobs.priority_reason``, shown by the admin's
``/why <id>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ayvona.config import PriorityConfig, Settings
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold
from ayvona.processing.salary import EUR, RUB, USD, UZS

TOP, NORMAL, BOTTOM = 1, 2, 3

# monthly equivalents of a daily / weekly / hourly pay
_PERIOD_TO_MONTH = {"month": 1.0, "week": 4.3, "day": 22.0, "hour": 176.0}
_EUR_IN_USD = 1.1  # only for the high / low salary test: a rough figure is enough
_RUB_PER_USD = 90.0


@dataclass(frozen=True, slots=True)
class Priority:
    tier: int
    score: int
    reasons: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        why = "; ".join(self.reasons) or "qoida topilmadi"
        return f"daraja {self.tier} (ball {self.score:+d}): {why}"[:500]

    def fields(self) -> dict[str, Any]:
        """The ``jobs`` columns."""
        return {
            "priority_tier": self.tier,
            "priority_score": self.score,
            "priority_reason": self.reason,
        }


def monthly_uzs(
    salary_min: int | None,
    salary_max: int | None,
    currency: str | None,
    period: str | None,
    usd_rate: float,
) -> tuple[float | None, float | None]:
    """(lowest, highest) known pay as so'm per month, or (None, None) if it cannot be told."""
    factor = _PERIOD_TO_MONTH.get(period or "month")
    if factor is None or currency not in (UZS, USD, EUR, RUB):
        return None, None
    if currency == UZS:
        rate = 1.0
    elif currency == USD:
        rate = usd_rate
    elif currency == EUR:
        rate = usd_rate * _EUR_IN_USD
    else:
        rate = usd_rate / _RUB_PER_USD
    values = [float(v) * rate * factor for v in (salary_min, salary_max) if v]
    if not values:
        return None, None
    return min(values), max(values)


def _mln(amount: float) -> str:
    return f"{amount / 1_000_000:.1f} mln"


class PriorityScorer:
    """Build once per process (the word lists are compiled here)."""

    def __init__(self, settings: Settings) -> None:
        self.cfg: PriorityConfig = settings.app.priority
        self.usd_rate = settings.app.search.usd_rate_fallback
        self._high_words = KeywordSet(self.cfg.high_keywords)
        self._low_words = KeywordSet(self.cfg.low_keywords)
        self._high_professions = set(self.cfg.high_professions)
        self._low_professions = set(self.cfg.low_professions)
        self._mild_professions = set(self.cfg.mild_low_professions)
        self._high_categories = set(self.cfg.high_categories)

    def score(
        self,
        *,
        title: str | None,
        profession: str | None = None,
        category: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        currency: str | None = None,
        salary_period: str | None = None,
    ) -> Priority:
        cfg = self.cfg
        if not cfg.enabled:
            return Priority(NORMAL, 0, ("tartiblash o'chirilgan (priority.enabled)",))
        pts = cfg.points
        folded = fold(title or "")
        reasons: list[str] = []

        # --- the strongest "high" role rule counts once
        high: list[tuple[int, str]] = []
        if profession and profession in self._high_professions:
            high.append((pts.high_profession, f"kasb {profession}"))
        if hits := self._high_words.find(folded):
            high.append((pts.high_keyword, f"sarlavha: {', '.join(sorted(hits))}"))
        if category and category in self._high_categories:
            high.append((pts.high_category, f"soha {category}"))
        score = 0
        if high:
            points, why = max(high, key=lambda t: t[0])
            score += points
            reasons.append(f"{why} ({points:+d})")

        # --- the worst "low" role rule counts once
        low: list[tuple[int, str]] = []
        if profession and profession in self._low_professions:
            low.append((pts.low_profession, f"oddiy kasb {profession}"))
        if hits := self._low_words.find(folded):
            low.append((pts.low_keyword, f"oddiy ish: {', '.join(sorted(hits))}"))
        if profession and profession in self._mild_professions:
            low.append((pts.mild_low, f"kasb {profession}"))
        if low:
            points, why = min(low, key=lambda t: t[0])
            score += points
            reasons.append(f"{why} ({points:+d})")

        # --- salary (monthly so'm)
        lo, hi = monthly_uzs(salary_min, salary_max, currency, salary_period, self.usd_rate)
        if lo is not None and hi is not None:
            if lo >= cfg.high_salary_uzs:  # the whole range is high: "clearly" high
                score += pts.high_salary
                reasons.append(f"maosh {_mln(lo)}+ ({pts.high_salary:+d})")
            elif hi < cfg.low_salary_uzs:  # even the top of the range is low
                score += pts.low_salary
                reasons.append(f"maosh {_mln(hi)} gacha ({pts.low_salary:+d})")

        if score >= cfg.tier1_at:
            tier = TOP
        elif score <= cfg.tier3_at:
            tier = BOTTOM
        else:
            tier = NORMAL
        return Priority(tier, score, tuple(reasons))

    # ------------------------------------------------------------------ sources of the inputs
    def for_extraction(self, ex: Any) -> Priority:
        """An :class:`~ayvona.processing.extract.Extraction` (aggregator posts, form drafts)."""
        return self.score(
            title=ex.title_uz or ex.title,
            profession=ex.profession,
            category=ex.category,
            salary_min=ex.salary_min,
            salary_max=ex.salary_max,
            currency=ex.currency,
            salary_period=ex.salary_period,
        )

    def for_job(self, job: Any) -> Priority:
        """A ``jobs`` row (the backfill and ``/why``)."""
        return self.score(
            title=job.title,
            profession=job.profession,
            category=job.category,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            currency=job.currency,
            salary_period=job.salary_period,
        )
