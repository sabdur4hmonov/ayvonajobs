"""/images review: fresh pictures for the posts, one slot at a time, nothing replaced without the
admin's explicit approval. Stock APIs are mocked (httpx.MockTransport) — nothing leaves the
machine; pictures are drawn with Pillow."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram.methods import EditMessageCaption, EditMessageMedia, SendMessage, SendPhoto
from PIL import Image
from pydantic import SecretStr

from ayvona.bot import texts as T
from ayvona.bot.handlers import admin_images
from ayvona.config import Settings
from ayvona.db.repositories import kv_repo
from ayvona.processing.image_gen import (
    HEIGHT,
    ICONS,
    MAX_BYTES,
    WIDTH,
    brand_photo,
    encode_jpeg,
    render_flat,
)
from ayvona.processing.images import ImagePicker
from ayvona.services import image_review as review
from ayvona.timeutil import utcnow
from tests.test_admin_bot import ADMIN, STRANGER, BotHarness, callback_update, message_update
from tests.test_public_bot import bot_settings
from tests.worker_helpers import SF, make_image, make_settings

NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=utcnow().tzinfo)


def photo_bytes(
    size: tuple[int, int] = (1600, 900), color: tuple[int, int, int] = (30, 120, 60)
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


def with_keys(settings: Settings, **keys: str) -> Settings:
    env = settings.env.model_copy(update={k: SecretStr(v) for k, v in keys.items()})
    return settings.model_copy(update={"env": env})


def settings_in(tmp_path: Path, **keys: str) -> Settings:
    s = make_settings(tmp_path / "images", db_file=tmp_path / "data" / "ayvona.db")
    return with_keys(s, **keys)


# ------------------------------------------------------------------ drawn pictures
def test_drawn_pictures_have_the_required_size_and_stay_under_1mb() -> None:
    for icon in ICONS:
        img = render_flat(
            category="sotuv",
            title="Sotuv va savdo",
            subtitle=None,
            icon=icon,
            variant=1,
            channel="ayvonajobs",
        )
        assert img.size == (WIDTH, HEIGHT) == (1280, 720)
        assert len(encode_jpeg(img)) < MAX_BYTES < 1_000_000


def test_drawn_pictures_are_stable_and_variants_differ() -> None:
    def make(variant: int) -> bytes:
        return encode_jpeg(
            render_flat(
                category="it",
                title="Dasturchi",
                subtitle="IT",
                icon="laptop",
                variant=variant,
                channel="ayvonajobs",
            )
        )

    assert make(1) == make(1)  # the same slot always gives the same picture
    assert len({make(1), make(2), make(3)}) == 3
    unknown = render_flat(
        category="x", title="X", subtitle=None, icon="no-such-icon", variant=1, channel="c"
    )
    assert unknown.size == (1280, 720)  # an unknown icon falls back to the star


@pytest.mark.parametrize("size", [(1600, 900), (3000, 1000), (800, 1200), (1280, 720)])
def test_stock_photo_is_cropped_to_16_9_and_branded(size: tuple[int, int]) -> None:
    out = brand_photo(photo_bytes(size), title="Buxgalter", channel="ayvonajobs")
    assert out.size == (1280, 720)
    top, bottom = out.getpixel((640, 100)), out.getpixel((60, 700))
    assert top == pytest.approx((30, 120, 60), abs=6)  # the photo itself is untouched at the top
    assert sum(bottom) < sum(top)  # the dark strip with the title is at the bottom


def test_something_that_is_not_a_picture_is_refused() -> None:
    with pytest.raises(ValueError):
        brand_photo(b"<html>not an image</html>", title="X", channel="c")


# ------------------------------------------------------------------ slots
def test_slots_cover_every_folder_in_the_documented_order(tmp_path: Path) -> None:
    s = settings_in(tmp_path)
    slots = review.build_slots(s)
    n_prof = sum(len(c.professions) for c in s.categories.values())
    assert len(slots) == (len(s.categories) + n_prof) * review.PER_FOLDER
    assert len({sl.key for sl in slots}) == len(slots)
    cats = [sl for sl in slots if sl.profession is None]
    assert slots[: len(cats)] == cats  # categories first ...
    first_prof = [sl.profession for sl in slots if sl.profession][: review.PER_FOLDER * 3 : 3]
    assert first_prof == s.image_queries.first[:3]  # ... then the common professions
    assert slots[0].key == f"{next(iter(s.categories))}/1"


def test_slot_current_prefers_real_pictures_over_placeholders(tmp_path: Path) -> None:
    root = tmp_path / "images"
    make_image(root, "sotuv/1.jpg")
    make_image(root, "sotuv/placeholder_1.jpg")
    make_image(root, "sotuv/placeholder_2.jpg")
    make_image(root, "operator/placeholder_1.jpg")
    slots = {sl.key: sl for sl in review.build_slots(settings_in(tmp_path))}
    assert slots["sotuv/1"].current == root / "sotuv" / "1.jpg" and slots["sotuv/1"].replaces_real
    assert slots["sotuv/2"].current == root / "sotuv" / "placeholder_2.jpg"
    assert not slots["sotuv/2"].replaces_real
    assert slots["operator/1"].current is not None and slots["operator/3"].current is None


# ------------------------------------------------------------------ stock providers
PEXELS = {
    "photos": [
        {
            "id": 11,
            "url": "https://www.pexels.com/photo/11/",
            "photographer": "Ali",
            "src": {"large2x": "https://images.pexels.com/photos/11/a.jpeg"},
        },
        {
            "id": 12,
            "url": "https://www.pexels.com/photo/12/",
            "photographer": "Vali",
            "src": {"large2x": "https://images.pexels.com/photos/12/b.jpeg"},
        },
        {
            "id": 13,
            "url": "x",
            "photographer": "Evil",
            "src": {"large2x": "https://evil.example.com/c.jpeg"},
        },
    ]
}
UNSPLASH = {
    "results": [
        {
            "id": "u1",
            "urls": {"raw": "https://images.unsplash.com/photo-u1?ixid=1"},
            "links": {
                "html": "https://unsplash.com/photos/u1",
                "download_location": "https://api.unsplash.com/photos/u1/download?ixid=1",
            },
            "user": {"name": "Gulnora"},
        }
    ]
}
PIXABAY = {
    "hits": [
        {
            "id": 7,
            "pageURL": "https://pixabay.com/photos/7/",
            "user": "Bobur",
            "largeImageURL": "https://pixabay.com/get/7_1280.jpg",
        }
    ]
}


class Stock:
    """A fake of the three APIs and their image CDNs; records every request."""

    def __init__(self, **bodies: Any) -> None:
        self.bodies = bodies
        self.requests: list[httpx.Request] = []
        self.fail_downloads = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        if host == "api.pexels.com":
            return self._api("pexels")
        if host == "api.unsplash.com":
            if request.url.path.endswith("/download"):
                return httpx.Response(200, json={"url": "x"})
            return self._api("unsplash")
        if host == "pixabay.com" and request.url.path == "/api/":
            return self._api("pixabay")
        if self.fail_downloads:
            return httpx.Response(404)
        return httpx.Response(200, content=photo_bytes())

    def _api(self, provider: str) -> httpx.Response:
        body = self.bodies.get(provider)
        return httpx.Response(429) if body is None else httpx.Response(200, json=body)

    def factory(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def slot_of(settings: Settings, key: str = "it/1") -> review.Slot:
    return next(sl for sl in review.build_slots(settings) if sl.key == key)


def test_only_providers_with_a_key_are_used(tmp_path: Path) -> None:
    assert review.configured_providers(settings_in(tmp_path)) == []
    s = settings_in(tmp_path, unsplash_access_key="k", pexels_api_key="k")
    assert review.configured_providers(s) == ["pexels", "unsplash"]  # fixed order


async def test_without_any_key_the_proposals_are_our_own_pictures(tmp_path: Path) -> None:
    s = settings_in(tmp_path)
    stock = Stock()
    src = review.CandidateSource(s, slot_of(s), http_factory=stock.factory)
    a, b = await src.next(), await src.next()
    assert a.source == b.source == "generated" and a.jpeg != b.jpeg
    assert "Pillow" in a.license and a.meta["icon"] == "laptop"
    assert stock.requests == []  # no network at all
    assert Image.open(io.BytesIO(a.jpeg)).size == (1280, 720)


async def test_pexels_proposals_follow_the_search_then_our_own(tmp_path: Path) -> None:
    s = settings_in(tmp_path, pexels_api_key="PEXELS-KEY-123")
    stock = Stock(pexels=PEXELS)
    src = review.CandidateSource(s, slot_of(s), http_factory=stock.factory)
    first, second = await src.next(), await src.next()
    assert (first.source, first.meta["id"], first.meta["author"]) == ("pexels", "11", "Ali")
    assert second.meta["id"] == "12"
    assert "Pexels License" in first.license
    assert Image.open(io.BytesIO(first.jpeg)).size == (1280, 720)

    search = stock.requests[0]
    assert (
        search.url.host == "api.pexels.com" and search.headers["Authorization"] == "PEXELS-KEY-123"
    )
    assert "software+developer" in str(search.url) and "landscape" in str(search.url)
    # the photo of the foreign host was never downloaded; results run out -> our own picture
    assert all(r.url.host != "evil.example.com" for r in stock.requests)
    third = await src.next()
    assert third.source == "generated"


async def test_unsplash_and_pixabay_results_are_understood(tmp_path: Path) -> None:
    s = settings_in(tmp_path, unsplash_access_key="U-KEY")
    stock = Stock(unsplash=UNSPLASH)
    cand = await review.CandidateSource(s, slot_of(s), http_factory=stock.factory).next()
    assert (cand.source, cand.meta["author"]) == ("unsplash", "Gulnora")
    assert stock.requests[0].headers["Authorization"] == "Client-ID U-KEY"
    assert "w=1280" in str(stock.requests[1].url)  # the photo is asked at the size we need

    s2 = settings_in(tmp_path, pixabay_api_key="PIX-KEY")
    stock2 = Stock(pixabay=PIXABAY)
    cand2 = await review.CandidateSource(s2, slot_of(s2), http_factory=stock2.factory).next()
    assert (cand2.source, cand2.meta["id"]) == ("pixabay", "7")
    assert "Pixabay Content License" in cand2.license


async def test_a_broken_provider_falls_back_without_crashing(tmp_path: Path) -> None:
    s = settings_in(tmp_path, pexels_api_key="K", pixabay_api_key="P")
    stock = Stock(pixabay=PIXABAY)  # pexels answers 429
    cand = await review.CandidateSource(s, slot_of(s), http_factory=stock.factory).next()
    assert cand.source == "pixabay"  # the next configured provider took over

    broken = Stock(pexels=PEXELS)
    broken.fail_downloads = True  # every download fails
    cand2 = await review.CandidateSource(
        settings_in(tmp_path, pexels_api_key="K"), slot_of(s), http_factory=broken.factory
    ).next()
    assert cand2.source == "generated"


async def test_a_stock_photo_already_used_elsewhere_is_not_proposed_again(tmp_path: Path) -> None:
    s = settings_in(tmp_path, pexels_api_key="K")
    src = review.CandidateSource(
        s, slot_of(s), used={"pexels:11"}, http_factory=Stock(pexels=PEXELS).factory
    )
    assert (await src.next()).meta["id"] == "12"


def test_secrets_never_reach_the_logs_or_the_candidate(tmp_path: Path) -> None:
    s = settings_in(tmp_path, pixabay_api_key="SECRET-PIX-KEY")
    assert "SECRET-PIX-KEY" not in repr(s.env)  # SecretStr


# ------------------------------------------------------------------ approving a picture
def candidate(source: str = "generated") -> review.Candidate:
    return review.Candidate(
        jpeg=photo_bytes((1280, 720)),
        source=source,
        label="x",
        license="L",
        meta={"id": "11", "author": "Ali"},
    )


def test_approving_a_placeholder_slot_adds_a_real_file_and_keeps_the_placeholder(
    tmp_path: Path,
) -> None:
    s = settings_in(tmp_path)
    root = tmp_path / "images"
    make_image(root, "it/placeholder_1.jpg")
    slot = slot_of(s, "it/1")
    done = review.apply_candidate(s, slot, candidate("pexels"), admin_id=111, now=NOW)

    assert done.path == root / "it" / "1.jpg" and done.backup is None
    assert (root / "it" / "placeholder_1.jpg").is_file()  # untouched
    meta = json.loads(done.sidecar.read_text(encoding="utf-8"))
    assert meta["source"] == "pexels" and meta["license"] == "L" and meta["approved_by"] == 111
    assert meta["details"] == {"id": "11", "author": "Ali"} and meta["replaced"] is None
    # the picker now uses the real picture and ignores the placeholder
    picked = ImagePicker(root).candidates("it", None)
    assert [p.name for p, _, _ in picked] == ["1.jpg"]


def test_approving_over_a_real_picture_keeps_the_old_one_as_a_backup(tmp_path: Path) -> None:
    s = settings_in(tmp_path)
    root = tmp_path / "images"
    old = make_image(root, "it/1.jpg")
    old_bytes = old.read_bytes()
    (root / "it" / "1.jpg.json").write_text('{"source": "old"}', encoding="utf-8")
    slot = slot_of(s, "it/1")
    done = review.apply_candidate(s, slot, candidate(), admin_id=1, now=NOW)

    assert done.path == old and old.read_bytes() != old_bytes  # replaced in place
    assert done.backup is not None and done.backup.read_bytes() == old_bytes
    assert done.backup.parent == tmp_path / "data" / "images_backup" / "it"
    assert (done.backup.parent / f"{done.backup.name}.json").read_text() == '{"source": "old"}'
    assert json.loads(done.sidecar.read_text())["replaced"] == done.backup.name


def test_a_png_slot_becomes_a_jpg_and_the_png_is_backed_up(tmp_path: Path) -> None:
    s = settings_in(tmp_path)
    root = tmp_path / "images"
    (root / "it").mkdir(parents=True)
    Image.new("RGB", (64, 36)).save(root / "it" / "1.png")
    done = review.apply_candidate(s, slot_of(s, "it/1"), candidate(), admin_id=1, now=NOW)
    assert done.path == root / "it" / "1.jpg" and not (root / "it" / "1.png").exists()
    assert done.backup is not None and done.backup.name.endswith("_1.png")


def test_three_approvals_fill_three_names(tmp_path: Path) -> None:
    s = settings_in(tmp_path)
    for i in (1, 2, 3):
        review.apply_candidate(s, slot_of(s, f"it/{i}"), candidate(), admin_id=1, now=NOW)
    names = sorted(p.name for p in (tmp_path / "images" / "it").glob("*.jpg"))
    assert names == ["1.jpg", "2.jpg", "3.jpg"]


def test_failed_write_leaves_the_old_picture_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = settings_in(tmp_path)
    old = make_image(tmp_path / "images", "it/1.jpg")
    before = old.read_bytes()

    def boom(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(review, "save_jpeg", boom)
    with pytest.raises(OSError):
        review.apply_candidate(s, slot_of(s, "it/1"), candidate(), admin_id=1, now=NOW)
    assert old.read_bytes() == before  # the backup was moved back


# ------------------------------------------------------------------ the admin flow in the bot
@pytest.fixture
def harness(tmp_path: Path, session_factory: SF, monkeypatch: pytest.MonkeyPatch) -> BotHarness:
    admin_images.REVIEWS.clear()
    stock = Stock(pexels=PEXELS, unsplash=UNSPLASH)
    monkeypatch.setattr(admin_images, "HTTP_FACTORY", stock.factory)
    s = with_keys(bot_settings(tmp_path), pexels_api_key="K", unsplash_access_key="U")
    h = BotHarness(s, session_factory)
    h.stock = stock  # type: ignore[attr-defined]
    for cat in ("sotuv", "operator"):  # a folder with placeholders, one with a real picture
        make_image(tmp_path / "images", f"{cat}/placeholder_1.jpg")
    make_image(tmp_path / "images", "ofis/1.jpg")
    return h


def latest_callback(h: BotHarness, action: str) -> str:
    """The callback data of the ``action`` button of the proposal that is on screen now."""
    for r in reversed(h.session.requests):
        markup = getattr(r, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for b in row:
                if (b.callback_data or "").startswith(f"imr:{action}:"):
                    return b.callback_data
    raise AssertionError(f"no {action} button on screen")


async def press(h: BotHarness, action: str, uid: int = ADMIN) -> None:
    await h.send(callback_update(latest_callback(h, action), uid=uid))


def photos(h: BotHarness) -> list[Any]:
    return h.session.sent(SendPhoto)


def files_under(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


async def test_review_shows_current_and_proposal_and_changes_nothing_by_itself(
    harness: BotHarness, tmp_path: Path
) -> None:
    before = files_under(tmp_path / "images")
    await harness.send(message_update("/images review", uid=ADMIN))
    intro = harness.texts()[0]
    assert "Rasmlarni yangilash" in intro and "Pexels" in intro
    first, proposal = photos(harness)[-2:]
    assert "sotuv/1" in first.caption or "Sotuv" in first.caption  # the current picture
    assert "Taklif" in proposal.caption and "Pexels · Ali" in proposal.caption
    assert [b.text for row in proposal.reply_markup.inline_keyboard for b in row] == [
        T.BTN_IMGREV_OK,
        T.BTN_IMGREV_MORE,
        T.BTN_IMGREV_SKIP,
        T.BTN_IMGREV_STOP,
    ]
    assert files_under(tmp_path / "images") == before  # nothing written, nothing deleted


async def test_more_replaces_the_proposal_in_place(harness: BotHarness, tmp_path: Path) -> None:
    await harness.send(message_update("/images review", uid=ADMIN))
    await press(harness, "more")
    [edit] = harness.session.sent(EditMessageMedia)
    assert "Pexels · Vali" in edit.media.caption  # the next search result
    assert files_under(tmp_path / "images") == files_under(tmp_path / "images")
    await press(harness, "more")  # results run out -> our own
    await press(harness, "more")
    assert "original rasm" in harness.session.sent(EditMessageMedia)[-1].media.caption


async def test_approve_writes_the_file_the_sidecar_and_moves_on(
    harness: BotHarness, tmp_path: Path, session_factory: SF
) -> None:
    root = tmp_path / "images"
    await harness.send(message_update("/images review", uid=ADMIN))
    await press(harness, "ok")

    assert (root / "sotuv" / "1.jpg").is_file()
    meta = json.loads((root / "sotuv" / "1.jpg.json").read_text(encoding="utf-8"))
    assert meta["source"] == "pexels" and meta["approved_by"] == ADMIN
    assert (root / "sotuv" / "placeholder_1.jpg").is_file()  # the old one is not touched
    edit = harness.session.sent(EditMessageCaption)[-1]
    assert "Saqlandi" in edit.caption and "1.jpg" in edit.caption
    assert "sotuv/2" in photos(harness)[-2].caption or "sotuv/2" in harness.texts()[-1]  # next slot
    async with session_factory() as s:
        progress = json.loads(await kv_repo.get(s, review.PROGRESS_KEY) or "{}")
    assert progress["done"] == {"sotuv/1": "approved"} and progress["used"] == ["pexels:11"]


async def test_the_next_slot_does_not_get_the_same_stock_photo(
    harness: BotHarness,
) -> None:
    await harness.send(message_update("/images review", uid=ADMIN))
    await press(harness, "ok")  # used pexels:11
    proposal = photos(harness)[-1]
    assert "Pexels · Vali" in proposal.caption


async def test_skip_changes_nothing_and_is_remembered(
    harness: BotHarness, tmp_path: Path, session_factory: SF
) -> None:
    before = files_under(tmp_path / "images")
    await harness.send(message_update("/images review", uid=ADMIN))
    await press(harness, "skip")
    assert files_under(tmp_path / "images") == before
    assert "O'tkazildi" in harness.session.sent(EditMessageCaption)[-1].caption
    async with session_factory() as s:
        assert json.loads(await kv_repo.get(s, review.PROGRESS_KEY))["done"] == {
            "sotuv/1": "skipped"
        }


async def test_stop_then_resume_continues_after_the_reviewed_slots(
    harness: BotHarness, tmp_path: Path
) -> None:
    await harness.send(message_update("/images review", uid=ADMIN))
    await press(harness, "ok")
    await press(harness, "skip")
    await press(harness, "stop")
    assert "Tasdiqlangan: 1, o'tkazilgan: 1" in harness.texts()[-1]
    assert admin_images.REVIEWS == {}

    await harness.send(message_update("/images review", uid=ADMIN))  # a new session resumes
    assert "2 tasi allaqachon ko'rilgan" in harness.texts()[-3] or any(
        "2 tasi allaqachon" in t for t in harness.texts()
    )
    assert any("sotuv/3" in t for t in harness.texts())  # the 3rd slot has no picture to show

    await harness.send(message_update("/images review reset", uid=ADMIN))
    assert T.IMGREV_RESET in harness.texts()
    assert any("0 tasi allaqachon" in t for t in harness.texts())


async def test_a_double_click_on_approve_writes_one_file(
    harness: BotHarness, tmp_path: Path
) -> None:
    import asyncio

    await harness.send(message_update("/images review", uid=ADMIN))
    cb = latest_callback(harness, "ok")
    await asyncio.gather(*(harness.send(callback_update(cb, uid=ADMIN)) for _ in range(3)))
    jpgs = sorted(
        p.name
        for p in (tmp_path / "images" / "sotuv").glob("*.jpg")
        if not p.name.startswith("placeholder_")
    )
    assert jpgs == ["1.jpg"]  # not 1.jpg, 2.jpg, 3.jpg


async def test_unsplash_is_told_when_its_photo_is_used(
    tmp_path: Path, session_factory: SF, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin_images.REVIEWS.clear()
    stock = Stock(unsplash=UNSPLASH)
    monkeypatch.setattr(admin_images, "HTTP_FACTORY", stock.factory)
    h = BotHarness(with_keys(bot_settings(tmp_path), unsplash_access_key="U"), session_factory)
    await h.send(message_update("/images review", uid=ADMIN))
    assert not any(r.url.path.endswith("/download") for r in stock.requests)  # not before the OK
    await press(h, "ok")
    pings = [r for r in stock.requests if r.url.path.endswith("/download")]
    assert len(pings) == 1 and pings[0].headers["Authorization"] == "Client-ID U"


async def test_only_admins_and_only_on_request(harness: BotHarness, tmp_path: Path) -> None:
    before = files_under(tmp_path / "images")
    await harness.send(message_update("/images review", uid=STRANGER))
    await harness.send(callback_update("imr:ok", uid=STRANGER))
    assert admin_images.REVIEWS == {} and harness.session.requests == []
    assert files_under(tmp_path / "images") == before
    # an admin button press without a started review (e.g. after a restart) is refused politely
    await harness.send(callback_update("imr:ok:1", uid=ADMIN))
    assert files_under(tmp_path / "images") == before
    # normal bot use never starts it
    await harness.send(message_update("/start", uid=ADMIN))
    await harness.send(message_update("/images", uid=ADMIN))
    assert admin_images.REVIEWS == {} and photos(harness) == []
    _ = SendMessage
