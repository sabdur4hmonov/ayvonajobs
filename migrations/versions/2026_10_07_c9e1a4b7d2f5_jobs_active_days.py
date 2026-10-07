"""jobs.active_days (how many days a user ad stays active, chosen by the poster)

Revision ID: c9e1a4b7d2f5
Revises: b8d4f0a2c6e9
Create Date: 2026-10-07 09:00:00.000000

Additive and data preserving: a nullable column. ``NULL`` = "not asked" — every existing job keeps
its current behaviour (``expiry.user_days`` / ``expiry.aggregator_days``). Plain ``ADD COLUMN``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e1a4b7d2f5"
down_revision: str | Sequence[str] | None = "b8d4f0a2c6e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("active_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_column("jobs", "active_days")
