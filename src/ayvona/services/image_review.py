"""Fresh pictures for the channel posts: the logic behind the admin's ``/images review``.

The admin goes through the picture slots ONE BY ONE (bot/handlers/admin_images.py). For each slot
we show the current picture and propose a new one; nothing changes until the admin presses
"Tasdiqlash". Where the proposals come from, in this order:

1. free-licence stock photos (Pexels, Unsplash, Pixabay) — only for a provider whose API key is in
   ``.env`` (``PEXELS_API_KEY`` / ``UNSPLASH_ACCESS_KEY`` / ``PIXABAY_API_KEY``), searched with the
   English words of ``config/image_queries.yaml``, cropped to 1280 x 720 and branded;
2. otherwise (or when the results run out) an original flat picture we draw ourselves (Pillow).

NEVER: scraping, Google Images, hot-linking. Only the official APIs, and only on hosts of the
provider's own image CDN. Every approved picture gets a ``<name>.json`` next to it with its source
and licence; the picture it replaces is moved to ``data/images_backup/`` first (a placeholder it
only sits next to is kept as it is — real pictures win over placeholders by themselves).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import Settings
from ayvona.db.repositories import kv_repo
from ayvona.processing.image_gen import (
    brand_photo,
    encode_jpeg,
    render_flat,
    save_jpeg,
)
from ayvona.processing.images import IMAGE_EXTENSIONS, is_placeholder, list_images

PER_FOLDER = 3  # docs/IMAGES.md: 3 variants per folder, used in turn
PROGRESS_KEY = "images:review"
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
MAX_PAGES = 3  # result pages asked per provider and slot
PER_PAGE = 15

PROVIDERS = ("pexels", "unsplash", "pixabay")
LICENSES = {
    "pexels": "Pexels License (free to use, no permission needed; credit appreciated)",
    "unsplash": "Unsplash License (free to use; credit appreciated)",
    "pixabay": "Pixabay Content License (free to use, credit not required)",
    "generated": "Original artwork drawn by Ayvona Jobs with Pillow; no third-party material",
}
# the only hosts a photo may be downloaded from, per provider (their own image CDN)
CDN_HOSTS = {
    "pexels": ("images.pexels.com",),
    "unsplash": ("images.unsplash.com",),
    "pixabay": ("pixabay.com", "cdn.pixabay.com"),
}


# --------------------------------------------------------------------------- slots
@dataclass(frozen=True, slots=True)
class Slot:
    """Picture number ``index`` (1..3) of a folder: a category or a profession of it."""

    category: str
    profession: str | None
    index: int
    title: str  # Uzbek, shown on the picture and to the admin
    category_title: str
    current: Path | None  # the file shown as "hozirgi" (a real picture, else a placeholder)

    @property
    def key(self) -> str:
        base = f"{self.category}/{self.profession}" if self.profession else self.category
        return f"{base}/{self.index}"

    @property
    def folder_rel(self) -> str:
        return f"{self.category}/{self.profession}" if self.profession else self.category

    @property
    def replaces_real(self) -> bool:
        return self.current is not None and not is_placeholder(self.current)


def _slots_of(
    settings: Settings, category: str, profession: str | None, title: str, cat_title: str
) -> list[Slot]:
    root = settings.images_dir
    folder = root / category / profession if profession else root / category
    files = list_images(folder)
    real = [f for f in files if not is_placeholder(f)]
    placeholders = [f for f in files if is_placeholder(f)]
    out = []
    for i in range(1, PER_FOLDER + 1):
        current = (
            real[i - 1]
            if len(real) >= i
            else (placeholders[i - 1] if len(placeholders) >= i else None)
        )
        out.append(Slot(category, profession, i, title, cat_title, current))
    return out


def build_slots(settings: Settings) -> list[Slot]:
    """Every picture slot, in the order of docs/IMAGES.md: the categories first (they make the
    system complete), then the common professions, then the rest."""
    cats = settings.categories
    slots: list[Slot] = []
    for cat_key, cat in cats.items():
        slots += _slots_of(settings, cat_key, None, cat.title, cat.title)
    owner = {p: (ck, c) for ck, c in cats.items() for p in c.professions}
    first = [p for p in settings.image_queries.first if p in owner]
    rest = [p for p in owner if p not in first]
    for prof in [*first, *rest]:
        cat_key, cat = owner[prof]
        slots += _slots_of(settings, cat_key, prof, cat.professions[prof].title, cat.title)
    return slots


def icon_of(settings: Settings, slot: Slot) -> str:
    iq = settings.image_queries
    if slot.profession and (p := iq.professions.get(slot.profession)) and p.icon:
        return p.icon
    return (
        iq.categories.get(slot.category).icon if slot.category in iq.categories else None
    ) or "star"


def query_of(settings: Settings, slot: Slot) -> str:
    iq = settings.image_queries
    if slot.profession:
        q = iq.professions.get(slot.profession)
        if q and q.query:
            return q.query
        return slot.profession.replace("_", " ")
    q = iq.categories.get(slot.category)
    return q.query if q and q.query else slot.category.replace("_", " ")


# --------------------------------------------------------------------------- progress (kv_store)
async def load_progress(session: AsyncSession) -> dict[str, Any]:
    raw = await kv_repo.get(session, PROGRESS_KEY)
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    data.setdefault("done", {})
    data.setdefault("used", [])
    return data


async def save_progress(session: AsyncSession, data: dict[str, Any]) -> None:
    """Does not commit."""
    await kv_repo.set_value(session, PROGRESS_KEY, json.dumps(data, ensure_ascii=False))


async def reset_progress(session: AsyncSession) -> None:
    await save_progress(session, {"done": {}, "used": []})


# --------------------------------------------------------------------------- stock photos
@dataclass(frozen=True, slots=True)
class StockPhoto:
    provider: str
    id: str
    download_url: str
    page_url: str
    author: str
    track_url: str | None = None  # Unsplash: must be pinged when a photo is used

    @property
    def uid(self) -> str:
        return f"{self.provider}:{self.id}"


HttpFactory = Callable[[], httpx.AsyncClient]


def default_http() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        headers={"User-Agent": "AyvonaJobsBot/1.0 (+https://t.me/ayvonajobs)"},
        follow_redirects=False,
    )


def _s(value: Any, limit: int = 200) -> str:
    return str(value or "")[:limit]


def _photos(provider: str, data: dict[str, Any]) -> list[StockPhoto]:
    out: list[StockPhoto] = []
    if provider == "pexels":
        for p in data.get("photos") or []:
            src = p.get("src") or {}
            url = src.get("large2x") or src.get("large")
            if url and p.get("id"):
                out.append(
                    StockPhoto(
                        "pexels", str(p["id"]), url, _s(p.get("url")), _s(p.get("photographer"))
                    )
                )
    elif provider == "unsplash":
        for p in data.get("results") or []:
            urls = p.get("urls") or {}
            raw = urls.get("raw")
            url = f"{raw}&w=1280&h=720&fit=crop&q=85&fm=jpg" if raw else urls.get("regular")
            links = p.get("links") or {}
            if url and p.get("id"):
                out.append(
                    StockPhoto(
                        "unsplash",
                        str(p["id"]),
                        url,
                        _s(links.get("html")),
                        _s((p.get("user") or {}).get("name")),
                        track_url=links.get("download_location"),
                    )
                )
    else:  # pixabay
        for p in data.get("hits") or []:
            url = p.get("largeImageURL")
            if url and p.get("id"):
                out.append(
                    StockPhoto(
                        "pixabay", str(p["id"]), url, _s(p.get("pageURL")), _s(p.get("user"))
                    )
                )
    return out


def allowed_host(provider: str, url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in CDN_HOSTS[provider]


def configured_providers(settings: Settings) -> list[str]:
    env = settings.env
    keys = {
        "pexels": env.pexels_api_key,
        "unsplash": env.unsplash_access_key,
        "pixabay": env.pixabay_api_key,
    }
    return [p for p in PROVIDERS if keys[p] is not None]


async def search_stock(
    provider: str, settings: Settings, query: str, page: int, http: httpx.AsyncClient
) -> list[StockPhoto]:
    """One page of results from the provider's official API. ``[]`` on any problem (logged
    without the key)."""
    env = settings.env
    try:
        if provider == "pexels":
            assert env.pexels_api_key is not None
            r = await http.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "orientation": "landscape",
                    "size": "large",
                    "per_page": PER_PAGE,
                    "page": page,
                },
                headers={"Authorization": env.pexels_api_key.get_secret_value()},
            )
        elif provider == "unsplash":
            assert env.unsplash_access_key is not None
            r = await http.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "orientation": "landscape",
                    "per_page": PER_PAGE,
                    "page": page,
                    "content_filter": "high",
                },
                headers={
                    "Authorization": f"Client-ID {env.unsplash_access_key.get_secret_value()}",
                    "Accept-Version": "v1",
                },
            )
        else:
            assert env.pixabay_api_key is not None
            r = await http.get(
                "https://pixabay.com/api/",
                params={
                    "key": env.pixabay_api_key.get_secret_value(),
                    "q": query,
                    "image_type": "photo",
                    "orientation": "horizontal",
                    "min_width": 1280,
                    "safesearch": "true",
                    "per_page": PER_PAGE,
                    "page": page,
                },
            )
        if r.status_code != 200:
            logger.warning("rasm qidirish ({}): HTTP {}", provider, r.status_code)
            return []
        return [p for p in _photos(provider, r.json()) if allowed_host(provider, p.download_url)]
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("rasm qidirish ({}): {}", provider, type(e).__name__)  # never the URL (key)
        return []


async def download(provider: str, url: str, http: httpx.AsyncClient) -> bytes | None:
    if not allowed_host(provider, url):
        logger.warning("rasm yuklanmadi: begona manzil ({})", provider)
        return None
    try:
        async with http.stream("GET", url) as r:
            if r.status_code != 200:
                return None
            data = bytearray()
            async for chunk in r.aiter_bytes():
                data += chunk
                if len(data) > MAX_DOWNLOAD_BYTES:
                    return None
            return bytes(data)
    except httpx.HTTPError as e:
        logger.warning("rasm yuklanmadi ({}): {}", provider, type(e).__name__)
        return None


async def ping_unsplash_download(
    settings: Settings, photo: StockPhoto, http: httpx.AsyncClient
) -> None:
    """Unsplash's API terms: tell them when a photo is actually used. Best effort."""
    if (
        photo.provider != "unsplash"
        or not photo.track_url
        or settings.env.unsplash_access_key is None
    ):
        return
    if urlparse(photo.track_url).hostname != "api.unsplash.com":
        return
    with contextlib.suppress(httpx.HTTPError):
        await http.get(
            photo.track_url,
            headers={
                "Authorization": f"Client-ID {settings.env.unsplash_access_key.get_secret_value()}"
            },
        )


