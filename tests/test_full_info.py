"""PART A — "📖 To'liq ma'lumot" stays in OUR bot: a shortened caption gets a button to the bot's
full card (``jobs.full_html``), never a link to the source channel; cuts happen only after a whole
sentence / list item. Anonymized fixtures (fake phones and usernames). Mocked Bot API."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import update

from ayvona.db.models import Job, JobStatus
from ayvona.processing.formatter import truncate_units, visible_len
from ayvona.processing.pipeline import Pipeline
from ayvona.processing.project_format import format_project, parse_budget
from ayvona.services import job_submission as js
from tests.test_admin_bot import BotHarness, message_update
from tests.test_job_submission import draft, settings, submit, user
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, RecordingNotifier, add_raw, add_source, get_job, get_raw

USER = 777

# The "HR menejer" post of the 2026-10-07 sample (school name, contacts changed): long, so the
# caption had been cut mid-sentence ("KPI, motivatsiya va baholash…") with a source link.
HR_POST = """🏫 Nur School'ga HR MENEJER lavozimiga taklif qilamiz!

🎯 ASOSIY VAZIFALAR
- Yagona HR siyosatini noldan ishlab chiqish va rivojlantirish;
- TOP-menejment, akademik va administrativ lavozimlar uchun xodimlarni jalb qilish;
- Rekruting va ishga qabul qilish jarayonlarini boshqarish;
- Onboarding, xodimlarni baholash va rivojlantirish tizimini yo'lga qo'yish;
- KPI va motivatsiya tizimlarini ishlab chiqish va joriy etish;
- HR jarayonlarini tahlil qilish va avtomatlashtirish (HRM/CRM);
- Korporativ madaniyat, team-building va 1-on-1 tizimini rivojlantirish.

🔎 NOMZODGA TALABLAR
- HR jarayonlarini noldan qurish va tizimlashtirish tajribasi;
- HR Policy, reglament va yo'riqnomalar ishlab chiqish ko'nikmasi;
- C-level va rahbar lavozimlariga nomzodlar bilan ishlash tajribasi;
- KPI, motivatsiya va baholash tizimlarini joriy qilish tajribasi;
- Ta'lim sohasida ishlagan bo'lsa ustunlik beriladi;
- Rus va ingliz tillarini bilish afzallik.

💼 SHARTLAR
- Rasmiy ishga joylashish va barqaror oylik;
- Zamonaviy ofis, do'stona jamoa;
- Kasbiy o'sish uchun kurslar va treninglar.

