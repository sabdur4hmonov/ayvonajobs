"""jobs.kind + project columns (Loyihalar: one-time paid projects next to salaried jobs)

Revision ID: e2a6c9d4b8f1
Revises: d1f5b8c3a7e2
Create Date: 2026-10-07 13:00:00.000000

Additive and data preserving: ``kind`` is NOT NULL but has the server default ``'job'``, so every
existing row becomes a normal job without being rewritten by the application; the three project
columns are nullable. Plain ``ADD COLUMN`` (SQLite allows a NOT NULL column with a constant
default) and one index.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2a6c9d4b8f1"
down_revision: str | Sequence[str] | None = "d1f5b8c3a7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "jobs",
        sa.Column("kind", sa.String(length=16), server_default="job", nullable=False),
    )
    op.add_column("jobs", sa.Column("budget_amount", sa.BigInteger(), nullable=True))
    op.add_column("jobs", sa.Column("budget_currency", sa.String(length=8), nullable=True))
    op.add_column("jobs", sa.Column("deadline_text", sa.String(length=255), nullable=True))
    op.create_index("ix_jobs_kind_status", "jobs", ["kind", "status"])


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_index("ix_jobs_kind_status", table_name="jobs")
    op.drop_column("jobs", "deadline_text")
    op.drop_column("jobs", "budget_currency")
    op.drop_column("jobs", "budget_amount")
    op.drop_column("jobs", "kind")
