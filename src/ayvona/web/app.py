"""Ayvona Jobs website (Bosqich 17) — FastAPI + Jinja2, rendered on the server (no JS framework).

Read-only for now: home (newest jobs), search with filters (the bot's search: services/search.py),
job pages ``/ish/<id>-<slug>``, category / region pages, ``sitemap.xml``, ``robots.txt``.
Every query goes through ``services/`` — the same rules as the bot. The site never writes to the
DB; posting a job and Telegram login come later (docs/ROADMAP.md, Bosqich 17).

SEO: title / description / canonical / Open Graph on every page; schema.org ``JobPosting``
JSON-LD only for jobs from Telegram channels and our users (Himalayas / Remotive forbid Google
Jobs), ``validThrough`` = ``expires_at``.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.bot.cards import filters_summary, place_short, profession_title, salary_short
from ayvona.config import Settings
from ayvona.db.models import Job
from ayvona.services import jobs_public, search
from ayvona.services.search import REMOTE, SearchFilters
from ayvona.timeutil import to_local, utcnow

HERE = Path(__file__).parent
_TAG_RE = re.compile(r"<[^>]+>")


def _plain(text: str | None) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def create_app(settings: Settings, sf: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI(title="Ayvona Jobs", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    cfg = settings.app.website
    brand = settings.app.branding

    def base_url(request: Request) -> str:
        return (cfg.base_url or str(request.base_url)).rstrip("/")

    def job_url(job: Job) -> str:
        return f"/ish/{job.id}-{jobs_public.slug(job.title)}"

    def local(dt: datetime | None) -> str:
        return to_local(dt, settings.timezone).strftime("%d.%m.%Y") if dt else ""

    def card(job: Job, now: datetime) -> dict[str, Any]:
        return {
            "url": job_url(job),
            "title": job.title or "Ish e'loni",
            "company": job.company,
            "salary": salary_short(job),
            "place": place_short(job, settings),
            "date": local(job.published_at),
            "open": jobs_public.is_open(job, now),
        }

    def render(request: Request, name: str, status: int = 200, **ctx: Any) -> HTMLResponse:
        ctx.setdefault("canonical", base_url(request) + request.url.path)
        return templates.TemplateResponse(
            request,
            name,
            {
                "brand": brand,
                "categories": settings.categories,
                "regions": settings.regions.regions,
                "remote": REMOTE,
                "salary_steps": settings.app.search.salary_steps,
                **ctx,
            },
            status_code=status,
        )

    async def results(request: Request, f: SearchFilters, page: int, **ctx: Any) -> HTMLResponse:
        now = utcnow()
        size = cfg.page_size
        async with sf() as s:
            rate = await search.usd_rate(s, settings.app.search.usd_rate_fallback)
            jobs, total = await search.search(
                s, f, now, usd_rate=rate, offset=(page - 1) * size, limit=size
            )
        pages = max((total + size - 1) // size, 1)
        query = {k: v for k, v in request.query_params.items() if k != "sahifa"}
        return render(
            request,
            "search.html",
            jobs=[card(j, now) for j in jobs],
            total=total,
            page=page,
            pages=pages,
            query=query,
            f=f,
            summary=Markup(filters_summary(f, settings)),  # already escaped
            **ctx,
        )

    # ------------------------------------------------------------------ pages
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        now = utcnow()
        async with sf() as s:
            jobs = await jobs_public.latest_open(s, now, cfg.page_size)
        return render(
            request,
            "index.html",
            jobs=[card(j, now) for j in jobs],
            title=f"{brand.channel_title} — O'zbekistonda ish e'lonlari",
            description="O'zbekiston bo'ylab yangi ish e'lonlari: soha, hudud va maosh bo'yicha "
            "qidiring. Bepul.",
        )

    @app.get("/ish", response_class=HTMLResponse)
    async def search_page(
        request: Request,
        q: str = Query("", max_length=100),
        soha: str = "",
        kasb: str = "",
        hudud: str = "",
        maosh: int = Query(0, ge=0),
        sahifa: int = Query(1, ge=1, le=500),
    ) -> HTMLResponse:
        f = SearchFilters(
            category=soha if soha in settings.categories else None,
            profession=kasb or None,
            region=hudud if hudud == REMOTE or hudud in settings.regions.regions else None,
            min_salary=maosh or None,
            keyword=q.strip() or None,
        )
        return await results(
            request,
            f,
            sahifa,
            title=f"Ish qidirish — {_plain(filters_summary(f, settings))} | {brand.channel_title}",
            description="Ish e'lonlari: kategoriya, kasb, hudud va maosh bo'yicha qidiruv.",
        )

    @app.get("/soha/{category}", response_class=HTMLResponse)
    async def category_page(
        request: Request, category: str, sahifa: int = Query(1, ge=1, le=500)
    ) -> HTMLResponse:
        cat = settings.categories.get(category)
        if cat is None:
            raise HTTPException(404)
        return await results(
            request,
            SearchFilters(category=category),
            sahifa,
            title=f"{cat.title} — ish e'lonlari | {brand.channel_title}",
            description=f"{cat.title} sohasidagi yangi ish e'lonlari, O'zbekiston bo'ylab.",
            heading=cat.title,
        )

    @app.get("/hudud/{region}", response_class=HTMLResponse)
    async def region_page(
        request: Request, region: str, sahifa: int = Query(1, ge=1, le=500)
    ) -> HTMLResponse:
        if region == REMOTE:
            name = "Masofaviy"
        elif region in settings.regions.regions:
            name = settings.regions.regions[region].title
        else:
            raise HTTPException(404)
        return await results(
            request,
            SearchFilters(region=region),
            sahifa,
            title=f"{name} — ish e'lonlari | {brand.channel_title}",
            description=f"{name}: yangi ish e'lonlari.",
            heading=name,
        )

    @app.get("/ish/{job_ref}", response_class=HTMLResponse, response_model=None)
    async def job_page(request: Request, job_ref: str) -> Response:
        m = re.match(r"^(\d{1,12})(?:-[a-z0-9-]*)?$", job_ref)
        if not m:
            raise HTTPException(404)
        now = utcnow()
        async with sf() as s:
            job = await jobs_public.get_visible_job(s, int(m.group(1)))
            if job is None or job.kind != "job":  # projects are shown in the bot only
                raise HTTPException(404)
            markup_ok = await jobs_public.allows_job_posting_markup(s, job)
        canonical = job_url(job)
        if request.url.path != canonical:
            return RedirectResponse(canonical, status_code=301)
        open_ = jobs_public.is_open(job, now)
        buttons = [
            b
            for row in (job.buttons or [])[:1]
            for b in row
            if b.get("url") and "?start=" not in b["url"]
        ]
        # the full card when the channel caption was shortened (the whole text stays on our site)
        text = job.full_html or job.formatted_text or html.escape(job.title or "")
        ld = json_ld(job, base_url(request) + canonical) if markup_ok else None
        return render(
            request,
            "job.html",
            job=job,
            card=card(job, now),
            open=open_,
            post=Markup(text.replace("\n", "<br>")),  # our own escaped Telegram HTML
            buttons=buttons,
            channel_url=jobs_public.channel_post_url(settings, job),
            save_url=f"https://t.me/{brand.bot_username}?start=save_{job.id}",
            profession=profession_title(settings, job.category, job.profession),
            category=settings.categories.get(job.category),
            json_ld=Markup(json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
            if ld
            else None,
            title=f"{job.title or 'Ish'} — {job.company or brand.channel_title}",
            description=_plain(job.formatted_text)[:155],
            canonical=base_url(request) + canonical,
            noindex=not open_,
        )

    def json_ld(job: Job, url: str) -> dict[str, Any]:
        """schema.org JobPosting (https://developers.google.com/search/docs/appearance/structured-data/job-posting)."""
        ld: dict[str, Any] = {
            "@context": "https://schema.org/",
            "@type": "JobPosting",
            "title": job.title or "Ish e'loni",
            "description": html.escape(_plain(job.full_html or job.formatted_text)).replace(
                "\n", "<br>"
            ),
            "datePosted": (job.published_at or job.created_at).isoformat(),
            "hiringOrganization": {"@type": "Organization", "name": job.company or "—"},
            "url": url,
            "directApply": False,
        }
        if job.expires_at:
            ld["validThrough"] = job.expires_at.isoformat()
        if job.is_remote:
            ld["jobLocationType"] = "TELECOMMUTE"
            ld["applicantLocationRequirements"] = {"@type": "Country", "name": "Uzbekistan"}
        else:
            region = settings.regions.regions.get(job.region or "")
            ld["jobLocation"] = {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressCountry": "UZ",
                    **({"addressRegion": region.title} if region else {}),
                    **({"addressLocality": job.city} if job.city else {}),
                },
            }
        if (job.salary_min or job.salary_max) and job.currency:
            value: dict[str, Any] = {"@type": "QuantitativeValue", "unitText": "MONTH"}
            if job.salary_min:
                value["minValue"] = job.salary_min
            if job.salary_max:
                value["maxValue"] = job.salary_max
            ld["baseSalary"] = {"@type": "MonetaryAmount", "currency": job.currency, "value": value}
        return ld

    # ------------------------------------------------------------------ robots / sitemap
    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots(request: Request) -> str:
        # /ish?... filter combinations are endless: crawlers use the sitemap and job pages
        return (
            "User-agent: *\nAllow: /\nDisallow: /ish?\n\n"
            f"Sitemap: {base_url(request)}/sitemap.xml\n"
        )

    @app.get("/sitemap.xml")
    async def sitemap(request: Request) -> Response:
        now = utcnow()
        root = base_url(request)
        async with sf() as s:
            jobs = await jobs_public.sitemap_jobs(s, now, cfg.sitemap_limit)
        urls = [f"{root}/"]
        urls += [f"{root}/soha/{k}" for k in settings.categories]
        urls += [f"{root}/hudud/{k}" for k in settings.regions.regions]
        lines = [f"<url><loc>{xml_escape(u)}</loc></url>" for u in urls]
        for job in jobs:
            when = (job.updated_at or job.published_at or now).date().isoformat()
            loc = xml_escape(root + job_url(job))
            lines.append(f"<url><loc>{loc}</loc><lastmod>{when}</lastmod></url>")
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(lines)
            + "\n</urlset>\n"
        )
        return Response(body, media_type="application/xml")

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.exception_handler(404)
    async def not_found(request: Request, exc: Exception) -> HTMLResponse:
        return render(
            request,
            "404.html",
            status=404,
            title="Topilmadi — Ayvona Jobs",
            description="Sahifa topilmadi.",
            noindex=True,
        )

    return app
