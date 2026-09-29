"""Category / profession / feature tags (config/categories.yaml)."""

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.categorize import Categorizer
from ayvona.processing.normalize import fold


@pytest.fixture(scope="module")
def cat() -> Categorizer:
    s = load_settings(DEFAULT_CONFIG_DIR, env_file=None)
    return Categorizer(s.categories, s.feature_tags, s.negation_words)


@pytest.mark.parametrize(
    ("title", "text", "category", "profession"),
    [
        ("Kassir", "Restoranga kassir kerak", "sotuv", "kassir"),
        ("Marketing Manager", "Vositalar: SMM", "marketing", "marketolog"),  # not ofis/menejer
        ("Оператор колл-центра", "", "operator", "operator"),
        ("Somsa sotuvchi | Tajribali oshpaz", "", "oshxona", "oshpaz"),
        (
            "Sotuv agenti | Administrator | Gruzchik",
            "",
            "sotuv",
            "savdo_agenti",
        ),  # first wins a tie
        (
            "",
            "ishlab chiqarish fabrikasiga, to'qima stanoklar, upakovka",
            "ishlab_chiqarish",
            "sex_ishchisi",
        ),
        (
            "",
            "Fermer xo'jaligiga bog'ga va molga qarashga odam kk",
            "boshqa",
            None,
        ),  # "qa" != IT tester
        ("Logistics SALES Specialist", "logistics, freight forwarding", "logistika", "logist"),
        ("", "САВДО КОМПАНИЯСИГА ИШГА ТАКЛИФ ҚИЛАМИЗ", "sotuv", None),
        ("Germaniyada mavsumiy ish", "", "chet_el", None),
    ],
)
def test_category(
    cat: Categorizer, title: str, text: str, category: str, profession: str | None
) -> None:
    r = cat.categorize(title, text)
    assert (r.category, r.profession) == (category, profession), r.scores


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        ("Yotoqxona va 3 mahal ovqat bor", ("yotoqjoy",)),
        ("Yotoqxona yo'q", ()),
        ("Ayollar uchun yotoqxonamiz yo'q", ()),
        ("Ish tajribasi shart emas — o'rgatamiz", ("tajribasiz",)),
        ("Talabalar ham ishlashi mumkin", ("talabalar_uchun",)),
        ("TALABALAR BEZOVTA QILMASIN", ()),
        ("Studentlar va o'quvchilar kerak emas", ()),
        ("Part time: 14:00-20:00", ("yarim_stavka",)),
    ],
)
def test_feature_tags(cat: Categorizer, text: str, tags: tuple[str, ...]) -> None:
    assert cat.feature_tags(fold(text)) == tags
