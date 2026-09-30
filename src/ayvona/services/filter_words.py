"""Admin's own filter words (``filter_words``), on top of config/filters.yaml: /addword /delword
/words. Used by the job form checks (services/job_submission.filter_words)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.db.models import FilterKind, FilterWord
from ayvona.timeutil import utcnow

MAX_WORD = 100


def clean_word(word: str) -> str:
    return " ".join(word.strip().lower().split())[:MAX_WORD]


async def add_word(session: AsyncSession, word: str, kind: FilterKind, admin_id: int) -> bool:
    """False if it was already there. Does not commit."""
    word = clean_word(word)
    if not word:
        return False
    result = await session.execute(
        sqlite_insert(FilterWord)
        .values(word=word, kind=kind, added_by=admin_id, created_at=utcnow())
        .on_conflict_do_nothing()
    )
    return (result.rowcount or 0) == 1


async def delete_word(session: AsyncSession, word: str) -> int:
    """Removes the word from every kind. Does not commit."""
    result = await session.execute(delete(FilterWord).where(FilterWord.word == clean_word(word)))
    return result.rowcount or 0


async def list_words(session: AsyncSession) -> list[FilterWord]:
    rows = await session.scalars(select(FilterWord).order_by(FilterWord.kind, FilterWord.word))
    return list(rows.all())