# --------------------------------------------------------------------------- candidates
@dataclass(slots=True)
class Candidate:
    jpeg: bytes
    source: str  # pexels | unsplash | pixabay | generated
    label: str  # one line for the admin
    license: str
    meta: dict[str, Any] = field(default_factory=dict)
    stock: StockPhoto | None = None


class CandidateSource:
    """The proposals for ONE slot, one after the other (``next``): stock photos while the
    configured providers have results, then drawn pictures — never the same one twice."""

    def __init__(
        self,
        settings: Settings,
        slot: Slot,
        *,
        used: set[str] | None = None,
        http_factory: HttpFactory = default_http,
    ) -> None:
        self.settings = settings
        self.slot = slot
        self.used = used or set()
        self.http_factory = http_factory
        self.providers = configured_providers(settings)
        self.query = query_of(settings, slot)
        self._queue: list[StockPhoto] = []
        self._page = 0
        self._generated = 0
        self._seen: set[str] = set()

    async def _refill(self, http: httpx.AsyncClient) -> bool:
        """Next page of the current provider; moves on to the next provider when exhausted."""
        while self.providers:
            if self._page >= MAX_PAGES:
                self.providers.pop(0)
                self._page = 0
                continue
            self._page += 1
            found = await search_stock(
                self.providers[0], self.settings, self.query, self._page, http
            )
            fresh = [p for p in found if p.uid not in self.used and p.uid not in self._seen]
            if not found:  # nothing more (or an error): next provider
                self.providers.pop(0)
                self._page = 0
                continue
            if fresh:
                self._queue.extend(fresh)
                return True
        return False

    async def next(self) -> Candidate:
        branding = self.settings.app.branding
        if self.providers or self._queue:
            async with self.http_factory() as http:
                while self._queue or await self._refill(http):
                    photo = self._queue.pop(0)
                    self._seen.add(photo.uid)
                    raw = await download(photo.provider, photo.download_url, http)
                    if raw is None:
                        continue
                    try:
                        jpeg = encode_jpeg(
                            brand_photo(
                                raw, title=self.slot.title, channel=branding.channel_username
                            )
                        )
                    except ValueError:
                        continue
                    return Candidate(
                        jpeg=jpeg,
                        source=photo.provider,
                        label=f"{photo.provider.capitalize()} · {photo.author or '—'}",
                        license=LICENSES[photo.provider],
                        meta={
                            "provider": photo.provider,
                            "id": photo.id,
                            "author": photo.author,
                            "page_url": photo.page_url,
                            "query": self.query,
                        },
                        stock=photo,
                    )
        self._generated += 1
        variant = self.slot.index + PER_FOLDER * (self._generated - 1)
        img = render_flat(
            category=self.slot.category,
            title=self.slot.title,
            subtitle=self.slot.category_title if self.slot.profession else None,
            icon=icon_of(self.settings, self.slot),
            variant=variant,
            channel=branding.channel_username,
        )
        return Candidate(
            jpeg=encode_jpeg(img),
            source="generated",
            label=f"original rasm (Ayvona, {self._generated}-variant)",
            license=LICENSES["generated"],
            meta={
                "generator": "pillow-flat",
                "variant": variant,
                "icon": icon_of(self.settings, self.slot),
            },
        )


