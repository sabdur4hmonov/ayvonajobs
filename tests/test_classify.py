from datetime import UTC, datetime

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.boilerplate import BoilerplateRules, strip_boilerplate
from ayvona.processing.classify import Classifier, PostInput, PostKind, find_deadline, merge_album
from ayvona.processing.normalize import fold, normalize
from tests.post_fixtures import LABEL_DAY, REGRESSIONS_DIR, load_dir, to_post

POSTS = load_dir()
REGRESSIONS = load_dir(REGRESSIONS_DIR)
NOW = LABEL_DAY


@pytest.fixture(scope="module")
def classifier() -> Classifier:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    return Classifier(s.filters, s.source_rules)


def test_there_are_41_examples() -> None:
    assert len(POSTS) == 41


@pytest.mark.parametrize("fx", POSTS, ids=[fx["id"] for fx in POSTS])
def test_kind_of_real_posts(classifier: Classifier, fx: dict) -> None:
    result = classifier.classify(to_post(fx), NOW)
    assert result.kind == fx["expected"]["kind"], result.reasons


@pytest.mark.parametrize("fx", REGRESSIONS, ids=[fx["id"] for fx in REGRESSIONS])
def test_kind_of_regression_posts(classifier: Classifier, fx: dict) -> None:
    result = classifier.classify(to_post(fx), NOW)
    assert result.kind == fx["expected"]["kind"], result.reasons


def test_vacancy_list_with_apply_links_is_a_job(classifier: Classifier) -> None:
    lines = "\n".join(f"🔗 {t} (havola)" for t in ("Backend dasturchi", "Tizim tahlilchisi"))
    links = [{"text": "(havola)", "url": f"https://hh.uz/vacancy/{n}"} for n in (1, 2)]
    post = PostInput(text=f"Bank jamoasi kengaymoqda\n\n{lines}", extra={"links": links})
    r = classifier.classify(post, NOW)
    assert r.kind is PostKind.JOB
    assert "positions_with_links:2" in r.reasons
    # one link only (a course sign-up form) is not a vacancy list
    one = PostInput(text="Bepul kurs\n🔗 Ro'yxatdan o'tish (havola)", extra={"links": links[:1]})
    assert classifier.classify(one, NOW).kind is not PostKind.JOB


def test_jobs_in_examples_have_contact(classifier: Classifier) -> None:
    for fx in POSTS:
        r = classifier.classify(to_post(fx), NOW)
        if r.kind is PostKind.JOB:
            assert r.has_contact, fx["id"]


def test_deadline_not_passed_is_still_a_job(classifier: Classifier) -> None:
    fx = next(f for f in POSTS if f["id"] == "jobs_fba_63")  # "Ariza muddati: 2026-09-19"
    assert classifier.classify(to_post(fx), datetime(2026, 9, 17, tzinfo=UTC)).kind is PostKind.JOB
    assert (
        classifier.classify(to_post(fx), datetime(2026, 9, 20, tzinfo=UTC)).kind is PostKind.CLOSED
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("📅 Ariza muddati: 2026-09-19", "2026-09-19"),
        ("Deadline: 05.10.2026", "2026-10-05"),
        ("Oxirgi muddat - 1/11/2026", "2026-11-01"),
        ("Ariza muddati: tez orada", None),
    ],
)
def test_find_deadline(text: str, expected: str | None) -> None:
    d = find_deadline(fold(text))
    assert (d.isoformat() if d else None) == expected


def test_no_text_single_photo(classifier: Classifier) -> None:
    assert classifier.classify(PostInput(text="", has_media=True), NOW).kind is PostKind.NO_TEXT


def test_album_parts_are_merged() -> None:
    parts = [
        PostInput(text="", has_media=True, source="@x"),
        PostInput(text="Sotuvchi kerak", has_media=True, source="@x",
                  extra={"links": [{"text": "HR", "url": "https://t.me/hr_x"}]}),
        PostInput(text="", has_media=True, source="@x",
                  extra={"buttons": [{"text": "Apply", "url": "https://a.b/c"}]}),
    ]  # fmt: skip
    merged = merge_album(parts)
    assert merged.text == "Sotuvchi kerak"
    assert merged.has_media
    assert merged.extra == {
        "links": [{"text": "HR", "url": "https://t.me/hr_x"}],
        "buttons": [{"text": "Apply", "url": "https://a.b/c"}],
    }


def test_word_boundary_grant_vs_emigrant(classifier: Classifier) -> None:
    text = "Emigrantlar uchun kompaniyaga sotuvchi kerak. Maosh 5 mln. Tel: +998 90 123 45 67"
    r = classifier.classify(PostInput(text=text), NOW)
    assert r.kind is PostKind.JOB


