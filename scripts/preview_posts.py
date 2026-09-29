"""Show how every job post in data/ayvona.db would look in our channel (Bosqich 6 check).

Runs classify -> extract -> clean -> format over all posts (the DB is opened READ-ONLY) and writes
one HTML page you open in the browser: ``data/preview.html``. Nothing is sent to Telegram.

Usage:
    uv run python scripts/preview_posts.py                 # every job post
    uv run python scripts/preview_posts.py --fallback      # only posts shown with the fallback
    uv run python scripts/preview_posts.py --source @kasbdoruz
    start data\\preview.html                               # open it (PowerShell)
"""

from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime

from dedup_report import load_posts  # scripts/ is on sys.path when run as a script

from ayvona.config import get_settings
from ayvona.processing.classify import Classifier, PostKind
from ayvona.processing.clean import Cleaner
from ayvona.processing.extract import Extractor
from ayvona.processing.formatter import Formatter, telegram_post_url

PAGE = """<!doctype html>
<meta charset="utf-8"><title>Ayvona Jobs — postlar ko'rinishi</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #e7ebf0; margin: 16px; }}
.post {{ display: inline-block; vertical-align: top; width: 440px; margin: 8px; background: #fff;
        border-radius: 12px; padding: 12px 14px; box-shadow: 0 1px 2px #0002; }}
.cap {{ white-space: pre-wrap; font-size: 14px; line-height: 1.35; }}
.meta {{ color: #777; font-size: 12px; margin-bottom: 6px; }}
.fb {{ border-left: 4px solid #e99; }}
.btn {{ display: inline-block; margin: 6px 4px 0 0; padding: 4px 8px; border-radius: 8px;
       background: #eef3f8; font-size: 12px; color: #2a6fb0; text-decoration: none; }}
a {{ color: #2a6fb0; }}
</style>
<h2>Ayvona Jobs — {n} ta post</h2>
<p>{summary}</p>
{posts}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--fallback", action="store_true", help="only fallback-template posts")
    parser.add_argument("--source", help="only one channel, e.g. @kasbdoruz")
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
    cleaner = Cleaner(settings.source_rules)
    formatter = Formatter(settings)
    now = datetime.now(UTC)
    stats: Counter[str] = Counter()
    blocks: list[str] = []
    longest = 0
    for p in posts:
        post = p.input
        if args.source and (post.source or "").lower() != args.source.lower():
            continue
        if classifier.classify(post, now).kind is not PostKind.JOB:
            continue
        ex = extractor.extract(post)
        if not ex.publish:
            stats["chiqmaydi (aloqasiz / past sifat)"] += 1
            continue
        cleaned = cleaner.clean(
            post.text, post.extra, source=post.source, own_usernames=post.own_usernames
        )
        src, _, ext_id = p.key.rpartition("/")
        out = formatter.format(ex, cleaned, source_url=telegram_post_url(src, ext_id))
        stats["fallback" if out.fallback else "to'liq shablon"] += 1
        if out.shortened:
            stats["qisqartirilgan"] += 1
        longest = max(longest, out.length)
        if args.fallback and not out.fallback:
            continue
        buttons = "".join(
            f'<a class="btn" href="{html.escape(b.url)}">{html.escape(b.text)}</a>'
            for row in out.buttons(job_id=1)
            for b in row
        )
        folder = ex.category + (f"/{ex.profession}" if ex.profession else "")
        meta = (
            f"{html.escape(p.key)} · {ex.language} · ishonch {ex.confidence} · "
            f"{out.length}/1024 · rasm: {folder}"
            + (f" · qisqartirildi: {', '.join(out.shortened)}" if out.shortened else "")
        )
        cls = "post fb" if out.fallback else "post"
        blocks.append(
            f'<div class="{cls}"><div class="meta">{meta}</div>'
            f'<div class="cap">{out.html}</div>{buttons}</div>'
        )

    summary = ", ".join(f"{k}: {v}" for k, v in stats.items()) + f", eng uzun: {longest}/1024"
    path = settings.data_dir / "preview.html"
    path.write_text(
        PAGE.format(n=len(blocks), summary=html.escape(summary), posts="\n".join(blocks)),
        encoding="utf-8",
    )
    print(summary)
    print(f"Tayyor: {path}  (brauzerda oching: start {path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
