"""Temporary pictures for empty image folders (docs/IMAGES.md), so a post is never without one.

For every category and profession of config/categories.yaml (+ "boshqa") whose folder has no
picture yet, 3 pictures ``placeholder_1.jpg`` ... are made: 1280x720, the category's own colour,
the profession name in the middle, "Ayvona Jobs" in the corner. Real pictures are never touched,
and once a folder (or its category) has a real picture, the placeholders are not used any more.

Usage:
    uv run python scripts/make_placeholder_images.py            # only empty folders
    uv run python scripts/make_placeholder_images.py --force    # re-draw every placeholder
"""

from __future__ import annotations

import argparse
import colorsys
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ayvona.config import get_settings
from ayvona.processing.images import PLACEHOLDER_PREFIX, is_placeholder, list_images

WIDTH, HEIGHT = 1280, 720
VARIANTS = 3
# One hue per category (config order), spread around the colour wheel.
FONT_CANDIDATES = (
    "arialbd.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)

FontT = ImageFont.FreeTypeFont | ImageFont.ImageFont


def load_font(size: int) -> FontT:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: FontT) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def fit_lines(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> tuple[list[str], FontT]:
    """One line if it fits at a readable size, else two lines; biggest font that fits."""
    words = text.split()
    options = [[text]]
    if len(words) > 1:
        best = min(
            range(1, len(words)),
            key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))),
        )
        options.append([" ".join(words[:best]), " ".join(words[best:])])
    for size in range(120, 30, -6):
        font = load_font(size)
        for lines in options:
            if all(text_width(draw, ln, font) <= max_width for ln in lines):
                return lines, font
    return options[-1], load_font(30)


def draw_placeholder(label: str, subtitle: str | None, hue: float, variant: int, out: Path) -> None:
    base = rgb(hue, 0.55, 0.62 - 0.08 * variant)
    dark = rgb(hue, 0.65, 0.30 - 0.04 * variant)
    img = Image.new("RGB", (WIDTH, HEIGHT), base)
    draw = ImageDraw.Draw(img)

    # Background: vertical gradient + a few soft circles; the variants differ in layout.
    for y in range(HEIGHT):
        t = y / HEIGHT if variant != 1 else 1 - y / HEIGHT
        color = tuple(round(b + (d - b) * t) for b, d in zip(base, dark, strict=True))
        draw.line([(0, y), (WIDTH, y)], fill=color)
    light = rgb(hue, 0.35, 0.80)
    circles = {
        0: [(1100, 120, 260), (120, 640, 180)],
        1: [(160, 140, 220), (1180, 600, 300)],
        2: [(640, -120, 320), (1200, 700, 160), (60, 360, 120)],
    }[variant % 3]
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for cx, cy, r in circles:
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*light, 55))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    lines, font = fit_lines(draw, label.upper(), WIDTH - 160)
    heights = [draw.textbbox((0, 0), ln, font=font)[3] for ln in lines]
    gap = 18
    total = sum(heights) + gap * (len(lines) - 1)
    y = (HEIGHT - total) // 2 - (30 if subtitle else 0)
    for ln, h in zip(lines, heights, strict=True):
        x = (WIDTH - text_width(draw, ln, font)) / 2
        draw.text((x + 3, y + 3), ln, font=font, fill=dark)
        draw.text((x, y), ln, font=font, fill="white")
        y += h + gap
    if subtitle:
        small = load_font(40)
        x = (WIDTH - text_width(draw, subtitle, small)) / 2
        draw.text((x, y + 20), subtitle, font=small, fill=(235, 235, 235))

    brand = load_font(34)
    mark = "Ayvona Jobs"
    draw.text(
        (WIDTH - text_width(draw, mark, brand) - 40, HEIGHT - 70), mark, font=brand, fill="white"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=88, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--force", action="store_true", help="re-draw existing placeholders")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console

    settings = get_settings()
    root = settings.images_dir
    fallback = settings.app.images.fallback_category
    categories = dict(settings.categories)
    folders: list[tuple[Path, str, str | None, int]] = []  # (folder, label, subtitle, cat index)
    for i, (key, cat) in enumerate(categories.items()):
        folders.append((root / key, cat.title, None, i))
        for pkey, prof in cat.professions.items():
            folders.append((root / key / pkey, prof.title, cat.title, i))
    if fallback not in categories:
        folders.append((root / fallback, "Ish e'loni", None, len(categories)))

    made = skipped = 0
    n = max(len(categories), 1)
    for folder, label, subtitle, index in folders:
        existing = list_images(folder)
        real = [p for p in existing if not is_placeholder(p)]
        if real or (existing and not args.force):
            skipped += 1
            continue
        for old in existing:  # --force: only placeholders are ever deleted
            old.unlink()
        for v in range(VARIANTS):
            draw_placeholder(
                label, subtitle, index / n, v, folder / f"{PLACEHOLDER_PREFIX}{v + 1}.jpg"
            )
        made += 1
        print(f"✅ {folder.relative_to(root).as_posix()}: {VARIANTS} ta vaqtinchalik rasm")
    print(f"\nTayyor: {made} ta papkaga rasm chizildi, {skipped} ta papka o'tkazib yuborildi.")
    print(f"Papka: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
