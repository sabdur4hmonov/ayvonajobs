"""How long a published job stays in search (no aiogram: the website and the bot share it)."""

from __future__ import annotations

from datetime import timedelta

from ayvona.config import Settings
from ayvona.db.models import Job, JobOrigin


def active_days(job: Job, settings: Settings) -> int:
    """How many days ``job`` stays active from its publication: the poster's choice
    (``jobs.active_days``) or the default of its origin."""
    if job.active_days:
        return int(job.active_days)
    exp = settings.app.expiry
    return exp.user_days if job.origin == JobOrigin.USER else exp.aggregator_days


def remind_lead(job: Job, settings: Settings) -> timedelta:
    """How long before the end the "Uzaytirasizmi?" reminder goes out: ``remind_days_before``,
    but never more than a third of a short ad's life (3 days -> 1 day, not 2)."""
    days = active_days(job, settings)
    return timedelta(days=min(settings.app.expiry.remind_days_before, days / 3))
