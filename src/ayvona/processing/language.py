"""Detect the language / script of a post: ``uz_latin | uz_cyrillic | ru | en``.

Cheap and dependency-free: count letters per script, then within the winning script count
typical words. Uzbek Cyrillic has its own letters (ў қ ғ ҳ) and function words (учун, билан, ва),
so it is not confused with Russian (для, и, в, работа).
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class Language(StrEnum):
    UZ_LATIN = "uz_latin"
    UZ_CYRILLIC = "uz_cyrillic"
    RU = "ru"
    EN = "en"


UZ_CYRILLIC_LETTERS = frozenset("ўқғҳ")

# Frequent words. Lower case; Uzbek apostrophes already unified to "'".
_UZ_CYR_WORDS = frozenset(
    """
    ва учун билан керак иш ишга ишчи ойлик маош маоши тажриба тажрибаси манзил талаблар ёки ҳам хам
    эмас бор йўқ йук қилиш килиш вақти вакти вакт дан гача шаҳар шахар шахри тумани туман ҳисобидан
    хисобидан мавжуд бошланади мурожаат исмим биз сиз бўлиш булиш бўлган булган бўйича буйича
    таклиф киламиз қиламиз қилинади килинади келиш ёш ёшгача ёшдан ҳақи хаки керакли
    ишлаш ишлайдиган билади биладиган жой жойи жойлашган аёл эркак йигитлар қизлар кизлар
    ўқитувчи укитувчи ташкилот ташкилоти корхона корхонаси компания компанияси сўм сум ойига
    лавозим фақат факат яхши бир нечта ҳар хар кун кунлик соат
    """.split()
)
_RU_WORDS = frozenset(
    """
    и в на с по для от до не что это как мы вы или а но же при без из к у о об за
    работа работы работе опыт опытом зарплата заработная плата требования обязанности условия
    график компания компании ищем требуется вакансия сотрудник сотрудников знание знания
    умение навыки резюме оформление официальное трудоустройство обучение возможность
    чтобы место где который которые будет будем если ты тебя вас нас наш наша
    """.split()
)
_UZ_LAT_WORDS = frozenset(
    """
    va uchun bilan kerak ish ishga ishchi oylik maosh maoshi tajriba tajribasi manzil talablar
    yoki ham emas bor yo'q qilish vaqti dan gacha shahar shahri tumani hisobidan mavjud boshlanadi
    murojaat biz siz bo'lish bo'lgan bo'yicha taklif qilamiz qilinadi yosh yoshgacha haqi
    ishlash kerakli joy joyi ayol erkak yigitlar qizlar o'qituvchi tashkilot kompaniya kompaniyasi
    so'm som lavozim faqat yaxshi bir necha har kun kunlik soat bog'lanish aloqa
    beriladi to'lanadi ega bo'lishi shart asosida kelishiladi kelishilgan ma'lumot
    """.split()
)
_EN_WORDS = frozenset(
    """
    the and of to in for with we are you is our a an be as on at by from your will this that
    experience requirements salary job work company looking position skills team apply contact
    responsibilities required knowledge ability years location schedule english write via
    """.split()
)

_WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
_APOSTROPHES = str.maketrans({c: "'" for c in "‘’ʻʼ`´"})


def _prep(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_APOSTROPHES).lower()


def _is_cyrillic(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def cyrillic_scores(text: str) -> tuple[int, int]:
    """``(uzbek, russian)`` evidence in the Cyrillic part of an already lower-cased text."""
    uz = sum(1 for ch in text if ch in UZ_CYRILLIC_LETTERS)
    ru = 0
    for w in _WORD_RE.findall(text):
        if not _is_cyrillic(w[0]):
            continue
        if w in _UZ_CYR_WORDS:
            uz += 1
        elif w in _RU_WORDS:
            ru += 1
        elif "ы" in w or "щ" in w:  # letters Uzbek Cyrillic does not use
            ru += 1
    return uz, ru


def is_uzbek_cyrillic(text: str) -> bool:
    """True if the Cyrillic in ``text`` looks Uzbek rather than Russian."""
    uz, ru = cyrillic_scores(_prep(text))
    return uz > 0 and uz >= ru


def detect_language(text: str) -> Language:
    """Main language of a post. Ties go to Uzbek (our main audience)."""
    t = _prep(text)
    cyr = sum(1 for ch in t if _is_cyrillic(ch))
    lat = sum(1 for ch in t if "a" <= ch <= "z")
    if cyr > lat:
        uz, ru = cyrillic_scores(t)
        return Language.UZ_CYRILLIC if uz >= ru else Language.RU
    uz = en = 0
    for w in _WORD_RE.findall(t):
        if w in _UZ_LAT_WORDS:
            uz += 1
        elif w in _EN_WORDS:
            en += 1
    return Language.EN if en > uz else Language.UZ_LATIN
