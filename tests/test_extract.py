"""Expected extraction results of the real job posts (docs/POST_EXAMPLES.md).

Bosqich 4 wrote these as xfail; Bosqich 5 (processing/extract.py, categorize.py) makes them pass.
"""

from __future__ import annotations

from typing import Any

import pytest

from ayvona.config import DEFAULT_CONFIG_DIR, load_settings
from ayvona.processing.extract import Extraction, Extractor
from tests.post_fixtures import REGRESSIONS_DIR, load_dir, to_post

# Fields compared as-is; others need special handling below.
EXACT_FIELDS = (
    "category",
    "profession",
    "salary_min",
    "salary_max",
    "currency",
    "salary_period",
    "salary_text",
    "region",
    "district",
    "apply_url",
    "multi",
    "publish",
)
SET_FIELDS = ("phones", "emails")

EXAMPLES = [fx for fx in load_dir() if fx["expected"]["kind"] == "job"]
JOBS = EXAMPLES + load_dir(REGRESSIONS_DIR)


@pytest.fixture(scope="module")
def extractor() -> Extractor:
    return Extractor(load_settings(DEFAULT_CONFIG_DIR, env_file=None))


def run_extract(extractor: Extractor, fx: dict[str, Any]) -> Extraction:
    return extractor.extract(to_post(fx))


@pytest.mark.parametrize("fx", JOBS, ids=[fx["id"] for fx in JOBS])
def test_extract_real_post(extractor: Extractor, fx: dict[str, Any]) -> None:
    exp = fx["expected"]
    got = run_extract(extractor, fx)

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
    if "positions_min" in exp:
        assert len(got.positions) >= exp["positions_min"]


def test_every_example_job_with_title_or_salary_is_published(extractor: Extractor) -> None:
    for fx in JOBS:
        got = run_extract(extractor, fx)
        if fx["expected"].get("publish", True):
            assert got.publish, (fx["id"], got.reasons)
            if got.title_source in ("label", "phrase", "positions"):  # title + contact
                assert got.confidence >= 0.7, fx["id"]


def test_low_quality_post_is_not_published(extractor: Extractor) -> None:
    fx = next(f for f in JOBS if f["id"] == "ishtopuz_rasmiy_40829")  # Crafers: only a form link
    got = run_extract(extractor, fx)
    assert got.low_quality and not got.publish
    assert got.has_contact  # the form link is kept — the admin report shows it
