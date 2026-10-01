"""Bosqich 17: the read-only website (FastAPI + Jinja2) through ASGI — no network, no server."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update

from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin, JobStatus, RawPost, Source
from ayvona.services.jobs_public import slug
from ayvona.timeutil import utcnow
from ayvona.web.app import create_app
from tests.test_search import job
from tests.worker_helpers import SF, make_settings


def site_settings() -> Settings:
    s = make_settings()
    app = s.app.model_copy(
        update={"website": s.app.website.model_copy(update={"base_url": "https://ayvona.test"})}
    )
    return s.model_copy(update={"app": app})


@pytest.fixture
async def client(session_factory: SF) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(site_settings(), session_factory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


def ld(page: str) -> dict[str, Any] | None:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else None


async def test_slug() -> None:
    assert slug("Sotuv menejeri") == "sotuv-menejeri"
    assert slug("Оʻқитувчи (ingliz tili)!") == "oqituvchi-ingliz-tili"
    assert slug("") == "ish"


async def test_home_lists_open_jobs(client: httpx.AsyncClient, session_factory: SF) -> None:
    await job(
        session_factory, "Sotuvchi", region="toshkent_sh", salary_min=5_000_000, currency="UZS"
    )
    await job(session_factory, "Yopilgan ish", status=JobStatus.CLOSED)
    await job(session_factory, "Navbatdagi", status=JobStatus.QUEUED)
    r = await client.get("/")
    assert r.status_code == 200
    assert "Sotuvchi" in r.text and "5 000 000 so" in r.text
    assert "Yopilgan ish" not in r.text and "Navbatdagi" not in r.text
    assert '<link rel="canonical" href="https://ayvona.test/">' in r.text


async def test_search_filters_and_pages(client: httpx.AsyncClient, session_factory: SF) -> None:
    for i in range(25):
        await job(session_factory, f"Kassir {i}", minutes_ago=i, region="samarqand")
    await job(session_factory, "Oshpaz", category="oshxona", region="toshkent_sh")
    r = await client.get("/ish", params={"soha": "sotuv", "hudud": "samarqand"})
    assert "25 ta e'lon" in r.text and "Kassir 0" in r.text and "Oshpaz" not in r.text
    assert "sahifa=2" in r.text
    r2 = await client.get("/ish", params={"soha": "sotuv", "hudud": "samarqand", "sahifa": 2})
    assert "Kassir 24" in r2.text and "Kassir 0" not in r2.text
    r3 = await client.get("/ish", params={"q": "ОШПАЗ"})  # Cyrillic query, Latin job
    assert "1 ta e'lon" in r3.text and "Oshpaz" in r3.text
    assert (await client.get("/soha/oshxona")).status_code == 200
    assert (await client.get("/hudud/remote")).status_code == 200
    assert (await client.get("/soha/yoq")).status_code == 404


async def test_job_page_seo_and_redirect(client: httpx.AsyncClient, session_factory: SF) -> None:
    job_id = await job(
        session_factory,
        "Sotuv menejeri",
        company="Texnomart",
        region="toshkent_sh",
        salary_min=6_000_000,
        currency="UZS",
        expires_at=utcnow() + timedelta(days=20),
        origin=JobOrigin.USER,
        contact_phone="+998901234567",
        buttons=[[{"text": "📩 Murojaat", "url": "https://t.me/hr"}]],
    )
    r = await client.get(f"/ish/{job_id}", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == f"/ish/{job_id}-sotuv-menejeri"
    page = (await client.get(f"/ish/{job_id}-sotuv-menejeri")).text
    assert "<h1>Sotuv menejeri</h1>" in page and "📩 Murojaat" in page
    assert f"t.me/ayvona_jobs_bot?start=save_{job_id}" in page
    data = ld(page)
    assert data is not None and data["@type"] == "JobPosting"
    assert data["hiringOrganization"]["name"] == "Texnomart"
    assert data["baseSalary"]["value"]["minValue"] == 6_000_000
    assert "validThrough" in data and data["jobLocation"]["address"]["addressRegion"]
    assert f"https://ayvona.test/ish/{job_id}-sotuv-menejeri" in page  # canonical


async def test_no_job_posting_markup_for_web_sources(
    client: httpx.AsyncClient, session_factory: SF
) -> None:
    """Himalayas / Remotive forbid Google Jobs: their jobs get no JobPosting markup."""
    async with session_factory() as s, s.begin():
        src = Source(identifier="web:himalayas", type="web:himalayas")
        s.add(src)
        await s.flush()
        raw = RawPost(
            source_id=src.id, external_id="x1", text="Python Developer", fetched_at=utcnow()
        )
        s.add(raw)
        await s.flush()
        raw_id = raw.id
    job_id = await job(session_factory, "Python Developer", category="it", raw_post_id=raw_id)
    page = (await client.get(f"/ish/{job_id}-python-developer")).text
    assert "Python Developer" in page and ld(page) is None


async def test_closed_and_hidden_jobs(client: httpx.AsyncClient, session_factory: SF) -> None:
    closed = await job(session_factory, "Eski ish", status=JobStatus.CLOSED)
    page = (await client.get(f"/ish/{closed}-eski-ish")).text
    assert "yopilgan" in page and '<meta name="robots" content="noindex">' in page
    queued = await job(session_factory, "Hali chiqmagan", status=JobStatus.QUEUED)
    assert (await client.get(f"/ish/{queued}-hali-chiqmagan")).status_code == 404
    assert (await client.get("/ish/abc")).status_code == 404


async def test_html_is_escaped(client: httpx.AsyncClient, session_factory: SF) -> None:
    job_id = await job(session_factory, "<script>alert(1)</script>", company="<b>X</b>")
    async with session_factory() as s, s.begin():
        await s.execute(
            update(Job).where(Job.id == job_id).values(formatted_text="💼 <b>&lt;script&gt;</b>")
        )
    home = (await client.get("/")).text
    assert "<script>alert(1)</script>" not in home and "&lt;script&gt;" in home


async def test_sitemap_and_robots(client: httpx.AsyncClient, session_factory: SF) -> None:
    job_id = await job(session_factory, "Haydovchi", category="transport")
    await job(session_factory, "Yopiq", status=JobStatus.CLOSED)
    xml = (await client.get("/sitemap.xml")).text
    assert f"https://ayvona.test/ish/{job_id}-haydovchi" in xml
    assert "https://ayvona.test/soha/transport" in xml and "yopiq" not in xml
    robots = (await client.get("/robots.txt")).text
    assert "Sitemap: https://ayvona.test/sitemap.xml" in robots
    assert (await client.get("/healthz")).text == "ok"
    assert (await client.get("/static/style.css")).status_code == 200
