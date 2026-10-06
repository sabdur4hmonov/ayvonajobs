"""Optional Gemini helper (Bosqich 15). The system works 100% without it (CLAUDE.md hard rule 4).

When: a job ad (contact found by regex) whose regex ``confidence`` is below ``ai.min_confidence``,
that is Russian / English (``ai.translate_foreign``) or that regex found too little in
(``low_quality``). Never for posts without a contact.

How:
* phones, @usernames, e-mails and links are masked before sending ([PHONE] [USER] [EMAIL] [LINK]);
* structured JSON answer (title, company, category, salary, region, schedule, requirements,
  short description) — every text in Uzbek Latin;
* ``ai_cache``: the same text is never sent twice (also used by the worker's start-up re-render);
* limits: ``ai.daily_limit`` requests per Tashkent day, ``ai.min_interval_seconds`` between them;
* circuit breaker: 429 -> that key paused ``pause_minutes_rate_limited``, 5xx/timeout/network ->
  ``pause_minutes_error``; the pause DOUBLES with every failure in a row (exponential backoff, at
  most ``pause_minutes_max``; a ``Retry-After`` header is honoured) and resets after a success;
  then the regex result is used — AI never stops a job from publishing;
* the free-tier limits can be tightened from ``.env`` without touching YAML:
  ``GEMINI_DAILY_LIMIT`` and ``GEMINI_MIN_INTERVAL_SECONDS``;
* keys: ``GEMINI_API_KEY``; ``GEMINI_API_KEYS`` are used only with
  ``GEMINI_ALLOW_KEY_ROTATION=true`` (default OFF: several accounts to get around Google's limits
  may break Google's terms — docs/PROGRESS.md);
* quality check: no Cyrillic, a real title, no English left in a longer text, no masks; else
  the AI answer is dropped. Contacts ALWAYS come from regex (the AI never sees them).
* the admin switches it off / on from the bot (/ai, ``kv_store ai:disabled``) — no code or YAML.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.ai.client import (
    AIAuthError,
    AIBadResponse,
    AIError,
    AIRateLimited,
    GeminiClient,
)
from ayvona.config import AIConfig, Settings
from ayvona.db.models import AICache
from ayvona.db.repositories import kv_repo
from ayvona.processing.extract import Extraction
from ayvona.processing.language import Language, detect_language
from ayvona.timeutil import to_local, utcnow

PROMPT_VERSION = 1
DISABLED_KEY = "ai:disabled"
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
_MASK_TOKEN_RE = re.compile(r"\[(?:PHONE|USER|EMAIL|LINK)\]")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:t\.me|telegram\.me)/\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.%+\-]+@[\w.\-]+\.[a-z]{2,}\b", re.IGNORECASE)
_USER_RE = re.compile(r"(?<![\w@])@[a-z][a-z0-9_]{3,31}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\s?998[\s\-.]?)?\(?\d{2}\)?(?:[\s\-.]?\d){7}(?!\d)")
CURRENCIES = ["UZS", "USD", "EUR", "RUB"]
PERIODS = ["month", "week", "day", "hour"]

SYSTEM = (
    "Sen O'zbekistondagi ish e'lonlarini tahlil qiluvchi yordamchisan. Senga Telegram kanal yoki "
    "saytdan olingan bitta e'lon matni beriladi (o'zbek, rus yoki ingliz tilida). Faqat berilgan "
    "JSON sxema bo'yicha javob ber.\n"
    "Qoidalar:\n"
    "1. BARCHA matnli maydonlar faqat O'ZBEK tilida, LOTIN alifbosida (o' g' sh ch). Kirill harfi "
    "umuman bo'lmasin. Ruscha/inglizcha matnni tabiiy o'zbek tiliga tarjima qil.\n"
    "2. Matnda yo'q narsani to'qima: topilmasa null.\n"
    "3. [PHONE], [USER], [EMAIL], [LINK] — yashirilgan aloqalar; ularni javobga yozma.\n"
    "4. title — qisqa lavozim nomi (masalan: 'Sotuv menejeri'). requirements — talablar va "
    "vazifalar, qisqa, ';' bilan. short_description — 1-2 gaplik qisqa mazmun.\n"
    "5. Maosh: salary_min/salary_max butun son (asl valyutada), currency, salary_period (month, "
    "week, day, hour). Son bo'lmasa salary_text ga o'zbekcha yoz (masalan 'Kelishiladi').\n"
    "6. category va region faqat ruxsat etilgan ro'yxatdan; mos kelmasa null.\n"
    "7. is_job — haqiqiy ish e'loni bo'lsa true (reklama, kurs, rezyume bo'lsa false)."
)


# --------------------------------------------------------------------------- helpers
def _with_env_limits(settings: Settings) -> AIConfig:
    """``settings.app.ai`` with ``GEMINI_DAILY_LIMIT`` / ``GEMINI_MIN_INTERVAL_SECONDS`` applied
    (.env wins over YAML, so the free-tier cap can be changed on the server without a commit)."""
    cfg = settings.app.ai
    update: dict[str, Any] = {}
    if settings.env.gemini_daily_limit is not None:
        update["daily_limit"] = settings.env.gemini_daily_limit
    if settings.env.gemini_min_interval_seconds is not None:
        update["min_interval_seconds"] = settings.env.gemini_min_interval_seconds
    return cfg.model_copy(update=update) if update else cfg


def mask(text: str) -> str:
    """Contacts never leave the machine."""
    text = _URL_RE.sub("[LINK]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _USER_RE.sub("[USER]", text)
    return _PHONE_RE.sub("[PHONE]", text)


def schema(settings: Settings) -> dict[str, Any]:
    def s(nullable: bool = True, enum: list[str] | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"type": "STRING", "nullable": nullable}
        if enum:
            out["enum"] = enum
        return out

    integer = {"type": "INTEGER", "nullable": True}
    return {
        "type": "OBJECT",
        "properties": {
            "is_job": {"type": "BOOLEAN"},
            "title": s(False),
            "company": s(),
            "category": s(enum=list(settings.categories)),
            "salary_min": integer,
            "salary_max": integer,
            "currency": s(enum=CURRENCIES),
            "salary_period": s(enum=PERIODS),
            "salary_text": s(),
            "region": s(enum=list(settings.regions.regions)),
            "city": s(),
            "is_remote": {"type": "BOOLEAN"},
            "schedule": s(),
            "requirements": s(),
            "short_description": s(),
        },
        "required": ["is_job", "title", "category"],
    }


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(_MASK_TOKEN_RE.sub(" ", value).split()).strip(" ;,.-")
    return value[:limit] if value else None


def _int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


@dataclass(frozen=True, slots=True)
class AIResult:
    is_job: bool
    title: str | None
    company: str | None
    category: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    salary_period: str | None
    salary_text: str | None
    region: str | None
    city: str | None
    is_remote: bool
    schedule: str | None
    requirements: str | None
    short_description: str | None

    @classmethod
    def parse(cls, data: dict[str, Any], settings: Settings) -> AIResult:
        cat = data.get("category")
        reg = data.get("region")
        cur = data.get("currency")
        per = data.get("salary_period")
        lo, hi = _int(data.get("salary_min")), _int(data.get("salary_max"))
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        return cls(
            is_job=bool(data.get("is_job", True)),
            title=_text(data.get("title"), 120),
            company=_text(data.get("company"), 120),
            category=cat if cat in settings.categories else None,
            salary_min=lo,
            salary_max=hi,
            currency=cur if cur in CURRENCIES and (lo or hi) else None,
            salary_period=per if per in PERIODS else None,
            salary_text=_text(data.get("salary_text"), 80),
            region=reg if reg in settings.regions.regions else None,
            city=_text(data.get("city"), 120),
            is_remote=bool(data.get("is_remote", False)),
            schedule=_text(data.get("schedule"), 120),
            requirements=_text(data.get("requirements"), 600),
            short_description=_text(data.get("short_description"), 400),
        )

    def texts(self) -> list[str]:
        return [
            t
            for t in (
                self.title,
                self.company,
                self.salary_text,
                self.city,
                self.schedule,
                self.requirements,
                self.short_description,
            )
            if t
        ]

    def quality_problem(self) -> str | None:
        """Why the answer must not be used, or ``None`` if it is fine."""
        if not self.title or sum(ch.isalpha() for ch in self.title) < 3:
            return "lavozim yo'q"
        joined = "\n".join(self.texts())
        if _CYRILLIC_RE.search(joined):
            return "kirill harflar qoldi"
        body = " ".join(t for t in (self.requirements, self.short_description) if t)
        if len(body) >= 80 and detect_language(body) is Language.EN:
            return "tarjima qilinmagan (inglizcha)"
        return None


def merge(ex: Extraction, r: AIResult, *, foreign: bool) -> Extraction:
    """The regex extraction improved with the AI answer. Contacts are always the regex ones."""

    def latin(value: str | None) -> str | None:
        return value if value and not _CYRILLIC_RE.search(value) else None

    has_numbers = ex.salary_min is not None or ex.salary_max is not None
    use_ai_salary = not has_numbers and (r.salary_min or r.salary_max) and r.currency
    requirements = "; ".join(t for t in (r.requirements, r.short_description) if t) or None
    return replace(
        ex,
        title=r.title,
        title_uz=None,
        title_source="ai",
        company=r.company or latin(ex.company),
        positions=() if foreign else ex.positions,
        category=r.category or ex.category,
        profession=ex.profession if r.category in (None, ex.category) else None,
        salary_min=r.salary_min if use_ai_salary else ex.salary_min,
        salary_max=r.salary_max if use_ai_salary else ex.salary_max,
        currency=r.currency if use_ai_salary else ex.currency,
        salary_period=(r.salary_period or "month") if use_ai_salary else ex.salary_period,
        salary_text=r.salary_text if not has_numbers else latin(ex.salary_text),
        region=ex.region or r.region,
        address=r.city if foreign else (latin(ex.address) or r.city),
        is_remote=ex.is_remote or r.is_remote,
        schedule=r.schedule or latin(ex.schedule),
        requirements=(requirements[:600] if requirements else None) or latin(ex.requirements),
        language=Language.UZ_LATIN,
        confidence=max(ex.confidence, 0.9),
        low_quality=False,
        ai_used=True,
    )


# --------------------------------------------------------------------------- state
def _day(settings: Settings, now: datetime) -> str:
    return to_local(now, settings.timezone).date().isoformat()


async def _incr(session: AsyncSession, key: str) -> int:
    n = int(await kv_repo.get(session, key) or 0) + 1
    await kv_repo.set_value(session, key, str(n))
    return n


async def set_admin_disabled(session: AsyncSession, disabled: bool) -> None:
    """/ai: the admin's runtime switch (kv_store). Does not commit."""
    await kv_repo.set_bool(session, DISABLED_KEY, disabled)


