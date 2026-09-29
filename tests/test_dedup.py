from datetime import UTC, datetime, timedelta

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.classify import Classifier
from ayvona.processing.dedup import DedupEntry, DedupIndex, dedup_text, guess_title, make_entry
from ayvona.processing.normalize import normalize
from tests.post_fixtures import DEDUP_DIR, LABEL_DAY, load, to_post

T0 = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def classifier() -> Classifier:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    return Classifier(s.filters, s.source_rules)


def real_entry(classifier: Classifier, stem: str) -> DedupEntry:
    """A real post from tests/fixtures/dedup, prepared exactly like the pipeline will."""
    fx = load(DEDUP_DIR / f"{stem}.json")
    r = classifier.classify(to_post(fx), LABEL_DAY)
    return make_entry(
        fx["id"],
        datetime.fromisoformat(fx["posted_at"]),
        r.clean_text,
        [*r.contacts.phones, *r.contacts.usernames],
        ignore_usernames=[fx["source"]],
    )


def pair(classifier: Classifier, first: str, second: str) -> tuple[DedupIndex, DedupEntry]:
    index = DedupIndex()
    assert index.check(real_entry(classifier, first)) is None
    return index, real_entry(classifier, second)


# --------------------------------------------------------------------------- real posts
def test_same_template_same_contact_different_position_is_not_duplicate(classifier) -> None:
    # Sardor's case: @huntmejob, one contact @Hr1_Stella, Safety Specialist vs Fleet Manager
    index, second = pair(classifier, "huntmejob_37089", "huntmejob_37090")
    assert index.find(second) is None


def test_admin_contact_under_every_ad_is_not_enough(classifier) -> None:
    # @jobs_fba: texts 89.8% alike and share @jobs_admin_1, but different positions
    index, second = pair(classifier, "jobs_fba_50", "jobs_fba_51")
    assert index.find(second) is None


def test_channel_reposts_its_own_ad(classifier) -> None:
    index, second = pair(classifier, "NextHireX_2516", "NextHireX_2523")
    m = index.find(second)
    assert m is not None and m.original == "NextHireX_2516"


def test_cross_post_in_another_channel(classifier) -> None:
    # "YIGITLAR, KUCHLI JAMOAGA OPERATORLAR KERAK" — SOURCE_ANALYSIS §8
    index, second = pair(classifier, "ishlaUZ_rasmiy_11773", "ishtopuz_rasmiy_40837")
    m = index.find(second)
    assert m is not None and m.original == "ishlaUZ_rasmiy_11773"


def test_fuzzy_cross_post_without_contacts_needs_similar_title(classifier) -> None:
    index, second = pair(classifier, "ishtoparuz_kanal_25026", "ishtopuz_rasmiy_40831")
    m = index.find(second)
    assert m is not None and m.layer in {"hash", "fuzzy"}


# --------------------------------------------------------------------------- rules
def entry(key: str, text: str, when: datetime = T0, contacts=(), title=None) -> DedupEntry:
    return make_entry(key, when, normalize(text), contacts, title=title)


BASE = (
    "Sotuvchi kerak\nMaosh: 5 000 000 so'm\nIsh vaqti: 09:00-18:00\n"
    "Manzil: Toshkent, Chilonzor tumani, Novza metro yonida\nTalablar: 20-35 yosh, rus tili"
)


def test_exact_text_is_duplicate_and_first_stays() -> None:
    index = DedupIndex()
    assert index.check(entry("a", BASE)) is None
    m = index.check(entry("b", BASE, T0 + timedelta(hours=3)))
    assert m is not None and (m.original, m.layer) == ("a", "hash")


def test_links_hashtags_and_channel_accounts_do_not_matter() -> None:
    index = DedupIndex()
    first = normalize(BASE + "\n#toshkent\n@kanal_bir")
    index.check(make_entry("a", T0, first, ignore_usernames=["@kanal_bir"]))
    b = make_entry(
        "b", T0, normalize(BASE + "\nhttps://t.me/x?utm_source=y\n@kanal_ikki"),
        ignore_usernames=["@kanal_ikki"],
    )  # fmt: skip
    m = index.find(b)
    assert m is not None and m.layer == "hash"


