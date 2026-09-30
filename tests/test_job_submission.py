"""services/job_submission.py (Bosqich 11): rendering, contact rules, filters, limits,
duplicates, moderation, admin decision."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from ayvona.config import Settings
from ayvona.db.models import FilterKind, FilterWord, Job, JobOrigin, JobStatus, User
from ayvona.processing.formatter import visible_len
from ayvona.services import job_submission as js
from ayvona.services import users as users_svc
from ayvona.services.job_submission import Draft, LimitReason, Outcome, Verdict
from ayvona.timeutil import utcnow
from tests.worker_helpers import SF, make_settings

USER = 501


def draft(**kw: object) -> Draft:
    base = {
        "category": "sotuv",
        "title": "Sotuvchi",
        "company": "Ishonch savdo",
        "salary": "4-6 mln so'm",
        "region": "toshkent_sh",
        "city": "Chilonzor tumani",
        "schedule": "9:00-18:00, 6/1",
        "requirements": "Mas'uliyatli, xushmuomala",
        "phone": "+998901234567",
        "username": None,
    }
    base.update(kw)
    return Draft(**base)  # type: ignore[arg-type]


def settings(**posting: object) -> Settings:
    s = make_settings()
    app = s.app.model_copy(update={"posting": s.app.posting.model_copy(update=posting)})
    return s.model_copy(update={"app": app})


async def user(sf: SF, trust: int = 0, tg_id: int = USER) -> User:
    async with sf() as s, s.begin():
        u = await users_svc.touch_user(s, tg_id, "ali", "Ali", utcnow())
        u.trust_level = trust
    return u


async def submit(sf: SF, d: Draft, u: User, st: Settings | None = None, now=None):  # noqa: ANN001
    async with sf() as s, s.begin():
        return await js.submit(s, d, u, now or utcnow(), st or settings())


async def jobs(sf: SF) -> list[Job]:
    async with sf() as s:
        return list((await s.scalars(select(Job).order_by(Job.id))).all())


# ------------------------------------------------------------------ fields / rendering
def test_contact_parsing() -> None:
    assert js.parse_contact("+998 90 123 45 67") == ("+998901234567", None)
    assert js.parse_contact("@hr_manager") == (None, "@hr_manager")
    assert js.parse_contact("hr_manager") == (None, "@hr_manager")
    assert js.parse_contact("90 123 45 67, @Ali_HR") == ("+998901234567", "@Ali_HR")
    assert js.parse_contact("qo'ng'iroq qiling") == (None, None)
    assert js.phone_from_contact("998901234567") == "+998901234567"
    assert js.phone_from_contact("+7 999 123 45 67") is None  # only Uzbek numbers
    assert js.clean_field("  a \n\n b ", 10) == "a\nb"
    assert js.clean_field("x" * 11, 10) is None and js.clean_field("   ", 10) is None


def test_render_is_the_channel_template_in_latin() -> None:
    out, ex = js.render(draft(title="Сотувчи", company="Ишонч савдо"), make_settings())
    assert out.html.startswith("💼 <b>Sotuvchi</b>")
    assert "🏢 Kompaniya: Ishonch savdo" in out.html
    assert "💰 Maosh: 4 000 000 – 6 000 000 so'm" in out.html
    assert "📍 Manzil: Toshkent sh., Chilonzor tumani" in out.html
    assert "📞 Aloqa: +998 90 123 45 67" in out.html
    assert "@ayvona_jobs_bot" in out.html and "manba" not in out.html
    assert not any("Ѐ" <= ch <= "ӿ" for ch in out.html)
    assert ex.salary_min == 4_000_000 and ex.category == "sotuv"
    assert visible_len(out.html) <= 1024


def test_render_negotiable_and_remote() -> None:
    out, ex = js.render(draft(salary=None, region=js.REMOTE, city=None), make_settings())
    assert "💰 Maosh: Kelishiladi" in out.html
    assert "📍 Manzil: Masofaviy" in out.html
    assert ex.is_remote and ex.region is None


# ------------------------------------------------------------------ content checks
@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ("Sotuvchi kerak, maosh yaxshi", Verdict.OK),
        ("Kazino operatori kerak", Verdict.BAN),
        ("Pul ishlash oson! Kuniga 100$", Verdict.SPAM),
        ("a https://a.uz b https://b.uz c https://c.uz", Verdict.SPAM),
        ("SOTUVCHI KERAK TEZDA MAOSH YUQORI QO'NG'IROQ QILING", Verdict.SPAM),
        ("Sotuvchi kerak 🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥", Verdict.SPAM),
        ("Ishga olish uchun oldindan to'lov 200 000", Verdict.SCAM),
        ("Предоплата за оформление", Verdict.SCAM),
        ("Vazifa: mijozlardan oldindan to'lovlarni qabul qilish", Verdict.OK),
    ],
)
def test_check_content(text: str, verdict: Verdict) -> None:
    assert js.check_content(text, make_settings()).verdict is verdict


def test_admin_words_from_the_db_count_too() -> None:
    extra = {FilterKind.BAN: ["qimor"], FilterKind.SPAM: [], FilterKind.SCAM: ["garov puli"]}
    assert js.check_content("Qimor uyiga", make_settings(), extra).verdict is Verdict.BAN
    assert js.check_content("Garov puli kerak", make_settings(), extra).verdict is Verdict.SCAM


# ------------------------------------------------------------------ submit + moderation
async def test_no_contact_is_never_written(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    res = await submit(session_factory, draft(phone=None, username=None), u)
    assert res.outcome is Outcome.NO_CONTACT and await jobs(session_factory) == []


async def test_new_users_first_job_goes_to_review_then_trusted(session_factory: SF) -> None:
    u = await user(session_factory)
    res = await submit(session_factory, draft(), u)
    assert res.outcome is Outcome.REVIEW and "yangi foydalanuvchi" in res.review_reasons[0]
    [job] = await jobs(session_factory)
    assert job.status is JobStatus.PENDING_REVIEW and job.origin is JobOrigin.USER
    assert job.author_id == USER and job.contact_phone == "+998901234567"
    assert job.buttons and any("save_" in b["url"] for row in job.buttons for b in row)

    async with session_factory() as s, s.begin():
        approved = await js.approve(s, job.id, utcnow())
        assert approved is not None and approved.status is JobStatus.QUEUED
        assert await js.approve(s, job.id, utcnow()) is None  # decided once
    async with session_factory() as s:
        assert (await s.get(User, USER)).trust_level == 1  # type: ignore[union-attr]


async def test_trusted_user_goes_straight_to_the_queue(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    res = await submit(session_factory, draft(), u)
    assert res.outcome is Outcome.QUEUED
    [job] = await jobs(session_factory)
    assert job.status is JobStatus.QUEUED and job.next_retry_at is not None


async def test_scam_goes_to_review_even_for_trusted(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    res = await submit(session_factory, draft(requirements="Oldindan to'lov 100 000 so'm"), u)
    assert res.outcome is Outcome.REVIEW and "shubhali" in res.review_reasons[0]


@pytest.mark.parametrize(
    ("mode", "trust", "outcome"),
    [
        ("auto", 0, Outcome.QUEUED),
        ("all", 1, Outcome.REVIEW),
        ("all", 2, Outcome.QUEUED),  # admins are never moderated
    ],
)
async def test_moderation_modes(
    session_factory: SF, mode: str, trust: int, outcome: Outcome
) -> None:
    u = await user(session_factory, trust=trust)
    res = await submit(session_factory, draft(), u, settings(moderation=mode))
    assert res.outcome is outcome


async def test_ban_and_spam_are_rejected_without_a_row(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    res = await submit(session_factory, draft(title="Kazino dilleri"), u)
    assert res.outcome is Outcome.REJECTED and "ban" in res.reason
    async with session_factory() as s, s.begin():
        s.add(FilterWord(word="tarmoqli marketing", kind=FilterKind.BAN))
    res = await submit(session_factory, draft(requirements="Tarmoqli marketing"), u)
    assert res.outcome is Outcome.REJECTED
    assert await jobs(session_factory) == []


async def test_duplicate_is_rejected(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    now = utcnow()
    assert (await submit(session_factory, draft(), u, now=now)).outcome is Outcome.QUEUED
    other = await user(session_factory, trust=1, tg_id=USER + 1)
    res = await submit(session_factory, draft(), other, now=now + timedelta(minutes=30))
    assert res.outcome is Outcome.DUPLICATE and res.job_id is not None
    # a different job of the same company is fine
    res = await submit(
        session_factory,
        draft(title="Omborchi", requirements="Ombor hisobini yuritish, 1C bilish", salary="5 mln"),
        other,
        now=now + timedelta(minutes=31),
    )
    assert res.outcome is Outcome.QUEUED


# ------------------------------------------------------------------ limits
async def test_limits(session_factory: SF) -> None:
    u = await user(session_factory, trust=1)
    now = utcnow()
    st = settings(max_waiting=5)
    assert (await submit(session_factory, draft(), u, st, now)).outcome is Outcome.QUEUED
    res = await submit(session_factory, draft(title="Kassir"), u, st, now + timedelta(minutes=3))
    assert res.outcome is Outcome.LIMIT and res.limit is not None
    assert res.limit.reason is LimitReason.INTERVAL and res.limit.minutes == 7
    later = now + timedelta(minutes=11)
    res = await submit(session_factory, draft(title="Kassir", requirements="Kassa"), u, st, later)
    assert res.outcome is Outcome.QUEUED
    res = await submit(
        session_factory,
        draft(title="Oshpaz", requirements="Milliy taomlar"),
        u,
        st,
        later + timedelta(minutes=11),
    )
    assert res.limit is not None and res.limit.reason is LimitReason.DAILY
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Job)) == 2


async def test_one_waiting_job_at_a_time_and_admins_have_no_limits(session_factory: SF) -> None:
    u = await user(session_factory)  # new -> review
    now = utcnow()
    assert (await submit(session_factory, draft(), u, now=now)).outcome is Outcome.REVIEW
    res = await submit(session_factory, draft(title="Kassir"), u, now=now + timedelta(hours=1))
    assert res.limit is not None and res.limit.reason is LimitReason.WAITING

    admin = await user(session_factory, trust=2, tg_id=9)
    for i, title in enumerate(("Kassir", "Oshpaz", "Haydovchi")):
        d = draft(title=title, requirements=f"talab {title}", phone=f"+99890000000{i}")
        assert (await submit(session_factory, d, admin, now=now)).outcome is Outcome.QUEUED


async def test_reject(session_factory: SF) -> None:
    u = await user(session_factory)
    res = await submit(session_factory, draft(), u)
    async with session_factory() as s, s.begin():
        job = await js.reject(s, res.job_id or 0)
        assert job is not None and job.status is JobStatus.REJECTED
        assert await js.reject(s, res.job_id or 0) is None
