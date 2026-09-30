"""processing/formatter.py: the agreed channel template, language rule, 1024 limit, snapshots.

Snapshots: every real example (tests/fixtures/posts + regressions) is rendered into
``tests/snapshots/<kanal>_<id>.html``. After an intended change, re-create them:

    $env:UPDATE_SNAPSHOTS=1; uv run pytest tests/test_formatter.py; Remove-Item Env:UPDATE_SNAPSHOTS
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, Settings, load_settings
from ayvona.processing.classify import Classifier, PostKind
from ayvona.processing.clean import CleanedText, Cleaner, Link
from ayvona.processing.extract import Extraction, Extractor
from ayvona.processing.formatter import (
    Formatter,
    format_phone,
    telegram_post_url,
    tidy_address,
    truncate,
    visible_len,
)
from ayvona.processing.language import Language
from tests.post_fixtures import LABEL_DAY, REGRESSIONS_DIR, load_dir, to_post

SNAPSHOTS = Path(__file__).parent / "snapshots"
UPDATE = os.environ.get("UPDATE_SNAPSHOTS") == "1"
SRC = "https://t.me/manba_kanal/12345"


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(DEFAULT_CONFIG_DIR, env_file=None)


@pytest.fixture(scope="module")
def fmt(settings: Settings) -> Formatter:
    return Formatter(settings)


def job(**kw: Any) -> Extraction:
    base: dict[str, Any] = {
        "title": "Sotuvchi-konsultant",
        "title_source": "label",
        "company": "Texnomart",
        "salary_min": 4_000_000,
        "salary_max": 6_000_000,
        "currency": "UZS",
        "salary_period": "month",
        "region": "toshkent_sh",
        "regions": ("toshkent_sh",),
        "district": "Chilonzor",
        "schedule": "09:00–18:00, 6/1",
        "requirements": "18–30 yosh, rus tili bilan ishlash",
        "phones": ("+998901234567",),
        "usernames": ("@hr_texnomart",),
        "category": "sotuv",
        "profession": "sotuvchi",
        "language": Language.UZ_LATIN,
        "confidence": 0.95,
    }
    base.update(kw)
    return Extraction(**base)


# ------------------------------------------------------------------ the agreed template
def test_full_template_matches_the_agreed_example(fmt: Formatter) -> None:
    out = fmt.format(job(), source_url=SRC)
    assert out.html == (
        "💼 <b>Sotuvchi-konsultant</b>\n"
        "🏢 Kompaniya: Texnomart\n"
        "\n"
        "💰 Maosh: 4 000 000 – 6 000 000 so'm\n"
        "📍 Manzil: Toshkent sh., Chilonzor tumani\n"
        "🕒 Ish vaqti: 09:00–18:00, 6/1\n"
        "📋 Talablar: 18–30 yosh, rus tili bilan ishlash\n"
        "\n"
        "📞 Aloqa: +998 90 123 45 67\n"
        "✉️ Telegram: @hr_texnomart\n"
        "\n"
        "#sotuvchi #sotuv #toshkent\n"
        "➖➖➖➖➖➖➖➖\n"
        "🔍 Ish qidiryapsizmi? @ayvona_jobs_bot\n"
        "📢 @ayvonajobs — Ayvona Jobs\n"
        '<i><a href="https://t.me/manba_kanal/12345">manba</a></i>'
    )
    assert not out.fallback


def test_empty_fields_have_no_line_and_no_salary_is_negotiable(fmt: Formatter) -> None:
    ex = job(
        company=None,
        schedule=None,
        requirements=None,
        salary_min=None,
        salary_max=None,
        currency=None,
        salary_text=None,
        district=None,
    )
    out = fmt.format(ex, source_url=SRC).html
    assert "Kompaniya" not in out and "Ish vaqti" not in out and "Talablar" not in out
    assert "💰 Maosh: Kelishiladi" in out
    assert "📍 Manzil: Toshkent sh.\n" in out


def test_user_post_has_no_source_line(fmt: Formatter) -> None:
    out = fmt.format(job()).html
    assert "manba" not in out
    assert out.endswith("📢 @ayvonajobs — Ayvona Jobs")


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"salary_max": None}, "4 000 000 so'mdan"),
        ({"salary_min": None}, "6 000 000 so'mgacha"),
        ({"salary_max": 4_000_000}, "4 000 000 so'm"),
        (
            {"salary_min": 250_000, "salary_max": 250_000, "salary_period": "day"},
            "250 000 so'm (kunlik)",
        ),
        ({"salary_min": 500, "salary_max": 800, "currency": "USD"}, "500 – 800 $"),
        ({"salary_max": None, "salary_text": "4.000.000 Fix + KPI"}, "4 000 000 so'mdan + KPI"),
        ({"salary_min": None, "salary_max": None, "salary_text": "Suhbat asosida"}, "Kelishiladi"),
        ({"salary_min": None, "salary_max": None, "salary_text": "250 000"}, "250 000"),
    ],
)
def test_salary(fmt: Formatter, kw: dict[str, Any], expected: str) -> None:
    assert f"💰 Maosh: {expected}\n" in fmt.format(job(**kw)).html


def test_multi_position_post(fmt: Formatter) -> None:
    ex = job(
        title="Anorbank",
        title_source="positions",
        company="Anorbank",
        positions=("Backend dasturchi", "Tizim tahlilchisi", "Dizayner"),
    )
    out = fmt.format(ex).html
    assert out.startswith(
        "💼 <b>Anorbank</b>\n📌 Lavozimlar:\n• Backend dasturchi\n• Tizim tahlilchisi\n• Dizayner"
    )
    assert "Kompaniya" not in out
    no_company = job(
        title="Bir nechta vakansiya",
        title_source="positions",
        company=None,
        positions=("Oshpaz", "Ofitsiant"),
    )
    assert fmt.format(no_company).html.startswith("💼 <b>Bir nechta vakansiya</b>")


def test_tags_limit_and_no_repeats(fmt: Formatter) -> None:
    ex = job(feature_tags=("masofaviy", "tajribasiz", "yotoqjoy"))
    assert fmt.format(ex).tags == ("sotuvchi", "sotuv", "toshkent", "masofaviy", "tajribasiz")
    # operator: profession tag == category tag -> written once
    op = job(category="operator", profession="operator", feature_tags=())
    assert fmt.format(op).tags == ("operator", "toshkent")
    many = job(
        region="kop_hudud",
        regions=("toshkent_sh", "samarqand", "buxoro", "andijon"),
        feature_tags=("masofaviy",),
    )
    assert len(fmt.format(many).tags) == 5


def test_everything_is_html_escaped(fmt: Formatter) -> None:
    ex = job(title="<script>alert(1)</script>", company="A & B <MChJ>")
    out = fmt.format(ex).html
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "A &amp; B &lt;MChJ&gt;" in out


def test_long_requirements_are_shortened_to_fit_1024(fmt: Formatter) -> None:
    ex = job(
        requirements="Juda uzun talab " * 200,
        schedule="Dushanba-shanba " * 5,
        phones=("+998901234567", "+998911234567", "+998931234567"),
    )
    out = fmt.format(ex, source_url=SRC)
    assert out.length <= 1024
    assert "📋 Talablar: Juda uzun talab" in out.html and "…" in out.html


def test_details_shrink_first_when_the_limit_is_tight(settings: Settings) -> None:
    app = settings.app.model_copy(
        update={"formatter": settings.app.formatter.model_copy(update={"max_caption_length": 420})}
    )
    tight = Formatter(settings.model_copy(update={"app": app}))
    ex = job(
        requirements="Juda uzun talab " * 30,
        schedule="Dushanba-shanba " * 5,
        phones=("+998901234567", "+998911234567", "+998931234567"),
    )
    out = tight.format(ex, source_url=SRC)
    assert out.length <= 420
    assert "requirements" in out.shortened
    for must in (
        "Sotuvchi-konsultant",
        "💰 Maosh",
        "📍 Manzil",
        "+998 93 123 45 67",
        "@ayvona_jobs_bot",
        "manba",
    ):
        assert must in out.html


def test_many_positions_are_shortened(fmt: Formatter) -> None:
    positions = tuple(f"Juda uzun nomli lavozim raqami {i}" for i in range(60))
    ex = job(title_source="positions", positions=positions, requirements=None)
    out = fmt.format(ex, source_url=SRC)
    assert out.length <= 1024
    assert re.search(r"… va yana \d+ ta", out.html)


def test_uzbek_cyrillic_is_transliterated(fmt: Formatter) -> None:
    ex = job(
        title="Бош ҳисобчи",
        company="«Сладово» қандолат фабрикаси",
        requirements="Тажриба 3 йилдан кам бўлмаслиги",
        schedule=None,
        language=Language.UZ_CYRILLIC,
    )
    out = fmt.format(ex).html
    assert "Bosh hisobchi" in out
    assert "«Sladovo» qandolat fabrikasi" in out
    assert "Tajriba 3 yildan kam bo'lmasligi" in out
    assert not re.search(r"[Ѐ-ӿ]", out)


# ------------------------------------------------------------------ usernames from config
def test_real_usernames_are_in_settings(settings: Settings) -> None:
    b = settings.app.branding
    assert (b.channel_username, b.bot_username) == ("ayvonajobs", "ayvona_jobs_bot")
    own = settings.source_rules.defaults.extra_own_usernames
    assert {"@ayvonajobs", "@ayvona_jobs_bot", "@ayvona"} <= set(own)


def test_signature_and_buttons_use_branding_from_config(settings: Settings) -> None:
    branding = settings.app.branding.model_copy(
        update={"channel_username": "test_kanal", "bot_username": "test_ish_bot"}
    )
    app = settings.app.model_copy(update={"branding": branding})
    out = Formatter(settings.model_copy(update={"app": app})).format(job())
    assert out.html.endswith(
        "➖➖➖➖➖➖➖➖\n🔍 Ish qidiryapsizmi? @test_ish_bot\n📢 @test_kanal — Ayvona Jobs"
    )
    urls = [b.url for row in out.buttons(job_id=7) for b in row]
    assert "https://t.me/test_ish_bot?start=save_7" in urls
    assert "https://t.me/test_ish_bot?start=search" in urls
    assert "ayvona" not in out.html


# ------------------------------------------------------------------ no hashtags in the body
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "18-30 yosh; Faqat #Erkaklar; Jismonan baquvvat",
            "18-30 yosh; Faqat erkaklar; Jismonan baquvvat",
        ),
        ("#Ayollar uchun", "Ayollar uchun"),
        ("Yotoqxona bor #yotoqjoy", "Yotoqxona bor yotoqjoy"),
        ("Xushmuomala; #Talabalarni_ham_ishga_olamiz", "Xushmuomala; Talabalarni ham ishga olamiz"),
        ("#DIMKA Sushka va krekerlar", "DIMKA Sushka va krekerlar"),
        (
            "Ish joyi #Toshkent markazida",
            "Ish joyi Toshkent markazida",
        ),  # a place keeps its capital
        ("C# dasturchi, site.uz/#narx, #1 kompaniya", "C# dasturchi, site.uz/#narx, #1 kompaniya"),
        ("# Toshkent", "Toshkent"),
        ("Oddiy  matn  (heshtegsiz)", "Oddiy  matn  (heshtegsiz)"),  # untouched
    ],
)
def test_hashtags_inside_text_become_words(fmt: Formatter, text: str, expected: str) -> None:
    assert fmt._plain(text) == expected


def test_only_the_tag_line_has_hashtags(fmt: Formatter) -> None:
    ex = job(
        title="#Sotuvchi",
        company="#Texnomart",
        schedule="09:00–18:00 #smena",
        requirements="18–30 yosh; Faqat #Erkaklar",
        address="#Toshkent #Chilonzor",
        feature_tags=("yotoqjoy",),
    )
    lines = fmt.format(ex, source_url=SRC).html.split("\n")
    tag_line = lines.index("#sotuvchi #sotuv #toshkent #yotoqjoy")
    assert not [ln for i, ln in enumerate(lines) if "#" in ln and i != tag_line]
    assert "📋 Talablar: 18–30 yosh; Faqat erkaklar" in lines


def test_non_place_hashtags_of_the_address_keep_their_meaning(fmt: Formatter) -> None:
    ex = job(address="#Toshkent  #Ayollar #Erkaklar", district=None, requirements="Tajriba")
    out = fmt.format(ex).html
    assert "📍 Manzil: Toshkent\n" in out
    assert "📋 Talablar: Ayollar, erkaklar; Tajriba" in out
    assert "#Ayollar" not in out and "#Erkaklar" not in out


def test_fallback_body_has_no_hashtags(fmt: Formatter) -> None:
    cleaned = CleanedText(
        text="Yangi do'kon\n#DIMKA Sushka va krekerlar\nFaqat #Ayollar\n#vakansiya #ish",
        links=(),
    )
    out = fmt.format(job(confidence=0.3), cleaned).html
    assert "DIMKA Sushka va krekerlar\nFaqat ayollar" in out
    body = out.split("\n\n#")[0]  # everything above our tag line
    assert "#" not in body


# ------------------------------------------------------------------ address commas
@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("Samarqand viloyati Samarqand shahri", "Samarqand viloyati, Samarqand shahri"),
        ("Toshkent shahar Yashnobod tumani", "Toshkent sh., Yashnobod tumani"),
        ("Toshkent sh. Yashnobod tumani", "Toshkent sh., Yashnobod tumani"),
        ("Toshkent shahri Toshkent", "Toshkent sh."),
        ("Toshkent sh., Toshkent", "Toshkent sh."),
        (
            "Toshkent shaxar Olmazor tumani Chukursoy 82",
            "Toshkent sh., Olmazor tumani, Chukursoy 82",
        ),
        ("Toshkent.Sh Mirzo Ulug'bek Tumani massiv", "Toshkent sh., Mirzo Ulug'bek tumani massiv"),
        ("Toshkent shahar , Uchtepa tumani", "Toshkent sh., Uchtepa tumani"),
        ("Toshkent viloyati Keles shahari", "Toshkent viloyati, Keles shahari"),
        ("Mirobod tumani, Kuylyuk,Kompas", "Mirobod tumani, Kuylyuk, Kompas"),
        # unchanged: no capital word after the unit / not a repeat / another word form
        ("Toshkent shahri bo'ylab", "Toshkent shahri bo'ylab"),
        ("Toshkent shahridan 3 km", "Toshkent shahridan 3 km"),
        ("Toshkent viloyati, Toshkent", "Toshkent viloyati, Toshkent"),
        ("Buxoro viloyati, G'ijduvon shahar", "Buxoro viloyati, G'ijduvon shahar"),
    ],
)
def test_address_commas(fmt: Formatter, address: str, expected: str) -> None:
    assert tidy_address(address, fmt._city_titles) == expected


def test_address_in_the_post(fmt: Formatter) -> None:
    samarqand = job(
        region="samarqand",
        regions=("samarqand",),
        district=None,
        address="Samarqand viloyati Samarqand shahri",
    )
    out = fmt.format(samarqand).html
    assert "📍 Manzil: Samarqand viloyati, Samarqand shahri\n" in out
    yashnobod = job(district=None, address="Toshkent shahar Yashnobod tumani")
    assert "📍 Manzil: Toshkent sh., Yashnobod tumani\n" in fmt.format(yashnobod).html
    # no city in the address -> ours is put first; another region named -> nothing added
    street = job(district=None, address="Samarqand Darvoza ro'parasi")
    assert "📍 Manzil: Toshkent sh., Samarqand Darvoza ro'parasi\n" in fmt.format(street).html
    other = job(district=None, address="Navoiy viloyati")
    assert "📍 Manzil: Navoiy viloyati\n" in fmt.format(other).html


@pytest.mark.parametrize(
    ("fixture_id", "must", "must_not"),
    [
        (
            "ishtoparuz_kanal_25045",
            [
                "📋 Talablar: 18-30 yosh; Faqat erkaklar",
                "📍 Manzil: Samarqand viloyati, Samarqand shahri",
            ],
            ["#Erkaklar"],
        ),
        (
            "manavakansiya_uz_68991",
            ["📍 Manzil: Toshkent", "Ayollar, erkaklar"],
            ["#Ayollar", "#Erkaklar", "#Toshkent"],
        ),
        (
            "ishlaUZ_rasmiy_11779",
            ["📍 Manzil: Toshkent sh., Yakkasaroy Minglar ko'chasi 36-uy"],
            ["#Toshkent"],
        ),
    ],
)
def test_real_posts_with_hashtags_and_addresses(
    fixture_id: str,
    must: list[str],
    must_not: list[str],
    pipeline: tuple[Classifier, Extractor, Cleaner, Formatter],
) -> None:
    fx = next(f for f in FIXTURES if f["id"] == fixture_id)
    got = render_snapshot(fx, pipeline).split("\n", 1)[1]  # without the fixture title line
    for text in must:
        assert html.escape(text, quote=False) in got, text
    for text in must_not:
        assert text not in got, text
    assert "🔍 Ish qidiryapsizmi? @ayvona_jobs_bot\n📢 @ayvonajobs — Ayvona Jobs" in got


def test_russian_post_gets_uzbek_fields_only(fmt: Formatter) -> None:
    ex = job(
        title="Бухгалтер",
        title_uz="Buxgalter",
        company="ООО Ромашка",
        requirements="Опыт работы от 3 лет",
        schedule="Пн-Пт с 9 до 18",
        address="Ташкент, Юнусабад",
        language=Language.RU,
        category="moliya",
        profession="buxgalter",
    )
    out = fmt.format(ex, source_url=SRC).html
    assert "💼 <b>Buxgalter</b>" in out
    assert "Talablar" not in out and "Опыт" not in out and "Ish vaqti" not in out
    assert f"📝 To'liq ma'lumot: <a href=\"{SRC}\">asl e'londa</a>" in out
    assert not re.search(r"[Ѐ-ӿ]", out)


def test_untranslated_russian_title_uses_the_profession(fmt: Formatter) -> None:
    ex = job(
        title="Менеджер по работе с ключевыми клиентами",
        title_uz="Menejer po rabote s klyuchevymi klientami",  # word-by-word result
        language=Language.RU,
        category="sotuv",
        profession="sotuv_menejeri",
    )
    assert "💼 <b>Sotuv menejeri</b>" in fmt.format(ex).html


def test_foreign_schedule_keeps_only_times_and_days(fmt: Formatter) -> None:
    ru = job(language=Language.RU, title="Бухгалтер", schedule="с 10:00 до 19:00, 5/2")
    assert "🕒 Ish vaqti: 10:00–19:00, 5/2\n" in fmt.format(ru).html
    en = job(language=Language.EN, title="Accountant", schedule="Flexible hours")
    assert "Ish vaqti" not in fmt.format(en).html


def test_title_starts_with_a_capital_letter(fmt: Formatter) -> None:
    assert (
        "💼 <b>Moddiy ashyoviy xisobchi</b>"
        in fmt.format(job(title="moddiy ashyoviy xisobchi")).html
    )


def test_address_is_shown_with_its_region(fmt: Formatter) -> None:
    ex = job(address="Chilonzor 9-kvartal, Novza metro yonida")
    assert "📍 Manzil: Toshkent sh., Chilonzor 9-kvartal, Novza metro yonida" in fmt.format(ex).html
    ex = job(address="Toshkent, Yunusobod 4-kvartal", is_remote=True)
    assert "📍 Manzil: Masofaviy, Toshkent, Yunusobod 4-kvartal" in fmt.format(ex).html


def test_fallback_template(fmt: Formatter) -> None:
    cleaned = CleanedText(
        text="Bizga tajribali xodim kerak!\nAriza: havola\n#ish #vakansiya",
        links=(Link("havola", "https://forms.gle/abc"),),
    )
    ex = job(
        title=None,
        title_source=None,
        company=None,
        confidence=0.45,
        phones=("+998901234567",),
        usernames=(),
    )
    out = fmt.format(ex, cleaned, source_url=SRC)
    assert out.fallback
    assert out.html.startswith(
        "💼 <b>Yangi ish e'loni — Sotuv va savdo</b>\n\n"
        'Bizga tajribali xodim kerak!\nAriza: <a href="https://forms.gle/abc">havola</a>\n\n'
        "📞 Aloqa: +998 90 123 45 67"
    )
    assert "#vakansiya" not in out.html  # the source's own tags are dropped


def test_foreign_fallback_has_fields_and_a_link_instead_of_text(fmt: Formatter) -> None:
    cleaned = CleanedText(text="We are hiring! Great team, remote-friendly culture ...")
    ex = job(
        title="Recruitment Assistant",
        title_uz="Rekruter yordamchisi",
        company=None,
        language=Language.EN,
        confidence=0.55,
        category="ofis",
        profession="hr",
    )
    out = fmt.format(ex, cleaned, source_url=SRC)
    assert out.fallback
    assert out.html.startswith("💼 <b>Rekruter yordamchisi</b>\n\n💰 Maosh: 4 000 000")
    assert "We are hiring" not in out.html
    assert f"📝 To'liq ma'lumot: <a href=\"{SRC}\">asl e'londa</a>" in out.html


def test_fallback_body_does_not_repeat_the_contacts(fmt: Formatter) -> None:
    cleaned = CleanedText(
        text="Bog'ga ishchi kerak, oylik 4.5mln\n\n📞 MUROJAAT UCHUN:\n\n+998 99 197 67 96\n"
        "TELEGRAM : @OzodXakimov\nQo'shimcha: +998 90 000 11 22 ga ham yozing, kechqurun"
    )
    ex = job(title=None, confidence=0.4, phones=("+998991976796",), usernames=("@OzodXakimov",))
    out = fmt.format(ex, cleaned).html
    assert out.startswith(
        "💼 <b>Yangi ish e'loni — Sotuv va savdo</b>\n\nBog'ga ishchi kerak, oylik 4.5mln\n"
        "Qo'shimcha: +998 90 000 11 22 ga ham yozing, kechqurun\n\n"  # not shown below: kept
        "📞 Aloqa: +998 99 197 67 96\n✉️ Telegram: @OzodXakimov"
    )


def test_fallback_long_body_is_cut_with_a_link_to_the_original(fmt: Formatter) -> None:
    cleaned = CleanedText(text="Ish haqida juda uzun matn. " * 100)
    out = fmt.format(job(confidence=0.3), cleaned, source_url=SRC)
    assert out.length <= 1024
    assert "…" in out.html and "📝 To'liq ma'lumot" in out.html


def test_buttons(fmt: Formatter) -> None:
    out = fmt.format(job(apply_url="hh.uz/vacancy/1"))
    rows = [[(b.text, b.url) for b in row] for row in out.buttons(job_id=42)]
    assert rows == [
        [
            ("📩 Murojaat", "https://t.me/hr_texnomart"),
            ("🔗 Ariza topshirish", "https://hh.uz/vacancy/1"),
        ],
        [
            ("⭐ Saqlash", "https://t.me/ayvona_jobs_bot?start=save_42"),
            ("🔍 Boshqa ishlar", "https://t.me/ayvona_jobs_bot?start=search"),
        ],
    ]
    only_phone = fmt.format(job(usernames=())).buttons()
    assert [[b.text for b in row] for row in only_phone] == [["🔍 Boshqa ishlar"]]


def test_apply_url_line_only_without_other_contacts(fmt: Formatter) -> None:
    assert "🔗 Ariza" not in fmt.format(job(apply_url="https://forms.gle/x")).html
    alone = job(phones=(), usernames=(), apply_url="https://forms.gle/x")
    assert '🔗 Ariza: <a href="https://forms.gle/x">ariza topshirish</a>' in fmt.format(alone).html


def test_helpers() -> None:
    assert format_phone("+998901234567") == "+998 90 123 45 67"
    assert telegram_post_url("@ishmi_ish", "123") == "https://t.me/ishmi_ish/123"
    assert telegram_post_url("-1001234567", "5") == "https://t.me/c/1234567/5"
    assert telegram_post_url("web:hh_uz", "https://hh.uz/1") is None
    assert truncate("salom dunyo bu matn", 12) == "salom dunyo…"
    assert visible_len("<b>a&amp;b</b> 🔥") == 6  # "a&b " + emoji (2 UTF-16 units)


# ------------------------------------------------------------------ snapshots
FIXTURES = load_dir() + load_dir(REGRESSIONS_DIR)


@pytest.fixture(scope="module")
def pipeline(settings: Settings) -> tuple[Classifier, Extractor, Cleaner, Formatter]:
    return (
        Classifier(settings.filters, settings.source_rules),
        Extractor(settings),
        Cleaner(settings.source_rules),
        Formatter(settings),
    )


def render_snapshot(
    fx: dict[str, Any], parts: tuple[Classifier, Extractor, Cleaner, Formatter]
) -> str:
    classifier, extractor, cleaner, formatter = parts
    post = to_post(fx)
    kind = classifier.classify(post, LABEL_DAY).kind
    head = f"<!-- {fx['source']}/{fx['external_id']} — {fx.get('title') or ''} -->\n"
    if kind is not PostKind.JOB:
        return head + f"<!-- kind={kind}: kanalga chiqmaydi -->\n"
    ex = extractor.extract(post)
    if not ex.publish:
        return head + f"<!-- job, lekin kanalga chiqmaydi: {', '.join(ex.reasons)} -->\n"
    cleaned = cleaner.clean(
        post.text, post.extra, source=post.source, own_usernames=post.own_usernames
    )
    out = formatter.format(
        ex, cleaned, source_url=telegram_post_url(fx["source"], fx["external_id"])
    )
    folder = ex.category + (f"/{ex.profession}" if ex.profession else "")
    meta = (
        f"<!-- til={ex.language} shablon={'fallback' if out.fallback else 'toliq'}"
        f" confidence={ex.confidence} uzunlik={out.length}/1024 rasm={folder}"
        f"{' qisqartirildi=' + ','.join(out.shortened) if out.shortened else ''} -->\n"
    )
    buttons = " · ".join(
        f'<a href="{html.escape(b.url)}">[{html.escape(b.text)}]</a>'
        for row in out.buttons(job_id=1)
        for b in row
    )
    return (
        head
        + meta
        + '<meta charset="utf-8">\n'
        + '<div style="white-space:pre-wrap;font-family:sans-serif;max-width:520px;'
        + 'border:1px solid #ccc;padding:12px;margin:12px 0">\n'
        + out.html
        + "\n</div>\n<p>"
        + buttons
        + "</p>\n"
    )


@pytest.mark.parametrize("fx", FIXTURES, ids=[fx["id"] for fx in FIXTURES])
def test_snapshot(
    fx: dict[str, Any], pipeline: tuple[Classifier, Extractor, Cleaner, Formatter]
) -> None:
    got = render_snapshot(fx, pipeline)
    path = SNAPSHOTS / f"{fx['id']}.html"
    if UPDATE or not path.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(got, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == got, f"snapshot o'zgardi: {path.name}"


@pytest.mark.parametrize("fx", FIXTURES, ids=[fx["id"] for fx in FIXTURES])
def test_real_posts_fit_and_are_latin(
    fx: dict[str, Any], pipeline: tuple[Classifier, Extractor, Cleaner, Formatter]
) -> None:
    classifier, extractor, cleaner, formatter = pipeline
    post = to_post(fx)
    if classifier.classify(post, LABEL_DAY).kind is not PostKind.JOB:
        return
    ex = extractor.extract(post)
    cleaned = cleaner.clean(
        post.text, post.extra, source=post.source, own_usernames=post.own_usernames
    )
    for e in (ex, replace(ex, confidence=0.0)):  # both templates
        out = formatter.format(e, cleaned, source_url=SRC)
        assert out.length <= 1024
        assert not re.search(r"[Ѐ-ӿ]", out.html), out.html
        for phone in ex.phones[:3]:
            assert format_phone(phone) in out.html
