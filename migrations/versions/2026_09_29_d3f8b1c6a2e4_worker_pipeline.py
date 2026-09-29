"""Worker pipeline columns (Bosqich 7): backfill flag, dedup entry, job link, channel buttons

Revision ID: d3f8b1c6a2e4
Revises: c7a4e2d8f1b6
Create Date: 2026-09-29 23:00:00.000000

Plain ``ADD COLUMN`` (no batch table rebuild), like b5e1a7c3d9f2: rebuilding ``jobs`` would drop
the FTS5 sync triggers. New raw_posts statuses (resume, closed, ...) need no migration: the status
column is a plain VARCHAR.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f8b1c6a2e4"
down_revision: str | Sequence[str] | None = "c7a4e2d8f1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "raw_posts",
        sa.Column("is_backfill", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("raw_posts", sa.Column("job_id", sa.Integer(), nullable=True))
    op.add_column("raw_posts", sa.Column("duplicate_of", sa.Integer(), nullable=True))
    op.add_column("raw_posts", sa.Column("dedup_text", sa.Text(), nullable=True))
    op.add_column("raw_posts", sa.Column("dedup_title", sa.String(length=255), nullable=True))
    op.add_column("raw_posts", sa.Column("dedup_contacts", sa.JSON(), nullable=True))
    op.add_column("raw_posts", sa.Column("fingerprint", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_raw_posts_job_id"), "raw_posts", ["job_id"], unique=False)
    op.add_column("jobs", sa.Column("buttons", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place, the triggers stay)."""
    op.drop_column("jobs", "buttons")
    op.drop_index(op.f("ix_raw_posts_job_id"), table_name="raw_posts")
    for column in (
        "fingerprint",
        "dedup_contacts",
        "dedup_title",
        "dedup_text",
        "duplicate_of",
        "job_id",
        "is_backfill",
    ):
        op.drop_column("raw_posts", column)