📍 Manzil: Toshkent sh., Yunusobod tumani
📩 Rezyume: @hr_test_school"""


def pipeline(sf: SF) -> Pipeline:
    from tests.worker_helpers import make_settings

    return Pipeline(make_settings(), sf, RecordingNotifier())  # type: ignore[arg-type]


def no_mid_cut(caption: str) -> bool:
    """Every "…" follows a whole unit (". ! ? ;" or a line end), never a word."""
    return not re.search(r"[^\s.!?;]\s?…", caption.replace("\n…", "."))


# ------------------------------------------------------------------ cutting rules
def test_truncate_units_cuts_only_after_whole_units() -> None:
    text = "Birinchi gap. Ikkinchi gap uzunroq. Uchinchi gap juda ham uzun bo'lib ketadi."
    assert truncate_units(text, 40) == "Birinchi gap. Ikkinchi gap uzunroq. …"
    assert truncate_units(text, 200) == text  # fits: unchanged
    items = "- birinchi talab;\n- ikkinchi talab;\n- uchinchi talab;\n- to'rtinchi talab;"
    assert truncate_units(items, 40) == "- birinchi talab;\n- ikkinchi talab;\n…"
    # a header left without its items goes too
    headed = "Ish haqida matn bor.\n\n🔎 NOMZODGA TALABLAR\n- juda uzun talab " + "x" * 80
    assert truncate_units(headed, 60) == "Ish haqida matn bor.\n…"
    # a clause when not even the first sentence fits; nothing at all -> ""
    assert truncate_units("Shoahmad ko'chasi, 12-uy, Shayxontohur tumani", 30).endswith(" …")
    assert truncate_units("Bitta juda uzun so'z" + "z" * 50, 10) == ""
    for limit in range(5, 90, 3):  # never inside a word
        cut = truncate_units(text, limit)
        assert not cut or cut == text or cut.endswith((". …", "\n…")), (limit, cut)


# ------------------------------------------------------------------ aggregator post
async def test_shortened_post_gets_the_bot_button_and_no_source_link(
    session_factory: SF, tmp_path: Path
) -> None:
    sf = session_factory
    src = await add_source(sf, "@test_hr_kanal")
    raw = await add_raw(sf, src, HR_POST, external_id="1497")
    await pipeline(sf).run_once()
    job = await get_job(sf, (await get_raw(sf, raw)).job_id)  # type: ignore[arg-type]
    caption = job.formatted_text or ""

    assert visible_len(caption) <= 1024
    assert "asl e'londa" not in caption and "To'liq ma'lumot:" not in caption
    assert no_mid_cut(caption), caption
    assert 'href="https://t.me/test_hr_kanal/1497">manba</a>' in caption  # attribution kept
    urls = {b["text"]: b["url"] for row in job.buttons or [] for b in row}
    assert urls["📖 To'liq ma'lumot"] == f"https://t.me/ayvona_jobs_bot?start=job_{job.id}"
    assert "⭐ Saqlash" in urls and "🔍 Boshqa ishlar" in urls  # the other buttons stay
    full = job.full_html or ""
    assert "Kasbiy o'sish uchun kurslar va treninglar." in full  # the very end of the post
    assert "KPI, motivatsiya va baholash tizimlarini joriy qilish tajribasi;" in full

    # the deep link opens the full card in our bot
    async with sf() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job.id).values(status=JobStatus.PUBLISHED))
    harness = BotHarness(bot_settings(tmp_path), sf)
    await harness.send(message_update(f"/start job_{job.id}", uid=USER))
    assert harness.texts()[-1] == full


async def test_short_post_has_no_full_card(session_factory: SF) -> None:
    sf = session_factory
    src = await add_source(sf, "@test_kanal")
    text = "Sotuvchi kerak\nMaosh: 4 mln so'm\nManzil: Toshkent, Chilonzor\nTel: +998 90 000 00 01"
    raw = await add_raw(sf, src, text)
    await pipeline(sf).run_once()
    job = await get_job(sf, (await get_raw(sf, raw)).job_id)  # type: ignore[arg-type]
    assert job.full_html is None
    assert not any(b["text"].startswith("📖") for row in job.buttons or [] for b in row)


# ------------------------------------------------------------------ user ads
async def test_user_ad_with_long_text_gets_the_button_and_shows_all_of_it(
    session_factory: SF, tmp_path: Path
) -> None:
    sf = session_factory
    requirements = "\n".join(f"- {i}-talab: ishga mas'uliyat bilan yondashish;" for i in range(40))
    u = await user(sf, trust=1, tg_id=USER)
    result = await submit(sf, draft(requirements=requirements), u, settings())
    assert result.outcome is js.Outcome.QUEUED
    async with sf() as s:
        job = await s.get(Job, result.job_id)
    assert job is not None
    assert visible_len(job.formatted_text or "") <= 1024
    assert no_mid_cut(job.formatted_text or "")
    assert any(b["text"] == "📖 To'liq ma'lumot" for row in job.buttons or [] for b in row)
    assert "39-talab" in (job.full_html or "")  # everything the user wrote

    async with sf() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job.id).values(status=JobStatus.PUBLISHED))
    harness = BotHarness(bot_settings(tmp_path), sf)
    await harness.send(message_update(f"/start job_{job.id}", uid=USER + 1))
    assert "39-talab" in harness.texts()[-1]


def test_project_with_long_description() -> None:
    st = settings()
    description = " ".join(f"{i}-bosqichda bot yangi funksiyani oladi." for i in range(60))
    post = format_project(
        title="Telegram bot yasash",
        description=description,
        budget=parse_budget("3 mln so'm", st),
        deadline="2 hafta",
        phone="+998900000001",
        username="@test_buyurtmachi",
        settings=st,
    )
    assert visible_len(post.html) <= 1024 and no_mid_cut(post.html)
    assert post.full_html is not None and "59-bosqichda" in post.full_html
    texts = [b["text"] for row in post.buttons(5) for b in row]
    assert "📖 To'liq ma'lumot" in texts


@pytest.mark.parametrize("n", [1, 3])
def test_project_short_description_has_no_button(n: int) -> None:
    st = settings()
    post = format_project(
        title="Logo dizayni",
        description="Kafe uchun logo. " * n,
        budget=parse_budget(None, st),
        deadline=None,
        phone=None,
        username="@test_buyurtmachi",
        settings=st,
    )
    assert post.full_html is None
    assert all(b["text"] != "📖 To'liq ma'lumot" for row in post.buttons(5) for b in row)