@dataclass(slots=True)
class AIStatus:
    configured: bool  # a key in .env
    config_enabled: bool  # settings.yaml ai.enabled
    admin_disabled: bool  # /ai off
    model: str
    keys: int
    rotation: bool
    calls_today: int = 0
    ok_today: int = 0
    failed_today: int = 0
    cache_hits_today: int = 0
    daily_limit: int = 0
    paused: list[str] = field(default_factory=list)  # "kalit 1: 14:05 gacha"
    cached_total: int = 0

    @property
    def active(self) -> bool:
        return self.configured and self.config_enabled and not self.admin_disabled


class AIHelper:
    def __init__(
        self,
        settings: Settings,
        sf: async_sessionmaker[AsyncSession],
        client: GeminiClient | None = None,
    ) -> None:
        self.settings = settings
        self.cfg = _with_env_limits(settings)
        self.sf = sf
        self.keys = self.api_keys(settings)
        self.model = settings.env.gemini_model
        self.client = client or GeminiClient(self.model, timeout=self.cfg.timeout_seconds)
        self._schema = schema(settings)
        self._last_call = 0.0
        self._cap_logged_day = ""

    @staticmethod
    def api_keys(settings: Settings) -> list[str]:
        env = settings.env
        keys = [env.gemini_api_key.get_secret_value()] if env.gemini_api_key else []
        if env.gemini_allow_key_rotation and env.gemini_api_keys:
            keys += [
                k.strip() for k in env.gemini_api_keys.get_secret_value().split(",") if k.strip()
            ]
        return list(dict.fromkeys(k for k in keys if k))

    # ------------------------------------------------------------------ status
    async def status(self, now: datetime | None = None) -> AIStatus:
        now = now or utcnow()
        day = _day(self.settings, now)
        async with self.sf() as s:
            st = AIStatus(
                configured=bool(self.keys),
                config_enabled=self.cfg.enabled,
                admin_disabled=await kv_repo.get_bool(s, DISABLED_KEY),
                model=self.model,
                keys=len(self.keys),
                rotation=self.settings.env.gemini_allow_key_rotation,
                calls_today=int(await kv_repo.get(s, f"ai:calls:{day}") or 0),
                ok_today=int(await kv_repo.get(s, f"ai:ok:{day}") or 0),
                failed_today=int(await kv_repo.get(s, f"ai:fail:{day}") or 0),
                cache_hits_today=int(await kv_repo.get(s, f"ai:cache:{day}") or 0),
                daily_limit=self.cfg.daily_limit,
                cached_total=int(await s.scalar(select(func.count()).select_from(AICache)) or 0),
            )
            for i in range(len(self.keys)):
                until = await kv_repo.get_time(s, f"ai:pause:{i}")
                if until is not None and until > now:
                    local = to_local(until, self.settings.timezone)
                    st.paused.append(f"kalit {i + 1}: {local:%H:%M} gacha")
        return st

    def wanted(self, ex: Extraction) -> bool:
        foreign = ex.language in (Language.RU, Language.EN)
        return (
            ex.confidence < self.cfg.min_confidence
            or ex.low_quality
            or (self.cfg.translate_foreign and foreign)
        )

    # ------------------------------------------------------------------ main
    async def enhance(
        self,
        text: str,
        ex: Extraction,
        *,
        cache_only: bool = False,
        now: datetime | None = None,
    ) -> Extraction | None:
        """The improved extraction, or ``None`` (not needed / off / limit / error / bad answer)
        — then the caller keeps the regex result."""
        if not self.keys or not self.cfg.enabled or not self.wanted(ex):
            return None
        now = now or utcnow()
        masked = mask(text)[: self.cfg.max_input_chars]
        text_hash = hashlib.sha256(f"{PROMPT_VERSION}|{self.model}|{masked}".encode()).hexdigest()
        foreign = ex.language in (Language.RU, Language.EN)
        day = _day(self.settings, now)

        async with self.sf() as s:
            if await kv_repo.get_bool(s, DISABLED_KEY):
                return None
            cached = await s.get(AICache, text_hash)
        if cached is not None:
            async with self.sf() as s, s.begin():
                await _incr(s, f"ai:cache:{day}")
            return self._use(ex, cached.response_json, foreign, "kesh")
        if cache_only:
            return None

        data = await self._call(masked, now, day)
        if data is None:
            return None
        async with self.sf() as s, s.begin():
            await s.execute(
                sqlite_insert(AICache)
                .values(text_hash=text_hash, model=self.model, response_json=data, created_at=now)
                .on_conflict_do_nothing()
            )
        return self._use(ex, data, foreign, "javob")

    def _use(
        self, ex: Extraction, data: dict[str, Any], foreign: bool, where: str
    ) -> Extraction | None:
        result = AIResult.parse(data, self.settings)
        if problem := result.quality_problem():
            logger.info("AI {} ishlatilmadi: {}", where, problem)
            return None
        if not result.is_job:
            logger.info("AI: '{}' e'lon emas deb hisobladi — regex qarori qoladi", result.title)
        return merge(ex, result, foreign=foreign)

    async def _call(self, masked: str, now: datetime, day: str) -> dict[str, Any] | None:
        async with self.sf() as s, s.begin():
            calls = int(await kv_repo.get(s, f"ai:calls:{day}") or 0)
            if calls >= self.cfg.daily_limit:
                if self._cap_logged_day != day:
                    self._cap_logged_day = day
                    logger.info(
                        "AI: kunlik limit tugadi ({}/{}) — ertagacha hammasi regex bilan",
                        calls,
                        self.cfg.daily_limit,
                    )
                return None
            key_index = None
            for i in range(len(self.keys)):
                until = await kv_repo.get_time(s, f"ai:pause:{i}")
                if until is None or until <= now:
                    key_index = i
                    break
            if key_index is None:
                return None
            await _incr(s, f"ai:calls:{day}")

        wait = self.cfg.min_interval_seconds - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        prompt = f"E'lon matni:\n{masked}"
        try:
            data = await self.client.generate_json(
                self.keys[key_index], SYSTEM, prompt, self._schema
            )
        except AIError as e:
            await self._failed(key_index, e, now, day)
            return None
        async with self.sf() as s, s.begin():
            await _incr(s, f"ai:ok:{day}")
            if await kv_repo.get(s, f"ai:streak:{key_index}"):
                await kv_repo.set_value(s, f"ai:streak:{key_index}", "0")  # backoff starts over
        return data

    async def _failed(self, key_index: int, e: AIError, now: datetime, day: str) -> None:
        backoff = not isinstance(e, AIAuthError | AIBadResponse)
        streak_key = f"ai:streak:{key_index}"
        streak = 0
        if backoff:
            async with self.sf() as s, s.begin():
                streak = int(await kv_repo.get(s, streak_key) or 0) + 1
                await kv_repo.set_value(s, streak_key, str(streak))
        if isinstance(e, AIAuthError):
            pause = timedelta(hours=6)  # wrong key / model: no point retrying soon
        elif isinstance(e, AIBadResponse):
            pause = timedelta(0)
        else:
            base = (
                self.cfg.pause_minutes_rate_limited
                if isinstance(e, AIRateLimited)
                else self.cfg.pause_minutes_error
            )
            minutes = min(base * 2 ** min(streak - 1, 10), self.cfg.pause_minutes_max)
            retry_after = getattr(e, "retry_after", None)
            if retry_after:  # the server said how long: never come back earlier than that
                minutes = max(minutes, min(retry_after / 60, 24 * 60))
            pause = timedelta(minutes=minutes)
        async with self.sf() as s, s.begin():
            await _incr(s, f"ai:fail:{day}")
            if pause:
                await kv_repo.set_value(s, f"ai:pause:{key_index}", (now + pause).isoformat())
        logger.warning(
            "AI xatosi (kalit {}): {} — regex natijasi ishlatiladi{}",
            key_index + 1,
            e,
            f", kalit {int(pause.total_seconds() // 60)} daqiqa dam oladi" if pause else "",
        )
