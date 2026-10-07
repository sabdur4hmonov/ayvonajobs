"""📢 E'lon joylash: a job submitted by a user through the bot form (later the website too).

Everything that decides something lives here; the bot handler only asks the questions.

* :class:`Draft` — the answers of the form (kept in the FSM between steps as a dict);
* field helpers: :func:`clean_field`, :func:`parse_contact`, :func:`phone_from_contact`;
* :func:`render` — the channel caption (the same Formatter as the aggregator: Uzbek Latin);
* checks: limits (per day / interval / waiting), ban words and spam signs -> rejected,
  scam words -> admin review, duplicates -> rejected;
* :func:`submit` -> ``jobs`` row (``origin=user``) ``queued`` or ``pending_review``;
* :func:`approve` / :func:`reject` — the admin's decision.

Hard rule 7: a user job always has a phone (+998...) or a @username — :func:`submit` refuses
otherwise, and the ``jobs`` table has a CHECK constraint for it too.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ayvona.config import FALLBACK_CATEGORY, Settings
from ayvona.db.models import (
    FilterKind,
    FilterWord,
    Job,
    JobKind,
    JobOrigin,
    JobStatus,
    ParseMethod,
    User,
)
from ayvona.processing.categorize import Categorizer
from ayvona.processing.contacts import find_phones, find_urls, find_usernames
from ayvona.processing.dedup import DedupIndex, make_entry
from ayvona.processing.extract import Extraction
from ayvona.processing.formatter import FormattedPost, Formatter
from ayvona.processing.keywords import KeywordSet
from ayvona.processing.language import detect_language
from ayvona.processing.normalize import fold, normalize, search_text
from ayvona.processing.pipeline import buttons_json
from ayvona.processing.priority import PriorityScorer
from ayvona.processing.project_format import Budget, ProjectPost, format_project, parse_budget
from ayvona.processing.salary import SalaryBlock, SalaryParser
from ayvona.services.users import TRUST_ADMIN, TRUST_NEW, TRUST_TRUSTED
from ayvona.timeutil import ensure_utc

REMOTE = "remote"  # Draft.region value for "Masofaviy"
WAITING = (JobStatus.PENDING_REVIEW, JobStatus.QUEUED, JobStatus.SENDING, JobStatus.RETRY)
ACCEPTED = (
    JobStatus.QUEUED,
    JobStatus.SENDING,
    JobStatus.RETRY,
    JobStatus.PUBLISHED,
    JobStatus.CLOSED,
    JobStatus.EXPIRED,
)
_EMOJI_RE = re.compile("[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff⭐⭕‼⁉]")
_USERNAME_ONLY_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{4,31})$")


# --------------------------------------------------------------------------- draft
@dataclass(slots=True)
class Draft:
    category: str = ""
    title: str = ""
    company: str | None = None
    salary: str | None = None  # None = "Kelishiladi"
    region: str | None = None  # regions.yaml key or REMOTE
    city: str | None = None
    schedule: str | None = None
    requirements: str | None = None
    phone: str | None = None  # +998XXXXXXXXX
    username: str | None = None  # @name
    days: int | None = None  # how long the ad stays active (posting.duration_options)
    # Loyiha (one-time paid project): kind == "project"; uses title, description, budget,
    # deadline, phone / username and days. A normal job leaves them empty.
    kind: str = JobKind.JOB.value
    description: str | None = None
    budget: str | None = None  # as typed: "3 mln so'm", "$300"; None = "Kelishiladi"
    deadline: str | None = None  # as typed: "2 hafta", "15-noyabrgacha"

    @property
    def is_project(self) -> bool:
        return self.kind == JobKind.PROJECT.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Draft:
        names = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in names})

    @property
    def has_contact(self) -> bool:
        return bool(self.phone or self.username)

    def text(self) -> str:
        """Everything the user typed, one field per line (filters, duplicates, search)."""
        parts = [
            self.title,
            self.company,
            self.salary,
            self.city,
            self.schedule,
            self.requirements,
            self.description,
            self.budget,
            self.deadline,
            self.phone,
            self.username,
        ]
        return "\n".join(p for p in parts if p)


def clean_field(text: str | None, limit: int) -> str | None:
    """Trim spaces, collapse blank lines. ``None`` if empty or longer than ``limit``."""
    if text is None:
        return None
    value = "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())
    if not value or len(value) > limit:
        return None
    return value


def phone_from_contact(raw: str) -> str | None:
    """A phone shared with the "📱 Raqamni yuborish" button: ``998901234567`` / ``+998...``.
    Only Uzbek numbers (+998) are accepted."""
    digits = re.sub(r"\D", "", raw)
    return f"+{digits}" if digits.startswith("998") and len(digits) == 12 else None


def parse_contact(text: str) -> tuple[str | None, str | None]:
    """Typed contact: ``+998 90 123 45 67`` and/or ``@username`` -> (phone, username)."""
    phones = find_phones(text)
    users = find_usernames(text, keep_case=True)
    if not users and (m := _USERNAME_ONLY_RE.match(text.strip())) and not phones:
        users = ["@" + m.group(1)]
    return (phones[0] if phones else None), (users[0] if users else None)


def username_of(tg_username: str | None) -> str | None:
    """The Telegram username of the user as a contact ("@username'imni ishlat")."""
    return f"@{tg_username}" if tg_username else None


# --------------------------------------------------------------------------- rendering
_TOOLS: dict[int, tuple[Settings, Formatter, SalaryParser, Categorizer]] = {}


_SCORERS: dict[int, tuple[Settings, PriorityScorer]] = {}


def _scorer(settings: Settings) -> PriorityScorer:
    cached = _SCORERS.get(id(settings))
    if cached is None or cached[0] is not settings:
        if len(_SCORERS) > 8:
            _SCORERS.clear()
        cached = (settings, PriorityScorer(settings))
        _SCORERS[id(settings)] = cached
    return cached[1]


def _tools(settings: Settings) -> tuple[Formatter, SalaryParser, Categorizer]:
    """Built once per Settings object (Settings is not hashable, so keyed by id)."""
    cached = _TOOLS.get(id(settings))
    if cached is None or cached[0] is not settings:
        if len(_TOOLS) > 8:
            _TOOLS.clear()
        cached = (
            settings,
            Formatter(settings),
            SalaryParser(settings.extract),
            Categorizer(settings.categories, settings.feature_tags, settings.negation_words),
        )
        _TOOLS[id(settings)] = cached
    return cached[1], cached[2], cached[3]


def extraction(draft: Draft, settings: Settings) -> Extraction:
    """The draft as an :class:`Extraction`, so the aggregator's Formatter renders it."""
    formatter, salary_parser, categorizer = _tools(settings)
    del formatter
    sal = (
        salary_parser.parse([SalaryBlock(display=draft.salary, folded=fold(draft.salary))])
        if draft.salary
        else None
    )
    cat = categorizer.categorize(draft.title, draft.text())
    profession = cat.profession if cat.category == draft.category else None
    remote = draft.region == REMOTE
    return Extraction(
        title=draft.title,
        title_source="form",
        company=draft.company,
        salary_min=sal.min if sal else None,
        salary_max=sal.max if sal else None,
        currency=sal.currency if sal else None,
        salary_period=sal.period if sal else None,
        salary_text=(sal.text if sal else None) or draft.salary,
        region=None if remote else draft.region,
        address=draft.city,
        is_remote=remote,
        schedule=draft.schedule,
        requirements=draft.requirements,
        phones=(draft.phone,) if draft.phone else (),
        usernames=(draft.username,) if draft.username else (),
        category=draft.category if draft.category in settings.categories else FALLBACK_CATEGORY,
        profession=profession,
        feature_tags=cat.feature_tags,
        language=detect_language(draft.text()),
        confidence=1.0,
    )


