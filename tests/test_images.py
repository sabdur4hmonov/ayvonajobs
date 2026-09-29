"""processing/images.py: folder fallback, placeholders, rotation stored in the DB, file_id cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.db.models import Image
from ayvona.db.repositories import images_repo
from ayvona.processing.images import ImagePicker

T0 = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def put(root: Path, rel: str, content: bytes = b"img") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


async def names(
    picker: ImagePicker, session: AsyncSession, n: int, cat: str, prof: str | None
) -> list[str]:
    out = []
    for i in range(n):
        picked = await picker.pick(session, cat, prof, now=T0 + timedelta(minutes=i))
        assert picked is not None
        out.append(picked.path.relative_to(picker.root).as_posix())
    await session.commit()
    return out


def test_folder_order_profession_category_fallback(tmp_path: Path) -> None:
    picker = ImagePicker(tmp_path)
    put(tmp_path, "boshqa/1.jpg")
    assert [p.name for p, _, _ in picker.candidates("tibbiyot", "shifokor")] == ["1.jpg"]
    put(tmp_path, "tibbiyot/1.jpg")
    assert picker.candidates("tibbiyot", "shifokor")[0][1:] == ("tibbiyot", None)
    put(tmp_path, "tibbiyot/shifokor/a.png")
    put(tmp_path, "tibbiyot/shifokor/notes.txt")  # not a picture
    assert [p.name for p, _, _ in picker.candidates("tibbiyot", "shifokor")] == ["a.png"]
    assert picker.candidates("tibbiyot", "shifokor")[0][1:] == ("tibbiyot", "shifokor")
    assert picker.candidates(None, None)[0][1] == "boshqa"


def test_real_pictures_win_over_placeholders(tmp_path: Path) -> None:
    picker = ImagePicker(tmp_path)
    put(tmp_path, "tibbiyot/shifokor/placeholder_1.jpg")
    put(tmp_path, "boshqa/placeholder_1.jpg")
    assert picker.candidates("tibbiyot", "shifokor")[0][0].name == "placeholder_1.jpg"
    assert picker.candidates("tibbiyot", "shifokor")[0][2] == "shifokor"
    put(tmp_path, "tibbiyot/real.jpg")  # a real category picture beats profession placeholders
    got = picker.candidates("tibbiyot", "shifokor")
    assert [(p.name, prof) for p, _, prof in got] == [("real.jpg", None)]
    assert picker.candidates("it", None) == [
        (tmp_path / "boshqa/placeholder_1.jpg", "boshqa", None)
    ]
    assert ImagePicker(tmp_path / "missing").candidates("it", None) == []


async def test_rotation_survives_restart(
    tmp_path: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for n in (1, 2, 3):
        put(tmp_path, f"sotuv/sotuvchi/{n}.jpg", bytes([n]))
    async with session_factory() as s:
        got = await names(ImagePicker(tmp_path), s, 4, "sotuv", "sotuvchi")
    assert got == [
        "sotuv/sotuvchi/1.jpg",
        "sotuv/sotuvchi/2.jpg",
        "sotuv/sotuvchi/3.jpg",
        "sotuv/sotuvchi/1.jpg",
    ]
    # "restart": a new picker and a new session continue where the counters stopped
    async with session_factory() as s:
        picker = ImagePicker(tmp_path)
        picked = await picker.pick(s, "sotuv", "sotuvchi", now=T0 + timedelta(hours=1))
        assert picked is not None and picked.path.name == "2.jpg"
        await s.commit()
        rows = (await s.scalars(select(Image).order_by(Image.file_path))).all()
        assert [r.times_used for r in rows] == [2, 2, 1]


async def test_new_file_is_used_without_restart(
    tmp_path: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    put(tmp_path, "it/1.jpg")
    picker = ImagePicker(tmp_path)
    async with session_factory() as s:
        await names(picker, s, 2, "it", None)
        put(tmp_path, "it/2.jpg")
        picked = await picker.pick(s, "it", None, now=T0 + timedelta(hours=1))
        assert picked is not None and picked.path.name == "2.jpg"  # never used -> first


async def test_file_id_cache_is_reset_when_the_file_changes(
    tmp_path: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    path = put(tmp_path, "boshqa/1.jpg", b"old")
    picker = ImagePicker(tmp_path)
    async with session_factory() as s:
        first = await picker.pick(s, "boshqa", None, now=T0)
        assert first is not None and first.telegram_file_id is None
        await images_repo.set_telegram_file_id(s, first.id, "FILE_ID_1", first.file_hash)
        await s.commit()
    async with session_factory() as s:
        again = await picker.pick(s, "boshqa", None, now=T0 + timedelta(minutes=1))
        assert again is not None and again.telegram_file_id == "FILE_ID_1"
        await s.commit()
    path.write_bytes(b"new picture")
    async with session_factory() as s:
        changed = await picker.pick(s, "boshqa", None, now=T0 + timedelta(minutes=2))
        assert changed is not None and changed.telegram_file_id is None
        # a late upload result of the OLD file must not be cached for the new one
        await images_repo.set_telegram_file_id(s, changed.id, "STALE", first.file_hash)
        await s.commit()
        row = await s.get(Image, changed.id)
        assert row is not None and row.telegram_file_id is None


async def test_no_pictures_at_all(
    tmp_path: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        assert await ImagePicker(tmp_path).pick(s, "it", "dasturchi") is None
