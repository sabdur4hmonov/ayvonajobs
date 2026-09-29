"""Expected extraction results of the 41 real posts (docs/POST_EXAMPLES.md).

Bosqich 5 writes processing/extract.py and processing/categorize.py; until then every test here
is an expected failure (xfail). When Bosqich 5 is done, remove ``pytestmark`` and adapt only
:func:`run_extract` to the real API.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.post_fixtures import load_dir, to_post

pytestmark = pytest.mark.xfail(reason="Bosqich 5: extract.py / categorize.py hali yozilmagan")

# Fields compared as-is; others need special handling below.
EXACT_FIELDS = (
    "category",
    "profession",
    "salary_min",
    "salary_max",
    "currency",
    "salary_period",
    "region",
    "district",
    "apply_url",
    "multi",
)
SET_FIELDS = ("phones", "emails")

JOBS = [fx for fx in load_dir() if fx["expected"]["kind"] == "job"]


def run_extract(fx: dict[str, Any]) -> Any:
    """The one place to adapt when extract.py exists."""
    from ayvona.processing.extract import extract  # noqa: PLC0415 — module does not exist yet

    return extract(to_post(fx))


@pytest.mark.parametrize("fx", JOBS, ids=[fx["id"] for fx in JOBS])
def test_extract_real_post(fx: dict[str, Any]) -> None:
    exp = fx["expected"]
    got = run_extract(fx)

    for field in EXACT_FIELDS:
        if field in exp:
            assert getattr(got, field) == exp[field], field
    for field in SET_FIELDS:
        if field in exp:
            assert set(getattr(got, field)) == set(exp[field]), field
    if "usernames" in exp:  # Telegram usernames are case-insensitive
        assert {u.lower() for u in got.usernames} == {u.lower() for u in exp["usernames"]}
    if "company" in exp:  # expected is the core name: "ALSTAR ACP" in "ALSTAR ACP ... zavodi"
        assert exp["company"].lower() in (got.company or "").lower()
    if "title_contains" in exp:
        assert exp["title_contains"].lower() in (got.title or "").lower()
