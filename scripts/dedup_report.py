"""Dry run of classify + dedup over every post in data/ayvona.db. Prints duplicate groups.

The DB is opened READ-ONLY: nothing is written, raw_posts statuses stay as they are.

Usage:
    uv run python scripts/dedup_report.py            # duplicate groups (all posts with text)
    uv run python scripts/dedup_report.py --kinds    # + list of every non-job post and why
    uv run python scripts/dedup_report.py --jobs-only
    uv run python scripts/dedup_report.py --review   # + weak "job" posts (score <= 2 / no contact)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from ayvona.config import Settings, get_settings
from ayvona.processing.classify import Classification, Classifier, PostInput, PostKind, merge_album
from ayvona.processing.dedup import DedupIndex, DedupMatch, make_entry

_QUERY = """
SELECT s.identifier, s.own_usernames, r.external_id, r.grouped_id, r.text, r.has_media,
       r.extra, r.posted_at, r.fetched_at
FROM raw_posts r JOIN sources s ON s.id = r.source_id
ORDER BY COALESCE(r.posted_at, r.fetched_at), r.id
"""


@dataclass
class Post:
    key: str  # "@channel/123"
    posted_at: datetime
    input: PostInput
    result: Classification | None = None
    title: str = ""


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def load_posts(conn: sqlite3.Connection) -> list[Post]:
    """Raw posts, album parts merged into one post (keyed by the first part)."""
    albums: dict[tuple[str, int], list[tuple[str, datetime, PostInput]]] = defaultdict(list)
    order: list[tuple[str, int] | tuple[str, str]] = []
    singles: dict[tuple[str, str], tuple[str, datetime, PostInput]] = {}
    for src, own, ext, gid, text, has_media, extra, posted_at, fetched_at in conn.execute(_QUERY):
        item = PostInput(
            text=text or "",
            source=src,
            extra=json.loads(extra) if extra else None,
            has_media=bool(has_media),
            posted_at=_dt(posted_at or fetched_at),
            own_usernames=tuple(json.loads(own) if own else ()),
        )
        entry = (f"{src}/{ext}", item.posted_at, item)  # type: ignore[arg-type]
        if gid is not None:
            if (src, gid) not in albums:
                order.append((src, gid))
            albums[(src, gid)].append(entry)
        else:
            order.append((src, ext))
            singles[(src, ext)] = entry
    posts: list[Post] = []
    for k in order:
        if k in singles:
            key, when, item = singles[k]  # type: ignore[index]
            posts.append(Post(key, when, item))
        else:
            parts = albums[k]  # type: ignore[index]
            posts.append(Post(parts[0][0], parts[0][1], merge_album([p[2] for p in parts])))
    return posts


def all_own_usernames(settings: Settings) -> set[str]:
    """Every channel's own accounts — they are not contacts and must not make posts look alike."""
    own = set()
    for s in settings.app.sources:
        own.add(s.identifier)
        own.update(s.own_usernames)
    for name, rule in settings.source_rules.sources.items():
        own.add(name)
        own.update(rule.extra_own_usernames)
    return own


def run(
    posts: list[Post], jobs_only: bool, ignore: set[str]
) -> dict[str, list[tuple[Post, DedupMatch]]]:
    index = DedupIndex()
    groups: dict[str, list[tuple[Post, DedupMatch]]] = defaultdict(list)
    for p in posts:
        r = p.result
        assert r is not None
        if r.kind is PostKind.NO_TEXT or (jobs_only and r.kind is not PostKind.JOB):
            continue
        entry = make_entry(
            p.key,
            p.posted_at,
            r.clean_text,
            r.contacts.keys and _ordered(r),
            ignore_usernames=ignore,
        )
        p.title = entry.title
        if match := index.check(entry):
            groups[str(match.original)].append((p, match))
    return groups


def _ordered(r: Classification) -> list[str]:
    return [*r.contacts.phones, *r.contacts.usernames]


def print_groups(groups: dict[str, list[tuple[Post, DedupMatch]]], by_key: dict[str, Post]) -> None:
    for n, (orig_key, dups) in enumerate(
        sorted(groups.items(), key=lambda g: g[1][0][0].posted_at), 1
    ):
        orig = by_key[orig_key]
        kind = orig.result.kind if orig.result else "?"
        print(f"\n[{n}] ORIGINAL {orig_key}  ({kind})  {orig.posted_at:%m-%d %H:%M}")
        print(f"      lavozim: {orig.title or '-'}")
        for p, m in dups:
            shared = ", ".join(sorted(m.shared_contacts)) or "-"
            print(
                f"    = {p.key}  ({p.result.kind if p.result else '?'})  {p.posted_at:%m-%d %H:%M}"
                f"  layer={m.layer} matn={m.score:.0f} lavozim={m.title_score:.0f}"
                f" umumiy_aloqa={shared}"
            )
            print(f"      lavozim: {p.title or '-'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--jobs-only", action="store_true", help="only posts classified as job")
    parser.add_argument("--kinds", action="store_true", help="also list every non-job post")
    parser.add_argument(
        "--review", action="store_true", help="also list weak jobs (score <= 2 or no contact)"
    )
    args = parser.parse_args()

    settings = get_settings()
    db = settings.db_file
    if not db.exists():
        print(f"Baza topilmadi: {db}")
        return 1
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)  # read-only
    try:
        posts = load_posts(conn)
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_posts").fetchone()[0]
    finally:
        conn.close()

    classifier = Classifier(settings.filters, settings.source_rules)
    now = datetime.now(UTC)
    for p in posts:
        p.result = classifier.classify(p.input, now)
    kinds = Counter(p.result.kind for p in posts if p.result)

    print(f"Baza: {raw_count} ta raw post -> {len(posts)} ta post (albomlar birlashtirildi)")
    print("Turlar: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common()))
    if args.kinds:
        print("\n--- E'lon bo'lmaganlar (kind != job) ---")
        for p in posts:
            r = p.result
            if r and r.kind is not PostKind.JOB:
                first = p.input.text.strip().split("\n", 1)[0][:70]
                print(f"  {r.kind:<11} {p.key:<36} {', '.join(r.reasons)[:60]:<60} | {first}")

    if args.review:
        print("\n--- Tekshirish kerak bo'lgan job'lar (ball <= 2 yoki aloqa yo'q) ---")
        for p in posts:
            r = p.result
            if r and r.kind is PostKind.JOB and (r.job_score <= 2 or not r.has_contact):
                first = p.input.text.strip().split("\n", 1)[0][:70]
                contact = "aloqa bor" if r.has_contact else "ALOQA YO'Q"
                print(f"  ball={r.job_score} {contact:<10} {p.key:<36} | {first}")

    groups = run(posts, args.jobs_only, all_own_usernames(settings))
    by_key = {p.key: p for p in posts}
    print_groups(groups, by_key)
    dup_posts = sum(len(d) for d in groups.values())
    layers = Counter(m.layer for d in groups.values() for _, m in d)
    scope = "faqat job" if args.jobs_only else "matnli hamma postlar"
    print(
        f"\nJAMI ({scope}): {len(groups)} guruh, {dup_posts} dublikat post "
        f"({dup_posts + len(groups)} post guruhlarda). Qatlamlar: {dict(layers)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