def test_job_without_contact_is_flagged_not_dropped(classifier: Classifier) -> None:
    r = classifier.classify(PostInput(text="Sotuvchi kerak\nMaosh: 5 mln\nIsh vaqti: 9-18"), NOW)
    assert r.kind is PostKind.JOB
    assert not r.has_contact
    assert "no_contact" in r.reasons


def test_employee_discount_does_not_make_job_an_ad(classifier: Classifier) -> None:
    text = (
        "O'quv markazga ustoz kerak\nOylik: 5-10 mln\nTalablar: tajriba\n"
        "Xodimlarga 50% chegirma\nTelegram: @imkon_hr"
    )
    assert classifier.classify(PostInput(text=text), NOW).kind is PostKind.JOB


def test_prepayment_as_duty_is_not_scam(classifier: Classifier) -> None:
    text = (
        "Sotuv menejeri kerak\nMaosh: 5 mln\n"
        "Vazifalar: mijozlardan oldindan to‘lovlarni qabul qilish\n"
        "Aloqa: @hr_x"
    )
    assert classifier.classify(PostInput(text=text), NOW).kind is PostKind.JOB
    scam = "Ishga kirish uchun oldindan to'lov qilasiz. Maosh 10 mln, kerak. Tel: 901234567"
    assert classifier.classify(PostInput(text=scam), NOW).kind is PostKind.SUSPICIOUS


def test_unpaid_internship_beats_strong_job_score(classifier: Classifier) -> None:
    text = (
        "Dasturchi kerak, jamoamizga qo'shiling!\nTalablar: Python\nVazifalar: backend\n"
        "Murojaat uchun: @hr_x\nAmaliyot uchun haq to'lanmaydi."
    )
    assert classifier.classify(PostInput(text=text), NOW).kind is PostKind.OPPORTUNITY


def test_channel_footer_does_not_add_job_points(classifier: Classifier) -> None:
    # "vakansiya" only in @ish_kerak_edu's footer -> must not count
    text = "Kitob do'koni ochildi!\n\nAgar vakansiya sizga mos bo'lmasa — tanishingizga ulashing!"
    r = classifier.classify(PostInput(text=text, source="@ish_kerak_edu"), NOW)
    assert r.kind is PostKind.NOT_JOB
    assert r.job_score == 0


def test_kasbdoruz_requires_its_hashtag(classifier: Classifier) -> None:
    text = "📌 Sotuvchi kerak\n• Maosh: 5 mln\n• Ish vaqti: 9-18\n@hr_x"
    post = PostInput(text=text, source="@kasbdoruz")
    assert classifier.classify(post, NOW).kind is PostKind.NOT_JOB
    tagged = PostInput(text="#vakansiya\n\n" + text, source="@kasbdoruz")
    assert classifier.classify(tagged, NOW).kind is PostKind.JOB


# --------------------------------------------------------------------------- boilerplate
def test_boilerplate_cut_from_and_strip_lines() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    rules = BoilerplateRules.build(s.source_rules.for_source("@kasbdoruz"), s.source_rules.defaults)
    text = normalize(
        "#vakansiya\n\n📌 Call operator\n• Maosh: 3 500 000\n• Ish vaqti: 9:00-18:00\n"
        "📞 Bog‘lanish uchun: @uysot_elyor\n\n👉🏻 E’lon joylash uchun: @kasbdor_uz\n"
        "🌏 @Kasbdoruz— kasbiy o‘sishdagi ideal platformangiz!\n\nN3311"
    )
    out = strip_boilerplate(text, rules)
    assert "@kasbdor_uz" not in out
    assert "platformangiz" not in out
    assert "n3311" not in out
    assert "@uysot_elyor" in out


def test_boilerplate_cut_is_skipped_when_too_much_would_go() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    rules = BoilerplateRules.build(s.source_rules.for_source("@kasbdoruz"), s.source_rules.defaults)
    text = normalize("E'lon joylash uchun: @kasbdor_uz\nSotuvchi kerak, maosh 5 mln, aloqa @hr")
    assert "sotuvchi kerak" in strip_boilerplate(text, rules)


def test_boilerplate_header_junk_words() -> None:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    rules = BoilerplateRules.build(s.source_rules.for_source("@NextHireX"), s.source_rules.defaults)
    out = strip_boilerplate(normalize("New\n💼 Job Title: Dispatcher"), rules)
    assert out == "job title: dispatcher"