# --------------------------------------------------------------------------- approve
@dataclass(frozen=True, slots=True)
class Applied:
    path: Path  # the new file
    backup: Path | None  # where the replaced real picture went
    sidecar: Path


def _free_name(folder: Path) -> Path:
    n = 1
    while any((folder / f"{n}{e}").exists() for e in IMAGE_EXTENSIONS):
        n += 1
    return folder / f"{n}.jpg"


def apply_candidate(
    settings: Settings, slot: Slot, cand: Candidate, *, admin_id: int, now: datetime
) -> Applied:
    """Write the approved picture. A real picture in this slot is moved to
    ``data/images_backup/<folder>/<time>_<name>`` first (with its ``.json``); a slot that only has
    a placeholder gets a new real file next to it (the placeholder stays: real pictures win by
    themselves). Raises ``OSError`` if a file cannot be written — nothing is half done."""
    root = settings.images_dir
    folder = root / slot.category / slot.profession if slot.profession else root / slot.category
    folder.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if slot.replaces_real and slot.current is not None and slot.current.is_file():
        stamp = f"{now:%Y%m%d%H%M%S}"
        bdir = settings.data_dir / "images_backup" / slot.folder_rel
        bdir.mkdir(parents=True, exist_ok=True)
        backup = bdir / f"{stamp}_{slot.current.name}"
        slot.current.replace(backup)
        old_meta = slot.current.with_name(slot.current.name + ".json")
        if old_meta.is_file():
            old_meta.replace(bdir / f"{stamp}_{old_meta.name}")
        target = slot.current.with_suffix(".jpg")
    else:
        target = _free_name(folder)
    try:
        save_jpeg(cand.jpeg, target)
    except OSError:
        if backup is not None:  # put the old picture back
            backup.replace(slot.current)  # type: ignore[arg-type]
        raise
    sidecar = target.with_name(target.name + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "file": target.name,
                "folder": slot.folder_rel,
                "slot": slot.index,
                "source": cand.source,
                "license": cand.license,
                "details": cand.meta,
                "approved_by": admin_id,
                "approved_at": now.isoformat(),
                "replaced": backup.name if backup else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return Applied(target, backup, sidecar)
