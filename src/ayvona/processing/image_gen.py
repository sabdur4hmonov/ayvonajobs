"""Post pictures drawn by us (Pillow only): original flat-style art, no third-party artwork or fonts
shipped, so there is no licence to track. Also puts the Ayvona branding on a stock photo.

Both give a 1280 x 720 JPEG under 1 MB (docs/IMAGES.md): a coloured background, big Uzbek title,
a simple pictogram of the category and the small ``@channel`` mark in the corner. The same
(category, profession, variant) always gives the same picture; every variant looks different.
"""

from __future__ import annotations

import colorsys
import hashlib
import io
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720
MAX_BYTES = 950_000  # docs/IMAGES.md: under 1 MB
WHITE = (255, 255, 255)

_FONTS = (
    "arialbd.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)

ICONS = (
    "briefcase",
    "cart",
    "headset",
    "chef",
    "truck",
    "pin",
    "box",
    "gear",
    "wrench",
    "cross",
    "cap",
    "calculator",
    "laptop",
    "camera",
    "megaphone",
    "scissors",
    "globe",
    "star",
)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def encode_jpeg(img: Image.Image, max_bytes: int = MAX_BYTES) -> bytes:
    """JPEG bytes, quality lowered until the file fits ``max_bytes``."""
    quality = 90
    while True:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_bytes or quality <= 40:
            return buf.getvalue()
        quality -= 8


def _seed(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


def _text_width(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=f)
    return right - left


def _fit_lines(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, sizes: tuple[int, ...]
) -> tuple[list[str], ImageFont.ImageFont]:
    """The biggest font in ``sizes`` that shows ``text`` in at most two lines."""
    words = text.split()
    for size in sizes:
        f = font(size)
        if _text_width(draw, text, f) <= max_width:
            return [text], f
        for cut in range(1, len(words)):
            a, b = " ".join(words[:cut]), " ".join(words[cut:])
            if max(_text_width(draw, a, f), _text_width(draw, b, f)) <= max_width:
                return [a, b], f
    f = font(sizes[-1])
    return [text[:28]], f


# --------------------------------------------------------------------------- pictograms
def draw_icon(d: ImageDraw.ImageDraw, name: str, cx: float, cy: float, size: float, ink, accent):  # noqa: ANN001, C901, PLR0915
    """A flat pictogram in a ``size`` x ``size`` box centred at (cx, cy). Coordinates below are
    in a 0..100 box."""
    k = size / 100
    ox, oy = cx - size / 2, cy - size / 2

    def p(x: float, y: float) -> tuple[float, float]:
        return ox + x * k, oy + y * k

    def box(x1: float, y1: float, x2: float, y2: float) -> list[float]:
        return [*p(x1, y1), *p(x2, y2)]

    def poly(*pts: tuple[float, float], fill=ink) -> None:  # noqa: ANN001
        d.polygon([p(x, y) for x, y in pts], fill=fill)

    def disc(x: float, y: float, r: float, fill=ink) -> None:  # noqa: ANN001
        d.ellipse(box(x - r, y - r, x + r, y + r), fill=fill)

    w = max(int(7 * k), 2)
    if name == "briefcase":
        d.rounded_rectangle(box(8, 30, 92, 86), radius=int(8 * k), fill=ink)
        d.rounded_rectangle(box(34, 14, 66, 34), radius=int(6 * k), outline=ink, width=w)
        d.rectangle(box(8, 52, 92, 57), fill=accent)
        d.rounded_rectangle(box(44, 48, 56, 62), radius=int(3 * k), fill=accent)
    elif name == "cart":
        d.line([p(4, 14), p(20, 14), p(32, 62), p(80, 62)], fill=ink, width=w, joint="curve")
        poly((24, 28), (92, 28), (82, 54), (32, 54))
        disc(40, 78, 8)
        disc(72, 78, 8)
    elif name == "headset":
        d.arc(box(20, 10, 80, 70), 180, 360, fill=ink, width=w)
        d.rounded_rectangle(box(12, 40, 30, 72), radius=int(6 * k), fill=ink)
        d.rounded_rectangle(box(70, 40, 88, 72), radius=int(6 * k), fill=ink)
        d.line([p(80, 70), p(74, 86), p(54, 88)], fill=ink, width=w, joint="curve")
        disc(50, 88, 6, accent)
    elif name == "chef":
        for x, y, r in ((30, 36, 18), (50, 28, 21), (70, 36, 18)):
            disc(x, y, r)
        d.rectangle(box(30, 40, 70, 74), fill=ink)
        d.rectangle(box(28, 70, 72, 86), fill=accent)
    elif name == "truck":
        d.rounded_rectangle(box(6, 26, 60, 70), radius=int(4 * k), fill=ink)
        poly((62, 40), (82, 40), (94, 56), (94, 70), (62, 70))
        poly((68, 46), (80, 46), (88, 56), (68, 56), fill=accent)
        disc(26, 74, 10, accent)
        disc(76, 74, 10, accent)
    elif name == "pin":
        disc(50, 38, 28)
        poly((26, 52), (74, 52), (50, 92))
        disc(50, 38, 11, accent)
    elif name == "box":
        poly((50, 12), (90, 30), (50, 48), (10, 30))
        poly((10, 34), (47, 52), (47, 90), (10, 72), fill=accent)
        poly((90, 34), (53, 52), (53, 90), (90, 72))
    elif name == "gear":
        for i in range(8):
            a = math.radians(i * 45)
            x, y = 50 + 36 * math.cos(a), 50 + 36 * math.sin(a)
            pts = [
                (x + 9 * math.cos(a + t) - 0, y + 9 * math.sin(a + t))
                for t in (math.pi / 2, math.pi / 2 + math.pi / 2, 3 * math.pi / 2, 0)
            ]
            poly(*pts)
        disc(50, 50, 30)
        disc(50, 50, 13, accent)
    elif name == "wrench":
        d.line([p(22, 82), p(62, 42)], fill=ink, width=int(15 * k))
        disc(68, 34, 24)
        poly((66, 20), (92, 0), (102, 14), (80, 36), fill=WHITE)  # the open jaw of the wrench
        disc(22, 82, 8)
    elif name == "cross":
        d.rounded_rectangle(box(36, 8, 64, 92), radius=int(6 * k), fill=ink)
        d.rounded_rectangle(box(8, 36, 92, 64), radius=int(6 * k), fill=ink)
        disc(50, 50, 9, accent)
    elif name == "cap":
        poly((50, 16), (96, 38), (50, 60), (4, 38))
        poly((24, 52), (50, 66), (76, 52), (76, 74), (50, 88), (24, 74), fill=accent)
        d.line([p(90, 42), p(90, 72)], fill=ink, width=w)
        disc(90, 76, 5)
    elif name == "calculator":
        d.rounded_rectangle(box(20, 6, 80, 94), radius=int(8 * k), fill=ink)
        d.rounded_rectangle(box(28, 14, 72, 34), radius=int(4 * k), fill=accent)
        for row in range(3):
            for col in range(3):
                x, y = 28 + col * 17, 42 + row * 16
                d.rounded_rectangle(box(x, y, x + 12, y + 11), radius=int(3 * k), fill=accent)
    elif name == "laptop":
        d.rounded_rectangle(box(16, 18, 84, 66), radius=int(5 * k), fill=ink)
        for i, wd in enumerate((38, 26, 32)):
            d.line([p(24, 30 + i * 11), p(24 + wd, 30 + i * 11)], fill=accent, width=int(5 * k))
        poly((6, 70), (94, 70), (86, 82), (14, 82))
    elif name == "camera":
        d.rounded_rectangle(box(8, 30, 92, 82), radius=int(8 * k), fill=ink)
        d.rectangle(box(60, 20, 78, 32), fill=ink)
        disc(50, 56, 20, accent)
        disc(50, 56, 11)
    elif name == "megaphone":
        poly((18, 40), (66, 16), (66, 84), (18, 60))
        d.rounded_rectangle(box(8, 38, 24, 62), radius=int(4 * k), fill=ink)
        d.arc(box(60, 28, 92, 72), -60, 60, fill=ink, width=w)
        d.arc(box(68, 20, 100, 80), -60, 60, fill=accent, width=w)
        poly((26, 62), (38, 66), (36, 86), (24, 84), fill=accent)
    elif name == "scissors":
        d.ellipse(box(10, 12, 38, 40), outline=ink, width=w)
        d.ellipse(box(10, 60, 38, 88), outline=ink, width=w)
        d.line([p(34, 34), p(92, 66)], fill=ink, width=w)
        d.line([p(34, 66), p(92, 34)], fill=accent, width=w)
    elif name == "globe":
        d.ellipse(box(8, 8, 92, 92), outline=ink, width=w)
        d.ellipse(box(30, 8, 70, 92), outline=ink, width=int(w * 0.7))
        d.line([p(8, 50), p(92, 50)], fill=ink, width=int(w * 0.7))
        d.arc(box(14, 22, 86, 78), 200, 340, fill=accent, width=int(w * 0.7))
    else:  # "star" and anything unknown
        pts = []
        for i in range(10):
            a = math.radians(-90 + i * 36)
            r = 46 if i % 2 == 0 else 20
            pts.append((50 + r * math.cos(a), 52 + r * math.sin(a)))
        poly(*pts)


# --------------------------------------------------------------------------- flat art
def render_flat(
    *,
    category: str,
    title: str,
    subtitle: str | None,
    icon: str,
    variant: int,
    channel: str,
    brand: str = "Ayvona Jobs",
) -> Image.Image:
    """The picture of one folder (category or profession) in flat style."""
    rng = random.Random(_seed(category, title, variant))
    hue = (_seed(category) % 360) / 360 + 0.04 * (variant - 1)
    top, bottom = _hsv(hue, 0.62, 0.62), _hsv(hue + 0.06, 0.70, 0.30)
    img = Image.new("RGB", (WIDTH, HEIGHT), top)
    px = ImageDraw.Draw(img)
    for y in range(HEIGHT):  # vertical gradient
        t = y / (HEIGHT - 1)
        px.line(
            [(0, y), (WIDTH, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )

    shapes = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shapes)
    for _ in range(7):  # soft decorative shapes, different for every variant
        x, y = rng.randint(-100, WIDTH), rng.randint(-100, HEIGHT)
        s = rng.randint(120, 380)
        alpha = rng.randint(18, 46)
        kind = rng.choice(("circle", "round", "ring"))
        if kind == "circle":
            sd.ellipse([x, y, x + s, y + s], fill=(255, 255, 255, alpha))
        elif kind == "round":
            sd.rounded_rectangle(
                [x, y, x + s, y + s // 2], radius=s // 6, fill=(255, 255, 255, alpha)
            )
        else:
            sd.ellipse([x, y, x + s, y + s], outline=(255, 255, 255, alpha + 20), width=14)
    img = Image.alpha_composite(img.convert("RGBA"), shapes)

    d = ImageDraw.Draw(img)
    cx, cy, r = WIDTH - 330, HEIGHT // 2 - 20, 215  # the badge with the pictogram
    ink = _hsv(hue, 0.70, 0.46)
    accent = _hsv(hue + 0.08, 0.55, 0.95)
    lines, f = _fit_lines(d, title.upper(), 640, (96, 84, 72, 60, 50))
    line_h = int(getattr(f, "size", 60) * 1.18)
    y0 = HEIGHT // 2 - 120 - (len(lines) - 1) * 50
    y_end = y0 + line_h * len(lines)
    sf, bf = font(40), font(32)
    pill_w = int(_text_width(d, subtitle, sf)) + 48 if subtitle else 0

    # translucent parts are drawn on their own layer (drawing alpha straight onto RGBA replaces
    # the pixels instead of blending them)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 235))
    for i, line in enumerate(lines):
        od.text((83, y0 + i * line_h + 3), line, font=f, fill=(0, 0, 0, 70))
    if subtitle:
        od.rounded_rectangle(
            [80, y_end + 14, 80 + pill_w, y_end + 78], radius=32, fill=(255, 255, 255, 60)
        )
    od.text(
        (WIDTH - 80 - _text_width(d, brand, bf), HEIGHT - 94),
        brand,
        font=bf,
        fill=(255, 255, 255, 190),
    )
    img = Image.alpha_composite(img, overlay)

    d = ImageDraw.Draw(img)
    draw_icon(d, icon, cx, cy, 250, ink, accent)
    for i, line in enumerate(lines):
        d.text((80, y0 + i * line_h), line, font=f, fill=WHITE)
    if subtitle:
        d.text((104, y_end + 22), subtitle, font=sf, fill=WHITE)
    d.rectangle([80, HEIGHT - 120, 200, HEIGHT - 112], fill=accent)
    d.text((80, HEIGHT - 100), f"@{channel}", font=font(36), fill=WHITE)
    return img.convert("RGB")


# --------------------------------------------------------------------------- stock photo + brand
def brand_photo(
    photo: bytes, *, title: str, channel: str, brand: str = "Ayvona Jobs"
) -> Image.Image:
    """A stock photo cropped to 16:9 (1280 x 720) with the Ayvona strip: the Uzbek title on the
    left, ``@channel`` on the right. Raises ``ValueError`` for something that is not a picture."""
    try:
        with Image.open(io.BytesIO(photo)) as src:
            src.load()
            img = src.convert("RGB")
    except Exception as e:
        raise ValueError(f"not an image: {type(e).__name__}") from e
    scale = max(WIDTH / img.width, HEIGHT / img.height)
    img = img.resize(
        (max(WIDTH, round(img.width * scale)), max(HEIGHT, round(img.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left, top = (img.width - WIDTH) // 2, (img.height - HEIGHT) // 2
    img = img.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGBA")
    strip = Image.new("RGBA", (WIDTH, 150), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    for y in range(150):  # fade from transparent to dark
        sd.line([(0, y), (WIDTH, y)], fill=(8, 12, 24, round(190 * (y / 149) ** 1.4)))
    img.alpha_composite(strip, (0, HEIGHT - 150))
    d = ImageDraw.Draw(img)
    lines, f = _fit_lines(d, title.upper(), 760, (52, 46, 40))
    d.text((48, HEIGHT - 28 - int(getattr(f, "size", 46)) - 18), lines[0], font=f, fill=WHITE)
    cf, bf = font(30), font(26)
    d.text(
        (WIDTH - 48 - _text_width(d, f"@{channel}", cf), HEIGHT - 86),
        f"@{channel}",
        font=cf,
        fill=WHITE,
    )
    d.text(
        (WIDTH - 48 - _text_width(d, brand, bf), HEIGHT - 48),
        brand,
        font=bf,
        fill=(255, 255, 255, 200),
    )
    return img.convert("RGB")


def save_jpeg(data: bytes, path: Path) -> None:
    """Write atomically (a half-written picture is never picked)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
