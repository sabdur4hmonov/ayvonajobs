"""Channel post (HTML caption) + buttons — docs/POST_EXAMPLES.md "KELISHILGAN SHABLON".

Full template (extract confidence >= ``formatter.min_confidence``)::

    💼 <b>Sotuvchi-konsultant</b>
    🏢 Kompaniya: Texnomart

    💰 Maosh: 4 000 000 – 6 000 000 so'm
    📍 Manzil: Toshkent sh., Chilonzor tumani
    🕒 Ish vaqti: 09:00–18:00, 6/1
    📋 Talablar: 18–30 yosh, rus tili bilan ishlash

    📞 Aloqa: +998 90 123 45 67
    ✉️ Telegram: @hr_texnomart

    #sotuvchi #sotuv #toshkent
    ➖➖➖➖➖➖➖➖
    🔍 Ish qidiryapsizmi? @ayvona_jobs_bot
    📢 @ayvonajobs — Ayvona Jobs
    <i><a href="https://t.me/manba_kanal/12345">manba</a></i>

Rules: an empty field has no line; no salary -> "Kelishiladi"; several positions -> "📌 Lavozimlar:"
list; tags = #kasb #kategoriya #hudud + at most 2 feature tags (<= 5, no repeats); the "manba"
line only for aggregator posts. The usernames in the signature and the bot buttons come from
``branding`` in config/settings.yaml. Only the tag line has hashtags: a hashtag inside a field or
the text becomes a plain word ("Faqat #Erkaklar" -> "Faqat erkaklar"). The address gets commas
between its parts ("Samarqand viloyati, Samarqand shahri", "Toshkent sh., Yashnobod tumani").
Everything is HTML-escaped. At most 1024 characters: first the
requirements / details shrink; title, salary, place, contacts, signature and "manba" never.

Fallback (low confidence): category headline + the cleaned original text + contacts.

Language (docs/SOURCE_ANALYSIS.md §11): always Uzbek, Latin script. Uzbek Cyrillic is
transliterated. Russian / English posts get only Uzbek fields (title via the dictionary, salary,
place, contacts); their free text is replaced by "📝 To'liq ma'lumot: asl e'londa".
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ayvona.config import Settings
from ayvona.processing.clean import CleanedText
from ayvona.processing.contacts import canon_username, find_phones, find_usernames
from ayvona.processing.extract import MULTI_TITLE, Extraction, TitleTranslator
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.language import Language
from ayvona.processing.normalize import fold, to_latin
from ayvona.processing.salary import EUR, RUB, USD, UZS

# --------------------------------------------------------------------------- texts
T_TITLE = "💼"
T_COMPANY = "🏢 Kompaniya:"
T_POSITIONS = "📌 Lavozimlar:"
T_SALARY = "💰 Maosh:"
T_PLACE = "📍 Manzil:"
T_SCHEDULE = "🕒 Ish vaqti:"
T_REQUIREMENTS = "📋 Talablar:"
T_PHONE = "📞 Aloqa:"
T_TELEGRAM = "✉️ Telegram:"
T_EMAIL = "📧 Email:"
T_APPLY = "🔗 Ariza:"
T_APPLY_LINK = "ariza topshirish"
T_FULL_INFO = "📝 To'liq ma'lumot:"
T_FULL_INFO_LINK = "asl e'londa"
T_NEGOTIABLE = "Kelishiladi"
T_REMOTE = "Masofaviy"
T_FALLBACK_TITLE = "Yangi ish e'loni"
T_MORE_POSITIONS = "… va yana {n} ta"
T_SEPARATOR = "➖➖➖➖➖➖➖➖"
T_SIGN_BOT = "🔍 Ish qidiryapsizmi? @{bot}"
T_SIGN_CHANNEL = "📢 @{channel} — {title}"
T_SOURCE = "manba"
B_CONTACT = "📩 Murojaat"
B_APPLY = "🔗 Ariza topshirish"
B_SAVE = "⭐ Saqlash"
B_MORE = "🔍 Boshqa ishlar"

CURRENCY_NAMES = {UZS: "so'm", USD: "$", EUR: "€", RUB: "rubl"}
PERIOD_NAMES = {"day": "kunlik", "week": "haftalik", "hour": "soatbay"}
TASHKENT_CITY = "toshkent_sh"  # its districts are "tuman"s: "Chilonzor tumani"

MIN_REQUIREMENTS = 25  # shorter than this after shrinking -> the line is dropped
_KPI_RE = re.compile(r"\bkpi\b")
_BONUS_RE = re.compile(r"bonus|premiya|премия")
_TAG_RE = re.compile(r"[^a-z0-9_]")
_TAG_LINE_RE = re.compile(r"^\s*(?:#[^\s#]+[\s,.]*)+$")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
_LETTERS_RE = re.compile(r"[^\W\d_]")
_USERNAME_OR_URL_RE = re.compile(r"@\w+|\S+\.\S+/\S*|t\.me/\S+", re.IGNORECASE)
_CONTACT_HEADER_RE = re.compile(
    r"tel|aloqa|bog'lan|murojaat|contact|telegram|phone|телефон|связ", re.IGNORECASE
)
# "#Erkaklar" (not "C#", "site.uz/#x", "#1"): a hashtag that starts with a letter
_HASHTAG_RE = re.compile(r"(?<![\w/&#])#([^\W\d_]\w*)")
_LONE_HASH_RE = re.compile(r"(?<!\S)#(?:[ \t]+|$)")
_SENTENCE_START_RE = re.compile(r"(?:^|[\n.;:!?(•\-–—])\s*$")
# "shahri Yakkasaroy" -> "shahri, Yakkasaroy" (only before a capital letter / a number)
_ADDRESS_UNIT_RE = re.compile(
    r"(?<![\w'])(viloyati|viloyat|vil\.|shahri|shahar|shaxar|shaxri|shahari|sh\.|tumani|tuman)"
    r"(?![\w'])[ \t]+(?=([^\W_]))",
    re.IGNORECASE,
)
_CITY_UNIT = r"\s*\.?\s*(?:shahri|shahar|shaxar|shaxri|shahr|sh)(?![\w'])\.?"
_CITY_TAIL_RE = re.compile(r"\s+(?:shahri|shahar|sh\.?)$")  # "toshkent sh." names "toshkent"


def tg_len(text: str) -> int:
    """Length as Telegram counts it (UTF-16 code units): emoji count as 2."""
    return len(text.encode("utf-16-le")) // 2


def visible_len(html_text: str) -> int:
    """Length of an HTML caption after Telegram parses the tags."""
    return tg_len(html.unescape(_HTML_TAG_RE.sub("", html_text)))


def truncate(text: str, limit: int) -> str:
    """At most ``limit`` (Telegram) characters, cut at a word boundary, with "…"."""
    if tg_len(text) <= limit:
        return text
    if limit <= 1:
        return ""
    kept, used = [], 0
    for ch in text:
        used += 2 if ord(ch) > 0xFFFF else 1
        if used > limit - 1:  # room for "…"
            break
        kept.append(ch)
    cut = "".join(kept)
    if " " in cut[len(cut) * 2 // 3 :]:  # don't break a word if a space is close
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" \n,;:.-–—") + "…"


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def format_phone(phone: str) -> str:
    """``+998901234567`` -> ``+998 90 123 45 67``."""
    d = phone.removeprefix("+998")
    if len(d) == 9 and d.isdigit():
        return f"+998 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}"
    return phone


def format_amount(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def telegram_post_url(source: str | None, external_id: str | None) -> str | None:
    """``("@kanal", "123")`` -> ``https://t.me/kanal/123``; ``-100...`` ids -> ``t.me/c/...``."""
    if not source or not external_id or not external_id.isdigit():
        return None
    s = source.strip()
    for prefix in ("https://", "http://", "t.me/s/", "t.me/", "@"):
        s = s.removeprefix(prefix)
    if s.lstrip("-").isdigit():
        chat = s.removeprefix("-100") if s.startswith("-100") else s.lstrip("-")
        return f"https://t.me/c/{chat}/{external_id}"
    return f"https://t.me/{s.split('/')[0]}/{external_id}"


