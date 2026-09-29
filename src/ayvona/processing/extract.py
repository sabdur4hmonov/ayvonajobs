"""Regex extractor: turn a job post into fields (docs/SOURCE_ANALYSIS.md §4-7, §9-10).

Works line by line on the post without channel boilerplate. Every line exists in two forms:
``display`` (readable: NFKC, keycaps -> digits, no emoji, case and script kept — what we show) and
``folded`` (lower case, all Cyrillic -> Latin — what we match). Both have the same words, so a match
in the folded line is mapped back to the display line by word position.

Fields:
* contacts   — phones, @usernames, emails, apply_url (contacts.py; 6 places incl. hidden links);
* title      — "Lavozim:/Position:/Вакансия:" label, else "... kerak" / "ищет ..." /
               "We are looking for ...", else a short first line with a profession in it,
               else the profession name; a vacancy list -> company or "Bir nechta vakansiya";
* company, schedule, requirements — template labels (config/extract.yaml), "—" = empty;
* salary     — salary.py; region / district / is_remote — location.py;
* positions  — vacancy lists (header + items, 1️⃣ 2️⃣ blocks, several "... kerak" blocks, lines
               with their own apply links) -> ``multi``;
* category / profession / feature tags — categorize.py;
* confidence — title + contact >= 0.7; ``low_quality`` — neither title nor salary found
               (not published, shown in the admin report).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ayvona.config import DEFAULT_CONFIG_DIR, Settings, load_settings
from ayvona.processing.boilerplate import BoilerplateRules, keep_mask
from ayvona.processing.categorize import Categorization, Categorizer
from ayvona.processing.classify import PostInput
from ayvona.processing.contacts import Contacts, find_contacts, linked_positions
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.language import Language, detect_language
from ayvona.processing.location import Location, LocationFinder
from ayvona.processing.normalize import display, fold, normalize_lines
from ayvona.processing.salary import Salary, SalaryBlock, SalaryParser, looks_like_money

MULTI_TITLE = "Bir nechta vakansiya"
MAX_TITLE_LEN = 90
MAX_TITLE_WORDS = 12
MAX_PHRASE_LINE = 150  # longer lines are paragraphs, not headlines
MAX_BLOCK_LINES = 8
EMPTY_VALUES = frozenset({"", "-", "—", "–", "--", "yo'q", "нет", "n/a"})

# Leading bullets / numbering of a folded line: "• ", "– ", "1. ", "1) ", "-".
_LEAD_RE = re.compile(r"^[\s\W_]*?(?:\d{1,2}[.)]\s+)?(?=[\w#$@«\"(])")
_BULLET_START_RE = re.compile(r"^\s*[•·\-–—*▪►➤>]")
_KEYCAP_LINE_RE = re.compile(r"^\W*\d{1,2}️?⃣")
_HASHTAG_LINE_RE = re.compile(r"^(?:#[^\s#]+\s*)+$")
_SEP_RE = re.compile(r"^\s*(?:[:：]|[-—–]\s|[-—–]$)\s*")
_TIME_RE = re.compile(r"\d{1,2}[:.]\d{2}")
# A block of a multi-ad post has its own salary or address line.
_BLOCK_DETAIL_RE = re.compile(r"maosh|oylik|salary|zarplata|manzil|address|adres|location")
_AMOUNT_START_RE = re.compile(r"^[\s\-–—]*(?:\d|\$|do\s|up to)")
_GENERIC_TITLES = frozenset(
    fold(w)
    for w in (
        "xodim", "xodimlar", "odam", "odamlar", "yigitlar", "qizlar", "ayollar", "erkaklar",
        "yigit", "qiz", "mutaxassis", "mutaxassislar", "сотрудник", "сотрудники", "ходим",
        "ходимлар", "ishchi xodim", "xodimlarni", "ishchilar", "arizalar", "hujjatlar",
        "rezyumelar", "buyurtmalar", "заявки", "yigitlarni", "qizlarni", "ayollarni",
        "erkaklarni", "yigit-qizlar", "yigit-qizlarni", "talabalar", "studentlar", "odamni",
        "xodimni", "xodimga", "человека", "человек", "людей", "kimni", "biz", "bizga", "sizni",
        "someone", "person", "people", "nomzod", "nomzodlar", "nomzodlarni", "hamkorlar",
        "hamkor", "specialists", "two specialists",
    )
)  # fmt: skip
# "Buxgalterga yordamchi": the dative word is part of the position.
# Dropped from the end of a title together with generic words ("yigitlar va").
_CONJUNCTIONS = frozenset(fold(w) for w in ("va", "ham", "и", "and", "&", "hamda"))
_HELPER_WORDS = frozenset(
    fold(w)
    for w in ("yordamchi", "yordamchisi", "assistent", "shogird", "shogirt", "ассистент",
              "помощник", "помощница", "ёрдамчи")
)  # fmt: skip
# Capitalized sentence starts that are not company names: "Bizning jamoamizga ..."
_NOT_COMPANY_WORDS = frozenset(
    fold(w)
    for w in ("bizning", "sizning", "biz", "siz", "bizga", "our", "the", "your", "kuchli", "katta",
              "yosh", "do'stona", "наша", "нашу", "в", "мы", "ushbu", "yangi")
)  # fmt: skip
# Dative ("-ga", "bankka", "o'rtoqqa"). Plain "-ka/-qa" words are nouns (matematika, boshqa).
_DATIVE_RE = re.compile(r"(?:ga|kka|qqa)$")
# Where a title phrase starts after a place: dative "-ga" or locative "-da" ("Olmaliqda kuryerlar").
_PLACE_CASE_RE = re.compile(r"(?:ga|kka|qqa|da|dagi)$")
_COMPANY_WORD_RE = re.compile(r"^(?:kompaniya|kompaniyasi|company|kompaniya nomi)\s+")
# Where an English/Russian "looking for X ..." title ends.
_TITLE_TAIL_RE = re.compile(
    r"\s+(?:to join|to work|who|which|for our|in our|at our|with|в команду|в компанию|для)\s"
    r"|,\s+(?:who|which|который|которая|kim|qaysi)\b|[.;!]\s|[.;!]$",
    re.IGNORECASE,
)
_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
_COMPANY_ORG_RE = re.compile(
    r"[«\"“„'‘`,]{1,2}\s*([^»\"”'’`]{2,40}?)\s*[»\"”'’`]{1,2}\s*"
    r"(?:kompaniya|korxona|firma|mchj|ooo|llc|zavod|fabrika|restoran|kafe|do'kon|markaz|klinika"
    r"|компани|корхона|фирм|завод|фабрик|ресторан|магазин|клиник|ооо|мчж)",
    re.IGNORECASE,
)
_COMPANY_TEAM_RE = re.compile(
    r"((?:[A-ZА-ЯЎҚҒҲ][\w&.'’-]*\s+){0,2}[A-ZА-ЯЎҚҒҲ][\w&.'’-]*)\s+"
    r"(?:jamoasi|jamoasiga|jamoamiz|jamoasini|жамоаси|жамоасига|team)\b"
)
_COMPANY_SUFFIX_RE = re.compile(
    r"((?:[A-ZА-Я][\w&.'’-]*\s+){0,3}[A-ZА-Я][\w&.'’-]*)\s+(?:LLC|MChJ|OOO|Inc\.?|Ltd\.?|ООО|МЧЖ)\b"
)


# --------------------------------------------------------------------------- lines
@dataclass(frozen=True, slots=True)
class Line:
    raw: str  # original line
    display: str
    folded: str
    blank_before: bool  # previous kept line is empty (or this is the first line)

    @property
    def body(self) -> str:
        """Folded line without leading bullets / numbering."""
        m = _LEAD_RE.match(self.folded)
        return self.folded[m.end() :] if m else self.folded

    def display_from(self, folded_pos: int, folded_end: int | None = None) -> str:
        """Display text of ``folded[folded_pos:folded_end]`` (mapped by word position)."""
        return _map_span(self.folded, self.display, folded_pos, folded_end)


def _word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _map_span(folded: str, disp: str, start: int, end: int | None) -> str:
    end = len(folded) if end is None else end
    fw, dw = _word_spans(folded), _word_spans(disp)
    if len(fw) != len(dw):
        return folded[start:end].strip()

    def to_disp(pos: int, is_end: bool) -> int:
        for (fs, fe), (ds, de) in zip(fw, dw, strict=True):
            if fs <= pos <= fe if is_end else fs <= pos < fe:
                offset = pos - fs
                same_len = (fe - fs) == (de - ds)
                if offset == 0:
                    return ds
                if offset == fe - fs:
                    return de
                return ds + offset if same_len else (de if is_end else ds)
            if pos < fs:
                return ds
        return len(disp)

    return disp[to_disp(start, False) : to_disp(end, True)].strip()


# --------------------------------------------------------------------------- result
@dataclass(frozen=True, slots=True)
class Extraction:
    title: str | None = None
    title_uz: str | None = None  # title via config/title_translations.yaml (ru/en posts)
    title_source: str | None = None  # label | phrase | first_line | positions | profession
    company: str | None = None
    positions: tuple[str, ...] = ()
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    salary_period: str | None = None  # month | week | day | hour
    salary_text: str | None = None
    region: str | None = None
    regions: tuple[str, ...] = ()
    district: str | None = None
    is_remote: bool = False
    schedule: str | None = None
    requirements: str | None = None
    phones: tuple[str, ...] = ()
    usernames: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()
    apply_url: str | None = None
    category: str = "boshqa"
    profession: str | None = None
    feature_tags: tuple[str, ...] = ()
    language: Language | None = None
    confidence: float = 0.0
    low_quality: bool = False
    reasons: tuple[str, ...] = field(default=())

    @property
    def multi(self) -> bool:
        return len(self.positions) >= 2

    @property
    def has_contact(self) -> bool:
        return bool(self.phones or self.usernames or self.emails or self.apply_url)

    @property
    def publish(self) -> bool:
        """Goes to the channel: has a contact and is not low quality."""
        return self.has_contact and not self.low_quality


# --------------------------------------------------------------------------- extractor
def _label_re(words: list[str]) -> re.Pattern[str] | None:
    folded = sorted({fold(w) for w in words if fold(w)}, key=len, reverse=True)
    if not folded:
        return None
    return re.compile(r"^(?P<label>" + "|".join(re.escape(w) for w in folded) + r")(?![\w'])")


def _phrase_re(words: list[str]) -> str:
    folded = sorted({fold(w) for w in words if fold(w)}, key=len, reverse=True)
    return "|".join(re.escape(w) for w in folded) or "(?!)"


class Extractor:
    """Build once from :class:`Settings`, call :meth:`extract` per job post."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        cfg = settings.extract
        self.labels = {
            name: _label_re(getattr(cfg.labels, name))
            for name in ("title", "company", "salary", "schedule", "requirements", "location")
        }
        self._salary_inline = re.compile(
            r"(?<![\w'])(?P<label>" + _phrase_re(cfg.labels.salary) + r")(?![\w'])"
            r"(?=\s*[:：\-—–]?\s*(?:ot\s|do\s|от\s|до\s|up to\s|\$|\d))"
        )
        self._before = re.compile(
            r"^(?P<t>.+?)\s+(?:" + _phrase_re(cfg.hiring_phrases.before) + r")(?![\w'])"
            r"(?!\s*emas)(?!mas\b)"
        )
        self._after = re.compile(
            r"(?:^|(?P<pre>.*?)\s)(?:"
            + _phrase_re(cfg.hiring_phrases.after)
            + r")\s*:?\s+(?P<t>.+)$"
        )
        # "В команду ... требуется:" / "Bizga kerak:" — the position is on the next line.
        self._lead_in = re.compile(
            r"(?:"
            + _phrase_re([*cfg.hiring_phrases.before, *cfg.hiring_phrases.after])
            + r")\s*:\s*$"
        )
        self._headers = [fold(h) for h in cfg.position_list_headers if fold(h)]
        self.salary = SalaryParser(cfg)
        self.location = LocationFinder(settings.regions)
        self.categorizer = Categorizer(
            settings.categories, settings.feature_tags, settings.negation_words
        )
        self._professions = {
            p: prof.title for c in settings.categories.values() for p, prof in c.professions.items()
        }
        self._region_words = KeywordSet(
            w for r in settings.regions.regions.values() for w in [*r.keywords, *r.districts]
        )
        tt = settings.title_translations
        self._exact = {fold(k): v for k, v in tt.exact.items()}
        self._words = sorted(
            ((fold(k), v) for k, v in tt.words.items()), key=lambda kv: -len(kv[0])
        )
        self._rules: dict[str, BoilerplateRules] = {}

    # ------------------------------------------------------------------ helpers
    def _boilerplate(self, source: str | None) -> BoilerplateRules:
        key = (source or "").lower()
        if key not in self._rules:
            sr = self.settings.source_rules
            self._rules[key] = BoilerplateRules.build(sr.for_source(source), sr.defaults)
        return self._rules[key]

    def _own_usernames(self, post: PostInput) -> list[str]:
        rule = self.settings.source_rules.for_source(post.source)
        own = [*post.own_usernames, *rule.extra_own_usernames]
        if post.source:
            own.append(post.source)
        return own

    def lines(self, post: PostInput) -> list[Line]:
        """The post's lines without channel boilerplate."""
        raw = post.text.split("\n")
        norm = normalize_lines(post.text)
        keep = keep_mask(norm, self._boilerplate(post.source))
        out: list[Line] = []
        prev_blank = True
        for r, k in zip(raw, keep, strict=True):
            if not k:
                continue
            disp = display(r)
            out.append(Line(r, disp, fold(disp), prev_blank))
            prev_blank = not disp
        return out

    def _label(self, name: str, line: Line) -> tuple[str, str] | None:
        """``(label, value_display)`` if ``line`` is "<label>: value" for field ``name``."""
        rx = self.labels.get(name)
        body = line.body
        m = rx.match(body) if rx else None
        if not m:
            return None
        rest = body[m.end() :]
        sep = _SEP_RE.match(rest)
        if sep is None and rest.strip():
            return None  # "Oylik o'z vaqtida to'lanadi": a sentence, not a label
        start = len(line.folded) - len(rest) + (sep.end() if sep else 0)
        value = line.display_from(start)
        return m.group("label"), value

    def _any_label(self, line: Line) -> bool:
        return any(self._label(n, line) for n in self.labels)

    def _is_header(self, line: Line) -> bool:
        b = line.body.rstrip()
        return b.endswith(":") and len(b) <= 60

    def _block(
        self, lines: list[Line], i: int, value: str, limit: int = MAX_BLOCK_LINES
    ) -> list[str]:
        """Value of a label at ``lines[i]``: inline, else the following list lines."""
        if fold(value).strip(" .") not in EMPTY_VALUES:
            return [value]
        if value.strip() in ("—", "-", "–"):
            return []
        out: list[str] = []
        j = i + 1
        while j < len(lines) and len(out) < limit:
            ln = lines[j]
            if not ln.display:
                if out or (j > i + 1):
                    break
                j += 1
                continue
            if self._is_header(ln) or self._any_label(ln):
                break
            out.append(_strip_bullet(ln.display))
            j += 1
        return [x for x in out if fold(x).strip(" .") not in EMPTY_VALUES]

    # ------------------------------------------------------------------ fields
    def _title_from_phrase(self, line: Line) -> tuple[str | None, str | None]:
        """``("title", "company or None")`` from "X kerak" / "ищет X" / "looking for X"."""
        if _BULLET_START_RE.match(line.display):
            return None, None
        body = line.body
        offset = len(line.folded) - len(body)
        # "We are looking for a Recruitment Assistant to join our team at ..." may open a long
        # paragraph; "... kerak" at the end of a paragraph is not a headline.
        if len(line.folded) <= MAX_PHRASE_LINE and (m := self._before.match(body)):
            t = line.display_from(offset + m.start("t"), offset + m.end("t"))
            if self._lead_in.search(body) and not self.categorizer.has_profession(t):
                return None, None  # "В команду ... требуется:" — the position is on the next line
            trimmed = _trim_dative(t)
            # "Buxgalterga yordamchi", "Rahbar bo'lima marketinga i reklami": the position was in
            # the cut-off part and nothing generic ("xodimlar") is left -> keep the whole phrase.
            if (
                trimmed != t
                and not self.categorizer.has_profession(trimmed)
                and self.categorizer.has_profession(t)
                and not any(fold(w).strip(".,!") in _GENERIC_TITLES for w in trimmed.split())
            ) or fold(trimmed).strip(" .!") in _HELPER_WORDS:
                trimmed = t
            return self._named_position(_clean_title(trimmed)), None
        if m := self._after.match(body):
            t = line.display_from(offset + m.start("t"), offset + m.end("t"))
            t = _TITLE_TAIL_RE.split(t, maxsplit=1)[0]
            if not self._named_position(_clean_title(_ARTICLE_RE.sub("", t))):
                return None, None  # "ищем человека, который ..."
            pre = m.group("pre")
            company = (
                line.display_from(offset + m.start("pre"), offset + m.end("pre"))
                if pre and len(pre.split()) <= 3
                else None
            )
            return _clean_title(_ARTICLE_RE.sub("", t)), company
        return None, None

    def _named_position(self, title: str | None) -> str | None:
        """Drop trailing "yigitlar / xodimlar / va" words; ``None`` if no position is left.

        "Sotuv menejer yigitlar" -> "Sotuv menejer"; "mas'uliyatli va chaqqon xodimlar" -> None;
        "Paxta ishlab chiqarish tsexiga yigitlar" -> None (only a place is left).
        """
        if not title or title.startswith("("):
            return None
        words = title.split()
        while words and fold(words[-1]).strip(".,!") in _GENERIC_TITLES | _CONJUNCTIONS:
            words.pop()
        if not words:
            return None
        rest = " ".join(words)
        if len(words) < len(title.split()) and not self.categorizer.has_profession(rest):
            return None
        if _DATIVE_RE.search(fold(words[-1]).strip(".,")):
            return None
        return rest

    def _title(self, lines: list[Line]) -> tuple[str | None, str | None, str | None]:
        """``(title, source, company_hint)``."""
        for ln in lines:
            if lab := self._label("title", ln):
                value = _clean_title(lab[1])
                value = self._named_position(value) or value  # "Sotuv menejer yigitlar"
                if value and fold(value) not in EMPTY_VALUES:
                    return value, "label", None
        for i, ln in enumerate(lines[:8]):
            title, company = self._title_from_phrase(ln)
            if title and _good_title(title):
                return title, "phrase", company
            if self._lead_in.search(ln.body):
                nxt = next((n for n in lines[i + 1 : i + 3] if n.display), None)
                cand = (
                    self._named_position(_clean_title(_strip_bullet(nxt.display))) if nxt else None
                )
                if cand and self.categorizer.has_profession(cand):
                    return cand, "phrase", None
        first = next(
            (
                ln
                for ln in lines
                if ln.display
                and not _HASHTAG_LINE_RE.match(ln.folded)
                and not _only_place(ln.folded, self._region_words)
            ),
            None,
        )
        if (
            first
            and len(first.display) <= 60
            and len(first.display.split()) <= 7
            and not first.display.rstrip().endswith(("!", "?", ":"))
            and self.categorizer.has_profession(first.folded)
            and not self._before.match(first.body)  # "... kerak" lines were judged above
            and not first.raw.lstrip().startswith("🏢")
            # "«Сладово» қандолат фабрикасига ...": a sentence about a place, not a title
            and not any(len(w) > 4 and _PLACE_CASE_RE.search(w) for w in first.folded.split())
            and (title := self._named_position(_clean_title(first.display)))
        ):
            return title, "first_line", None
        return None, None, None

    def _company(self, lines: list[Line], hint: str | None) -> str | None:
        labeled = [
            v
            for ln in lines
            if (lab := self._label("company", ln)) and (v := _clean_company(lab[1]))
        ]
        if labeled:
            # Several different employers in one post (3 schools) -> no single company.
            return labeled[0] if len({fold(v) for v in labeled}) == 1 else None
        for ln in lines:  # "Компания FreeLink - ведущий ..." (no colon, a capitalized name)
            if (m := _COMPANY_WORD_RE.match(ln.body)) and ":" not in ln.body:
                rest = ln.display_from(len(ln.folded) - len(ln.body) + m.end())
                name = re.split(r"\s[-—–]\s|[.,;]", rest)[0]
                if name[:1].isupper() and (value := _clean_company(name)):
                    return value
        if hint:
            return _clean_company(hint)
        for ln in lines:
            if ln.raw.lstrip().startswith("🏢") and not self._any_label(ln):
                return _clean_company(ln.display)
        for rx in (_COMPANY_ORG_RE, _COMPANY_SUFFIX_RE, _COMPANY_TEAM_RE):
            for ln in lines:
                if (m := rx.search(ln.display)) and (value := _clean_company(m.group(1))):
                    return value
        return None

    def _positions(self, lines: list[Line], post: PostInput) -> list[str]:
        # 1. "Ochiq vakansiyalar:" + items
        for i, ln in enumerate(lines):
            head = ln.body.rstrip()
            if not head.endswith(":") or not any(
                head[:-1].rstrip().endswith(h) for h in self._headers
            ):
                continue
            items: list[str] = []
            blanks = 0
            for nxt in lines[i + 1 :]:
                if not nxt.display:
                    blanks += 1
                    if blanks >= 2 and items:
                        break
                    continue
                blanks = 0
                if (
                    self._is_header(nxt)
                    or self._any_label(nxt)
                    or len(nxt.display) > MAX_PHRASE_LINE
                ):
                    break
                items.append(nxt.display)
            if (found := _clean_positions(items)) and len(found) >= 2:
                return found
        # 2. lines with their own apply links (Anorbank / hh.uz, telegra.ph per position)
        text = "\n".join(ln.raw for ln in lines)
        linked = linked_positions(text, post.extra)
        if len({u for _, u in linked}) >= 2:
            found = _clean_positions([display(t) for t, _ in linked])
            if len(found) >= 2:
                return found
        # 3. 1️⃣ SOMSA SOTUVCHI ... 2️⃣ TAJRIBALI OSHPAZ
        keycaps = [
            ln.display
            for ln in lines
            if _KEYCAP_LINE_RE.match(ln.raw)
            and len(ln.display) <= 60
            and (self.categorizer.has_profession(ln.folded) or ln.display.isupper())
        ]
        if len(found := _clean_positions(keycaps)) >= 2:
            return found
        # 4. several "... kerak" blocks (@beminnatvakant_ish: 3 schools in one post)
        # Each block must be a whole ad with its own salary or address — not "1-smena ... kerak /
        # 2-smena ... kerak" of one vacancy.
        heads: list[tuple[int, str]] = []
        for i, ln in enumerate(lines):
            if ln.blank_before:
                title, _ = self._title_from_phrase(ln)
                if title and _good_title(title) and self.categorizer.has_profession(title):
                    heads.append((i, title))
        bounds = [i for i, _ in heads] + [len(lines)]
        complete = [
            title
            for k, (i, title) in enumerate(heads)
            if any(_BLOCK_DETAIL_RE.search(ln.folded) for ln in lines[i + 1 : bounds[k + 1]])
        ]
        if len(complete) == len(heads) and len(found := _clean_positions(complete)) >= 2:
            return found
        return []

    def _salary(self, lines: list[Line]) -> Salary:
        blocks: list[SalaryBlock] = []
        labels: list[str] = []
        for i, ln in enumerate(lines):
            if lab := self._label("salary", ln):
                values = self._block(lines, i, lab[1], limit=4)
                # "Oylik: 3.000.000 dan" + next line "4.500.000 gacha"
                inline = fold(lab[1]).strip() not in EMPTY_VALUES
                if (
                    inline
                    and i + 1 < len(lines)
                    and _AMOUNT_START_RE.match(lines[i + 1].folded)
                    and not self._any_label(lines[i + 1])
                ):
                    values.append(lines[i + 1].display)
                labels.append(lab[0])
                blocks.extend(SalaryBlock(v, fold(v)) for v in values)
                continue
            if m := self._salary_inline.search(ln.folded):
                value = _money_prefix(ln.display_from(m.end("label")))
                labels.append(m.group("label"))
                blocks.append(SalaryBlock(value, fold(value)))
        labeled = self.salary.parse(blocks, " ".join(labels))
        if labeled.has_numbers:
            return labeled
        money = [
            SalaryBlock(ln.display, ln.folded, labeled=False)
            for ln in lines
            if looks_like_money(ln.folded) and not _TIME_RE.fullmatch(ln.folded.strip())
        ]
        loose = self.salary.parse(money)
        return loose if loose.has_numbers else labeled

    def _text_field(self, name: str, lines: list[Line], limit: int) -> str | None:
        for i, ln in enumerate(lines):
            if lab := self._label(name, ln):
                values = self._block(lines, i, lab[1], limit=limit)
                if values:
                    return "; ".join(v.strip(" ;,.[]") for v in values)[:500]
        return None

    def translate_title(self, title: str | None, language: Language | None) -> str | None:
        """Russian / English title -> Uzbek (config/title_translations.yaml: exact, then words)."""
        if not title or language not in (Language.RU, Language.EN):
            return title
        key = fold(title).strip(" .")
        if key in self._exact:
            return self._exact[key]
        out, changed = key, False
        for src, dst in self._words:
            new = re.sub(rf"(?<![\w']){re.escape(src)}(?![\w'])", dst, out)
            changed |= new != out
            out = new
        return (out[:1].upper() + out[1:]) if changed else title

    # ------------------------------------------------------------------ main
    def extract(self, post: PostInput) -> Extraction:
        lines = self.lines(post)
        reasons: list[str] = []
        language = detect_language(post.text)
        defaults = self.settings.source_rules.defaults
        contacts: Contacts = find_contacts(
            "\n".join(ln.display for ln in lines),
            post.extra,
            own_usernames=self._own_usernames(post),
            drop_link_patterns=defaults.drop_link_patterns,
            drop_whitespace_text_links=defaults.drop_whitespace_text_links,
            strip_url_params=defaults.strip_url_params,
            keep_case=True,
        )

        title, source, company_hint = self._title(lines)
        positions = self._positions(lines, post)
        company = self._company(lines, company_hint)
        full_text = "\n".join(ln.folded for ln in lines)
        cat: Categorization = self.categorizer.categorize(
            " | ".join(positions) if positions else title, full_text
        )
        if positions and source != "label":
            title, source = company or MULTI_TITLE, "positions"
        if not title and cat.profession:
            title, source = self._professions[cat.profession], "profession"

        salary = self._salary(lines)
        loc: Location = self.location.find([ln.folded for ln in lines])
        schedule = self._text_field("schedule", lines, limit=3)
        requirements = self._text_field("requirements", lines, limit=MAX_BLOCK_LINES)

        has_contact = bool(contacts)
        confidence = 0.0
        if title:
            confidence += 0.35 if source in ("label", "phrase", "positions") else 0.2
        if has_contact:
            confidence += 0.35
        confidence += 0.1 if salary else 0.0
        confidence += 0.1 if loc.region else 0.0
        confidence += 0.1 if (company or schedule) else 0.0
        low_quality = not title and not salary
        if low_quality:
            reasons.append("low_quality:no_title_no_salary")
        if not has_contact:
            reasons.append("no_contact")

        return Extraction(
            title=title,
            title_uz=self.translate_title(title, language) if source != "positions" else title,
            title_source=source,
            company=company,
            positions=tuple(positions),
            salary_min=salary.min,
            salary_max=salary.max,
            currency=salary.currency,
            salary_period=salary.period,
            salary_text=salary.text,
            region=loc.region,
            regions=loc.regions,
            district=loc.district,
            is_remote=loc.is_remote,
            schedule=schedule,
            requirements=requirements,
            phones=tuple(contacts.phones),
            usernames=tuple(contacts.usernames),
            emails=tuple(contacts.emails),
            apply_url=contacts.apply_url,
            category=cat.category,
            profession=cat.profession,
            feature_tags=_remote_tag(cat.feature_tags, loc.is_remote),
            language=language,
            confidence=round(min(confidence, 1.0), 2),
            low_quality=low_quality,
            reasons=tuple(reasons),
        )


