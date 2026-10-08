"""PART B — the extraction / formatting errors seen in the channel sample of 2026-10-07, each with
an anonymized reconstruction of its source post (tests/sample_posts.py, fake contacts)."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, Settings, load_settings
from ayvona.db.models import RawPostStatus
from ayvona.processing.classify import Classifier, PostInput, PostKind
from ayvona.processing.clean import Cleaner
from ayvona.processing.dedup import DedupIndex, make_entry, title_core, variants
from ayvona.processing.extract import Extraction, Extractor
from ayvona.processing.formatter import FormattedPost, Formatter
from ayvona.processing.pipeline import Pipeline
from ayvona.processing.tone import Tone
from ayvona.services import admin_alerts
from tests import sample_posts as S
from tests.worker_helpers import SF, RecordingNotifier, add_raw, add_source, get_raw, make_settings

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
TAG_RE = re.compile(r"<[^>]+>")


@pytest.fixture(scope="module")
def st() -> Settings:
    return load_settings(DEFAULT_CONFIG_DIR, env_file=None)


@pytest.fixture(scope="module")
def tools(st: Settings) -> tuple[Classifier, Extractor, Cleaner, Formatter]:
    return (
        Classifier(st.filters, st.source_rules),
        Extractor(st),
        Cleaner(st.source_rules),
        Formatter(st),
    )


def run(
    tools: tuple[Classifier, Extractor, Cleaner, Formatter], text: str
) -> tuple[Extraction, FormattedPost, str]:
    cl, exr, cleaner, fmt = tools
    post = PostInput(text=text, source="@test_kanal", posted_at=NOW)
    assert cl.classify(post, NOW).kind is PostKind.JOB
    ex = exr.extract(post)
    out = fmt.format(
        ex, cleaner.clean(text, None, source="@test_kanal"), source_url="https://t.me/test_kanal/1"
    )
    return ex, out, html.unescape(TAG_RE.sub("", out.html))


def line(caption: str, prefix: str) -> str | None:
    return next((ln for ln in caption.split("\n") if ln.startswith(prefix)), None)


def tags(caption: str) -> set[str]:
    return {t for ln in caption.split("\n") if ln.startswith("#") for t in ln.split()}


# ------------------------------------------------------------------ B.1 category / region / tags
def test_tin_can_workshop_is_production_in_tashkent(tools) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, S.TIN_CAN_WORKSHOP)
    assert ex.category == "ishlab_chiqarish"  # "temir banka" is a jar, not a bank
    assert "#moliya" not in tags(caption) and "Buxgalteriya" not in caption
    # the region comes only from the address field: "Qarshi" in a sentence is not where it is
    assert ex.region == "toshkent_sh" and "#qashqadaryo" not in tags(caption)


def test_cybersecurity_is_it(tools) -> None:  # noqa: ANN001
    ex, out, caption = run(tools, S.CYBERSECURITY)
    assert (ex.category, ex.profession) == ("it", "kiberxavfsizlik")
    assert "#texnolog" not in tags(caption) and "#it" in tags(caption)
    # the fallback template shows the found position, not "Yangi ish e'loni — <category>"
    assert out.fallback and caption.startswith("💼 Kiberxavfsizlik mutaxassisi\n")


@pytest.mark.parametrize(
    ("text", "profession"),
    [
        (S.HEAD_OF_MARKETING, "marketolog"),
        (S.GROWTH_MARKETING, "marketolog"),
        (S.MARKETING_SPECIALIST, "marketolog"),
        (S.MARKETING_DIRECTOR, "marketolog"),
        (S.DIGITAL_CONTENT, "smm"),
        (S.CONTENT_MANAGER, "smm"),
    ],
)
def test_marketing_roles_get_the_marketing_category(tools, text: str, profession: str) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, text)
    assert ex.category == "marketing" and ex.profession == profession
    assert "#boshqa" not in tags(caption) and "#marketing" in tags(caption)


# ------------------------------------------------------------------ B.2 titles
@pytest.mark.parametrize(
    ("text", "title"),
    [
        (S.MARKETING_SPECIALIST, "Marketing mutaxassisi"),
        (S.MARKETING_DIRECTOR, "Marketing direktori"),
        (S.MEN_AND_WOMEN, "Sex ishchisi"),  # was "Erkak va ayollarini"
        (S.WAREHOUSE_WORKER, "Ombor ishchisi"),  # was "Ishchi" (and a requirements line)
        (S.UPDATE_SPECIALIST, "Yuk kuzatuvi mutaxassisi (Update)"),
        (S.CASHIER, "Kassir va vitrinachi"),
        (S.ILLUSTRATOR, "Illustration dizayner"),
    ],
)
def test_titles(tools, text: str, title: str) -> None:  # noqa: ANN001
    _, _, caption = run(tools, text)
    assert caption.split("\n")[0] == f"💼 {title}"


def test_title_sanity_rules(tools) -> None:  # noqa: ANN001
    fix = tools[1].fix_title
    assert fix("Erkak va ayollarini") is None  # names no position
    assert fix("Yigitlar va qizlarni") is None
    assert fix("Kiberxavfsizlik bo'yicha") is None  # the position word got lost
    assert fix("Mutaxassis bo'yicha marketing") == "Marketing mutaxassisi"
    assert fix("Boshliq bo'yicha savdo") == "Savdo boshlig'i"
    assert fix("Sotuv bo'yicha menejer") == "Sotuv bo'yicha menejer"  # correct order: untouched
    assert fix("Sotuv Menejeri") == "Sotuv menejeri"
    assert fix("Kassir VA vitrinachi") == "Kassir va vitrinachi"
    assert fix("Digital Content Specialist") == "Digital Content Specialist"  # English keeps case
    assert fix("Uzum Tezkor kuryeri") == "Uzum Tezkor kuryeri"  # a name stays


def test_illustrator_company_is_taken_out_of_the_title(tools) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, S.ILLUSTRATOR)
    assert ex.company == "Test Agency" and "🏢 Kompaniya: Test Agency" in caption


# ------------------------------------------------------------------ B.3 salary
def test_range_with_a_short_lower_bound(tools) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, S.SALES_OPERATOR)
    assert (ex.salary_min, ex.salary_max) == (3_000_000, 7_000_000)
    assert line(caption, "💰") == "💰 Maosh: 3 000 000 – 7 000 000 so'm"


def test_numbers_that_cannot_be_som_are_not_shown(tools) -> None:  # noqa: ANN001
    _, out, caption = run(tools, S.MARKETING_DIRECTOR)
    assert line(caption, "💰") == "💰 Maosh: Kelishiladi"  # not "1 000 – 5 000 so'm"
    assert out.full_html is not None and "💬 Maosh haqida: 1 000 – 5 000 so'm" in out.full_html


def test_a_dollar_sign_elsewhere_makes_it_dollars(tools) -> None:  # noqa: ANN001
    text = S.MARKETING_DIRECTOR.replace("1 000 – 5 000 so'm", "1 000 – 5 000") + "\nTo'lov $ da"
    ex, _, caption = run(tools, text)
    assert (ex.currency, ex.salary_min, ex.salary_max) == ("USD", 1000, 5000)
    assert line(caption, "💰") == "💰 Maosh: 1 000 – 5 000 $"


def test_a_salary_sentence_is_normalized_never_cut(tools) -> None:  # noqa: ANN001
    _, out, caption = run(tools, S.TEACHER_AND_ADMIN)
    salary = line(caption, "💰") or ""
    assert salary == "💰 Maosh: 3 000 000 so'm (administrator)" and "…" not in salary
    # the conditions are kept in the bot's full card
    assert out.full_html is not None
    assert "O'qituvchilar uchun har bir o'quvchidan 50 000 so'm" in out.full_html


# ------------------------------------------------------------------ B.4 company
@pytest.mark.parametrize("text", [S.CALL_OPERATOR_SLOGAN, S.SALES_SLOGAN, S.COFFEE_LADY])
def test_slogans_and_sentences_are_not_a_company(tools, text: str) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, text)
    assert ex.company is None and "🏢 Kompaniya" not in caption


def test_company_quotes_are_balanced(tools) -> None:  # noqa: ANN001
    ex, _, _ = run(tools, S.SCHOOL_QUOTE)
    assert ex.company == '"Testismus school" xususiy maktabi'


@pytest.mark.parametrize(
    ("value", "company"),
    [
        ("CITY HOUSE — bino inshootlar fabrikasi", "CITY HOUSE"),
        ("Kompaniya haqida: Sfera — 4 yildan buyon brendlarni patentlaydi", "Sfera"),
        (
            "GEPARD IMPORT EXPORT\" mas'uliyati cheklangan jamiyati",
            "GEPARD IMPORT EXPORT mas'uliyati cheklangan jamiyati",
        ),
        ("O'quv markaz", None),
        ("KHADYA NUR kompaniyasi oxranalik lavozimiga xodim qabul qiladi", None),
        ("Chetga o'qishga jo'natish bilan shug'illanadi", None),
        ("kulubnika v shokolade ga", None),
        ("Ilhom Testqulov", "Ilhom Testqulov"),
        ("Omega", "Omega"),
        ("MAD MEDIA HUB MCHJ", "MAD MEDIA HUB MCHJ"),
    ],
)
def test_company_rules(tools, value: str, company: str | None) -> None:  # noqa: ANN001
    assert tools[1]._clean_company(value) == company


# ------------------------------------------------------------------ B.5 duplicates
def entry(tools, key: str, text: str, minutes: int):  # noqa: ANN001, ANN201
    cl, exr, _, _ = tools
    post = PostInput(text=text, source="@test_kanal", posted_at=NOW + timedelta(minutes=minutes))
    c = cl.classify(post, NOW)
    ex = exr.extract(post)
    return make_entry(
        key,
        post.posted_at,  # type: ignore[arg-type]
        c.clean_text,
        [*c.contacts.phones, *c.contacts.usernames],
        title=ex.title,
        company=ex.company,
    )


def test_same_vacancy_retyped_in_another_channel_is_a_duplicate(tools) -> None:  # noqa: ANN001
    index = DedupIndex()
    assert index.check(entry(tools, "a", S.DUPLICATE_A, 0)) is None
    match = index.check(entry(tools, "b", S.DUPLICATE_B, 45))
    assert match is not None and match.original == "a" and match.layer == "contact"


def test_same_recruiter_different_positions_is_not_a_duplicate(tools) -> None:  # noqa: ANN001
    template = (
        "🏢 TEST LOGISTICS LLC\n👔 Position: {pos}\n🌎 Location: Mirobod, Toshkent\n"
        "💵 Salary: Discussed on the interview\n📋 Job Requirements:\n{req}\n"
        "Contact: @test_recruiter"
    )
    safety = "• Clean driving records knowledge\n• FMCSA rules\n• Accident reports"
    update = "• Track loads in real time\n• Call drivers and brokers\n• Update the TMS"
    index = DedupIndex()
    a = entry(tools, "a", template.format(pos="Safety Specialist", req=safety), 0)
    assert index.check(a) is None
    b = entry(tools, "b", template.format(pos="Update Specialist", req=update), 30)
    assert index.check(b) is None
    # two different employers behind one recruiter are never one vacancy
    other = S.DUPLICATE_B.replace("Ilxom Testkulov", "Boshqa Firma MChJ")
    index2 = DedupIndex()
    index2.check(entry(tools, "a", S.DUPLICATE_A, 0))
    assert index2.check(entry(tools, "b", other, 45)) is None


def test_spelling_variants_and_title_core() -> None:
    assert variants("Ilxom Begimqulov") == variants("Ilhom Begimkulov")
    assert title_core('"HUNTER" sotuv menejeri') == title_core("Sotuv menejer") == "sotuv"
    assert title_core("O'qituvchi") == ""  # only a role word: cannot tell positions apart


async def test_pipeline_marks_it_duplicate_and_the_admin_alert_says_so(
    session_factory: SF,
) -> None:
    sf = session_factory
    settings = make_settings()
    assert Pipeline(settings, sf).index.window == timedelta(days=settings.app.dedup.window_days)
    a = await add_raw(
        sf,
        await add_source(sf, "@test_kanal_a"),
        S.DUPLICATE_A,
        posted_ago=timedelta(minutes=50),
        fetched_ago=timedelta(minutes=49),
    )
    b = await add_raw(
        sf,
        await add_source(sf, "@test_kanal_b"),
        S.DUPLICATE_B,
        posted_ago=timedelta(minutes=5),
        fetched_ago=timedelta(minutes=4),
    )
    await Pipeline(settings, sf, RecordingNotifier()).run_once()  # type: ignore[arg-type]
    first, second = await get_raw(sf, a), await get_raw(sf, b)
    assert first.status is RawPostStatus.DONE
    assert second.status is RawPostStatus.DUPLICATE and second.job_id == first.job_id
    async with sf() as s:
        from ayvona.db.models import Job

        job = await s.get(Job, first.job_id)
    state = admin_alerts.post_state(second, job)
    assert not state.published and state.reason and state.reason.startswith("dublikat")


# ------------------------------------------------------------------ B.6 meaningless fields
def test_requirements_that_only_repeat_the_title_are_dropped(tools) -> None:  # noqa: ANN001
    _, _, caption = run(tools, S.TEACHER_AND_ADMIN)
    assert "Talablar" not in caption  # "Talablar: Administrator uchun"
    fmt = tools[3]
    ex = Extraction(title="Administrator")
    assert fmt.meaningless("Administrator uchun", ex)
    assert fmt.meaningless("Lmk cf", ex)
    assert not fmt.meaningless("18–30 yosh", ex)  # numbers count
    assert not fmt.meaningless("Excel, Google Docs", ex)


# ------------------------------------------------------------------ B.7 shouting / rude text
def test_tone(st: Settings) -> None:
    tone = Tone(st.app.tone)
    assert (
        tone.normalize("!!️FAQAT ERKAKLAR UCHUN ISH. AYOLLAR BEZOVTA QILMANG!")
        == "Faqat erkaklar uchun ish."
    )
    assert tone.normalize("TALABALAR BEZOVTA QILMASIN!") is None  # nothing factual left
    assert (
        tone.normalize("🔥 HR MENEJER VA KPI BO'YICHA MUTAXASSIS KERAK!!! 🔥🔥🔥")
        == "🔥 Hr menejer va KPI bo'yicha mutaxassis kerak! 🔥"
        or tone.normalize("🔥 HR MENEJER VA KPI BO'YICHA MUTAXASSIS KERAK!!! 🔥🔥🔥")
        == "🔥 HR menejer va KPI bo'yicha mutaxassis kerak! 🔥"
    )
    assert tone.normalize("KOREYADA E-7 VIZASI BO'YICHA YANGI IMKONIYAT") == (
        "Koreyada E-7 vizasi bo'yicha yangi imkoniyat"
    )
    assert tone.normalize("Oddiy matn, katta harf: HR.") == "Oddiy matn, katta harf: HR."


def test_the_full_card_has_the_calm_text(tools) -> None:  # noqa: ANN001
    _, out, caption = run(tools, S.TIN_CAN_WORKSHOP)
    assert "BEZOVTA" not in caption and "AYOLLAR" not in caption
    full = out.full_html or ""
    assert "Faqat erkaklar uchun ish." in full and "bezovta" not in full.lower()
    assert "Mexanik (oylik alohida kelishiladi)" in full  # the rest of the post is kept


# ------------------------------------------------------------------ B.8 other
def test_quoted_name_in_the_title_is_not_a_profession(tools) -> None:  # noqa: ANN001
    ex, _, caption = run(tools, S.DUPLICATE_B)
    assert ex.profession == "sotuv_menejeri" and "#hr" not in tags(caption)  # "HUNTER"


def test_no_caption_has_a_link_to_the_source_post_or_a_cut_word(tools) -> None:  # noqa: ANN001
    for name, text in S.ALL.items():
        _, out, caption = run(tools, text)
        assert "asl e'londa" not in caption, name
        assert not re.search(r"[^\W_]…", caption), name
        assert out.length <= 1024, name
