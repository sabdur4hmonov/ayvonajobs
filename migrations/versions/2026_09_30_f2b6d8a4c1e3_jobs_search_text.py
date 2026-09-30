"""jobs.search_text + jobs_fts rebuilt over it (Bosqich 12: keyword search)

Revision ID: f2b6d8a4c1e3
Revises: e5a9c2f7b3d1
Create Date: 2026-09-30 23:00:00.000000

The first jobs_fts indexed title/company/description/city as written, so a Cyrillic query never
found a Latin post ("сотувчи" vs "sotuvchi", PROGRESS Bosqich 2 §9). Now the app writes one
folded column (lowercase, Cyrillic -> Latin, no apostrophes) and FTS5 indexes only that; queries
are folded the same way.

Existing rows get ``search_text`` from the worker / bot on their next start
(services/search.fill_search_text) — this migration does not import app code, so it never
changes. Until then those rows are simply not found by keyword (filters still work).

Plain ``ADD COLUMN`` (no batch rebuild of ``jobs``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b6d8a4c1e3"
down_revision: str | Sequence[str] | None = "e5a9c2f7b3d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DROP_FTS = (
    "DROP TRIGGER IF EXISTS jobs_fts_au",
    "DROP TRIGGER IF EXISTS jobs_fts_ad",
    "DROP TRIGGER IF EXISTS jobs_fts_ai",
    "DROP TABLE IF EXISTS jobs_fts",
)

NEW_FTS = (
    """
    CREATE VIRTUAL TABLE jobs_fts USING fts5(
        search_text,
        content='jobs', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER jobs_fts_ai AFTER INSERT ON jobs BEGIN
        INSERT INTO jobs_fts(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
    """
    CREATE TRIGGER jobs_fts_ad AFTER DELETE ON jobs BEGIN
        INSERT INTO jobs_fts(jobs_fts, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
    END
    """,
    """
    CREATE TRIGGER jobs_fts_au AFTER UPDATE OF search_text ON jobs BEGIN
        INSERT INTO jobs_fts(jobs_fts, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
        INSERT INTO jobs_fts(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
    "INSERT INTO jobs_fts(jobs_fts) VALUES ('rebuild')",
)

# The initial migration's FTS table, for downgrade.
OLD_FTS = (
    """
    CREATE VIRTUAL TABLE jobs_fts USING fts5(
        title, company, description, city,
        content='jobs', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER jobs_fts_ai AFTER INSERT ON jobs BEGIN
        INSERT INTO jobs_fts(rowid, title, company, description, city)
        VALUES (new.id, new.title, new.company, new.description, new.city);
    END
    """,
    """
    CREATE TRIGGER jobs_fts_ad AFTER DELETE ON jobs BEGIN
        INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description, city)
        VALUES ('delete', old.id, old.title, old.company, old.description, old.city);
    END
    """,
    """
    CREATE TRIGGER jobs_fts_au AFTER UPDATE OF title, company, description, city ON jobs BEGIN
        INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description, city)
        VALUES ('delete', old.id, old.title, old.company, old.description, old.city);
        INSERT INTO jobs_fts(rowid, title, company, description, city)
        VALUES (new.id, new.title, new.company, new.description, new.city);
    END
    """,
    "INSERT INTO jobs_fts(jobs_fts) VALUES ('rebuild')",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("jobs", sa.Column("search_text", sa.Text(), nullable=True))
    for sql in (*DROP_FTS, *NEW_FTS):
        op.execute(sql)


def downgrade() -> None:
    """Downgrade schema (SQLite >= 3.35 drops columns in place)."""
    for sql in DROP_FTS:
        op.execute(sql)
    op.drop_column("jobs", "search_text")
    for sql in OLD_FTS:
        op.execute(sql)