def _http(url: str) -> str:
    return url if re.match(r"https?://", url, re.IGNORECASE) else "https://" + url


def _latin(text: str | None) -> str:
    """Any Cyrillic -> Uzbek Latin (the channel is Latin only)."""
    return to_latin(text) if text and _CYRILLIC_RE.search(text) else (text or "")


def _neutral(text: str) -> bool:
    """Only digits / times ("9:00-18:00, 5/2"): readable in any language."""
    return not _LETTERS_RE.search(text)


def _cap(text: str) -> str:
    """``"moddiy ashyoviy xisobchi"`` -> ``"Moddiy ashyoviy xisobchi"``."""
    return text[:1].upper() + text[1:] if text[:1].islower() else text


def _all_caps(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    return len(letters) > 1 and all(c.isupper() for c in letters)


def plain_hashtags(text: str, is_place: Callable[[str], bool] | None = None) -> str:
    """Hashtags inside a field / the text -> plain words; only the tag line keeps ``#``.

    ``"Faqat #Erkaklar"`` -> ``"Faqat erkaklar"``, ``"#Talabalar_ham"`` -> ``"Talabalar ham"``.
    A sentence start or a place name keeps its capital letter, an all-caps word ("#DIMKA") stays.
    """
    if "#" not in text:
        return text

    def word(m: re.Match[str]) -> str:
        w = m.group(1).replace("_", " ").strip()
        if _all_caps(w):
            return w
        if _SENTENCE_START_RE.search(m.string[: m.start()]) or (is_place and is_place(w)):
            return _cap(w)
        return w.lower()

    text = _LONE_HASH_RE.sub("", _HASHTAG_RE.sub(word, text))
    return re.sub(r"(?<=\S)[ \t]{2,}", " ", text)


def tidy_address(text: str, city_titles: Sequence[str] = ()) -> str:
    """Commas between the parts of an address, no repeated city.

    ``"Samarqand viloyati Samarqand shahri"`` -> ``"Samarqand viloyati, Samarqand shahri"``;
    ``"Toshkent shahar Yashnobod tumani"`` -> ``"Toshkent sh., Yashnobod tumani"``;
    ``"Toshkent shahri Toshkent"`` -> ``"Toshkent sh."``. ``city_titles``: region titles like
    ``"Toshkent sh."`` — every spelling of that city ("Toshkent shahri", "Toshkent.Sh") becomes it.
    """
    for title in city_titles:
        name = title.removesuffix(" sh.")
        if name == title:
            continue

        def city(m: re.Match[str], title: str = title) -> str:
            nxt = m.string[m.end() :].lstrip()[:1]
            # "Toshkent shahri bo'ylab" reads better as it is
            return m.group(0) if nxt.isalpha() and nxt.islower() else title

        text = re.sub(rf"(?<![\w']){re.escape(name)}{_CITY_UNIT}", city, text, flags=re.IGNORECASE)

    def unit(m: re.Match[str]) -> str:
        u = m.group(1)
        if m.start() > 0 and u[:1].isupper() and u[1:].islower():  # "Mirobod Tumani" -> "tumani"
            u = u.lower()
        nxt = m.group(2)
        return u + (", " if nxt.isupper() or nxt.isdigit() else " ")

    text = _ADDRESS_UNIT_RE.sub(unit, text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",(?=[^\s\d])", ", ", text)
    text = re.sub(r",{2,}", ",", text)
    # drop a part that only repeats a name said before: "Toshkent sh., Toshkent"
    parts: list[str] = []
    seen: set[str] = set()
    for part in text.split(", "):
        key = fold(part).strip(" .")
        if key and key in seen:
            continue
        parts.append(part)
        seen.add(key)
        seen.add(_CITY_TAIL_RE.sub("", key).strip(" ."))
    return ", ".join(parts).strip(" ,")


_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}[:.]\d{2})\s*(?:-|–|—|до|to|dan|gacha)?\s*(\d{1,2}[:.]\d{2})", re.IGNORECASE
)
_WORK_DAYS_RE = re.compile(r"(?<!\d)([5-7])\s*/\s*([12])(?!\d)")


