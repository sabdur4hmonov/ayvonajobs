"""Region / district / remote detection (config/regions.yaml)."""

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.location import LocationFinder
from ayvona.processing.normalize import fold


@pytest.fixture(scope="module")
def finder() -> LocationFinder:
    return LocationFinder(load_settings(DEFAULT_CONFIG_DIR, env_file=None).regions)


def find(finder: LocationFinder, text: str):  # noqa: ANN201
    return finder.find([fold(line) for line in text.split("\n")])


@pytest.mark.parametrize(
    ("text", "region", "district"),
    [
        ("Manzil: Toshkent shahri, Yunusobod tumani", "toshkent_sh", "Yunusobod"),
        ("Yunusobod tumani, Bog'ishamol ko'chasi", "toshkent_sh", "Yunusobod"),  # no "Toshkent"
        ("Tashkent, Yunusabad", "toshkent_sh", "Yunusobod"),
        ("📍 Манзил: Мирабад тумани, Куйлюк", "toshkent_sh", "Mirobod"),
        ("Toshkent sh, Sergili", "toshkent_sh", "Sergeli"),  # typo
        ("Yunsobot 4-kvartal", "toshkent_sh", "Yunusobod"),  # typo
        ("Ofis: Yangi hayot, Indeks", "toshkent_sh", "Yangihayot"),
        ("📍 Локация: Ракат Махалля", "toshkent_sh", None),  # Sardor: Rakat = Toshkent
        ("Shayxontohur, Samarqand Darvoza ro'parasi", "toshkent_sh", "Shayxontohur"),
        ("Toshkent viloyati, Zangiota tumani", "toshkent_vil", "Zangiota"),
        ("Zangiota tumani, Katta Chinor MFY", "toshkent_vil", "Zangiota"),
        ("Toshkent viloyati Parkent tumani", "toshkent_vil", "Parkent"),
        ("SAMARQAND\nСамарканд шахрида жойлашган", "samarqand", None),
        ("Buxoro, G'ijduvon tumani", "buxoro", "G'ijduvon"),
    ],
)
def test_region_and_district(
    finder: LocationFinder, text: str, region: str, district: str | None
) -> None:
    loc = find(finder, text)
    assert (loc.region, loc.district) == (region, district)


def test_tashkent_city_and_region_are_one_area(finder: LocationFinder) -> None:
    loc = find(finder, "Manzil: Toshkent, Zangiota raysenter\nManzil: Uchtepa t.")
    assert loc.region == "toshkent_sh"  # 2 mentions against 1
    assert set(loc.regions) == {"toshkent_sh", "toshkent_vil"}


def test_many_regions(finder: LocationFinder) -> None:
    loc = find(finder, "Toshkent, Samarqand, Buxoro va Andijon filiallariga kuryerlar")
    assert loc.region == "kop_hudud"
    assert {"toshkent_sh", "samarqand", "buxoro", "andijon"} <= set(loc.regions)


def test_street_and_accounts_are_not_regions(finder: LocationFinder) -> None:
    assert find(finder, "Chilonzor, Buxoro ko'chasi 5").region == "toshkent_sh"
    assert find(finder, "Kvartira: @Kvartira_uylar_Tashkent").region is None


@pytest.mark.parametrize(
    ("text", "remote"),
    [
        ("Format: Remote", True),
        ("Uydan turib ishlash", True),
        ("Работа удаленно", True),
        ("Tashkent, Office (later Hybrid/Remote)", False),
        ("Online do'kon uchun sotuvchi", False),
    ],
)
def test_remote(finder: LocationFinder, text: str, remote: bool) -> None:
    assert find(finder, text).is_remote is remote
