"""Bosqich 16: website / API / RSS sources with SAVED answers (tests/fixtures/web/) — the
internet is never reached (conftest blocks it; each test installs a MockTransport).
Also the collector interval, the pipeline (site name, apply button, international cap) and
/addsource rss: / web:."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from ayvona.apps.collector import ActiveSource, SourcePool
from ayvona.config import Settings
from ayvona.db.models import Job, RawPost, RawPostStatus, Source, SourceStatus
from ayvona.processing.pipeline import Pipeline
from ayvona.sources.base import SourceError, SourceRateLimited
from ayvona.sources.registry import SourceDeps
from ayvona.sources.web import SITES
from ayvona.sources.web import base as web_base
from ayvona.sources.web.base import html_to_text, open_to_uzbekistan, parse_time
from ayvona.sources.web.remote_apis import (
    HimalayasSource,
    JobicySource,
    RemoteOkSource,
    RemotiveSource,
)
from ayvona.sources.web.rss import RssSource, parse_feed
from ayvona.sources.web.uzbek_sites import HhUzSource, OsonIshSource
from tests.test_admin_bot import BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, make_settings

FIX = Path(__file__).parent / "fixtures" / "web"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Routes:
    """A MockTransport answering from saved files by URL (without the query); records requests."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url).split("?", 1)[0]
        answer = self.routes.get(url)
        if answer is None:
            return httpx.Response(404, text="not found")
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, text=fixture(answer))


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any]], Routes]:
    def install(routes: dict[str, Any]) -> Routes:
        r = Routes(routes)
        monkeypatch.setattr(web_base, "TRANSPORT", httpx.MockTransport(r))
        return r

    return install


def settings(**web_cfg: Any) -> Settings:
    s = make_settings(publisher={"hold_minutes": 0})
    app = s.app.model_copy(update={"web_sources": s.app.web_sources.model_copy(update=web_cfg)})
    return s.model_copy(update={"app": app})


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize(
    ("locations", "timezones", "empty_ok", "expected"),
    [
        ([], [], True, True),
        ([], [], False, False),
        (["Worldwide"], [], False, True),
        (["USA Only"], [], False, False),
        ("Europe, Central Asia", None, False, True),
        (["Uzbekistan"], [], False, True),
        (["United States"], [-8, -5], True, False),
        ([], [3, 4, 5, 6], False, True),
        ([], ["UTC+3 - UTC+7"], False, True),
        ([], ["UTC-5"], False, False),
        (["APAC"], [], False, True),
    ],
)
def test_open_to_uzbekistan(locations: Any, timezones: Any, empty_ok: bool, expected: bool) -> None:
    assert open_to_uzbekistan(locations, timezones, empty_means_worldwide=empty_ok) is expected


def test_html_and_time_helpers() -> None:
    text = html_to_text("<p>Salom <b>dunyo</b></p><ul><li>bir</li><li>ikki</li></ul>&amp; x")
    assert text == "Salom dunyo\n• bir\n• ikki\n& x"
    assert parse_time(1790001000) == datetime.fromtimestamp(1790001000, UTC)
    assert parse_time("Wed, 30 Sep 2026 08:00:00 +0500") == datetime(2026, 9, 30, 3, tzinfo=UTC)
    assert parse_time("2026-09-30T10:00:00+0500") == datetime(2026, 9, 30, 5, tzinfo=UTC)
    assert parse_time("garbage") is None and parse_time(None) is None


# ------------------------------------------------------------------ international APIs
async def test_himalayas(web: Callable[[dict[str, Any]], Routes]) -> None:
    routes = web({HimalayasSource.URL: "himalayas.json"})
    src = HimalayasSource("web:himalayas", settings())
    first = await src.fetch_new(None)
    titles = [i.text.split("\n")[0] for i in first.items]
    assert titles == ["Senior Python Developer", "Data Analyst"]  # US-only one dropped
    assert first.cursor == "1790003000"
    item = first.items[0]
    assert item.extra and item.extra["source_name"] == "Himalayas"
    assert item.extra["url"].startswith("https://himalayas.app/")  # link back to Himalayas
    assert item.extra["apply_url"] == "https://acme.example/careers/python"
    assert item.extra["web"]["salary_min"] == 60000 and item.extra["web"]["international"]
    assert routes.requests[0].headers["User-Agent"].startswith("AyvonaJobsBot/1.0")
    assert routes.requests[0].url.params["limit"] == "20"
    again = await src.fetch_new(first.cursor)
    assert again.items == [] and again.cursor == "1790003000"
    await src.close()