def _schedule_numbers(text: str) -> str | None:
    """Times and work days of a Russian / English schedule: ``"с 10:00 до 19:00, 5/2"`` ->
    ``"10:00–19:00, 5/2"`` (the words can't be translated without AI)."""
    if _neutral(text):
        return text
    parts = [
        f"{a.replace('.', ':')}–{b.replace('.', ':')}" for a, b in _TIME_RANGE_RE.findall(text)
    ]
    parts += [f"{a}/{b}" for a, b in _WORK_DAYS_RE.findall(text)]
    return ", ".join(dict.fromkeys(parts)) or None


# --------------------------------------------------------------------------- result
@dataclass(frozen=True, slots=True)
class Button:
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class FormattedPost:
    html: str
    fallback: bool
    tags: tuple[str, ...]
    username: str | None = None  # first @username -> "📩 Murojaat"
    apply_url: str | None = None
    bot_username: str = ""  # always given by Formatter (branding in settings.yaml)
    shortened: tuple[str, ...] = field(default=())  # what was cut to fit the limit

    @property
    def length(self) -> int:
        return visible_len(self.html)

    def buttons(self, job_id: int | None = None) -> list[list[Button]]:
        """Inline keyboard rows. "⭐ Saqlash" needs the job id (a bot deep link)."""
        first: list[Button] = []
        if self.username:
            first.append(Button(B_CONTACT, f"https://t.me/{self.username.lstrip('@')}"))
        if self.apply_url:
            first.append(Button(B_APPLY, _http(self.apply_url)))
        second: list[Button] = []
        if job_id is not None:
            second.append(Button(B_SAVE, f"https://t.me/{self.bot_username}?start=save_{job_id}"))
        second.append(Button(B_MORE, f"https://t.me/{self.bot_username}?start=search"))
        return [row for row in (first, second) if row]


