"""Any RSS 2.0 / Atom feed (/addsource rss:<URL>) — no code per site (Bosqich 16.0).

The feed's items go through the normal pipeline (classify decides if an item is a job ad; a feed
can be anything). Cursor: the newest publication time; feeds without dates use the newest item's
id ("id:<sha1>") and take what is above it.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import ClassVar

from ayvona.config import Settings
from ayvona.sources.base import FetchResult, SourceError
from ayvona.sources.web.base import WebJob, WebSource, html_to_text, parse_time

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


@dataclass(frozen=True, slots=True)
class Feed:
    title: str
    jobs: list[WebJob]


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_feed(xml_text: str) -> Feed:
    """RSS 2.0 or Atom -> title + items. Raises SourceError if it is not a feed."""
    try:
        root = ET.fromstring(xml_text.strip().encode())
    except ET.ParseError as e:
        raise SourceError(f"RSS emas (XML xato): {e}") from e
    jobs: list[WebJob] = []
    if root.tag == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is None:
            raise SourceError("RSS: <channel> yo'q")
        title = _text(channel.find("title"))
        for item in channel.findall("item"):
            link = _text(item.find("link"))
            guid = _text(item.find("guid")) or link
            body = _text(item.find(CONTENT)) or _text(item.find("description"))
            jobs.append(
                WebJob(
                    id=_id(guid or _text(item.find("title"))),
                    url=link,
                    title=html_to_text(_text(item.find("title")), 200),
                    description=html_to_text(body),
                    posted_at=parse_time(_text(item.find("pubDate"))),
                    apply_url=link,
                )
            )
    elif root.tag == f"{ATOM}feed":
        title = _text(root.find(f"{ATOM}title"))
        for entry in root.findall(f"{ATOM}entry"):
            link_el = entry.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:  # (an Element without children is falsy: no "or" here)
                link_el = entry.find(f"{ATOM}link")
            link = link_el.get("href", "") if link_el is not None else ""
            body = _text(entry.find(f"{ATOM}content")) or _text(entry.find(f"{ATOM}summary"))
            when = _text(entry.find(f"{ATOM}published")) or _text(entry.find(f"{ATOM}updated"))
            jobs.append(
                WebJob(
                    id=_id(_text(entry.find(f"{ATOM}id")) or link),
                    url=link,
                    title=html_to_text(_text(entry.find(f"{ATOM}title")), 200),
                    description=html_to_text(body),
                    posted_at=parse_time(when),
                    apply_url=link,
                )
            )
    else:
        raise SourceError(f"RSS/Atom emas (<{root.tag}>)")
    return Feed(title=title or "RSS", jobs=jobs)


def _id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]


class RssSource(WebSource):
    type: ClassVar[str] = "rss"
    site_name: ClassVar[str] = "RSS"
    min_interval_minutes: ClassVar[int] = 15
    max_requests_per_day: ClassVar[int] = 96

    def __init__(self, identifier: str, settings: Settings, title: str | None = None) -> None:
        super().__init__(identifier, settings)
        self.url = identifier.removeprefix("rss:")
        self.feed_title = title

    @property
    def name(self) -> str:
        return self.feed_title or self.url.split("//", 1)[-1].split("/", 1)[0]

    async def fetch_jobs(self) -> list[WebJob]:
        resp = await self.get(self.url)
        return parse_feed(resp.text).jobs

    async def fetch_new(self, since: str | None) -> FetchResult:
        jobs = [j for j in await self.fetch_jobs() if j.title and j.url]
        if jobs and all(j.posted_at for j in jobs):
            result = await self._by_time(jobs, since)
        else:  # no dates: the feed's order (newest first) and the newest item's id
            ids = [j.id for j in jobs]
            mark = since.removeprefix("id:") if since and since.startswith("id:") else None
            fresh = jobs[: ids.index(mark)] if mark in ids else jobs
            fresh = list(reversed(fresh[: self.cfg.fetch_limit]))
            result = FetchResult(
                items=[j.to_raw(self.name) for j in fresh],
                cursor=f"id:{jobs[0].id}" if jobs else None,
            )
        return result

    async def _by_time(self, jobs: list[WebJob], since: str | None) -> FetchResult:
        jobs.sort(key=lambda j: (j.sort_key, j.id))
        cursor = int(since) if since and since.isdigit() else None
        fresh = [j for j in jobs if cursor is None or j.sort_key > cursor][-self.cfg.fetch_limit :]
        newest = max(j.sort_key for j in jobs)
        return FetchResult(
            items=[j.to_raw(self.name) for j in fresh], cursor=str(max(newest, cursor or 0))
        )
