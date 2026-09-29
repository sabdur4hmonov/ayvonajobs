"""jobs.profession and jobs.salary_period (Bosqich 5: categorizer and salary parser)

Revision ID: b5e1a7c3d9f2
Revises: 0574c13c842a
Create Date: 2026-09-29 18:00:00.000000

Plain ``ADD COLUMN`` (no batch table rebuild): SQLite supports it, and rebuilding ``jobs`` would
drop the FTS5 sync triggers created in the initial migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e1a7c3d9f2"
down_revision: str | Sequence[str] | None = "0574c13c842a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("profession", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("salary_period", sa.String(length=8), nullable=True))


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place, the triggers stay)."""
    op.drop_column("jobs", "salary_period")
    op.drop_column("jobs", "profession")
