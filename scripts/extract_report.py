"""Dry run of classify + extract over every post in data/ayvona.db. Prints contact statistics.

The DB is opened READ-ONLY: nothing is written.

Usage:
    uv run python scripts/extract_report.py              # summary for all posts
    uv run python scripts/extract_report.py --no-contact # + list of posts without any contact
    uv run python scripts/extract_report.py --jobs       # + one line per job (title, salary, ...)
    uv run python scripts/extract_report.py --low        # + low_quality jobs (admin report)
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime

from dedup_report import load_posts  # scripts/ is on sys.path when run as a script

from ayvona.config import get_settings
from ayvona.processing.classify import Classifier, PostKind
from ayvona.processing.extract import Extraction, Extractor


def _first_line(text: str) -> str:
    return text.strip().split("\n", 1)[0][:60]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--no-contact", action="store_true", help="list posts without a contact")
    parser.add_argument("--jobs", action="store_true", help="one line per job")
    parser.add_argument("--low", action="store_true", help="list low_quality jobs")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # emoji on Windows

    settings = get_settings()
    db = settings.db_file
    if not db.exists():
        print(f"Baza topilmadi: {db}")
        return 1
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)  # read-only
    try:
        posts = load_posts(conn)
    finally:
        conn.close()

    classifier = Classifier(settings.filters, settings.source_rules)
    extractor = Extractor(settings)
    now = datetime.now(UTC)
    rows: list[tuple[str, PostKind, Extraction | None, str]] = []
    for p in posts:
        kind = classifier.classify(p.input, now).kind
        ex = extractor.extract(p.input) if p.input.text.strip() else None
        rows.append((p.key, kind, ex, p.input.text))

    def stats(title: str, subset: list[tuple[str, PostKind, Extraction | None, str]]) -> None:
        exs = [e for _, _, e, _ in subset if e is not None]
        n = len(subset)
        phone = sum(bool(e.phones) for e in exs)
        user = sum(bool(e.usernames) for e in exs)
        url = sum(bool(e.apply_url) for e in exs)
        email = sum(bool(e.emails) for e in exs)
        none = n - sum(e.has_contact for e in exs)
        print(f"\n{title}: {n} ta post")
        print(f"  telefon topildi:    {phone}")
        print(f"  @username topildi:  {user}")
        print(f"  apply_url topildi:  {url}")
        print(f"  email topildi:      {email}")
        print(f"  ALOQASIZ qoldi:     {none}")

    print(f"Baza: {len(posts)} ta post (albomlar birlashtirildi)")
    print("Turlar: " + ", ".join(f"{k}={v}" for k, v in Counter(k for _, k, _, _ in rows).items()))
    stats("HAMMA postlar", rows)
    jobs = [r for r in rows if r[1] is PostKind.JOB]
    stats("Faqat job", jobs)
    job_ex = [e for _, _, e, _ in jobs if e is not None]
    print(
        f"\nJob'lar: lavozim {sum(bool(e.title) for e in job_ex)}, "
        f"maosh (son) {sum(e.salary_min is not None or e.salary_max is not None for e in job_ex)}, "
        f"hudud {sum(bool(e.region) for e in job_ex)}, "
        f"ko'p vakansiyali {sum(e.multi for e in job_ex)}, "
        f"low_quality {sum(e.low_quality for e in job_ex)}, "
        f"kanalga chiqadi (publish) {sum(e.publish for e in job_ex)}"
    )
    print(
        "Kategoriyalar: "
        + ", ".join(f"{k}={v}" for k, v in Counter(e.category for e in job_ex).most_common())
    )

    if args.no_contact:
        print("\n--- Aloqasiz postlar ---")
        for key, kind, e, text in rows:
            if e is None or not e.has_contact:
                print(f"  {kind:<11} {key:<36} | {_first_line(text)}")
    if args.low:
        print("\n--- low_quality job'lar (lavozim ham, maosh ham yo'q) ---")
        for key, _, e, text in jobs:
            if e is not None and e.low_quality:
                print(f"  {key:<36} | {_first_line(text)}")
    if args.jobs:
        print("\n--- Job'lar ---")
        for key, _, e, _ in jobs:
            if e is None:
                continue
            sal = f"{e.salary_min}-{e.salary_max} {e.currency or ''}" if e.currency else "-"
            print(
                f"  {key:<34} {e.category}/{e.profession or '-'} | {e.title or '-'} | {sal} | "
                f"{e.region or '-'} | conf={e.confidence}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
