"""Common base of website / API / RSS sources (Bosqich 16).

* one ``httpx`` client per source, ``User-Agent: AyvonaJobsBot/1.0 (+https://t.me/ayvonajobs)``;
* every site keeps the limits of its terms IN CODE (``min_interval_minutes``,
  ``max_requests_per_day``): the admin's interval button (/sources) can only make polling rarer;
* HTTP 429 -> :class:`SourceRateLimited` (Retry-After or 1 hour), 5xx -> one retry, then error;
* items become :class:`RawItem` with the structured data in ``extra["web"]`` (pipeline uses it
  instead of guessing from text), the original URL, the apply link and the site name
  (the post ends with "manba: <site>" — the APIs' terms require it);
* international remote jobs: only those open to Uzbekistan (:func:`open_to_uzbekistan`).

Tests never reach the internet: they set :data:`TRANSPORT` to an ``httpx.MockTransport``.
"""

from __future__ import annotations

import asyncio
import html
import re
from abc import abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any, ClassVar

import httpx
from loguru import logger

from ayvona.config import Settings
from ayvona.sources.base import BaseSource, FetchResult, RawItem, SourceError, SourceRateLimited

# Tests: an httpx.MockTransport. Production: None (real network).
TRANSPORT: httpx.AsyncBaseTransport | None = None
DEFAULT_USER_AGENT = "AyvonaJobsBot/1.0 (+https://t.me/ayvonajobs)"
MAX_DESCRIPTION = 1500

# "Can someone in Uzbekistan apply?" — location words (lowercase)
_OPEN_WORDS = (
    "worldwide",
    "anywhere",
    "global",
    "remote - global",
    "uzbekistan",
    "o'zbekiston",
    "узбекистан",
    "central asia",
    "cis",
    "asia",
    "apac",
)


def open_to_uzbekistan(
    locations: list[str] | str | None,
    timezones: list[Any] | None = None,
    *,
    empty_means_worldwide: bool = False,
) -> bool:
    """Location / timezone restrictions of an international remote job allow Uzbekistan
    (UTC+5): Worldwide, Anywhere, Uzbekistan, Central Asia, CIS, Asia / APAC, or a timezone
    range that covers +5."""
    if isinstance(locations, str):
        locations = [p for p in re.split(r"[,;/|]", locations) if p.strip()]
    locs = [x.strip().lower() for x in (locations or []) if x and x.strip()]
    for loc in locs:
        if any(w in loc for w in _OPEN_WORDS):
            return True
    tz = [t for t in (timezones or []) if t not in (None, "")]
    for t in tz:
        if _covers_plus5(t):
            return True
    return not locs and not tz and empty_means_worldwide


def _covers_plus5(value: Any) -> bool:
    if isinstance(value, int | float):
        return float(value) == 5
    text = str(value).replace("−", "-").upper()
    if "TASHKENT" in text or "SAMARKAND" in text:
        return True
    nums = [
        float(n.replace(":30", ".5").replace(":00", ""))
        for n in re.findall(r"[+-]\d{1,2}(?::\d0)?", text)
    ]
    if len(nums) >= 2:
        return min(nums) <= 5 <= max(nums)
    return len(nums) == 1 and nums[0] == 5


