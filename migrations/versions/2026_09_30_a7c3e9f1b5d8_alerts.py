"""subscriptions.profession + alert_deliveries.status (Bosqich 13: job alerts)

Revision ID: a7c3e9f1b5d8
Revises: f2b6d8a4c1e3
Create Date: 2026-09-30 23:30:00.000000

* ``subscriptions.profession`` — the alert wizard has the same steps as the search
  (category → profession → region → salary [+ keyword]);
* ``alert_deliveries.status`` — ``sent`` (a message went out), ``digest`` (over the daily limit:
  waits for the evening digest), ``digest_sent``. Existing rows (none yet) are ``sent``.

Plain ``ADD COLUMN`` (no batch rebuild).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b5d8"
down_revision: str | Sequence[str] | None = "f2b6d8a4c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("subscriptions", sa.Column("profession", sa.String(length=64), nullable=True))
    op.add_column(
        "alert_deliveries",
        sa.Column("status", sa.String(length=16), server_default="sent", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    op.drop_column("alert_deliveries", "status")
    op.drop_column("subscriptions", "profession")