def render(
    draft: Draft, settings: Settings
) -> tuple[FormattedPost | ProjectPost, Extraction | None]:
    """The caption exactly as it will be in the channel (Uzbek Latin). A job is rendered by the
    aggregator's Formatter; a project by ``project_format`` (``Extraction`` is ``None`` then)."""
    if draft.is_project:
        return render_project(draft, settings), None
    ex = extraction(draft, settings)
    return _tools(settings)[0].format(ex), ex


def render_project(draft: Draft, settings: Settings) -> ProjectPost:
    return format_project(
        title=draft.title,
        description=draft.description,
        budget=parse_budget(draft.budget, settings),
        deadline=draft.deadline,
        phone=draft.phone,
        username=draft.username,
        settings=settings,
    )


# --------------------------------------------------------------------------- checks
class Verdict(StrEnum):
    OK = "ok"
    BAN = "ban"  # rejected
    SPAM = "spam"  # rejected
    SCAM = "scam"  # admin review


@dataclass(frozen=True, slots=True)
class ContentCheck:
    verdict: Verdict
    reason: str = ""


async def filter_words(session: AsyncSession) -> dict[FilterKind, list[str]]:
    """Words the admin added with /addword (on top of config/filters.yaml)."""
    out: dict[FilterKind, list[str]] = {k: [] for k in FilterKind}
    for w in (await session.scalars(select(FilterWord))).all():
        out[w.kind].append(w.word)
    return out


