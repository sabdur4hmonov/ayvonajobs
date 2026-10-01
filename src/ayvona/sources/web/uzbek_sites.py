"""Uzbek job sites (docs/WEB_SOURCES.md, A).

**Oson Ish** (osonish.uz, the state employment system). robots.txt (read 2026-10-01): pages
allowed, ``/api/`` and ``/admin/`` disallowed, ``Crawl-delay: 1``, ``Sitemap:
https://osonish.uz/sitemap.xml``. So we read ONLY the sitemap (vacancy URLs + dates) and the
vacancy pages themselves, one request per second, at most ``web_sources.osonish_max_pages`` pages
per poll, every 30 minutes. A page is understood from its JSON-LD ``JobPosting`` (Google Jobs
markup) or, failing that, its title / Open Graph tags. ⚠️ Written without a live page (only
saved samples): check the first results after ``/addsource web:osonish``.

**hh.uz** (HeadHunter). Official API ``https://api.hh.ru/vacancies`` (``host=hh.uz``,
``area=97`` Uzbekistan). Needs a registered application (dev.hh.ru): ``HH_ACCESS_TOKEN`` and
``HH_USER_AGENT`` in .env — without them the source refuses to start (docs/PROGRESS.md,
"Sardor uchun").
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

from ayvona.config import Settings
from ayvona.sources.base import SourceError
from ayvona.sources.web.base import WebJob, WebSource, html_to_text, parse_time

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?P<k>og:title|og:description|description)["\'][^>]*'
    r'content=["\'](?P<v>[^"\']*)["\']',
    re.I,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_VACANCY_URL_RE = re.compile(r"/vacanc(?:y|ies)/[\w-]+/?$", re.I)


def _walk_ld(data: Any) -> dict[str, Any] | None:
    """The JobPosting object in a JSON-LD block (it may be nested in @graph / lists)."""
    if isinstance(data, list):
        for x in data:
            if found := _walk_ld(x):
                return found
    elif isinstance(data, dict):
        kind = data.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            return data
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data and (found := _walk_ld(data[key])):
                return found
    return None


def parse_vacancy_page(html_text: str, url: str) -> WebJob | None:
    """One osonish.uz vacancy page -> WebJob (JSON-LD JobPosting, else title/OG tags)."""
    for block in _LD_RE.findall(html_text):
        try:
            posting = _walk_ld(json.loads(block.strip()))
        except ValueError:
            continue
        if posting:
            org = posting.get("hiringOrganization") or {}
            place = posting.get("jobLocation") or {}
            if isinstance(place, list):
                place = place[0] if place else {}
            address = (place.get("address") or {}) if isinstance(place, dict) else {}
            locality = (
                ", ".join(
                    str(address.get(k))
                    for k in ("addressRegion", "addressLocality")
                    if address.get(k)
                )
                if isinstance(address, dict)
                else ""
            )
            salary = posting.get("baseSalary") or {}
            value = salary.get("value") if isinstance(salary, dict) else None
            lo = hi = None
            if isinstance(value, dict):
                lo, hi = value.get("minValue") or value.get("value"), value.get("maxValue")
            currency = salary.get("currency") if isinstance(salary, dict) else None
            text = []
            for part in (lo, hi):
                if part:
                    text.append(f"{int(float(part)):,}".replace(",", " "))
            return WebJob(
                id=url.rstrip("/").rsplit("/", 1)[-1],
                url=url,
                title=html_to_text(str(posting.get("title") or ""), 200),
                company=(org.get("name") if isinstance(org, dict) else None) or None,
                location=locality or None,
                description=html_to_text(str(posting.get("description") or "")),
                posted_at=parse_time(posting.get("datePosted")),
                apply_url=url,
                salary_text=(" – ".join(text) + f" {currency or 'UZS'}") if text else None,
            )
    meta = {m.group("k").lower(): m.group("v") for m in _META_RE.finditer(html_text)}
    title = meta.get("og:title") or "".join(_TITLE_RE.findall(html_text)[:1])
    title = html_to_text(title, 200)
    if not title:
        return None
    return WebJob(
        id=url.rstrip("/").rsplit("/", 1)[-1],
        url=url,
        title=title,
        description=html_to_text(meta.get("og:description") or meta.get("description") or ""),
        apply_url=url,
    )


def parse_sitemap(xml_text: str) -> tuple[list[str], list[tuple[str, str | None]]]:
    """-> (child sitemaps, [(page url, lastmod)])."""
    try:
        root = ET.fromstring(xml_text.strip().encode())
    except ET.ParseError as e:
        raise SourceError(f"Oson Ish: sitemap o'qilmadi: {e}") from e
    children = [
        (el.findtext(f"{SITEMAP_NS}loc") or "").strip()
        for el in root.findall(f"{SITEMAP_NS}sitemap")
    ]
    pages = [
        ((el.findtext(f"{SITEMAP_NS}loc") or "").strip(), el.findtext(f"{SITEMAP_NS}lastmod"))
        for el in root.findall(f"{SITEMAP_NS}url")
    ]
    return [c for c in children if c], [(u, m) for u, m in pages if u]


class OsonIshSource(WebSource):
    site_name: ClassVar[str] = "Oson Ish"
    min_interval_minutes: ClassVar[int] = 30
    max_requests_per_day: ClassVar[int] = 1500  # 48 polls x (sitemap + ≤ 20 pages) + margin
    request_delay_seconds: ClassVar[float] = 1.0  # robots.txt Crawl-delay: 1
    SITEMAP: ClassVar[str] = "https://osonish.uz/sitemap.xml"

    async def fetch_jobs(self) -> list[WebJob]:
        children, pages = parse_sitemap((await self.get(self.SITEMAP)).text)
        for child in children:
            if "vacanc" in child.lower():  # only the vacancies' sitemap(s)
                pages += parse_sitemap((await self.get(child)).text)[1]
        pages = [(u, m) for u, m in pages if _VACANCY_URL_RE.search(u) and "/api/" not in u]
        pages.sort(key=lambda p: parse_time(p[1]).timestamp() if parse_time(p[1]) else 0)
        newest = pages[-self.cfg.osonish_max_pages :]
        jobs: list[WebJob] = []
        for url, lastmod in newest:
            job = parse_vacancy_page((await self.get(url)).text, url)
            if job is None:
                continue
            if job.posted_at is None:
                job.posted_at = parse_time(lastmod)
            jobs.append(job)
        return jobs


class HhUzSource(WebSource):
    site_name: ClassVar[str] = "hh.uz"
    min_interval_minutes: ClassVar[int] = 30
    max_requests_per_day: ClassVar[int] = 200
    URL: ClassVar[str] = "https://api.hh.ru/vacancies"
    AREA_UZBEKISTAN: ClassVar[int] = 97

    @staticmethod
    def unavailable(settings: Settings) -> str | None:
        env = settings.env
        if not env.hh_access_token:
            return (
                "hh.uz uchun .env da HH_ACCESS_TOKEN yo'q (dev.hh.ru da ilova ro'yxatdan o'tkazing)"
            )
        if not env.hh_user_agent:
            return "hh.uz uchun .env da HH_USER_AGENT yo'q (masalan: AyvonaJobs/1.0 (email))"
        return None

    def __init__(self, identifier: str, settings: Settings) -> None:
        if reason := self.unavailable(settings):
            raise SourceError(reason)
        super().__init__(identifier, settings)

    def _headers(self) -> dict[str, str]:
        env = self.settings.env
        assert env.hh_access_token is not None
        return {
            "User-Agent": env.hh_user_agent,
            "HH-User-Agent": env.hh_user_agent,
            "Authorization": f"Bearer {env.hh_access_token.get_secret_value()}",
        }

    async def fetch_jobs(self) -> list[WebJob]:
        params = {
            "area": self.AREA_UZBEKISTAN,
            "host": "hh.uz",
            "per_page": 50,
            "order_by": "publication_time",
        }
        data = (await self.get(self.URL, params=params)).json()
        return [self.parse(v) for v in (data.get("items") or []) if isinstance(v, dict)]

    @staticmethod
    def parse(v: dict[str, Any]) -> WebJob:
        salary = v.get("salary") or {}
        lo, hi = salary.get("from"), salary.get("to")
        currency = {"RUR": "RUB", "SUM": "UZS"}.get(salary.get("currency"), salary.get("currency"))
        snippet = v.get("snippet") or {}
        parts = [snippet.get("responsibility"), snippet.get("requirement")]
        schedule = (v.get("schedule") or {}).get("name")
        amount = " – ".join(f"{int(x):,}".replace(",", " ") for x in (lo, hi) if x)
        url = v.get("alternate_url") or ""
        return WebJob(
            id=str(v.get("id") or url),
            url=url,
            title=html_to_text(v.get("name"), 200),
            company=(v.get("employer") or {}).get("name"),
            location=(v.get("area") or {}).get("name"),
            description=html_to_text(
                "\n".join(p for p in [*parts, f"График: {schedule}" if schedule else None] if p)
            ),
            posted_at=parse_time(v.get("published_at")),
            apply_url=v.get("apply_alternate_url") or url or None,
            salary_min=int(lo) if lo else None,
            salary_max=int(hi) if hi else None,
            currency=currency if (lo or hi) else None,
            salary_period="month" if (lo or hi) else None,
            salary_text=f"{amount} {currency}" if amount else None,
        )
