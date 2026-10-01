"""Jobs from websites / APIs (``raw_posts.extra["web"]``, sources/web/): their structured fields
are better than anything regex can guess from the text, so they replace the extraction.

Contacts stay as regex found them; the apply link (the job page) is always there, so a web job
always has a contact (``apply_url``) and gets the "🔗 Ariza topshirish" button.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ayvona.processing.extract import Extraction
from ayvona.processing.language import detect_language

PER_MONTH = {"year": 1 / 12, "annual": 1 / 12, "yearly": 1 / 12, "month": 1, "monthly": 1}
INTERNATIONAL_TAGS = ("masofaviy", "xalqaro")


def web_data(extra: dict[str, Any] | None) -> dict[str, Any] | None:
    web = (extra or {}).get("web")
    return web if isinstance(web, dict) else None


def _monthly(lo: Any, hi: Any, period: str | None) -> tuple[int | None, int | None, str | None]:
    factor = PER_MONTH.get((period or "month").lower())
    if factor is None:  # hourly / daily stay as they are
        return lo, hi, (period or "").lower() or None
    return (
        round(lo * factor) if lo else None,
        round(hi * factor) if hi else None,
        "month",
    )


def apply_web(ex: Extraction, web: dict[str, Any], extra: dict[str, Any]) -> Extraction:
    title = (web.get("title") or "").strip() or ex.title
    language = detect_language(f"{title}\n{web.get('description') or ''}")
    lo, hi, period = _monthly(
        web.get("salary_min"), web.get("salary_max"), web.get("salary_period")
    )
    has_salary = lo is not None or hi is not None
    international = bool(web.get("international"))
    return replace(
        ex,
        title=title,
        title_uz=None,
        title_source="web",
        company=web.get("company") or ex.company,
        positions=(),
        salary_min=lo if has_salary else ex.salary_min,
        salary_max=hi if has_salary else ex.salary_max,
        currency=(web.get("currency") or "USD") if has_salary else ex.currency,
        salary_period=period if has_salary else ex.salary_period,
        salary_text=web.get("salary_text") or ex.salary_text,
        region=None if international else ex.region,
        regions=() if international else ex.regions,
        is_remote=bool(web.get("is_remote")) or ex.is_remote,
        apply_url=extra.get("apply_url") or web.get("url") or ex.apply_url,
        feature_tags=INTERNATIONAL_TAGS if international else ex.feature_tags,
        language=language,
        confidence=max(ex.confidence, 0.9),
        low_quality=False,
    )