async def test_remotive_jobicy_remoteok(web: Callable[[dict[str, Any]], Routes]) -> None:
    web(
        {
            RemotiveSource.URL: "remotive.json",
            JobicySource.URL: "jobicy.json",
            RemoteOkSource.URL: "remoteok.json",
        }
    )
    s = settings()
    remotive = await RemotiveSource("web:remotive", s).fetch_new(None)
    assert [i.external_id for i in remotive.items] == ["2001", "2003"]  # "USA Only" dropped
    jobicy = await JobicySource("web:jobicy", s).fetch_new(None)
    assert [i.external_id for i in jobicy.items] == ["3001"]  # Canada dropped
    assert jobicy.items[0].extra["web"]["salary_max"] == 42000  # type: ignore[index]
    remoteok = await RemoteOkSource("web:remoteok", s).fetch_new(None)
    # the legal notice is not a job; an empty location is not "worldwide"
    assert [i.external_id for i in remoteok.items] == ["4001"]
    assert remoteok.items[0].extra["source_name"] == "Remote OK"  # type: ignore[index]


async def test_site_limits_in_code(web: Callable[[dict[str, Any]], Routes]) -> None:
    web({RemotiveSource.URL: "remotive.json"})
    src = RemotiveSource("web:remotive", settings())
    for _ in range(4):  # "max. 4 times a day"
        await src.fetch_new(None)
    with pytest.raises(SourceError, match="kunlik"):
        await src.fetch_new(None)
    assert RemotiveSource.min_interval_minutes == 360 and JobicySource.min_interval_minutes == 60


async def test_429_and_errors(web: Callable[[dict[str, Any]], Routes]) -> None:
    web({HimalayasSource.URL: httpx.Response(429, headers={"Retry-After": "120"})})
    with pytest.raises(SourceRateLimited) as e:
        await HimalayasSource("web:himalayas", settings()).fetch_new(None)
    assert e.value.seconds == 120
    web({JobicySource.URL: httpx.Response(403)})
    with pytest.raises(SourceError, match="403"):
        await JobicySource("web:jobicy", settings()).fetch_new(None)


# ------------------------------------------------------------------ Uzbek sites
async def test_hh_needs_a_token_then_works(web: Callable[[dict[str, Any]], Routes]) -> None:
    s = settings()
    assert "HH_ACCESS_TOKEN" in (HhUzSource.unavailable(s) or "")
    with pytest.raises(SourceError):
        HhUzSource("web:hh_uz", s)

    env = s.env.model_copy(
        update={"hh_access_token": SecretStr("APP-TOKEN"), "hh_user_agent": "Ayvona/1.0 (a@b.uz)"}
    )
    s2 = s.model_copy(update={"env": env})
    routes = web({HhUzSource.URL: "hh_vacancies.json"})
    result = await HhUzSource("web:hh_uz", s2).fetch_new(None)
    req = routes.requests[0]
    assert req.headers["Authorization"] == "Bearer APP-TOKEN"
    assert req.headers["HH-User-Agent"] == "Ayvona/1.0 (a@b.uz)"
    assert req.url.params["area"] == "97" and req.url.params["host"] == "hh.uz"
    first = result.items[0]
    assert first.text.startswith("Бухгалтер") and "1С" in first.text
    assert first.extra["web"]["salary_min"] == 6_000_000  # type: ignore[index]
    assert first.extra["apply_url"].startswith("https://hh.uz/applicant/")  # type: ignore[index]


async def test_osonish_reads_only_sitemap_and_vacancy_pages(
    web: Callable[[dict[str, Any]], Routes], monkeypatch: pytest.MonkeyPatch
) -> None:
    routes = web(
        {
            OsonIshSource.SITEMAP: "osonish_sitemap_index.xml",
            "https://osonish.uz/sitemap-vacancies.xml": "osonish_sitemap_vacancies.xml",
            "https://osonish.uz/vacancies/701": "osonish_vacancy_ld.html",
            "https://osonish.uz/vacancies/702": "osonish_vacancy_og.html",
        }
    )
    src = OsonIshSource("web:osonish", settings())
    monkeypatch.setattr(src, "request_delay_seconds", 0)  # robots.txt delay, not needed here
    result = await src.fetch_new(None)
    urls = [str(r.url) for r in routes.requests]
    assert not any("/api/" in u for u in urls)  # robots.txt: /api/ is off limits
    assert "https://osonish.uz/sitemap-pages.xml" not in urls  # only the vacancies' sitemap
    nurse, guard = result.items
    assert nurse.text.startswith("Hamshira") and "Samarqand viloyati" in nurse.text
    assert nurse.extra["web"]["company"].startswith("Samarqand")  # type: ignore[index]
    assert guard.text.startswith("Qorovul") and "Zarafshon" in guard.text
    assert OsonIshSource.request_delay_seconds == 1.0


