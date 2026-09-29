"""Quick look into the DB: sources, heartbeat and the latest raw posts.

Usage:
    uv run python scripts/show_status.py          # last 10 posts
    uv run python scripts/show_status.py 30       # last 30 posts
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from ayvona.config import get_settings
from ayvona.db.models import RawPost, Source
from ayvona.db.repositories import kv_repo
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.timeutil import to_local, utcnow


def _fmt(dt: object, tz: object) -> str:
    return to_local(dt, tz).strftime("%Y-%m-%d %H:%M:%S") if dt else "-"  # type: ignore[arg-type]


async def main(limit: int) -> int:
    settings = get_settings()
    tz = settings.timezone
    engine = create_engine(settings.db_url)
    try:
        if not await schema_is_ready(engine):
            print("Baza tayyor emas. Avval: uv run alembic upgrade head")
            return 1
        sf = create_session_factory(engine)
        async with sf() as s:
            hb = await kv_repo.read_heartbeat(s, "collector")
            age = f"{(utcnow() - hb).total_seconds():.0f} s oldin" if hb else "hali yo'q"
            print(f"Baza: {settings.db_file}")
            print(f"Collector heartbeat: {_fmt(hb, tz)} ({age})\n")

            count_rows = await s.execute(
                select(RawPost.source_id, func.count()).group_by(RawPost.source_id)
            )
            counts = {source_id: n for source_id, n in count_rows}
            print("MANBALAR")
            for src in (await s.scalars(select(Source).order_by(Source.id))).all():
                state = "yoqilgan" if src.enabled else "o'chiq"
                print(
                    f"  #{src.id} {src.identifier} [{state}] postlar={counts.get(src.id, 0)} "
                    f"last_seen_id={src.last_seen_id or '-'} "
                    f"oxirgi muvaffaqiyat={_fmt(src.last_success_at, tz)} xatolar={src.error_count}"
                )
                if src.last_error:
                    print(f"      oxirgi xato: {src.last_error[:200]}")

            print(f"\nOXIRGI {limit} TA POST")
            rows = (
                await s.execute(
                    select(RawPost, Source.identifier)
                    .join(Source, Source.id == RawPost.source_id)
                    .order_by(RawPost.id.desc())
                    .limit(limit)
                )
            ).all()
            for post, ident in rows:
                text = (post.text or "").replace("\n", " ")[:90]
                media = f" [{post.media_type}]" if post.has_media else ""
                print(
                    f"  {_fmt(post.posted_at, tz)} {ident} #{post.external_id} "
                    f"({post.status.value}){media}: {text}"
                )
            if not rows:
                print("  (hali post yo'q)")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sys.exit(asyncio.run(main(n)))
