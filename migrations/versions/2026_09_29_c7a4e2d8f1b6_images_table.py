"""images table (Bosqich 6): category_images -> images with rotation and file_id cache

Revision ID: c7a4e2d8f1b6
Revises: b5e1a7c3d9f2
Create Date: 2026-09-29 21:00:00.000000

``category_images`` held one picture per category (primary key = category). docs/IMAGES.md needs
3-4 rotating pictures per category *and* per profession, so the table becomes ``images``
(ARCHITECTURE §4). Existing rows are copied over; nothing used the old table yet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a4e2d8f1b6"
down_revision: str | Sequence[str] | None = "b5e1a7c3d9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("profession", sa.String(length=64), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("is_placeholder", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("times_used", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
        sa.UniqueConstraint("file_path", name=op.f("uq_images_file_path")),
    )
    op.create_index(
        "ix_images_category_profession", "images", ["category", "profession"], unique=False
    )
    op.execute(
        "INSERT INTO images (category, profession, file_path, telegram_file_id, is_placeholder,"
        " times_used, created_at, updated_at)"
        " SELECT category, NULL, file_path, telegram_file_id, 0, 0, updated_at, updated_at"
        " FROM category_images"
    )
    op.drop_table("category_images")


def downgrade() -> None:
    """Downgrade schema (one picture per category survives: the most used one)."""
    op.create_table(
        "category_images",
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("category", name=op.f("pk_category_images")),
    )
    op.execute(
        "INSERT OR IGNORE INTO category_images (category, file_path, telegram_file_id, updated_at)"
        " SELECT category, file_path, telegram_file_id, updated_at FROM images"
        " WHERE profession IS NULL ORDER BY times_used DESC"
    )
    op.drop_index("ix_images_category_profession", table_name="images")
    op.drop_table("images")
