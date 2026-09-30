"""🔍 Search (Bosqich 12): services/search.py (filters, FTS5 keyword with Cyrillic/Latin,
salary incl. USD, search_logs, search_text backfill, USD rate) and the bot wizard."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram.methods import EditMessageText, SendMessage
from sqlalchemy import select, update

from ayvona.bot import texts as T
from ayvona.db.models import Job, JobOrigin, JobStatus, ParseMethod, SearchLog
from ayvona.processing.normalize import search_text
from ayvona.services import search as svc
from ayvona.services import users as users_svc
from ayvona.services.currency import refresh_usd_rate
from ayvona.services.search import REMOTE, SearchFilters
from ayvona.timeutil import utcnow
from tests.test_admin_bot import BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, make_settings

USER = 900
RATE = 12_500.0


async def job(sf: SF, title: str, *, minutes_ago: int = 10, **kw: Any) -> int:
    values: dict[str, Any] = {
        "origin": JobOrigin.AGGREGATOR,
        "parse_method": ParseMethod.REGEX,
        "title": title,
        "category": "sotuv",
        "status": JobStatus.PUBLISHED,
        "published_at": utcnow() - timedelta(minutes=minutes_ago),
        "formatted_text": f"💼 <b>{title}</b>",
        "channel_message_id": 500,
    }
    values.update(kw)
    values["search_text"] = search_text(title, values.get("company"), values.get("description"))
    async with sf() as s, s.begin():
        row = Job(**values)
        s.add(row)
        await s.flush()
        return row.id


async def find(sf: SF, **filters: Any) -> list[int]:
    async with sf() as s:
        jobs, total = await svc.search(
            s, SearchFilters(**filters), utcnow(), usd_rate=RATE, limit=50
        )
    assert total == len(jobs)
    return [j.id for j in jobs]


# ------------------------------------------------------------------ filters
async def test_filters_and_newest_first(session_factory: SF) -> None:
    sf = session_factory
    old = await job(sf, "Sotuvchi", minutes_ago=300, region="toshkent_sh", profession="sotuvchi")
    new = await job(sf, "Kassir", minutes_ago=5, region="samarqand", profession="kassir")
    cook = await job(sf, "Oshpaz", category="oshxona", region="toshkent_sh")
    remote = await job(sf, "Operator", category="operator", is_remote=True)
    await job(sf, "Yopilgan", status=JobStatus.CLOSED)
    await job(sf, "Muddati o'tgan", expires_at=utcnow() - timedelta(hours=1))
    await job(sf, "Navbatda", status=JobStatus.QUEUED)

    assert await find(sf) == [new, cook, remote, old] or set(await find(sf)) == {
        new,
        cook,
        remote,
        old,
    }
    assert await find(sf, category="sotuv") == [new, old]  # newest first
    assert await find(sf, category="sotuv", profession="kassir") == [new]
    assert await find(sf, region="toshkent_sh") == [cook, old]
    assert await find(sf, region=REMOTE) == [remote]


async def test_salary_filter(session_factory: SF) -> None:
    sf = session_factory
    lo_hi = await job(sf, "A", salary_min=3_000_000, salary_max=5_000_000, currency="UZS")
    only_min = await job(sf, "B", salary_min=6_000_000, currency="UZS")
    usd = await job(sf, "C", salary_min=500, currency="USD", salary_period="month")  # 6.25 mln
    daily = await job(sf, "D", salary_min=400_000, currency="UZS", salary_period="day")
    no_salary = await job(sf, "E", salary_text="Kelishiladi")

    assert set(await find(sf, min_salary=4_000_000)) == {lo_hi, only_min, usd}
    assert set(await find(sf, min_salary=6_000_000)) == {only_min, usd}
    assert await find(sf, min_salary=10_000_000) == []
    everything = set(await find(sf))
    assert {daily, no_salary} <= everything  # "Farqi yo'q" shows jobs without a salary number


# ------------------------------------------------------------------ keyword (FTS5)
async def test_keyword_latin_cyrillic_and_prefix(session_factory: SF) -> None:
    sf = session_factory
    latin = await job(sf, "Sotuvchi-konsultant", company="Texnomart")
    cyr = await job(sf, "Сотувчи керак", description="Чилонзор тумани")
    teacher = await job(sf, "Ingliz tili o'qituvchisi", category="talim")
    await job(sf, "Haydovchi", category="transport")

    assert set(await find(sf, keyword="sotuvchi")) == {latin, cyr}
    assert set(await find(sf, keyword="СОТУВЧИ")) == {latin, cyr}
    assert await find(sf, keyword="sotuv texnomart") == [latin]
    assert await find(sf, keyword="chilonzor") == [cyr]
    assert await find(sf, keyword="o'qituvchi") == [teacher]
    assert await find(sf, keyword="oqituvchi") == [teacher]
    assert await find(sf, keyword="dasturchi") == []


@pytest.mark.parametrize("text", ['"; DROP TABLE jobs; --', "C++ AND OR NOT", "a", "***", ""])
def test_fts_query_is_always_safe(text: str) -> None:
    q = svc.fts_query(text)
    assert q is None or all(
        part.startswith('"') and part.endswith('"*') for part in q.split(" AND ")
    )


async def test_odd_keywords_do_not_crash(session_factory: SF) -> None:
    await job(session_factory, "C++ dasturchi")
    for kw in ['"; DROP TABLE jobs; --', "C++", "***", "NEAR(a b)"]:
        await find(session_factory, keyword=kw)
    assert len(await find(session_factory, keyword="dasturchi")) == 1


# ------------------------------------------------------------------ logs, backfill, rate
async def test_search_log_and_last_filters(session_factory: SF) -> None:
    f = SearchFilters(category="sotuv", region="toshkent_sh", min_salary=4_000_000)
    async with session_factory() as s, s.begin():
        await users_svc.touch_user(s, USER, "u", "U", utcnow())
        assert await svc.last_filters(s, USER) is None
        await svc.log_search(
            s, USER, SearchFilters(keyword="old"), 3, utcnow() - timedelta(hours=1)
        )
        await svc.log_search(s, USER, f, 7, utcnow())
    async with session_factory() as s:
        assert await svc.last_filters(s, USER) == f
        rows = (await s.scalars(select(SearchLog))).all()
    assert sorted(r.results_count for r in rows) == [3, 7]


async def test_fill_search_text_for_old_jobs(session_factory: SF) -> None:
    job_id = await job(session_factory, "Омборчи", company="Korzinka")
    async with session_factory() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job_id).values(search_text=None))
    assert await find(session_factory, keyword="omborchi") == []
    async with session_factory() as s, s.begin():
        assert await svc.fill_search_text(s) == 1
    async with session_factory() as s, s.begin():
        assert await svc.fill_search_text(s) == 0
    assert await find(session_factory, keyword="omborchi") == [job_id]


async def test_usd_rate_is_stored_or_falls_back(session_factory: SF) -> None:
    settings = make_settings()
    async with session_factory() as s:
        assert await svc.usd_rate(s, 12_800) == 12_800

    async def ok(url: str) -> float:
        return 12_950.5

    async def broken(url: str) -> float:
        raise OSError("no network")

    assert await refresh_usd_rate(settings, session_factory, ok) == 12_950.5
    assert await refresh_usd_rate(settings, session_factory, broken) is None  # old one stays
    async with session_factory() as s:
        assert await svc.usd_rate(s, 12_800) == 12_950.5


# ------------------------------------------------------------------ bot wizard
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    return BotHarness(bot_settings(tmp_path), session_factory)


def last_markup(h: BotHarness) -> Any:
    reqs = [r for r in h.session.requests if isinstance(r, SendMessage | EditMessageText)]
    return reqs[-1].reply_markup


def callbacks(markup: Any) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


async def test_wizard_to_results_and_pages(harness: BotHarness, session_factory: SF) -> None:
    ids = [
        await job(
            session_factory,
            f"Sotuvchi {i}",
            minutes_ago=i,
            region="toshkent_sh",
            profession="sotuvchi",
            salary_min=5_000_000,
            currency="UZS",
        )
        for i in range(7)
    ]
    await job(session_factory, "Kassir", region="samarqand", profession="kassir")

    await harness.send(message_update(T.MENU_SEARCH, uid=USER))
    assert harness.texts()[-1] == T.SEARCH_ASK_CATEGORY
    assert "sq:last:" not in callbacks(last_markup(harness))  # no earlier search yet
    await harness.send(callback_update("sq:cat:sotuv", uid=USER))
    assert "sq:prof:sotuvchi" in callbacks(last_markup(harness))
    await harness.send(callback_update("sq:prof:sotuvchi", uid=USER))
    assert "sq:reg:remote" in callbacks(last_markup(harness))
    await harness.send(callback_update("sq:reg:toshkent_sh", uid=USER))
    await harness.send(callback_update("sq:sal:4000000", uid=USER))

    page1 = harness.texts()[-1]
    assert "7 ta" in page1 and "sahifa 1/2" in page1 and "Toshkent sh." in page1
    assert "1. <b>Sotuvchi 0</b>" in page1  # newest first
    kb = callbacks(last_markup(harness))
    assert f"job:show:{ids[0]}" in kb and f"job:save:{ids[0]}" in kb and "sq:page:2" in kb

    await harness.send(callback_update("sq:page:2", uid=USER))
    assert "sahifa 2/2" in harness.texts()[-1] and "6. <b>Sotuvchi 5</b>" in harness.texts()[-1]

    await harness.send(callback_update(f"job:save:{ids[0]}", uid=USER))
    await harness.send(message_update(T.MENU_FAVORITES, uid=USER))
    assert "Sotuvchi 0" in harness.texts()[-1]

    # next time: "🔁 Oxirgi qidiruv" repeats it
    await harness.send(message_update(T.MENU_SEARCH, uid=USER))
    assert "sq:last:" in callbacks(last_markup(harness))
    await harness.send(callback_update("sq:last:", uid=USER))
    assert "7 ta" in harness.texts()[-1]


async def test_keyword_search_in_the_bot(harness: BotHarness, session_factory: SF) -> None:
    await job(session_factory, "Oshpaz", category="oshxona")
    await harness.send(message_update("/start search", uid=USER))
    assert harness.texts()[-1] == T.SEARCH_ASK_CATEGORY
    await harness.send(callback_update("sq:kw:", uid=USER))
    await harness.send(message_update("a", uid=USER))
    assert harness.texts()[-1] == T.SEARCH_BAD_KEYWORD
    await harness.send(message_update("ОШПАЗ", uid=USER))
    assert "1 ta" in harness.texts()[-1] and "Oshpaz" in harness.texts()[-1]
    await harness.send(callback_update("sq:new:", uid=USER))
    await harness.send(callback_update("sq:cat:*", uid=USER))  # all categories: straight to region
    assert "sq:reg:*" in callbacks(last_markup(harness))


async def test_nothing_found(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_SEARCH, uid=USER))
    for data in ("sq:cat:it", "sq:prof:*", "sq:reg:*", "sq:sal:0"):
        await harness.send(callback_update(data, uid=USER))
    assert "hozircha e'lon yo'q" in harness.texts()[-1]