def check_content(
    text: str, settings: Settings, extra: dict[FilterKind, list[str]] | None = None
) -> ContentCheck:
    """Ban words / spam -> rejected; scam words -> admin review."""
    extra = extra or {}
    cfg = settings.app.posting
    filters = settings.filters
    folded = fold(text)
    if hits := KeywordSet([*filters.ban, *extra.get(FilterKind.BAN, [])]).find(folded):
        return ContentCheck(Verdict.BAN, ", ".join(sorted(hits)))
    if hits := KeywordSet([*filters.spam, *extra.get(FilterKind.SPAM, [])]).find(folded):
        return ContentCheck(Verdict.SPAM, ", ".join(sorted(hits)))
    links = len(find_urls(text))
    if links > cfg.max_links:
        return ContentCheck(Verdict.SPAM, f"havolalar: {links}")
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= 20:
        caps = sum(ch.isupper() for ch in letters) / len(letters)
        if caps > cfg.max_caps_ratio:
            return ContentCheck(Verdict.SPAM, f"katta harflar: {round(caps * 100)}%")
    emoji = len(_EMOJI_RE.findall(text))
    if emoji > cfg.max_emoji:
        return ContentCheck(Verdict.SPAM, f"emoji: {emoji}")
    without_exceptions = KeywordSet(filters.scam_exceptions).remove(folded)
    if hits := KeywordSet([*filters.scam, *extra.get(FilterKind.SCAM, [])]).find(
        without_exceptions
    ):
        return ContentCheck(Verdict.SCAM, ", ".join(sorted(hits)))
    return ContentCheck(Verdict.OK)


class LimitReason(StrEnum):
    DAILY = "daily"
    INTERVAL = "interval"
    WAITING = "waiting"


@dataclass(frozen=True, slots=True)
class LimitHit:
    reason: LimitReason
    minutes: int = 0  # INTERVAL: how long to wait


async def check_limits(
    session: AsyncSession, user: User, now: datetime, settings: Settings
) -> LimitHit | None:
    """``None`` if the user may post now. Admins have no limits."""
    if user.trust_level >= TRUST_ADMIN:
        return None
    cfg = settings.app.posting
    mine = (Job.origin == JobOrigin.USER, Job.author_id == user.tg_id)
    waiting = await session.scalar(
        select(func.count()).select_from(Job).where(*mine, Job.status.in_(WAITING))
    )
    if (waiting or 0) >= cfg.max_waiting:
        return LimitHit(LimitReason.WAITING)
    day = await session.scalar(
        select(func.count())
        .select_from(Job)
        .where(*mine, Job.created_at >= now - timedelta(hours=24))
    )
    if (day or 0) >= cfg.max_per_day:
        return LimitHit(LimitReason.DAILY)
    last = await session.scalar(select(func.max(Job.created_at)).where(*mine))
    if last is not None and cfg.min_interval_minutes > 0:
        left = ensure_utc(last) + timedelta(minutes=cfg.min_interval_minutes) - now
        if left > timedelta(0):
            return LimitHit(LimitReason.INTERVAL, max(math.ceil(left.total_seconds() / 60), 1))
    return None


