import pytest

from ayvona.processing.language import Language, detect_language, is_uzbek_cyrillic
from tests.post_fixtures import load_dir

FIXTURES = [fx for fx in load_dir() if "language" in fx["expected"]]


@pytest.mark.parametrize("fx", FIXTURES, ids=[fx["id"] for fx in FIXTURES])
def test_language_of_real_posts(fx: dict) -> None:
    assert detect_language(fx["text"]) == fx["expected"]["language"]


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Sotuvchi kerak. Maosh 5 mln, ish vaqti 9:00-18:00", Language.UZ_LATIN),
        ("Сотувчи керак. Маош 5 млн, иш вақти 9:00-18:00", Language.UZ_CYRILLIC),
        ("Требуется продавец. Зарплата от 5 млн, опыт работы не нужен", Language.RU),
        ("We are looking for a sales manager with 2 years of experience", Language.EN),
        # Uzbek Cyrillic without ў қ ғ ҳ (people often type к instead of қ) — words decide
        ("Корхонага ишга таклиф киламиз, ойлик маош келишилади", Language.UZ_CYRILLIC),
    ],
)
def test_language_short_texts(text: str, lang: Language) -> None:
    assert detect_language(text) == lang


def test_is_uzbek_cyrillic() -> None:
    assert is_uzbek_cyrillic("Иш ҳақи 6 млндан бошланади")
    assert not is_uzbek_cyrillic("Заработная плата от 4,000,000")
    assert not is_uzbek_cyrillic("Toshkent")  # no Cyrillic at all