_BLOCK_RE = re.compile(r"<\s*(br|/p|/div|/li|/h\d|/tr)\b[^>]*>", re.I)
_LI_RE = re.compile(r"<\s*li\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"[ \t ]+")


def html_to_text(value: str | None, limit: int = MAX_DESCRIPTION) -> str:
    """Job description HTML -> readable plain text (lines kept, at most ``limit`` chars)."""
    if not value:
        return ""
    text = _LI_RE.sub("\n• ", _BLOCK_RE.sub("\n", value))
    text = html.unescape(_TAG_RE.sub(" ", text))
    lines = [_SPACES_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    out = "\n".join(ln for ln in lines if ln)
    return out if len(out) <= limit else out[: limit - 1].rsplit(" ", 1)[0] + "…"


def parse_time(value: Any) -> datetime | None:
    """Unix seconds / ISO 8601 / RFC 822 (RSS) -> aware UTC datetime."""
    if value in (None, ""):
        return None
    if isinstance(value, int | float) or (isinstance(value, str) and value.isdigit()):
        n = float(value)
        if n > 1e12:  # milliseconds
            n /= 1000
        return datetime.fromtimestamp(n, UTC)
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        from email.utils import parsedate_to_datetime

        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# --------------------------------------------------------------------------- one job
@dataclass(slots=True)
class WebJob:
    """One job from a site, already in our words."""

    id: str
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    apply_url: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    salary_period: str | None = None  # month | year | week | day | hour
    salary_text: str | None = None
    is_remote: bool = False
    international: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def sort_key(self) -> int:
        return int(self.posted_at.timestamp()) if self.posted_at else 0

    def to_raw(self, site_name: str) -> RawItem:
        lines = [self.title]
        if self.company:
            lines.append(f"Company: {self.company}")
        if self.location:
            lines.append(f"Location: {self.location}")
        if self.salary_text:
            lines.append(f"Salary: {self.salary_text}")
        if self.description:
            lines += ["", self.description]
        web = asdict(self)
        web["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        return RawItem(
            external_id=self.id[:255],
            text="\n".join(lines),
            has_media=False,
            posted_at=self.posted_at,
            extra={
                "web": web,
                "url": self.url,
                "apply_url": self.apply_url or self.url,
                "source_name": site_name,
            },
        )


# --------------------------------------------------------------------------- base class
class WebSource(BaseSource):
    """A website / API source. Subclasses implement :meth:`fetch_jobs`."""

    type: ClassVar[str] = "web"
    site_name: ClassVar[str] = "?"
    # the site's terms, enforced here (the admin can only poll more rarely)
    min_interval_minutes: ClassVar[int] = 60
    max_requests_per_day: ClassVar[int] = 24
    international: ClassVar[bool] = False
    request_delay_seconds: ClassVar[float] = 0.0  # between requests of one poll (crawl-delay)

    def __init__(self, identifier: str, settings: Settings) -> None:
        super().__init__(identifier)
        self.settings = settings
        self.cfg = settings.app.web_sources
        self._client: httpx.AsyncClient | None = None
        self._day: date | None = None
        self._requests_today = 0

    # ------------------------------------------------------------------ http
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.cfg.user_agent or DEFAULT_USER_AGENT, "Accept": "*/*"}

    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.timeout_seconds,
                headers=self._headers(),
                follow_redirects=True,
                transport=TRANSPORT,
            )
        return self._client

    def _count_request(self) -> None:
        today = datetime.now(UTC).date()
        if self._day != today:
            self._day, self._requests_today = today, 0
        if self._requests_today >= self.max_requests_per_day:
            raise SourceError(
                f"{self.site_name}: kunlik so'rov chegarasi ({self.max_requests_per_day}) tugadi"
            )
        self._requests_today += 1

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """GET with the site's limits; 429 -> SourceRateLimited, 5xx -> one retry."""
        for attempt in range(2):
            self._count_request()
            if self.request_delay_seconds and self._requests_today > 1:
                await asyncio.sleep(self.request_delay_seconds)
            try:
                resp = await self.client().get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                if attempt:
                    raise SourceError(f"{self.site_name}: tarmoq xatosi: {e}") from e
                await asyncio.sleep(5)
                continue
            if resp.status_code == 429:
                retry = resp.headers.get("Retry-After", "")
                raise SourceRateLimited(float(retry) if retry.isdigit() else 3600)
            if resp.status_code >= 500 and not attempt:
                await asyncio.sleep(5)
                continue
            if resp.status_code >= 400:
                raise SourceError(f"{self.site_name}: HTTP {resp.status_code} ({url})")
            return resp
        raise SourceError(f"{self.site_name}: javob yo'q ({url})")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ polling
    @abstractmethod
    async def fetch_jobs(self) -> list[WebJob]:
        """The newest jobs of the site (any order); may raise SourceError."""

    def accept(self, job: WebJob) -> bool:  # noqa: ARG002 — subclasses filter
        return True

    async def fetch_new(self, since: str | None) -> FetchResult:
        """Jobs newer than the cursor (``last_seen_id`` = publication time, Unix seconds),
        oldest first. The first poll (``since=None``) stores them as history (not published,
        ``publisher.publish_backfill``)."""
        jobs = [j for j in await self.fetch_jobs() if j.title and j.url and self.accept(j)]
        jobs.sort(key=lambda j: (j.sort_key, j.id))
        cursor = int(since) if since and since.isdigit() else None
        fresh = [j for j in jobs if cursor is None or j.sort_key > cursor]
        fresh = fresh[-self.cfg.fetch_limit :]
        newest = max((j.sort_key for j in jobs), default=0)
        if fresh or jobs:
            logger.debug("{}: {} ta yangi (jami {})", self.site_name, len(fresh), len(jobs))
        return FetchResult(
            items=[j.to_raw(self.site_name) for j in fresh],
            cursor=str(max(newest, cursor or 0)) if jobs else None,
        )


@dataclass(frozen=True, slots=True)
class WebSiteInfo:
    """A site we have code for (/addsource web:<key>)."""

    key: str  # "web:himalayas"
    title: str
    cls: type[WebSource]
    note: str = ""

    def unavailable(self, settings: Settings) -> str | None:
        """Why it cannot run now (missing token...), or ``None``."""
        check = getattr(self.cls, "unavailable", None)
        return check(settings) if check else None
