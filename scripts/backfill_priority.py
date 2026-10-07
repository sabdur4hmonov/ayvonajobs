"""Give every job its priority tier (processing/priority.py): the ranking of the publishing queue
and of search.

    uv run python scripts/backfill_priority.py --dry-run   # only count (nothing is written)
    uv run python scripts/backfill_priority.py             # jobs without a priority
    uv run python scripts/backfill_priority.py --all       # re-score everything (after editing
                                                           # the word lists in config/settings.yaml)

The worker already does the first form every time it starts. Only the three ``priority_*`` columns
are written. Safe to run while the services are running (short transactions; the DB is in WAL mode).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from ayvona.config import get_settings
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.services.priority_backfill import backfill_priority


async def main(rescore_all: bool, dry_run: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings.db_url)
    try:
        if not await schema_is_ready(engine):
            print("Baza eski versiyada. Avval: alembic upgrade head", file=sys.stderr)
            return 1
        report = await backfill_priority(
            settings, create_session_factory(engine), rescore_all=rescore_all, dry_run=dry_run
        )
    finally:
        await engine.dispose()
    print(f"Baholandi: {report.scored} ta e'lon, o'zgardi: {report.changed}")
    print(
        f"1-daraja: {report.tiers[1]} · 2-daraja: {report.tiers[2]} · 3-daraja: {report.tiers[3]}"
    )
    if dry_run:
        print("(--dry-run: hech narsa yozilmadi)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E'lonlarga ustuvorlik (daraja) berish")
    parser.add_argument("--all", action="store_true", help="hammasini qayta baholash")
    parser.add_argument("--dry-run", action="store_true", help="faqat sanash, yozmaslik")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.all, args.dry_run)))