def test_outside_14_day_window_is_new_post() -> None:
    index = DedupIndex()
    index.check(entry("a", BASE))
    assert index.find(entry("b", BASE, T0 + timedelta(days=15))) is None
    assert index.find(entry("c", BASE, T0 + timedelta(days=13))) is not None


def test_fuzzy_needs_second_signal() -> None:
    changed = BASE.replace("rus tili", "rus tilini bilish")  # ~95% alike
    index = DedupIndex()
    index.check(entry("a", BASE, title="sotuvchi"))
    # similar text, but different titles and no shared contact -> not a duplicate
    assert index.find(entry("b", changed, title="oshpaz")) is None
    # similar text + similar title -> duplicate
    m = index.find(entry("c", changed, title="sotuvchi"))
    assert m is not None and m.layer == "fuzzy"


def test_fuzzy_with_shared_contact() -> None:
    changed = BASE.replace("rus tili", "rus tilini bilish")
    index = DedupIndex()
    index.check(entry("a", BASE, contacts=["+998901234567"], title="sotuvchi kerak"))
    m = index.find(entry("b", changed, contacts=["+998901234567"], title="sotuvchi konsultant"))
    assert m is not None and m.shared_contacts == {"+998901234567"}


def test_shared_contact_with_conflicting_titles_is_not_duplicate() -> None:
    changed = BASE.replace("rus tili", "rus tilini bilish")
    index = DedupIndex()
    index.check(entry("a", BASE, contacts=["@hr"], title="sotuvchi"))
    assert index.find(entry("b", changed, contacts=["@hr"], title="buxgalter yordamchisi")) is None


def test_fingerprint_needs_similar_text_too() -> None:
    index = DedupIndex()
    index.check(entry("a", BASE, contacts=["@hr"], title="sotuvchi"))
    other = "Sotuvchi kerak\nYangi filial ochildi, 3 smena, yotoqxona bor, tushlik bepul"
    assert index.find(entry("b", other, contacts=["@hr"], title="sotuvchi")) is None


def test_chain_of_reposts_points_to_the_first_post() -> None:
    index = DedupIndex()
    index.check(entry("a", BASE))
    index.check(entry("b", BASE, T0 + timedelta(days=10)))
    # 20 days after "a" (outside its window) but 10 days after "b"
    m = index.check(entry("c", BASE, T0 + timedelta(days=20)))
    assert m is not None and (m.original, m.matched) == ("a", "b")


def test_short_texts_are_not_fuzzy_matched() -> None:
    index = DedupIndex()
    index.check(entry("a", "Results speak in @NextHireX"))
    assert index.find(entry("b", "Results speak in @NextHireX!!")) is not None  # same -> hash
    assert index.find(entry("c", "Results speak in @NextHire")) is None


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("👔 Position: Safety Specialist\n🌎 Location: Tashkent", "safety specialist"),
        ("💼 Job Title: #UPDATESPECIALIST\n🏢 Company: Fast Express", "updatespecialist"),
        ("#vakansiya\n\n📌 Call operator\n• Maosh: 3 mln", "call operator"),
        ("☑️Lavozim: Grafik Dizayner\n☑️ Firma: ALSTAR", "grafik dizayner"),
        ("Вакансия: Оператор колл-центра\nКомпания FreeLink", "оператор колл центра"),
    ],
)
def test_guess_title(text: str, title: str) -> None:
    assert guess_title(normalize(text)) == title


def test_dedup_text() -> None:
    assert dedup_text("sotuvchi kerak! #toshkent https://t.me/x @kanal @hr", ["@kanal"]) == (
        "sotuvchi kerak hr"
    )
