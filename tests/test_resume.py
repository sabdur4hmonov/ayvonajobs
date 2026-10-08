"""Job SEEKERS' posts must never reach the channel (2026-10-08: a freelancer's "#rezyume" post was
published as a vacancy titled "Proyekt"), and a channel's own advertising contact is not the
poster's contact. Anonymized fixtures: fake names, phones and usernames."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, Settings, load_settings
from ayvona.db.models import Job, RawPostStatus
from ayvona.processing.classify import Classifier, PostInput, PostKind
from ayvona.processing.clean import Cleaner
from ayvona.processing.extract import Extractor
from ayvona.processing.pipeline import Pipeline
from ayvona.services import admin_alerts
from tests.worker_helpers import SF, RecordingNotifier, add_raw, add_source, get_raw, make_settings

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
SRC = "@freelancer_Uzbek"

# The post of 2026-10-07 (names / contacts changed).
RESUME_POST = """#rezyume
🎬 Katta obyomdagi target montajlari uchun proyekt kerak
👨‍💼Xodim: Alisher Testov
🕘 Yosh: 21
⏳ Tajriba: 1 yil +
💼 Ish turi: Onlayn
📌Hudud: Toshkent
💰 Oylik: Obyomga va qiyinligiga qarab kelishiladi
🔎 Qo'shimcha: Oyiga 200+ target uchun video montaj qilib beramiz.
🗂 Portfolio: @test_portfolio
Murojaat uchun: @test_alisher, +998 90 000 00 31
━━━━
🌐 @freelancer_Uzbek — Ish va xodim bir joyda!
📬 Kanalda e'lon va rezyume joylashtirish uchun: @FreelancerUz_ads"""

# The same without the hashtag and the "proyekt kerak" line: only the SHAPE says "resume".
SHAPE_ONLY = RESUME_POST.replace("#rezyume\n", "").replace(
    "🎬 Katta obyomdagi target montajlari uchun proyekt kerak\n", "🎬 Video montaj\n"
)

# An employer's post that uses the same labels.
EMPLOYER_LABELS = """Xodim kerak: Sotuv menejeri
🕘 Yosh: 20-30
⏳ Tajriba: 1 yil
📌 Hudud: Toshkent
💰 Oylik: 5 000 000 so'm
📞 Aloqa: +998 90 000 00 32
@test_hr_kompaniya"""

# ... and in the "Xodim: <position>" form, with an employer's Talablar / Vazifalar
EMPLOYER_TEMPLATE = """Xodim: Sotuv menejeri
Yosh: 20-30
Tajriba: 1 yil
Hudud: Toshkent
Oylik: 5 000 000 so'm
Talablar: xushmuomala, CRM bilan ishlash
Aloqa: +998 90 000 00 33"""


@pytest.fixture(scope="module")
def st() -> Settings:
    return load_settings(DEFAULT_CONFIG_DIR, env_file=None)


@pytest.fixture(scope="module")
def clf(st: Settings) -> Classifier:
    return Classifier(st.filters, st.source_rules, st.categories)


def kind(clf: Classifier, text: str, source: str | None = SRC) -> tuple[PostKind, tuple[str, ...]]:
    c = clf.classify(PostInput(text=text, source=source, posted_at=NOW), NOW)
    return c.kind, c.reasons


# ------------------------------------------------------------------ resume detection
def test_the_freelancers_post_is_a_resume(clf: Classifier) -> None:
    k, reasons = kind(clf, RESUME_POST)
    assert k is PostKind.RESUME and "resume:#rezyume" in reasons


def test_the_shape_alone_is_enough(clf: Classifier) -> None:
    k, reasons = kind(clf, SHAPE_ONLY)
    assert k is PostKind.RESUME and reasons[0].startswith("resume:shape:")


@pytest.mark.parametrize(
    "text",
    [
        "#resume\nVideo montaj, 2 yil tajriba. Murojaat: @test_user",
        "#CV Dizayner, Toshkent, @test_user",
        "#резюме Менеджер по продажам, опыт 3 года, @test_user",
        "Men ish izlayman. Sotuvchi, 25 yosh. @test_user",
        "REZYUME\nAlisher, 22 yosh\n@test_user",
        "Ищу подработку: монтаж видео. @test_user",
        "Open to work: UX designer, Tashkent. @test_user",
    ],
)
def test_resume_markers(clf: Classifier, text: str) -> None:
    assert kind(clf, text)[0] is PostKind.RESUME


def test_name_and_portfolio_evidence(clf: Classifier) -> None:
    named = "Xodim: Dilnoza Karimova\nYosh: 24\nTajriba: 2 yil\nHudud: Samarqand\n@test_dilnoza"
    assert kind(clf, named)[0] is PostKind.RESUME  # a person's name
    portfolio = "Yosh: 24\nTajriba: 2 yil\nPortfolio: behance.net/test\nHudud: Samarqand\n@test_x"
    assert kind(clf, portfolio)[0] is PostKind.RESUME  # the seeker-only label
    one_word = "Xodim: Dilnoza\nYosh: 24\nTajriba: 2 yil\nHudud: Samarqand\n@test_dilnoza"
    assert kind(clf, one_word)[0] is not PostKind.RESUME  # one word: maybe a position


# ------------------------------------------------------------------ vacancies stay vacancies
def test_employers_using_the_same_labels_stay_jobs(clf: Classifier) -> None:
    assert kind(clf, EMPLOYER_LABELS)[0] is PostKind.JOB  # "Xodim kerak:" is not "Xodim:"
    assert kind(clf, EMPLOYER_TEMPLATE)[0] is PostKind.JOB  # position + Talablar