async def find_duplicate(
    session: AsyncSession, draft: Draft, now: datetime, settings: Settings
) -> int | None:
    """An earlier job (any origin, not rejected) the draft repeats, within ``duplicate_days``."""
    window = timedelta(days=settings.app.posting.duplicate_days)
    rows = (
        await session.execute(
            select(
                Job.id,
                Job.title,
                Job.description,
                Job.contact_phone,
                Job.contact_username,
                Job.created_at,
            ).where(
                Job.created_at >= now - window,
                Job.status.not_in((JobStatus.REJECTED,)),
            )
        )
    ).all()
    index = DedupIndex(window=window + timedelta(days=1))
    for job_id, title, description, phone, username, created in rows:
        contacts = [c for c in (phone, username) if c]
        index.add(
            make_entry(
                job_id,
                ensure_utc(created),
                normalize(description or title or ""),
                contacts,
                title=title,
            )
        )
    contacts = [c for c in (draft.phone, draft.username) if c]
    entry = make_entry("new", now, normalize(draft.text()), contacts, title=draft.title)
    match = index.find(entry)
    return int(match.matched) if match else None  # type: ignore[call-overload]


# --------------------------------------------------------------------------- submit
class Outcome(StrEnum):
    QUEUED = "queued"  # goes to the channel automatically
    REVIEW = "review"  # an admin must approve first
    REJECTED = "rejected"  # ban words / spam — no row written
    DUPLICATE = "duplicate"  # no row written
    LIMIT = "limit"  # no row written
    NO_CONTACT = "no_contact"  # no row written (hard rule 7)


@dataclass(frozen=True, slots=True)
class SubmitResult:
    outcome: Outcome
    job_id: int | None = None
    reason: str = ""
    limit: LimitHit | None = None
    review_reasons: tuple[str, ...] = field(default=())


def _review_reasons(
    user: User, check: ContentCheck, earlier_accepted: int, settings: Settings
) -> list[str]:
    mode = settings.app.posting.moderation
    if user.trust_level >= TRUST_ADMIN:
        return []
    reasons: list[str] = []
    if check.verdict is Verdict.SCAM:
        reasons.append(f"shubhali so'zlar: {check.reason}")
    if mode == "all":
        reasons.append("hamma e'lonlar tekshiriladi (moderation: all)")
    elif mode == "suspicious_only" and user.trust_level <= TRUST_NEW and not earlier_accepted:
        reasons.append("yangi foydalanuvchining birinchi e'loni")
    return reasons


async def submit(
    session: AsyncSession, draft: Draft, user: User, now: datetime, settings: Settings
) -> SubmitResult:
    """Check everything and write the job. Does not commit."""
    if not draft.has_contact:
        return SubmitResult(Outcome.NO_CONTACT)
    if hit := await check_limits(session, user, now, settings):
        return SubmitResult(Outcome.LIMIT, limit=hit)
    check = check_content(draft.text(), settings, await filter_words(session))
    if check.verdict in (Verdict.BAN, Verdict.SPAM):
        return SubmitResult(Outcome.REJECTED, reason=f"{check.verdict}: {check.reason}")
    if (dup := await find_duplicate(session, draft, now, settings)) is not None:
        return SubmitResult(Outcome.DUPLICATE, job_id=dup)

    accepted = await session.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.origin == JobOrigin.USER,
            Job.author_id == user.tg_id,
            Job.status.in_(ACCEPTED),
        )
    )
    reasons = _review_reasons(user, check, accepted or 0, settings)
    out, ex = render(draft, settings)
    days = draft.days if draft.days in settings.app.posting.duration_options else None
    if isinstance(out, ProjectPost):
        job = _project_row(draft, out, parse_budget(draft.budget, settings), days, settings)
    else:
        assert ex is not None
        job = Job(
            origin=JobOrigin.USER,
            title=draft.title[:255],
            company=draft.company,
            category=ex.category,
            profession=ex.profession,
            salary_min=ex.salary_min,
            salary_max=ex.salary_max,
            currency=ex.currency,
            salary_period=ex.salary_period,
            salary_text=(ex.salary_text or None) and ex.salary_text[:255],
            region=ex.region,
            city=(draft.city or None) and draft.city[:128],
            is_remote=ex.is_remote,
            schedule=draft.schedule,
            requirements=draft.requirements,
            description=draft.text(),
            contact_phone=draft.phone,
            contact_username=draft.username,
            parse_method=ParseMethod.FORM,
            confidence=1.0,
            active_days=days,
            **_scorer(settings).for_extraction(ex).fields(),
            formatted_text=out.html,
            search_text=search_text(draft.title, draft.company, draft.city, draft.text()),
        )
    job.author_id = user.tg_id
    job.status = JobStatus.PENDING_REVIEW if reasons else JobStatus.QUEUED
    job.attempts = 0
    job.next_retry_at = now
    job.created_at = now
    job.last_error = "; ".join(reasons) or None
    session.add(job)
    await session.flush()
    job.buttons = out.buttons(job.id) if isinstance(out, ProjectPost) else buttons_json(out, job.id)
    await session.flush()
    return SubmitResult(
        Outcome.REVIEW if reasons else Outcome.QUEUED, job.id, review_reasons=tuple(reasons)
    )


