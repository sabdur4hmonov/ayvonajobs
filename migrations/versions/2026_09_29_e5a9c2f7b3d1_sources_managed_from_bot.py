"""Sources managed from the bot (Bosqich 8): status, added_via, added_by, backfill, web limits

Revision ID: e5a9c2f7b3d1
Revises: d3f8b1c6a2e4
Create Date: 2026-09-29 23:30:00.000000

Existing rows are the settings.yaml channels: status 'active', added_via 'yaml'.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a9c2f7b3d1"
down_revision: str | Sequence[str] | None = "d3f8b1c6a2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    "daily_limit",
    "check_interval_minutes",
    "backfill_request",
    "added_by",
    "added_via",
    "status",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sources",
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("added_via", sa.String(length=8), server_default="yaml", nullable=False),
    )
    op.add_column("sources", sa.Column("added_by", sa.BigInteger(), nullable=True))
    op.add_column("sources", sa.Column("backfill_request", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("check_interval_minutes", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("daily_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for column in COLUMNS:
        op.drop_column("sources", column)