@dataclass(slots=True)
class _Parts:
    """Plain-text field values (not escaped yet); shrinking works on these."""

    title: str
    company: str | None = None
    positions: list[str] = field(default_factory=list)
    positions_hidden: int = 0
    salary: str | None = None
    place: str | None = None
    schedule: str | None = None
    requirements: str | None = None
    body: str | None = None  # fallback: cleaned original text
    body_links: list[tuple[str, str]] = field(default_factory=list)
    full_info: bool = False
    phones: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    apply_url: str | None = None
    tags: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- formatter
class Formatter:
    """Build once from :class:`Settings`, call :meth:`format` per job."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cfg = settings.app.formatter
        self.branding = settings.app.branding
        self.translator = TitleTranslator(settings.title_translations)
        self.negotiable = KeywordSet(settings.extract.salary_negotiable)
        self._region_names = {
            key: KeywordSet([reg.title, *reg.keywords])
            for key, reg in settings.regions.regions.items()
        }
        regions = list(settings.regions.regions.values())
        # "Navoiy viloyati" names a region; "Samarqand" alone may be "Samarqand Darvoza" (Toshkent)
        self._region_titles = KeywordSet(reg.title for reg in regions)
        self._place_names = KeywordSet(
            n
            for reg in regions
            for n in (
                reg.title,
                *reg.keywords,
                *reg.districts,
                *(k for kws in reg.districts.values() for k in kws),
            )
        )
        self._city_titles = [reg.title for reg in regions]

    def _is_place(self, word: str) -> bool:
        return bool(self._place_names.find(fold(word)))

    def _plain(self, text: str) -> str:
        return plain_hashtags(text, self._is_place)

    # ------------------------------------------------------------------ fields
    def _title(self, ex: Extraction, lang: Language | None) -> str:
        if ex.multi and ex.title_source == "positions":
            return _latin(ex.company) if ex.company else MULTI_TITLE
        title = ex.title
        if not title:
            return self._profession_title(ex.profession) or T_FALLBACK_TITLE
        if lang in (Language.RU, Language.EN):
            uz = ex.title_uz or self.translator.translate(title, lang) or title
            if _CYRILLIC_RE.search(title) and not self.translator.exact(title):
                # Russian word by word keeps Russian grammar ("Menejer po rabote s ...");
                # the profession name is Uzbek and still precise enough.
                return self._profession_title(ex.profession) or _latin(uz)
            return _latin(uz)
        return _latin(title)

    def _profession_title(self, profession: str | None) -> str | None:
        for cat in self.settings.categories.values():
            if profession in cat.professions:
                return cat.professions[profession].title
        return None

    def _positions(self, ex: Extraction, lang: Language | None) -> list[str]:
        if not ex.multi:
            return []
        return [_cap(self._plain(_latin(self.translator.exact(p) or p))) for p in ex.positions]

    def _salary(self, ex: Extraction, lang: Language | None) -> str:
        if ex.salary_min is None and ex.salary_max is None:
            text = (ex.salary_text or "").strip()
            if not text or self.negotiable.find(fold(text)):
                return T_NEGOTIABLE
            if lang in (Language.RU, Language.EN) and not _neutral(text):
                return T_NEGOTIABLE
            return truncate(self._plain(_latin(text)), 80)
        cur = CURRENCY_NAMES.get(ex.currency or UZS, ex.currency or "")
        lo, hi = ex.salary_min, ex.salary_max
        glue = "" if cur == "so'm" else " "  # "4 000 000 so'mdan", "500 $ dan"
        if lo is not None and hi is not None and lo != hi:
            out = f"{format_amount(lo)} – {format_amount(hi)} {cur}"
        elif lo is not None and hi is not None:
            out = f"{format_amount(lo)} {cur}"
        elif lo is not None:
            out = f"{format_amount(lo)} {cur}{glue}dan"
        else:
            assert hi is not None
            out = f"{format_amount(hi)} {cur}{glue}gacha"
        if period := PERIOD_NAMES.get(ex.salary_period or ""):
            out += f" ({period})"
        folded = fold(ex.salary_text or "")
        if _KPI_RE.search(folded):
            out += " + KPI"
        elif _BONUS_RE.search(folded):
            out += " + bonus"
        return out

    def _region_part(self, ex: Extraction) -> str | None:
        regions = self.settings.regions
        if not ex.region:
            return None
        if ex.region == regions.multi_region:
            titles = [regions.regions[r].title for r in ex.regions if r in regions.regions]
            return ", ".join(titles[:3]) or regions.multi_region_title
        reg = regions.regions.get(ex.region)
        if reg is None:
            return None
        if ex.district:
            suffix = " tumani" if ex.region == TASHKENT_CITY else ""
            return f"{reg.title}, {ex.district}{suffix}"
        return reg.title

    def _place(self, ex: Extraction, lang: Language | None) -> tuple[str | None, list[str]]:
        """The "📍 Manzil" line + words that were hashtags in it but are not places
        ("#Ayollar #Erkaklar" — they go to the requirements, so the meaning stays)."""
        region = self._region_part(ex)
        address = None
        extra: list[str] = []
        if ex.address and lang not in (Language.RU, Language.EN):
            address, extra = self._address_tags(_latin(ex.address))
            address = truncate(tidy_address(address, self._city_titles), 120)
        if address:
            # "Chilonzor 9-kvartal" -> "Toshkent sh., Chilonzor 9-kvartal";
            # "Toshkent, Yunusobod" (or "Navoiy viloyati") names the place already.
            reg = self.settings.regions.regions.get(ex.region or "")
            names = self._region_names.get(ex.region or "")
            folded = fold(address)
            if (
                reg is not None
                and names is not None
                and not names.find(folded)
                and not self._region_titles.find(folded)
            ):
                address = f"{reg.title}, {address}"
            place = address
        else:
            place = region
        if ex.is_remote:
            place = f"{T_REMOTE}, {place}" if place else T_REMOTE
        return place, extra

    def _address_tags(self, text: str) -> tuple[str, list[str]]:
        """``"#Toshkent #Ayollar #Erkaklar"`` -> ``("Toshkent", ["ayollar", "erkaklar"])``."""
        extra: list[str] = []

        def drop(m: re.Match[str]) -> str:
            if self._is_place(m.group(1)):
                return m.group(0)
            extra.append(m.group(1).replace("_", " ").lower())
            return ""

        text = self._plain(_HASHTAG_RE.sub(drop, text))
        return re.sub(r"\s{2,}", " ", text).strip(" ,;"), list(dict.fromkeys(extra))

    def _tags(self, ex: Extraction) -> list[str]:
        cats = self.settings.categories
        regions = self.settings.regions
        tags: list[str] = []
        if ex.profession:
            tags.append(ex.profession)
        if cat := cats.get(ex.category):
            tags.append(cat.hashtag)
        if ex.region == regions.multi_region:
            tags.extend(regions.regions[r].hashtag for r in ex.regions if r in regions.regions)
        elif reg := regions.regions.get(ex.region or ""):
            tags.append(reg.hashtag)
        base = [t for t in dict.fromkeys(_TAG_RE.sub("", t.lower()) for t in tags) if t]
        base = base[: self.cfg.max_tags]
        features = [
            t
            for t in dict.fromkeys(_TAG_RE.sub("", t.lower()) for t in ex.feature_tags)
            if t and t not in base
        ][: self.cfg.max_feature_tags]
        return (base + features)[: self.cfg.max_tags]

    # ------------------------------------------------------------------ rendering
    def _signature(self, source_url: str | None) -> list[str]:
        b = self.branding
        lines = [
            T_SEPARATOR,
            esc(T_SIGN_BOT.format(bot=b.bot_username)),
            esc(T_SIGN_CHANNEL.format(channel=b.channel_username, title=b.channel_title)),
        ]
        if source_url:
            lines.append(f'<i><a href="{html.escape(source_url)}">{T_SOURCE}</a></i>')
        return lines

    def _render(self, p: _Parts, source_url: str | None) -> str:
        head = [f"{T_TITLE} <b>{esc(p.title)}</b>"]
        if p.company:
            head.append(f"{T_COMPANY} {esc(p.company)}")
        if p.positions:
            head.append(T_POSITIONS)
            head.extend(f"• {esc(x)}" for x in p.positions)
            if p.positions_hidden:
                head.append(esc(T_MORE_POSITIONS.format(n=p.positions_hidden)))

        blocks: list[list[str]] = [head]
        if p.body:
            blocks.append([_link_body(p.body, p.body_links)])
        details = []
        if p.salary:
            details.append(f"{T_SALARY} {esc(p.salary)}")
        if p.place:
            details.append(f"{T_PLACE} {esc(p.place)}")
        if p.schedule:
            details.append(f"{T_SCHEDULE} {esc(p.schedule)}")
        if p.requirements:
            details.append(f"{T_REQUIREMENTS} {esc(p.requirements)}")
        if p.full_info and source_url:
            details.append(
                f'{esc(T_FULL_INFO)} <a href="{html.escape(source_url)}">'
                f"{esc(T_FULL_INFO_LINK)}</a>"
            )
        blocks.append(details)

        contacts = []
        if p.phones:
            contacts.append(f"{T_PHONE} {', '.join(format_phone(x) for x in p.phones)}")
        if p.usernames:
            contacts.append(f"{T_TELEGRAM} {esc(', '.join(p.usernames))}")
        if p.emails:
            contacts.append(f"{T_EMAIL} {esc(', '.join(p.emails))}")
        if p.apply_url:
            contacts.append(
                f'{T_APPLY} <a href="{html.escape(_http(p.apply_url))}">{T_APPLY_LINK}</a>'
            )
        blocks.append(contacts)

        tail = [" ".join(f"#{t}" for t in p.tags)] if p.tags else []
        tail.extend(self._signature(source_url))
        blocks.append(tail)
        return "\n\n".join("\n".join(b) for b in blocks if b)

    def _fit(self, p: _Parts, source_url: str | None) -> tuple[str, list[str]]:
        """Render, shrinking the less important parts until the caption fits."""
        limit = self.cfg.max_caption_length
        shortened: list[str] = []

        def over() -> int:
            return visible_len(self._render(p, source_url)) - limit

        if p.body is not None and (extra := over()) > 0:
            budget = tg_len(p.body) - extra
            p.body = truncate(p.body, max(budget, 0))
            p.full_info = True  # the rest is in the original post
            shortened.append("body")
            while over() > 0 and p.body:  # "📝 To'liq ma'lumot" line took some room
                p.body = truncate(p.body, max(tg_len(p.body) - over() - 1, 0))
        if p.requirements and (extra := over()) > 0:
            budget = tg_len(p.requirements) - extra
            p.requirements = (
                truncate(p.requirements, budget) if budget >= MIN_REQUIREMENTS else None
            )
            shortened.append("requirements")
        while p.positions and len(p.positions) > 2 and over() > 0:
            p.positions.pop()
            p.positions_hidden += 1
            shortened.append("positions")
        for name, keep in (("schedule", 40), ("company", 40), ("place", 60)):
            if getattr(p, name) and over() > 0:
                setattr(p, name, truncate(getattr(p, name), keep))
                shortened.append(name)
        if over() > 0 and p.schedule:
            p.schedule = None
            shortened.append("schedule")
        while over() > 0 and len(p.tags) > 1:
            p.tags.pop()
            shortened.append("tags")
        if over() > 0 and len(p.positions) > 1:
            p.positions_hidden += len(p.positions) - 1
            p.positions = p.positions[:1]
        return self._render(p, source_url), list(dict.fromkeys(shortened))

    # ------------------------------------------------------------------ main
    def format(
        self,
        ex: Extraction,
        cleaned: CleanedText | None = None,
        *,
        source_url: str | None = None,
    ) -> FormattedPost:
        """Caption + buttons of one job. ``source_url``: the original post (aggregator only).

        ``cleaned`` (clean.py) is the body of the fallback template; without it the full
        template is used whatever the confidence.
        """
        lang = ex.language
        foreign = lang in (Language.RU, Language.EN)
        n = self.cfg.max_contacts
        fallback = ex.confidence < self.cfg.min_confidence and cleaned is not None
        p = _Parts(
            title=_cap(self._plain(self._title(ex, lang))),
            phones=list(ex.phones[:n]),
            usernames=list(ex.usernames[:n]),
            emails=list(ex.emails[:2]),
            apply_url=None if (ex.phones or ex.usernames or ex.emails) else ex.apply_url,
            tags=self._tags(ex),
        )
        if fallback:
            cat = self.settings.categories.get(ex.category)
            p.title = (
                f"{T_FALLBACK_TITLE} — {cat.title}"
                if cat and ex.category != "boshqa"
                else T_FALLBACK_TITLE
            )
            if foreign:
                # The text itself is not shown, so a found title (even an unsure one) says
                # more than the generic headline.
                if ex.title:
                    p.title = _cap(self._plain(self._title(ex, lang)))
                p.salary = self._salary(ex, lang)
                p.place, _ = self._place(ex, lang)
                p.full_info = True
            else:
                assert cleaned is not None
                p.body, p.body_links = _fallback_body(
                    cleaned, p.phones, p.usernames, is_place=self._is_place
                )
        else:
            if ex.company and not (ex.multi and ex.title_source == "positions"):
                p.company = truncate(self._plain(_latin(ex.company)), 80)
            p.positions = self._positions(ex, lang)
            p.salary = self._salary(ex, lang)
            p.place, place_words = self._place(ex, lang)
            schedule = _schedule_numbers(ex.schedule) if foreign and ex.schedule else ex.schedule
            if schedule:
                p.schedule = truncate(self._plain(_latin(schedule)), 120)
            requirements = [_cap(", ".join(place_words))] if place_words and not foreign else []
            if ex.requirements and not foreign:
                requirements.append(self._plain(_latin(ex.requirements)))
            if requirements:
                p.requirements = truncate("; ".join(requirements), 400)
            p.full_info = foreign

        caption, shortened = self._fit(p, source_url)
        return FormattedPost(
            html=caption,
            fallback=fallback,
            tags=tuple(p.tags),
            username=ex.usernames[0] if ex.usernames else None,
            apply_url=_http(ex.apply_url) if ex.apply_url else None,
            bot_username=self.branding.bot_username,
            shortened=tuple(shortened),
        )


def _contact_only(line: str, phones: set[str], users: set[str]) -> bool:
    """``"TELEFON : +998991976796"``: a line that only repeats contacts shown below the text."""
    line_phones = set(find_phones(line))
    line_users = {canon_username(u) for u in find_usernames(line)}
    if not (line_phones or line_users) or not line_phones <= phones or not line_users <= users:
        return False
    rest = _USERNAME_OR_URL_RE.sub(" ", line)
    return len(_LETTERS_RE.findall(rest)) <= 20


def _fallback_body(
    cleaned: CleanedText,
    phones: Sequence[str] = (),
    usernames: Sequence[str] = (),
    is_place: Callable[[str], bool] | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """Cleaned original text in Latin, without the source's hashtag lines and without lines that
    only repeat the contacts (they are listed under the text); hidden links kept. Hashtags left
    inside the lines become plain words (only our tag line has hashtags)."""
    shown_phones = set(phones)
    shown_users = {canon_username(u) for u in usernames}
    lines: list[str] = []
    for ln in _latin(cleaned.text).split("\n"):
        if _TAG_LINE_RE.match(ln):
            continue
        if _contact_only(ln, shown_phones, shown_users):
            # "📞 MUROJAAT UCHUN:" right above the removed numbers goes too
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and _CONTACT_HEADER_RE.search(lines[-1]) and lines[-1].rstrip().endswith(":"):
                lines.pop()
            continue
        lines.append(plain_hashtags(ln, is_place))
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    links = [
        (plain_hashtags(_latin(lk.text), is_place), lk.url)
        for lk in cleaned.links
        if not lk.button and lk.text
    ]
    return body, links


def _link_body(body: str, links: list[tuple[str, str]]) -> str:
    """Escape ``body`` and put each hidden link back on the first occurrence of its text."""
    out: list[str] = []
    pos = 0
    for text, url in links:
        k = body.find(text, pos)
        if k < 0:
            continue
        out.append(esc(body[pos:k]))
        out.append(f'<a href="{html.escape(_http(url))}">{esc(text)}</a>')
        pos = k + len(text)
    out.append(esc(body[pos:]))
    return "".join(out)