def _project_row(
    draft: Draft, out: ProjectPost, budget: Budget, days: int | None, settings: Settings
) -> Job:
    """The ``jobs`` row of a project: not ranked (tier 2), kept out of the job search."""
    return Job(
        origin=JobOrigin.USER,
        kind=JobKind.PROJECT.value,
        title=draft.title[:255],
        category=FALLBACK_CATEGORY,
        description=draft.description,
        salary_text=budget.text[:255],  # the budget as the post shows it
        budget_amount=budget.amount,
        budget_currency=budget.currency,
        deadline_text=(draft.deadline or None) and draft.deadline[:255],
        contact_phone=draft.phone,
        contact_username=draft.username,
        parse_method=ParseMethod.FORM,
        confidence=1.0,
        active_days=days,
        priority_tier=2,
        priority_score=0,
        priority_reason="loyiha: reyting qo'llanmaydi (eng yangisi birinchi)",
        formatted_text=out.html,
        search_text=search_text(draft.title, draft.description, draft.text()),
    )


# --------------------------------------------------------------------------- admin decision
async def approve(
    session: AsyncSession, job_id: int, now: datetime, *, publish_now: bool = False
) -> Job | None:
    """The admin approves a job in ``pending_review``; the author becomes trusted. ``None`` if the
    job was already decided (so a double click or a second admin changes nothing). Does not
    commit.

    ``publish_now=False``: the job goes to the queue (``queued``, due now) — the old behaviour,
    also used while the publisher is paused. ``publish_now=True``: the job is moved straight to
    ``sending`` in the same conditional UPDATE, i.e. CLAIMED by the caller, who must send it right
    after the commit (``Publisher.publish_claimed``). It never sits in the queue, and the worker's
    publisher cannot take it, so it cannot be published twice.
    """
    target = JobStatus.SENDING if publish_now else JobStatus.QUEUED
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PENDING_REVIEW)
        .values(status=target, next_retry_at=now, last_error=None)
        .execution_options(synchronize_session=False)
    )
    if (result.rowcount or 0) != 1:
        return None
    job = await session.get(Job, job_id)
    if job is not None:
        await session.refresh(job)
        if job.author_id is not None and (author := await session.get(User, job.author_id)):
            author.trust_level = max(author.trust_level, TRUST_TRUSTED)
    return job


async def requeue_claimed(session: AsyncSession, job_id: int, now: datetime) -> bool:
    """A job claimed with ``approve(publish_now=True)`` that cannot be sent (no channel
    configured) goes to the normal queue. Does not commit."""
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.SENDING)
        .values(status=JobStatus.QUEUED, next_retry_at=now)
        .execution_options(synchronize_session=False)
    )
    return (result.rowcount or 0) == 1


async def reject(session: AsyncSession, job_id: int, reason: str = "admin") -> Job | None:
    """``pending_review`` -> ``rejected``. ``None`` if already decided. Does not commit."""
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PENDING_REVIEW)
        .values(status=JobStatus.REJECTED, last_error=f"rad etildi: {reason}")
        .execution_options(synchronize_session=False)
    )
    if (result.rowcount or 0) != 1:
        return None
    job = await session.get(Job, job_id)
    if job is not None:
        await session.refresh(job)
    return job