# ------------------------------------------------------------------ RSS
async def test_rss_atom_and_feeds_without_dates(web: Callable[[dict[str, Any]], Routes]) -> None:
    web(
        {
            "https://jobs.example.uz/feed": "feed_rss.xml",
            "https://atom.example.uz/feed": "feed_atom.xml",
            "https://n.example.uz/feed": "feed_nodates.xml",
        }
    )
    s = settings()
    rss = RssSource("rss:https://jobs.example.uz/feed", s, title="Namuna")
    first = await rss.fetch_new(None)
    assert [i.text.split("\n")[0] for i in first.items] == ["Sotuvchi kerak", "Oshpaz kerak"]
    assert (await rss.fetch_new(first.cursor)).items == []
    atom = await RssSource("rss:https://atom.example.uz/feed", s).fetch_new(None)
    assert atom.items[0].extra["url"] == "https://atom.example.uz/jobs/21"  # type: ignore[index]

    nodates = RssSource("rss:https://n.example.uz/feed", s)
    r1 = await nodates.fetch_new(None)
    assert [i.text for i in r1.items] == ["Birinchi", "Ikkinchi", "Uchinchi"]  # oldest first
    assert r1.cursor and r1.cursor.startswith("id:")
    assert (await nodates.fetch_new(r1.cursor)).items == []


def test_not_a_feed() -> None:
    with pytest.raises(SourceError):
        parse_feed("<html><body>hi</body></html>")


# ------------------------------------------------------------------ collector interval
async def test_web_sources_are_polled_by_their_interval(session_factory: SF) -> None:
    async with session_factory() as s, s.begin():
        s.add(Source(identifier="web:remotive", type="web:remotive", check_interval_minutes=15))
        s.add(Source(identifier="web:jobicy", type="web:jobicy", check_interval_minutes=120))
    pool = SourcePool(
        session_factory, SourceDeps(collector=settings().app.collector, settings=settings())
    )
    active = {a.source.identifier: a for a in await pool.refresh()}
    # the site's terms win over a too short admin interval
    assert active["web:remotive"].interval == timedelta(minutes=360)
    assert active["web:jobicy"].interval == timedelta(minutes=120)
    now = datetime.now(UTC)
    a = active["web:jobicy"]
    assert a.due(now)  # never checked
    a.last_checked = now - timedelta(minutes=30)
    assert not a.due(now)
    assert ActiveSource(1, a.source).due(now)  # Telegram-like: every cycle
    await pool.close()


# ------------------------------------------------------------------ pipeline
async def _web_raw(sf: SF, source_type: str, item: Any) -> int:
    async with sf() as s, s.begin():
        src = Source(identifier=source_type, type=source_type)
        s.add(src)
        await s.flush()
        row = RawPost(
            source_id=src.id,
            external_id=item.external_id,
            text=item.text,
            extra=item.extra,
            posted_at=datetime.now(UTC) - timedelta(minutes=5),
            fetched_at=datetime.now(UTC) - timedelta(minutes=2),
        )
        s.add(row)
        await s.flush()
        return row.id


async def test_pipeline_web_job_has_site_name_and_apply_button(
    session_factory: SF, web: Callable[[dict[str, Any]], Routes]
) -> None:
    web({HimalayasSource.URL: "himalayas.json"})
    items = (await HimalayasSource("web:himalayas", settings()).fetch_new(None)).items
    await _web_raw(session_factory, "web:himalayas", items[0])
    await Pipeline(settings(), session_factory).run_once()
    async with session_factory() as s:
        job = (await s.scalars(select(Job))).one()
    text = job.formatted_text or ""
    assert 'manba: <a href="https://himalayas.app/companies/acme-remote/jobs/' in text
    assert ">Himalayas</a>" in text
    assert "#masofaviy" in text and "#xalqaro" in text and "Masofaviy" in text
    assert "5 000 – 7 000 $" in text  # 60–84k a year -> per month
    assert not any("Ѐ" <= ch <= "ӿ" for ch in text)
    urls = [b["url"] for row in job.buttons or [] for b in row]
    assert "https://acme.example/careers/python" in urls  # 🔗 Ariza topshirish


