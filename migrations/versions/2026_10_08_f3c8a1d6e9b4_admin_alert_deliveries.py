"""admin_alert_deliveries (the admin's unfiltered alerts: one row per admin and collected post)

Revision ID: f3c8a1d6e9b4
Revises: e2a6c9d4b8f1
Create Date: 2026-10-08 10:00:00.000000

Additive: one NEW table, no existing table or row is touched. ``alert_deliveries`` is keyed by
``jobs.id`` (NOT NULL), so it cannot record a post that never became a job — hence a separate
table keyed by ``raw_posts.id``. Downgrade drops only this table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c8a1d6e9b4"
down_revision: str | Sequence[str] | None = "e2a6c9d4b8f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "admin_alert_deliveries",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("raw_post_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "sent",
                "digest",
                "digest_sent",
                "failed",
                name="adminalertstatus",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            server_default="sent",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["raw_post_id"],
            ["raw_posts.id"],
            name=op.f("fk_admin_alert_deliveries_raw_post_id_raw_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_admin_alert_deliveries_subscription_id_subscriptions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", "raw_post_id", name=op.f("pk_admin_alert_deliveries")),
    )
    with op.batch_alter_table("admin_alert_deliveries", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_admin_alert_deliveries_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_admin_alert_deliveries_raw_post_id"), ["raw_post_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("admin_alert_deliveries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_admin_alert_deliveries_raw_post_id"))
        batch_op.drop_index(batch_op.f("ix_admin_alert_deliveries_created_at"))
    op.drop_table("admin_alert_deliveries")
