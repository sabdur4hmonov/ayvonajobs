"""Rebuild the caption + buttons of jobs still waiting to be published (``queued`` / ``retry``)
with the CURRENT formatter and ``branding`` (services/reformat.py).

    uv run python scripts/reformat_queued.py --dry-run   # only show what would change
    uv run python scripts/reformat_queued.py             # backup, then update the jobs

Stop the worker first (the DB must not be busy, and it must not publish half-updated jobs).
Before writing, the DB is copied to ``data/backups/reformat/``. Published / sending / failed jobs
are never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ayvona.config import get_settings
from ayvona.db.session import create_engine, create_session_factory, schema_is_ready
from ayvona.services.backup import make_backup
from ayvona.services.reformat import (
    JobChange,
    ReformatReport,
    reformat_queued,
    worker_heartbeat_age,
    worker_seems_running,
)
from ayvona.timeutil import to_local, utcnow

SAMPLES = 3
LINE = "=" * 72


def _buttons(buttons: list[object]) -> str:
    return json.dumps(buttons, ensure_ascii=False)


def _print_change(c: JobChange) -> None:
    print(LINE)
    print(f"job #{c.job_id} ({c.status})")
    if c.changed_fields:
        print(f"Boshqa o'zgargan maydonlar: {', '.join(c.changed_fields)}")
    print("--- OLDIN " + "-" * 62)
    print(c.before_text)
    print(f"Tugmalar: {_buttons(c.before_buttons)}")
    print("--- KEYIN " + "-" * 62)
    print(c.after_text)
    print(f"Tugmalar: {_buttons(c.after_buttons)}")


def _print_report(r: ReformatReport) -> None:
    samples = [c for c in r.changes if c.text_changed][:SAMPLES] or r.changes[:SAMPLES]
    for c in samples:
        _print_change(c)
    print(LINE)
    print(f"Navbatdagi (queued/retry) e'lonlar: {r.total}")
    if r.dry_run:
        print(f"O'zgaradi: {len(r.changes)}  (--dry-run: hech narsa yozilmadi)")
    else:
        print(f"Yangilandi: {r.updated}")
    print(f"O'zgarishsiz: {r.unchanged}")
    if r.taken:
        print(f"Shu orada worker o'zgartirgan, tegilmadi: {len(r.taken)} -> {r.taken}")
    if r.skipped:
        print(f"O'tkazib yuborildi: {len(r.skipped)}")
        for job_id, reason in r.skipped:
            print(f"  job #{job_id}: {reason}")


async def main(dry_run: bool, force: bool) -> int:
    settings = get_settings()
    if not settings.db_file.exists():
        print(f"Baza topilmadi: {settings.db_file}")
        return 1
    engine = create_engine(settings.db_url)
    try:
        if not await schema_is_ready(engine):
            print("Baza tayyor emas. Avval: uv run alembic upgrade head")
            return 1
        sf = create_session_factory(engine)

        age = await worker_heartbeat_age(sf)
        if worker_seems_running(settings, age):
            assert age is not None
            msg = (
                f"Worker ishlayapti shekilli (oxirgi belgi {int(age.total_seconds())} s oldin). "
                "Avval uni to'xtating (Ctrl+C yoki: sudo systemctl stop ayvona-worker), "
                "2 daqiqa kuting va qayta ishga tushiring."
            )
            if dry_run:
                print(f"OGOHLANTIRISH: {msg}\n")
            elif not force:
                print(f"TO'XTATILDI: {msg}\n(Aniq bilsangiz: --force)")
                return 2
            else:
                print(f"OGOHLANTIRISH (--force): {msg}\n")

        if not dry_run:
            now = utcnow()
            name = f"ayvona_{to_local(now, settings.timezone):%Y-%m-%d_%H%M%S}_before_reformat.db"
            path = await asyncio.to_thread(
                make_backup,
                settings.db_file,
                settings.backup_dir / "reformat",
                now.date(),
                name,
            )
            print(f"Backup olindi: {path}\n")

        report = await reformat_queued(settings, sf, dry_run=dry_run)
        _print_report(report)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    # Uzbek letters / emoji in the Windows console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="faqat ko'rsatish, bazaga hech narsa yozilmaydi"
    )
    parser.add_argument(
        "--force", action="store_true", help="worker ishlayotgan bo'lsa ham davom etish"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run, args.force)))
