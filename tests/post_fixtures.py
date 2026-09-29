"""Load real-post fixtures (tests/fixtures/posts/*.json, made by scripts/export_fixtures.py)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ayvona.processing.classify import PostInput, merge_album

FIXTURES = Path(__file__).parent / "fixtures"
POSTS_DIR = FIXTURES / "posts"
DEDUP_DIR = FIXTURES / "dedup"

# The day the 41 examples were collected and labelled. "Ariza muddati" is judged against it.
LABEL_DAY = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    data["id"] = path.stem
    return data


def load_dir(directory: Path = POSTS_DIR) -> list[dict[str, Any]]:
    return [load(p) for p in sorted(directory.glob("*.json"))]


def to_post(fx: dict[str, Any]) -> PostInput:
    """Fixture -> classifier input, album parts merged (like the pipeline will do)."""
    posted_at = datetime.fromisoformat(fx["posted_at"]) if fx.get("posted_at") else None

    def part(d: dict[str, Any]) -> PostInput:
        return PostInput(
            text=d.get("text") or "",
            source=fx["source"],
            extra=d.get("extra") or None,
            has_media=bool(d.get("has_media")),
            posted_at=posted_at,
            own_usernames=(fx["source"],),
        )

    parts = [part(fx), *(part(a) for a in fx.get("album", []))]
    return merge_album(parts) if len(parts) > 1 else parts[0]
