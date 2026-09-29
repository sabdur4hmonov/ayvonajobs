"""Salary parser: every format from docs/SOURCE_ANALYSIS.md §6."""

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.normalize import display, fold
from ayvona.processing.salary import SalaryBlock, SalaryParser, looks_like_money


@pytest.fixture(scope="module")
def parser() -> SalaryParser:
    return SalaryParser(load_settings(DEFAULT_CONFIG_DIR, env_file=None).extract)


def parse(parser: SalaryParser, *texts: str, label: str = ""):  # noqa: ANN201
    return parser.parse([SalaryBlock(display(t), fold(t)) for t in texts], fold(label))


@pytest.mark.parametrize(
    ("text", "lo", "hi", "currency"),
    [
        ("4 000 000 so‘m", 4_000_000, 4_000_000, "UZS"),
        ("3.000.000 Fix + KPI", 3_000_000, None, "UZS"),
        ("5 - 30 mln so'm", 5_000_000, 30_000_000, "UZS"),
        ("7 500 000 - 15 000 000", 7_500_000, 15_000_000, "UZS"),
        ("от 7 000 000 до 15 000 000 сум", 7_000_000, 15_000_000, "UZS"),
        ("5–15 mln so‘m", 5_000_000, 15_000_000, "UZS"),
        ("2 mln+", 2_000_000, None, "UZS"),
        ("4million - 9 million", 4_000_000, 9_000_000, "UZS"),
        ("6 000 000 so‘mdan boshlanadi", 6_000_000, None, "UZS"),
        ("9 000 000 so‘mgacha", None, 9_000_000, "UZS"),
        ("Иш хаки 6 млндан бошланади", 6_000_000, None, "UZS"),
        ("$500 – 800", 500, 800, "USD"),
        ("$2 000 dan", 2_000, None, "USD"),
        ("Up to 3800 USD Gross", None, 3_800, "USD"),
        ("1 500 – 2 000 USD", 1_500, 2_000, "USD"),
        ("300$-2500$", 300, 2_500, "USD"),
        ("1000$ gacha", None, 1_000, "USD"),
        ("до 1000$", None, 1_000, "USD"),
        ("3️⃣.000.000 – 6️⃣.000.000", 3_000_000, 6_000_000, "UZS"),
        ("8 000 000dan –10 000 000 MLN", 8_000_000, 10_000_000, "UZS"),
        ("3 000 000 mln", 3_000_000, 3_000_000, "UZS"),
        ("15 00 000", 1_500_000, 1_500_000, "UZS"),
        ("5 00 000 – 7 000 000", 5_000_000, 7_000_000, "UZS"),  # typo fixed by its partner
        ("Tajribaga qarab ($300 - $1000)", 300, 1_000, "USD"),
        ("Заработная плата от 4,000,000.", 4_000_000, None, "UZS"),
    ],
)
def test_formats(
    parser: SalaryParser, text: str, lo: int | None, hi: int | None, currency: str
) -> None:
    s = parse(parser, text)
    assert (s.min, s.max, s.currency) == (lo, hi, currency)


def test_typo_in_a_range_and_two_lines(parser: SalaryParser) -> None:
    s = parse(parser, "Yigitlar uchun 4 000 000-10 00 0000", "Ayollar uchun 3 000 000 - 5 000 000")
    assert (s.min, s.max) == (3_000_000, 10_000_000)


@pytest.mark.parametrize(
    ("text", "label", "period"),
    [
        ("250 000 - 550 000", "kunlik", "day"),
        ("Haftasiga 1 000 000 dan 7 000 000", "", "week"),
        ("4 000 000", "oylik maosh", "month"),
        ("4 000 000", "maosh", "month"),  # default
    ],
)
def test_period(parser: SalaryParser, text: str, label: str, period: str) -> None:
    assert parse(parser, text, label=label).period == period


@pytest.mark.parametrize(
    "text",
    [
        "250 000",  # monthly 250k so'm is not a salary (probably daily) -> text only
        "(9 - 15 mln) soatbay",  # 9 mln per hour
        "Depozit 200$",  # not a salary at all
    ],
)
def test_insane_numbers_keep_only_text(parser: SalaryParser, text: str) -> None:
    s = parse(parser, text)
    assert not s.has_numbers
    assert s.currency is None and s.period is None
    assert s.text == display(text)


@pytest.mark.parametrize(
    "text", ["Kelishiladi", "Suhbat asosida", "Negotiable", "Shtat jadvali asosida"]
)
def test_negotiable(parser: SalaryParser, text: str) -> None:
    s = parse(parser, text)
    assert s.negotiable and not s.has_numbers and s.text == text


def test_times_ages_and_percents_are_not_money(parser: SalaryParser) -> None:
    s = parse(parser, "09:00-18:00, 18-35 yosh, 50% chegirma, 6/1, 5 000 000")
    assert (s.min, s.max) == (5_000_000, 5_000_000)


@pytest.mark.parametrize(
    ("line", "money"),
    [
        ("sotuv agenti — 5–15 mln so'm", True),
        ("up to 3800 usd gross", True),
        ("$300", True),
        ("product: marketplace from 0 of a european holding", False),
        ("ish vaqti 09:00-18:00", False),
    ],
)
def test_looks_like_money(line: str, money: bool) -> None:
    assert looks_like_money(line) is money
