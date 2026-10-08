"""jobs.full_html (the bot's full card behind the "📖 To'liq ma'lumot" button)

Revision ID: a4d2e7f1c3b9
Revises: f3c8a1d6e9b4
Create Date: 2026-10-08 18:00:00.000000

Additive and data preserving: one nullable TEXT column, no row is rewritten. Existing jobs keep
NULL (their bot card stays their channel caption); queued jobs get it from the worker's start-up
re-render.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d2e7f1c3b9"
down_revision: str | Sequence[str] | None = "f3c8a1d6e9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("full_html", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_column("jobs", "full_html")
