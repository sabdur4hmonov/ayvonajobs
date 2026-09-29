import pytest

from ayvona.processing.keywords import KeywordSet
from ayvona.processing.normalize import fold, normalize, to_latin, unify


def test_nfkc_bold_letters() -> None:
    assert normalize("We are looking for a 𝗨𝗫/𝗨𝗜 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿") == "we are looking for a ux/ui designer"


def test_keycap_digits() -> None:
    assert normalize("3️⃣.000.000 – 6️⃣.000.000 so‘m") == "3.000.000 – 6.000.000 so'm"


@pytest.mark.parametrize("raw", ["o‘qituvchi", "oʻqituvchi", "o’qituvchi", "o`qituvchi", "o'qituvchi"])
def test_apostrophes_unified(raw: str) -> None:
    assert normalize(raw) == "o'qituvchi"


def test_emoji_and_spaces_removed_line_breaks_kept() -> None:
    text = "⚡️ Maktabga   Ayol oshpaz kerak\n\n\n\n📌 Manzil:\t– Toshkent 👨‍💻"
    assert normalize(text) == "maktabga ayol oshpaz kerak\n\nmanzil: – toshkent"


def test_uzbek_cyrillic_transliterated() -> None:
    text = "🔥 САВДО КОМПАНИЯСИГА ИШГА ТАКЛИФ ҚИЛАМИЗ!\n📍 ИШ ЖОЙИ: Тошкент шаҳри"
    assert normalize(text) == "savdo kompaniyasiga ishga taklif qilamiz!\nish joyi: toshkent shahri"


def test_russian_text_is_not_transliterated() -> None:
    text = "Вакансия: Оператор колл-центра\nГрафик работы: с 10:00 до 19:00"
    assert normalize(text) == "вакансия: оператор колл-центра\nграфик работы: с 10:00 до 19:00"


def test_mixed_post_only_uzbek_lines_transliterated() -> None:
    text = "Требуется бухгалтер для работы в компании\nИш ҳақи 6 млндан бошланади"
    assert normalize(text) == "требуется бухгалтер для работы в компании\nish haqi 6 mlndan boshlanadi"


@pytest.mark.parametrize(
    ("cyr", "lat"),
    [
        ("Ўзбекистон", "O'zbekiston"),
        ("ғалаба", "g'alaba"),
        ("Шаҳар", "Shahar"),
        ("ШАҲАР", "SHAHAR"),
        ("ер", "yer"),  # е at word start -> ye
        ("келди", "keldi"),
        ("поезд", "poyezd"),  # е after a vowel -> ye
        ("Цех", "Sex"),
        ("милиция", "militsiya"),
        ("эълон", "e'lon"),
        ("маьлумот", "malumot"),
        ("ёш", "yosh"),
        ("юз", "yuz"),
        ("яхши", "yaxshi"),
        ("қандолат", "qandolat"),
    ],
)
def test_to_latin(cyr: str, lat: str) -> None:
    assert to_latin(cyr) == lat


def test_to_latin_keeps_non_cyrillic() -> None:
    assert to_latin("Tel: +998 90 123 45 67 @HR_dobroe") == "Tel: +998 90 123 45 67 @HR_dobroe"


def test_fold_transliterates_russian_too() -> None:
    assert fold("Вакансия") == "vakansiya"
    assert fold("#маьлумот") == "#malumot"


def test_unify_keeps_case() -> None:
    assert unify("O‘ZBEKISTON 1️⃣") == "O'ZBEKISTON 1"


def test_empty() -> None:
    assert normalize("") == ""
    assert fold("") == ""


# --------------------------------------------------------------------------- keywords
def test_keyword_word_boundary_at_start_only() -> None:
    ks = KeywordSet(["grant", "vakansiya"])
    assert ks.find(fold("Emigrantlar uchun")) == set()
    assert ks.find(fold("Grantlar va vakansiyalar")) == {"grant", "vakansiya"}


def test_keyword_not_inside_uzbek_word_after_apostrophe() -> None:
    assert KeywordSet(["qish"]).find(fold("o'qish")) == set()


def test_keyword_cyrillic_config_matches_latin_post_and_back() -> None:
    ks = KeywordSet(["иш излаяпман", "ish qidiryapman"])
    assert ks.find(fold("Assalomu alaykum, ish izlayapman")) == {"иш излаяпман"}
    assert ks.find(fold("Иш қидиряпман")) == {"ish qidiryapman"}


def test_keyword_with_symbols() -> None:
    ks = KeywordSet(["#reklama", "erid="])
    assert ks.find(fold("#reklama infinbank.com")) == {"#reklama"}
    assert ks.find("https://ya.cc/t/x/?erid=j1sukxjeq") == {"erid="}


def test_keyword_remove() -> None:
    ks = KeywordSet(["oldindan to'lovlarni qabul"])
    assert "oldindan" not in ks.remove(fold("mijozdan oldindan to‘lovlarni qabul qilib"))
