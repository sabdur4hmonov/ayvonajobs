"""Copy real posts from data/ayvona.db into test fixtures (tests/fixtures/posts/*.json).

The DB is opened READ-ONLY. Text and ``extra`` are copied exactly as stored.

Usage:
    uv run python scripts/export_fixtures.py
        -> refresh every existing fixture from the DB (keeps "title" and "expected")
    uv run python scripts/export_fixtures.py @kanal 12345
        -> add a new fixture (fill "expected" by hand afterwards)
    uv run python scripts/export_fixtures.py @kanal 12345 --dir tests/fixtures/dedup
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from ayvona.config import PROJECT_ROOT, get_settings

DEFAULT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "posts"
FIXTURE_DIRS = (DEFAULT_DIR, PROJECT_ROOT / "tests" / "fixtures" / "dedup")

_QUERY = """
SELECT r.external_id, r.grouped_id, r.text, r.has_media, r.media_type, r.extra, r.posted_at,
       r.source_id
FROM raw_posts r JOIN sources s ON s.id = r.source_id
WHERE s.identifier = ? AND r.external_id = ?
"""
_ALBUM = """
SELECT external_id, text, has_media, media_type FROM raw_posts
WHERE source_id = ? AND grouped_id = ? AND external_id != ?
ORDER BY CAST(external_id AS INTEGER)
"""


def fixture_path(directory: Path, source: str, external_id: str) -> Path:
    return directory / f"{source.lstrip('@')}_{external_id}.json"


def _iso(value: str | None) -> str | None:
    # SQLite stores "2026-09-28 13:15:07.000000" (UTC) -> "2026-09-28T13:15:07+00:00"
    return None if value is None else value.replace(" ", "T").split(".")[0] + "+00:00"


def load_raw(conn: sqlite3.Connection, source: str, external_id: str) -> dict[str, Any]:
    row = conn.execute(_QUERY, (source, external_id)).fetchone()
    if row is None:
        raise LookupError(f"{source}/{external_id} bazada topilmadi")
    ext, grouped_id, text, has_media, media_type, extra, posted_at, source_id = row
    extra_obj = json.loads(extra) if extra else None
    raw: dict[str, Any] = {
        "source": source,
        "external_id": ext,
        "grouped_id": grouped_id,
        "has_media": bool(has_media),
        "media_type": media_type,
        "posted_at": _iso(posted_at),
        "text": text,
        "extra": extra_obj or {},
    }
    if grouped_id is not None:
        raw["album"] = [
            {"external_id": e, "text": t, "has_media": bool(m), "media_type": mt}
            for e, t, m, mt in conn.execute(_ALBUM, (source_id, grouped_id, ext))
        ]
    return raw


def write_fixture(path: Path, raw: dict[str, Any], old: dict[str, Any] | None) -> None:
    data: dict[str, Any] = {"title": (old or {}).get("title", "")}
    data.update(raw)
    data["expected"] = (old or {}).get("expected", {})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:  # LF on Windows too
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("source", nargs="?", help="@kanal")
    parser.add_argument("external_id", nargs="?", help="post id")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    db = get_settings().db_file
    if not db.exists():
        print(f"Baza topilmadi: {db}")
        return 1
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        if args.source and args.external_id:
            path = fixture_path(args.dir, args.source, args.external_id)
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            write_fixture(path, load_raw(conn, args.source, args.external_id), old)
            print(f"Yozildi: {path.relative_to(PROJECT_ROOT)}")
            return 0
        n = 0
        for directory in FIXTURE_DIRS:
            for path in sorted(directory.glob("*.json")):
                old = json.loads(path.read_text(encoding="utf-8"))
                write_fixture(path, load_raw(conn, old["source"], old["external_id"]), old)
                n += 1
        print(f"Yangilandi: {n} ta fixture")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
