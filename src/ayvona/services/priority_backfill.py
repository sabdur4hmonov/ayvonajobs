"""Score jobs that have no priority yet (every job written before the ranking existed).

Runs once at the worker's start (a few hundred rows: instantly) and as
``scripts/backfill_priority.py`` (``--all`` re-scores everything after the word lists in
settings.yaml were changed). Jobs still
waiting in the queue are also re-scored by the start-up re-render (services/reformat.py).
Only the three ``priority_*`` columns are written; nothing else about a job changes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import Job, JobKind
from ayvona.processing.priority import PriorityScorer

BATCH = 500


@dataclass(slots=True)
class BackfillReport:
    scored: int = 0
    changed: int = 0
    tiers: Counter[int] = field(default_factory=Counter)


async def backfill_priority(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
    *,
    rescore_all: bool = False,
    dry_run: bool = False,
) -> BackfillReport:
    """Score the jobs with ``priority_tier IS NULL`` (or all of them with ``rescore_all``).
    Projects are never ranked (they are listed newest first)."""
    scorer = PriorityScorer(settings)
    report = BackfillReport()
    last_id = 0
    while True:
        async with sf() as s, s.begin():
            stmt = select(Job).where(Job.id > last_id, Job.kind == JobKind.JOB.value)
            if not rescore_all:
                stmt = stmt.where(Job.priority_tier.is_(None))
            jobs = list((await s.scalars(stmt.order_by(Job.id).limit(BATCH))).all())
            for job in jobs:
                p = scorer.for_job(job)
                report.scored += 1
                report.tiers[p.tier] += 1
                if (job.priority_tier, job.priority_score, job.priority_reason) != (
                    p.tier,
                    p.score,
                    p.reason,
                ):
                    report.changed += 1
                    if not dry_run:
                        await s.execute(
                            update(Job)
                            .where(Job.id == job.id)
                            .values(**p.fields())
                            .execution_options(synchronize_session=False)
                        )
        if len(jobs) < BATCH:
            return report
        last_id = jobs[-1].id


async def backfill_priority_step(settings: Settings, sf: async_sessionmaker[AsyncSession]) -> int:
    """The worker's start-up step. Never stops the worker."""
    try:
        report = await backfill_priority(settings, sf)
    except Exception:
        logger.exception("Ustuvorlikni hisoblashda xato — keyingi ishga tushishda davom etadi")
        return 0
    if report.scored:
        logger.info(
            "Ustuvorlik hisoblandi: {} ta e'lon (1-daraja: {}, 2: {}, 3: {})",
            report.scored,
            report.tiers[1],
            report.tiers[2],
            report.tiers[3],
        )
    return report.scored
