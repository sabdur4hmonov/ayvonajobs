"""International remote-job APIs (docs/WEB_SOURCES.md, C). Terms checked 2026-10-01:

* **Himalayas** — https://himalayas.app/jobs/api (max 20 per request). Link back to the job URL
  and name "Himalayas" as the source; do NOT submit the jobs to Jooble / Google Jobs / LinkedIn
  (so the website never gives them JobPosting markup). Rate limited (429) — we ask hourly.
* **Remotive** — https://remotive.com/api/remote-jobs. "max. 4 times a day"; link back + name
  "Remotive"; no third-party aggregators; never shown as our own listing.
* **Jobicy** — https://jobicy.com/api/v2/remote-jobs. "not more frequently than once per hour";
  keep Jobicy as the source and its canonical URL.
* **Remote OK** — https://remoteok.com/api (first element: the legal notice). Link back to
  Remote OK where the data is used.

Only jobs open to Uzbekistan are kept (:func:`open_to_uzbekistan`); the pipeline lets at most
``web_sources.max_international_per_day`` of them into the channel.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ayvona.sources.base import SourceError
from ayvona.sources.web.base import WebJob, WebSource, html_to_text, open_to_uzbekistan, parse_time


def _int(value: Any) -> int | None:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _salary_text(
    lo: int | None, hi: int | None, currency: str | None, period: str | None
) -> str | None:
    if lo is None and hi is None:
        return None
    amount = f"{lo:,}–{hi:,}" if lo and hi and lo != hi else f"{lo or hi:,}"
    return f"{amount} {currency or 'USD'}" + (f" / {period}" if period else "")


class _RemoteSource(WebSource):
    international: ClassVar[bool] = True

    def accept(self, job: WebJob) -> bool:
        return job.international


class HimalayasSource(_RemoteSource):
    site_name: ClassVar[str] = "Himalayas"
    min_interval_minutes: ClassVar[int] = 60
    max_requests_per_day: ClassVar[int] = 24
    URL: ClassVar[str] = "https://himalayas.app/jobs/api"

    async def fetch_jobs(self) -> list[WebJob]:
        data = (await self.get(self.URL, params={"limit": 20})).json()
        return [self.parse(j) for j in (data.get("jobs") or []) if isinstance(j, dict)]

    @staticmethod
    def parse(j: dict[str, Any]) -> WebJob:
        locations = j.get("locationRestrictions") or []
        timezones = j.get("timezoneRestriction") or j.get("timezoneRestrictions") or []
        lo, hi = _int(j.get("minSalary")), _int(j.get("maxSalary"))
        period = (j.get("salaryPeriod") or "year").lower() if (lo or hi) else None
        currency = j.get("currency") or ("USD" if lo or hi else None)
        url = j.get("applicationLink") or j.get("guid") or ""
        return WebJob(
            id=str(j.get("guid") or url),
            url=str(j.get("guid") or url),
            title=html_to_text(j.get("title"), 200),
            company=j.get("companyName"),
            location=", ".join(locations) or "Worldwide",
            description=html_to_text(j.get("description") or j.get("excerpt")),
            posted_at=parse_time(j.get("pubDate")),
            apply_url=url or None,
            salary_min=lo,
            salary_max=hi,
            currency=currency,
            salary_period=period,
            salary_text=_salary_text(lo, hi, currency, period),
            is_remote=True,
            international=open_to_uzbekistan(locations, timezones, empty_means_worldwide=True),
            tags=[str(c) for c in (j.get("categories") or j.get("parentCategories") or [])][:5],
        )


class RemotiveSource(_RemoteSource):
    site_name: ClassVar[str] = "Remotive"
    min_interval_minutes: ClassVar[int] = 360  # "max. 4 times a day"
    max_requests_per_day: ClassVar[int] = 4
    URL: ClassVar[str] = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(self) -> list[WebJob]:
        data = (await self.get(self.URL, params={"limit": 100})).json()
        return [self.parse(j) for j in (data.get("jobs") or []) if isinstance(j, dict)]

    @staticmethod
    def parse(j: dict[str, Any]) -> WebJob:
        location = j.get("candidate_required_location") or ""
        url = j.get("url") or ""
        return WebJob(
            id=str(j.get("id") or url),
            url=url,
            title=html_to_text(j.get("title"), 200),
            company=j.get("company_name"),
            location=location or "Worldwide",
            description=html_to_text(j.get("description")),
            posted_at=parse_time(j.get("publication_date")),
            apply_url=url or None,
            salary_text=(j.get("salary") or None),
            is_remote=True,
            international=open_to_uzbekistan(location, empty_means_worldwide=False),
            tags=[str(j.get("category") or "")][:1],
        )


class JobicySource(_RemoteSource):
    site_name: ClassVar[str] = "Jobicy"
    min_interval_minutes: ClassVar[int] = 60  # "not more frequently than once per hour"
    max_requests_per_day: ClassVar[int] = 24
    URL: ClassVar[str] = "https://jobicy.com/api/v2/remote-jobs"

    async def fetch_jobs(self) -> list[WebJob]:
        data = (await self.get(self.URL, params={"count": 50, "geo": "anywhere"})).json()
        return [self.parse(j) for j in (data.get("jobs") or []) if isinstance(j, dict)]

    @staticmethod
    def parse(j: dict[str, Any]) -> WebJob:
        geo = j.get("jobGeo") or ""
        lo = _int(j.get("salaryMin") or j.get("annualSalaryMin"))
        hi = _int(j.get("salaryMax") or j.get("annualSalaryMax"))
        period = (j.get("salaryPeriod") or "year").lower() if (lo or hi) else None
        currency = j.get("salaryCurrency") or ("USD" if lo or hi else None)
        url = j.get("url") or ""
        return WebJob(
            id=str(j.get("id") or url),
            url=url,
            title=html_to_text(j.get("jobTitle"), 200),
            company=j.get("companyName"),
            location=geo or "Anywhere",
            description=html_to_text(j.get("jobDescription") or j.get("jobExcerpt")),
            posted_at=parse_time(j.get("pubDate")),
            apply_url=url or None,
            salary_min=lo,
            salary_max=hi,
            currency=currency,
            salary_period=period,
            salary_text=_salary_text(lo, hi, currency, period),
            is_remote=True,
            international=open_to_uzbekistan(geo, empty_means_worldwide=True),
            tags=[str(t) for t in (j.get("jobIndustry") or [])][:3],
        )


class RemoteOkSource(_RemoteSource):
    site_name: ClassVar[str] = "Remote OK"
    min_interval_minutes: ClassVar[int] = 60
    max_requests_per_day: ClassVar[int] = 24
    URL: ClassVar[str] = "https://remoteok.com/api"

    async def fetch_jobs(self) -> list[WebJob]:
        data = (await self.get(self.URL)).json()
        if not isinstance(data, list):
            raise SourceError("Remote OK: kutilmagan javob")
        # data[0] is the legal notice, not a job
        return [self.parse(j) for j in data if isinstance(j, dict) and j.get("position")]

    @staticmethod
    def parse(j: dict[str, Any]) -> WebJob:
        location = j.get("location") or ""
        lo, hi = _int(j.get("salary_min")), _int(j.get("salary_max"))
        url = j.get("url") or ""
        return WebJob(
            id=str(j.get("id") or url),
            url=url,
            title=html_to_text(j.get("position"), 200),
            company=j.get("company"),
            location=location or None,
            description=html_to_text(j.get("description")),
            posted_at=parse_time(j.get("epoch") or j.get("date")),
            apply_url=j.get("apply_url") or url or None,
            salary_min=lo,
            salary_max=hi,
            currency="USD" if lo or hi else None,
            salary_period="year" if lo or hi else None,
            salary_text=_salary_text(lo, hi, "USD", "year"),
            is_remote=True,
            # an empty location on Remote OK says nothing -> not taken
            international=open_to_uzbekistan(location, empty_means_worldwide=False),
            tags=[str(t) for t in (j.get("tags") or [])][:5],
        )
