"""jobs.reminded_at (Bosqich 14: "Uzaytirasizmi?" reminder before a user job expires)

Revision ID: b8d4f0a2c6e9
Revises: a7c3e9f1b5d8
Create Date: 2026-10-01 00:30:00.000000

``expires_at`` already exists; old published jobs get it from the worker (services/expiry.py:
published_at + 21 / 30 days). Plain ``ADD COLUMN``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4f0a2c6e9"
down_revision: str | Sequence[str] | None = "a7c3e9f1b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("reminded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_column("jobs", "reminded_at")