async def test_international_daily_cap(
    session_factory: SF, web: Callable[[dict[str, Any]], Routes]
) -> None:
    web({HimalayasSource.URL: "himalayas.json"})
    items = (await HimalayasSource("web:himalayas", settings()).fetch_new(None)).items
    async with session_factory() as s, s.begin():
        src = Source(identifier="web:himalayas", type="web:himalayas")
        s.add(src)
        await s.flush()
        for i, item in enumerate(items):
            s.add(
                RawPost(
                    source_id=src.id,
                    external_id=item.external_id,
                    text=item.text,
                    extra=item.extra,
                    posted_at=datetime.now(UTC) - timedelta(minutes=5 + i),
                    fetched_at=datetime.now(UTC) - timedelta(minutes=2),
                )
            )
    await Pipeline(settings(max_international_per_day=1), session_factory).run_once()
    async with session_factory() as s:
        statuses = sorted(str(r.status) for r in (await s.scalars(select(RawPost))).all())
        jobs = (await s.scalars(select(Job))).all()
    assert len(jobs) == 1 and statuses == ["done", "skipped_limit"]


async def test_rss_items_are_classified_normally(
    session_factory: SF, web: Callable[[dict[str, Any]], Routes]
) -> None:
    web({"https://jobs.example.uz/feed": "feed_rss.xml"})
    items = (await RssSource("rss:https://jobs.example.uz/feed", settings()).fetch_new(None)).items
    await _web_raw(session_factory, "rss", items[0])
    await Pipeline(settings(), session_factory).run_once()
    async with session_factory() as s:
        job = (await s.scalars(select(Job))).one()
        row = (await s.scalars(select(RawPost))).one()
    assert row.status is RawPostStatus.DONE and job.contact_phone == "+998901234567"
    assert 'manba: <a href="https://jobs.example.uz/vacancy/11">' in (job.formatted_text or "")


# ------------------------------------------------------------------ /addsource
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


async def test_addsource_rss_flow(
    harness: BotHarness, session_factory: SF, web: Callable[[dict[str, Any]], Routes]
) -> None:
    web({"https://jobs.example.uz/feed": "feed_rss.xml"})
    await harness.send(message_update("/addsource rss:https://jobs.example.uz/feed"))
    assert "Namuna ish e&#x27;lonlari" in harness.texts()[-1]  # the feed title, escaped
    assert "2 ta yozuv" in harness.texts()[-1]
    await harness.send(callback_update("rss:add"))
    assert harness.texts()[-1].startswith("✅ RSS qo'shildi")
    async with session_factory() as s:
        src = (await s.scalars(select(Source))).one()
    assert src.type == "rss" and src.identifier == "rss:https://jobs.example.uz/feed"
    assert src.status is SourceStatus.ACTIVE and src.enabled and src.title == "Namuna ish e'lonlari"

    await harness.send(message_update("/addsource rss:https://jobs.example.uz/missing"))
    assert harness.texts()[-1].startswith("❌ Lentani o'qib bo'lmadi")


async def test_addsource_web_sites(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update("/addsource web:remotive"))
    reply = harness.texts()[-1]
    assert "Remotive" in reply and "360 daqiqada" in reply  # the site's minimum
    await harness.send(message_update("/addsource web:osonish"))
    assert "tekshirilmagan" in harness.texts()[-1]
    await harness.send(message_update("/addsource web:hh_uz"))
    assert "HH_ACCESS_TOKEN" in harness.texts()[-1]
    async with session_factory() as s:
        idents = sorted(r.identifier for r in (await s.scalars(select(Source))).all())
    assert idents == ["web:osonish", "web:remotive"]
    assert set(SITES) >= {"web:himalayas", "web:remotive", "web:jobicy", "web:remoteok"}
    await harness.send(message_update("/addsource"))
    assert "web:himalayas" in harness.texts()[-1]  # the usage lists the sites