# --------------------------------------------------------------------------- small helpers
_MONEY_WORD_RE = re.compile(
    r"^(?:[\d$€+\-–—.,:/()]+|(?:mln|млн|million|ming|минг|so'?m|сўм|сум|sum|usd|dollar)\w*|\$\S*|\S*\d\S*"
    r"|dan|дан|gacha|гача|ot|от|do|до|up|to|gross|net|fiks|fix|kpi|bonus\w*)[.,;]?$",
    re.IGNORECASE,
)


def _money_prefix(value: str, max_words: int = 8) -> str:
    """Salary words at the start of a sentence: ``"4.5mln sharoit+ovqat ..."`` -> ``"4.5mln"``."""
    words: list[str] = []
    for w in value.split()[:max_words]:
        if not _MONEY_WORD_RE.match(w):
            break
        words.append(w)
    return " ".join(words) or value


def _strip_bullet(text: str) -> str:
    return re.sub(r"^[\s•·\-–—*▪►➤>]+", "", text).strip()


def _clean_title(title: str | None) -> str | None:
    if not title:
        return None
    t = title.replace("#", " ").replace("_", " ")
    t = re.sub(r"\s+(?:ishga|ишга)\s*$", "", t, flags=re.IGNORECASE)  # "... xodimlar ishga"
    t = re.sub(r"^[\s•·\-–—*:.,;!]+|[\s•·\-–—*:,;!.]+$", "", t)
    t = re.sub(r"^\d{1,3}\s*(?:nafar|ta|x|чел\w*|человек)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 3 and t.isupper():  # "KASSIR" -> "Kassir", "HR / RECRUITER" -> "HR / recruiter"
        words = [w if len(w) <= 3 else w.lower() for w in t.split()]
        t = " ".join(words)
        t = t[0].upper() + t[1:]
    return t[:MAX_TITLE_LEN] or None


def _good_title(title: str) -> bool:
    f = fold(title)
    letters = sum(ch.isalpha() for ch in f)
    words = f.split()
    # "mas'uliyatli va chaqqon xodimlar", "Tajribali xodim": no position named
    return (
        letters >= 3
        and len(words) <= MAX_TITLE_WORDS
        and f not in _GENERIC_TITLES
        and words[-1].strip(".,!") not in _GENERIC_TITLES
    )


def _trim_dative(title: str) -> str:
    """``"Maktabga Ayol oshpaz"`` -> ``"Ayol oshpaz"``; ``"... startup uchun tajribali dizayner"``
    -> ``"tajribali dizayner"``: the place/purpose phrase before the position goes."""
    words = title.split()
    folded = [fold(w).strip(",.") for w in words]
    for marker in ("uchun", "для", "for"):
        if marker in folded[:-1]:
            k = len(folded) - 1 - folded[::-1].index(marker)
            if k + 1 < len(words):
                words, folded = words[k + 1 :], folded[k + 1 :]
    for k in range(len(folded) - 2, -1, -1):
        if len(folded[k]) > 4 and _PLACE_CASE_RE.search(folded[k]):
            return " ".join(words[k + 1 :])
    return " ".join(words)


def _clean_company(value: str | None) -> str | None:
    if not value:
        return None
    v = re.sub(r"^[\s«\"“„'‘`,]+|[\s»\"”'’`.,;:!]+$", "", value).strip()
    if fold(v) in EMPTY_VALUES or len(v) < 2 or fold(v).split()[0] in _NOT_COMPANY_WORDS:
        return None
    return v[:80]


def _clean_positions(items: list[str]) -> list[str]:
    out: dict[str, str] = {}
    for item in items:
        t = _strip_bullet(item)
        t = re.sub(r"^\d{1,2}\s*[.)]?\s+", "", t)  # "1 SOMSA" (keycap) / "1. Sotuvchi"
        t = re.split(r"\s\|\s", t)[0]
        # "... ta'lim (vaqtinchalik) o'qituvchilari": a short tail after ")" is part of the name;
        # "Грузчик (омбор га) кундузги смена 08:00": a long tail is details.
        if (m := re.search(r"\([^)]*\)", t)) and len(t[m.end() :].split()) <= 2:
            t = t[: m.start()] + t[m.end() :]
        t = re.split(r"\s*\(|\s[-—–]\s*(?=\d)|\s[—–]\s|:\s", t)[0]
        t = _clean_title(re.sub(r"\s+(?:kerak|керак|kk)\b.*$", "", t, flags=re.IGNORECASE))
        if t and _good_title(t) and len(t) <= 60:
            out.setdefault(fold(t), t)
    return list(out.values())


REMOTE_TAG = "masofaviy"


def _remote_tag(tags: tuple[str, ...], is_remote: bool) -> tuple[str, ...]:
    """The "masofaviy" tag follows ``is_remote`` ("Office (later Hybrid/Remote)" is not remote)."""
    rest = tuple(t for t in tags if t != REMOTE_TAG)
    return (REMOTE_TAG, *rest) if is_remote else rest


def _only_place(folded_line: str, places: KeywordSet) -> bool:
    """A line that only names a place ("SAMARQAND") is not a title."""
    return bool(places.find(folded_line)) and len(folded_line.split()) <= 3


@lru_cache(maxsize=1)
def default_extractor() -> Extractor:
    """Extractor built from the repository's ``config/`` (no ``.env`` needed)."""
    return Extractor(load_settings(DEFAULT_CONFIG_DIR, env_file=None))


def extract(post: PostInput, extractor: Extractor | None = None) -> Extraction:
    """Extract fields of one job post (album parts already merged)."""
    return (extractor or default_extractor()).extract(post)