def test_employer_evidence_beats_a_name(clf: Classifier) -> None:
    text = (
        "Xodim: Alisher Testov\nYosh: 20\nTajriba: 1 yil\nHudud: Toshkent\n"
        "Vazifalar: mijozlar bilan ishlash\nTel: +998 90 000 00 34"
    )
    assert kind(clf, text)[0] is not PostKind.RESUME


def test_profession_in_a_name_field_is_not_a_name(clf: Classifier) -> None:
    text = "Xodim: Sotuv Menejeri\nYosh: 20-30\nTajriba: 1 yil\nOylik: 5 mln\n@test_hr"
    assert kind(clf, text)[0] is not PostKind.RESUME


@pytest.mark.parametrize(
    "line",
    [
        "📩 Rezyume yuborish uchun: @test_hr",
        "Rezyume jo'nating: @test_hr",
        "Rezyume:",
        "- To'liq rezyume (CV)",
        "Ish kerak bo'lsa, murojaat qiling",
        '"Ish kerak edi."',
        "Loyiha uchun dasturchi kerak",
    ],
)
def test_words_that_normal_vacancies_use_are_not_markers(clf: Classifier, line: str) -> None:
    text = (
        "Sotuv menejeri kerak\nMaosh: 5 000 000 so'm\nManzil: Toshkent\nIsh vaqti: 9:00-18:00\n"
        f"Talablar: tajriba\n{line}\nTel: +998 90 000 00 35"
    )
    assert kind(clf, text, "@test_kanal")[0] is PostKind.JOB


def test_closed_still_comes_before_resume(clf: Classifier) -> None:
    k, _ = kind(clf, "#rezyume\nvakansiya yopildi")
    assert k is PostKind.CLOSED


# ------------------------------------------------------------------ the channel's own ad contact
AD_CONTACT = """Sotuv menejeri kerak
Maosh: 5 000 000 so'm
Manzil: Toshkent
Talablar: tajriba
Aloqa: +998 90 000 00 36
@test_hr_kompaniya
{footer}"""


def contacts(st: Settings, text: str, source: str = "@test_kanal") -> list[str]:
    post = PostInput(text=text, source=source, posted_at=NOW)
    return Extractor(st).extract(post).usernames


@pytest.mark.parametrize(
    "footer",
    [
        "📬 Kanalda e'lon va rezyume joylashtirish uchun: @FreelancerUz_ads",
        "Reklama uchun: @Some_Reklama_Admin",
        "Reklama bo'yicha - t.me/some_ads_admin",
        "E'lon berish uchun @News_Desk",
        "По рекламе: @ads_manager_uz",
        "For ads: @channel_ads_bot",
        "Reklama va hamkorlik:\n@collab_manager",
    ],
)
def test_ad_contact_lines_are_dropped_generically(
    st: Settings, clf: Classifier, footer: str
) -> None:
    text = AD_CONTACT.format(footer=footer)
    assert [u.lower() for u in contacts(st, text)] == ["@test_hr_kompaniya"]
    assert kind(clf, text, "@test_kanal")[0] is PostKind.JOB
    c = clf.classify(PostInput(text=text, source="@test_kanal", posted_at=NOW), NOW)
    assert list(c.contacts.usernames) == ["@test_hr_kompaniya"]
    # the published text has no trace of it either, and a hidden link to it is dropped
    extra = {"links": [{"text": "Reklama", "url": f"https://t.me/{_account(footer)}"}]}
    cleaned = Cleaner(st.source_rules).clean(text, extra, source="@test_kanal")
    assert _account(footer).lower() not in cleaned.text.lower()
    assert not cleaned.links


def _account(footer: str) -> str:
    import re

    return re.search(r"(?:@|t\.me/)(\w+)", footer).group(1)  # type: ignore[union-attr]


def test_the_phrase_alone_is_not_an_ad_line(st: Settings) -> None:
    """Only an account right after the phrase counts: no blind dropping of "*_ads" / "*admin*"."""
    text = AD_CONTACT.format(footer="Reklama bo'yicha menejer kerak. Murojaat: @Sales_Admin_Uz")
    assert [u.lower() for u in contacts(st, text)] == ["@test_hr_kompaniya", "@sales_admin_uz"]


def test_the_freelancer_source_rules(st: Settings) -> None:
    post = PostInput(text=RESUME_POST, source=SRC, posted_at=NOW)
    users = [u.lower() for u in Extractor(st).extract(post).usernames]
    assert "@freelanceruz_ads" not in users and "@freelancer_uzbek" not in users
    assert "@test_alisher" in users  # the poster's own contact stays
    cleaned = Cleaner(st.source_rules).clean(RESUME_POST, None, source=SRC)
    assert "FreelancerUz_ads" not in cleaned.text and "Ish va xodim bir joyda" not in cleaned.text
    assert "Kanalda e'lon va rezyume" not in cleaned.text
    assert "@test_alisher" in cleaned.text


# ------------------------------------------------------------------ pipeline + admin alerts
async def test_a_resume_is_never_published_but_the_admin_alert_sees_it(session_factory: SF) -> None:
    sf = session_factory
    src = await add_source(sf, SRC)
    raw = await add_raw(sf, src, RESUME_POST)
    stats = await Pipeline(make_settings(), sf, RecordingNotifier()).run_once()  # type: ignore[arg-type]
    row = await get_raw(sf, raw)
    assert row.status is RawPostStatus.RESUME and stats.new_jobs == 0
    async with sf() as s:
        from sqlalchemy import func, select

        assert (await s.scalar(select(func.count()).select_from(Job))) == 0
    state = admin_alerts.post_state(row, None)
    assert not state.published and state.reason and state.reason.startswith("rezyume")
