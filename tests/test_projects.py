"""🧩 Loyihalar: one-time paid projects next to salaried jobs — the form (type first), the channel
post (#loyiha, budget instead of salary), approval + immediate publication, the browse list, and
the isolation from the job search / alerts / website / ranking."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup

from ayvona.bot import texts as T
from ayvona.db.models import JobKind, JobOrigin, JobStatus
from ayvona.processing.formatter import visible_len
from ayvona.processing.project_format import MAX_CAPTION, format_project, parse_budget
from ayvona.services import projects as projects_svc
from ayvona.services import search as search_svc
from ayvona.services.priority_backfill import backfill_priority
from ayvona.services.search import SearchFilters, job_matches
from ayvona.timeutil import utcnow
from ayvona.web.app import create_app
from tests.test_admin_bot import ADMIN, BotHarness, callback_update, message_update
from tests.test_instant_publish import channel_posts, channel_settings
from tests.test_post_job import USER, all_jobs, contact_update, sent_to
from tests.test_web import site_settings
from tests.worker_helpers import SF, add_job, get_job, make_image, make_settings


@pytest.fixture
def harness(tmp_path: Path, session_factory: SF) -> BotHarness:
    make_image(tmp_path / "images", "boshqa/1.jpg")
    return BotHarness(channel_settings(tmp_path), session_factory)


# ------------------------------------------------------------------ budget
@pytest.mark.parametrize(
    ("raw", "amount", "currency", "shown"),
    [
        ("3 mln so'm", 3_000_000, "UZS", "3 000 000 so'm"),
        ("3 000 000", 3_000_000, "UZS", "3 000 000 so'm"),
        ("$300", 300, "USD", "300 $"),
        ("300 $", 300, "USD", "300 $"),
        ("500-800$", 500, "USD", "500 – 800 $"),
        (None, None, None, "Kelishiladi"),
        ("", None, None, "Kelishiladi"),
        ("kelishamiz", None, None, "kelishamiz"),
    ],
)
def test_parse_budget(
    raw: str | None, amount: int | None, currency: str | None, shown: str
) -> None:
    b = parse_budget(raw, make_settings())
    assert (b.amount, b.currency, b.text) == (amount, currency, shown)


# ------------------------------------------------------------------ the channel post
def post(**kw: object):  # noqa: ANN201
    args = {
        "title": "Telegram bot yozish",
        "description": "Do'kon uchun buyurtma boti kerak.",
        "budget": parse_budget("3 mln so'm", make_settings()),
        "deadline": "2 hafta",
        "phone": "+998901234567",
        "username": "@ali_dev",
        "settings": make_settings(),
    }
    args.update(kw)
    return format_project(**args)  # type: ignore[arg-type]


def test_project_post_is_clearly_marked_and_has_no_salary() -> None:
    out = post()
    assert out.html.startswith("🧩 <b>LOYIHA</b>\n<b>Telegram bot yozish</b>")
    assert "💰 Byudjet: 3 000 000 so'm (bir martalik)" in out.html
    assert "⏳ Muddat: 2 hafta" in out.html
    assert "📞 Aloqa: +998 90 123 45 67" in out.html and "✉️ Telegram: @ali_dev" in out.html
    assert "#loyiha" in out.html and "@ayvonajobs" in out.html
    assert "Maosh" not in out.html and "💼" not in out.html  # not a salaried job


def test_project_post_escapes_html_and_drops_empty_lines() -> None:
    out = post(title="<b>Hack</b> & co", description="<script>x</script>", deadline=None)
    assert "<script>" not in out.html and "&lt;script&gt;" in out.html
    assert "&lt;b&gt;Hack&lt;/b&gt; &amp; co" in out.html
    assert "Muddat" not in out.html


def test_long_description_is_cut_but_the_facts_stay() -> None:
    out = post(description="Juda uzun tavsif. " * 200)
    assert visible_len(out.html) <= MAX_CAPTION
    for must in ("Byudjet", "2 hafta", "+998 90 123 45 67", "#loyiha", "…"):
        assert must in out.html


def test_buttons_contact_only_with_a_username() -> None:
    with_user = post().buttons(7)
    assert with_user[0] == [{"text": "📩 Murojaat", "url": "https://t.me/ali_dev"}]
    assert with_user[1][0]["url"].endswith("?start=save_7")
    assert with_user[1][1]["url"].endswith("?start=projects")
    phone_only = post(username=None).buttons(7)
    assert len(phone_only) == 1 and len(phone_only[0]) == 2  # save + more, no contact button


# ------------------------------------------------------------------ the form
async def walk_project(h: BotHarness, *, contact: bool = True, deadline: str | None = None) -> None:
    await h.send(message_update(T.MENU_POST, uid=USER))
    await h.send(callback_update("pj:kind:project", uid=USER))
    await h.send(message_update("Telegram bot yozish", uid=USER))
    await h.send(message_update("Do'kon uchun buyurtma boti kerak", uid=USER))
    await h.send(message_update("3 mln so'm", uid=USER))
    await h.send(message_update(deadline or T.BTN_SKIP, uid=USER))
    if contact:
        await h.send(contact_update(USER))
        await h.send(callback_update("pj:days:14", uid=USER))


async def test_the_type_is_asked_first_and_project_steps_are_numbered(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    texts = harness.texts()
    assert T.POST_ASK_KIND in texts
    kind_msg = harness.session.sent(SendMessage)[-1]
    labels = [b.text for row in kind_msg.reply_markup.inline_keyboard for b in row]
    assert labels == [T.BTN_KIND_JOB, T.BTN_KIND_PROJECT]

    await harness.send(callback_update("pj:kind:project", uid=USER))
    assert harness.texts()[-1] == f"1/6. {T.POST_ASK_PROJECT_TITLE}"
    await harness.send(message_update("Telegram bot yozish", uid=USER))
    assert harness.texts()[-1] == f"2/6. {T.POST_ASK_DESCRIPTION}"
    await harness.send(message_update("Do'kon boti", uid=USER))
    assert harness.texts()[-1].startswith("3/6. Byudjet")
    await harness.send(message_update("300$", uid=USER))
    assert harness.texts()[-1] == f"4/6. {T.POST_ASK_DEADLINE}"
    await harness.send(message_update("2 hafta", uid=USER))
    assert harness.texts()[-1].startswith("5/6.") and "Aloqa" in harness.texts()[-1]


async def test_project_is_submitted_approved_and_published_at_once(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_project(harness, deadline="2 hafta")
    texts = harness.texts()
    preview = texts[texts.index(T.POST_PREVIEW_HEAD) + 1]
    assert preview.startswith("🧩 <b>LOYIHA</b>") and "#loyiha" in preview
    assert T.POST_PREVIEW_DAYS.format(n=14) in texts
    assert await all_jobs(session_factory) == []  # nothing before "Yuborish"

    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.kind == JobKind.PROJECT.value and job.status is JobStatus.PENDING_REVIEW
    assert job.origin is JobOrigin.USER and job.author_id == USER
    assert (job.budget_amount, job.budget_currency) == (3_000_000, "UZS")
    assert job.deadline_text == "2 hafta" and job.active_days == 14
    assert job.contact_phone == "+998901234567"
    assert job.priority_tier == 2  # not ranked

    [notice] = [r for r in harness.session.sent(SendMessage) if r.chat_id == ADMIN]
    assert "Turi: 🧩 Loyiha" in notice.text and "Faol muddat: <b>14 kun</b>" in notice.text

    await harness.send(callback_update(f"mod:ok:{job.id}", uid=ADMIN))
    [sent] = channel_posts(harness)
    assert "#loyiha" in (getattr(sent, "caption", None) or getattr(sent, "text", ""))
    [job] = await all_jobs(session_factory)
    assert job.status is JobStatus.PUBLISHED
    assert job.expires_at and job.published_at
    assert job.expires_at - job.published_at == timedelta(days=14)
    assert any("t.me/" in t for t in sent_to(harness, USER))  # the author got the link


async def test_deadline_is_optional(harness: BotHarness, session_factory: SF) -> None:
    await walk_project(harness)  # "skip" the deadline
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.deadline_text is None and "Muddat" not in (job.formatted_text or "")


async def test_negotiable_budget(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    await harness.send(callback_update("pj:kind:project", uid=USER))
    await harness.send(message_update("Logotip dizayni", uid=USER))
    await harness.send(message_update("Kafe uchun logotip", uid=USER))
    await harness.send(message_update(T.BTN_NEGOTIABLE, uid=USER))
    await harness.send(message_update(T.BTN_SKIP, uid=USER))
    await harness.send(contact_update(USER))
    await harness.send(callback_update("pj:days:7", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.budget_amount is None and job.salary_text == "Kelishiladi"


async def test_contact_is_required_for_projects_too(
    harness: BotHarness, session_factory: SF
) -> None:
    await walk_project(harness, contact=False)
    await harness.send(message_update("qo'ng'iroq qiling", uid=USER))
    assert harness.texts()[-1] == T.POST_NO_CONTACT
    await harness.send(callback_update("pj:send:", uid=USER))
    assert await all_jobs(session_factory) == []
    await harness.send(message_update("@ali_dev", uid=USER))
    await harness.send(callback_update("pj:days:3", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    [job] = await all_jobs(session_factory)
    assert job.contact_username == "@ali_dev" and job.contact_phone is None


async def test_spam_in_the_description_is_rejected(
    harness: BotHarness, session_factory: SF
) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    await harness.send(callback_update("pj:kind:project", uid=USER))
    await harness.send(message_update("Kazino sayti", uid=USER))
    await harness.send(message_update("Kazino dilleri kerak", uid=USER))
    await harness.send(message_update("100$", uid=USER))
    await harness.send(message_update(T.BTN_SKIP, uid=USER))
    await harness.send(contact_update(USER))
    await harness.send(callback_update("pj:days:7", uid=USER))
    await harness.send(callback_update("pj:send:", uid=USER))
    assert T.POST_REJECTED in harness.texts() and await all_jobs(session_factory) == []


async def test_changing_the_type_starts_the_answers_over(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    await harness.send(callback_update("pj:kind:job", uid=USER))
    await harness.send(callback_update("pj:cat:sotuv", uid=USER))
    await harness.send(message_update(T.BTN_BACK, uid=USER))  # category
    await harness.send(message_update(T.BTN_BACK, uid=USER))  # the type question again
    assert harness.texts()[-2] == T.POST_ASK_KIND
    await harness.send(callback_update("pj:kind:project", uid=USER))
    assert harness.texts()[-1] == f"1/6. {T.POST_ASK_PROJECT_TITLE}"


async def test_edit_keyboard_lists_the_project_fields(harness: BotHarness) -> None:
    await walk_project(harness)
    await harness.send(callback_update("pj:edit:", uid=USER))
    kb = harness.session.sent(SendMessage)[-1].reply_markup
    assert isinstance(kb, InlineKeyboardMarkup)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert labels == list(T.PROJECT_FIELDS.values())
    await harness.send(callback_update("pj:field:budget", uid=USER))
    await harness.send(message_update("500$", uid=USER))
    assert harness.texts()[-1] == T.POST_PREVIEW_ASK  # straight back to the preview
    await harness.send(callback_update("pj:field:category", uid=USER))  # a job field: ignored
    assert harness.texts()[-1] == T.POST_PREVIEW_ASK


# ------------------------------------------------------------------ browsing
async def published_project(
    sf: SF,
    title: str,
    *,
    minutes_ago: int = 10,
    status: JobStatus = JobStatus.PUBLISHED,
    **kw: object,
) -> int:
    now = utcnow()
    values: dict[str, object] = {
        "search_text": title.lower(),
        "kind": JobKind.PROJECT.value,
        "origin": JobOrigin.USER,
        "title": title,
        "salary_text": "3 000 000 so'm",
        "deadline_text": "2 hafta",
        "text": f"🧩 <b>LOYIHA</b>\n<b>{title}</b>",
        "published_at": now - timedelta(minutes=minutes_ago),
        "expires_at": now + timedelta(days=5),
        "channel_message_id": 500,
        **kw,
    }
    return await add_job(sf, status=status, **values)  # type: ignore[arg-type]


async def test_projects_list_newest_first_without_closed_expired_or_jobs(
    harness: BotHarness, session_factory: SF
) -> None:
    sf = session_factory
    old = await published_project(sf, "Eski loyiha", minutes_ago=300)
    new = await published_project(sf, "Yangi loyiha", minutes_ago=5)
    await published_project(sf, "Yopilgan", status=JobStatus.CLOSED)
    await published_project(sf, "Muddati o'tgan", expires_at=utcnow() - timedelta(hours=1))
    await add_job(sf, status=JobStatus.QUEUED, kind="project", title="Navbatdagi loyiha")
    await add_job(sf, status=JobStatus.PUBLISHED, title="Oddiy ish", published_at=utcnow())

    await harness.send(message_update(T.MENU_PROJECTS, uid=USER))
    text = harness.texts()[-1]
    assert T.PROJECTS_HEAD.format(total=2) in text
    assert text.index("Yangi loyiha") < text.index("Eski loyiha")
    for absent in ("Yopilgan", "Muddati", "Navbatdagi", "Oddiy ish"):
        assert absent not in text
    assert "💰 3 000 000 so&#x27;m · ⏳ 2 hafta" in text  # HTML-escaped, like every card

    async with sf() as s:
        jobs, total = await projects_svc.list_open(s, utcnow(), limit=5)
    assert [j.id for j in jobs] == [new, old] and total == 2


async def test_projects_are_paged_and_open_in_detail(
    harness: BotHarness, session_factory: SF
) -> None:
    ids = [await published_project(session_factory, f"Loyiha {i}", minutes_ago=i) for i in range(7)]
    await harness.send(message_update(T.MENU_PROJECTS, uid=USER))
    page1 = harness.session.sent(SendMessage)[-1]
    assert "1. 🧩 <b>Loyiha 0</b>" in page1.text and "Loyiha 5" not in page1.text
    buttons = [b for row in page1.reply_markup.inline_keyboard for b in row]
    assert any(b.callback_data == "prp:2" for b in buttons)
    assert any(b.callback_data == f"job:show:{ids[0]}" for b in buttons)

    await harness.send(callback_update("prp:2", uid=USER))
    edited = harness.session.requests[-1]
    assert "6. 🧩 <b>Loyiha 5</b>" in edited.text and "Loyiha 0" not in edited.text

    await harness.send(callback_update(f"job:show:{ids[0]}", uid=USER))
    assert harness.texts()[-1].startswith("🧩 <b>LOYIHA</b>")  # the full card


async def test_empty_list_and_deep_link(harness: BotHarness, session_factory: SF) -> None:
    await harness.send(message_update(T.MENU_PROJECTS, uid=USER))
    assert harness.texts()[-1] == T.PROJECTS_EMPTY
    await published_project(session_factory, "Bot yozish")
    await harness.send(message_update("/start projects", uid=USER))  # the channel post's button
    assert "Bot yozish" in harness.texts()[-1]


async def test_menu_button_leaves_a_half_filled_form(harness: BotHarness) -> None:
    await harness.send(message_update(T.MENU_POST, uid=USER))
    await harness.send(callback_update("pj:kind:project", uid=USER))
    await harness.send(message_update(T.MENU_PROJECTS, uid=USER))  # not taken as the title
    assert harness.texts()[-1] == T.PROJECTS_EMPTY


# ------------------------------------------------------------------ isolation from the jobs
async def test_projects_are_not_in_the_job_search_alerts_or_ranking(
    session_factory: SF,
) -> None:
    sf = session_factory
    project = await published_project(sf, "Telegram bot yozish")
    real = await add_job(
        sf,
        status=JobStatus.PUBLISHED,
        title="Telegram operator",
        search_text="telegram operator",
        published_at=utcnow(),
    )
    async with sf() as s:
        found, total = await search_svc.search(s, SearchFilters(), utcnow(), usd_rate=1, limit=10)
        keyword, _ = await search_svc.search(
            s, SearchFilters(keyword="telegram"), utcnow(), usd_rate=1, limit=10
        )
    assert [j.id for j in found] == [real] and total == 1
    assert [j.id for j in keyword] == [real]
    assert job_matches(SearchFilters(), await get_job(sf, project), utcnow(), 1) is False
    assert job_matches(SearchFilters(), await get_job(sf, real), utcnow(), 1) is True

    # the ranking never touches a project, even with --all
    report = await backfill_priority(make_settings(), sf, rescore_all=True)
    assert report.scored == 1
    assert (await get_job(sf, project)).priority_reason is None


async def test_website_lists_jobs_only(session_factory: SF) -> None:
    sf = session_factory
    project = await published_project(sf, "Bot yozish loyihasi")
    await add_job(sf, status=JobStatus.PUBLISHED, title="Kassir", published_at=utcnow())
    app = create_app(site_settings(), sf)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        home = await c.get("/")
        assert "Kassir" in home.text and "Bot yozish loyihasi" not in home.text
        assert "Bot yozish" not in (await c.get("/sitemap.xml")).text
        assert (await c.get(f"/ish/{project}")).status_code == 404


async def test_my_ads_marks_projects(harness: BotHarness, session_factory: SF) -> None:
    await walk_project(harness)
    await harness.send(callback_update("pj:send:", uid=USER))
    await harness.send(message_update(T.MENU_MY_JOBS, uid=USER))
    assert "🧩 Telegram bot yozish" in harness.texts()[-1]
