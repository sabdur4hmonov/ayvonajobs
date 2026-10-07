"""jobs.priority_tier / priority_score / priority_reason (ranking of the queue and of search)

Revision ID: d1f5b8c3a7e2
Revises: c9e1a4b7d2f5
Create Date: 2026-10-07 11:00:00.000000

Additive and data preserving: three nullable columns and one index. ``NULL`` = "not scored yet";
every reader treats it as tier 2 (normal), so nothing changes until the worker's start-up backfill
(services/priority_backfill.py) or the pipeline fills them in. Plain ``ADD COLUMN``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f5b8c3a7e2"
down_revision: str | Sequence[str] | None = "c9e1a4b7d2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("priority_tier", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("priority_score", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("priority_reason", sa.String(length=512), nullable=True))
    op.create_index("ix_jobs_status_priority_tier", "jobs", ["status", "priority_tier"])


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_index("ix_jobs_status_priority_tier", table_name="jobs")
    op.drop_column("jobs", "priority_reason")
    op.drop_column("jobs", "priority_score")
    op.drop_column("jobs", "priority_tier")
