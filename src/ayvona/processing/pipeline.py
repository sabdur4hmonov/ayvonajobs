"""Processing pipeline (worker): ``raw_posts(new)`` -> ``jobs(queued)``.

One logical post (album parts merged) at a time:

    backfill? -> classify -> extract (contact? quality?) -> dedup -> clean -> format -> jobs

* Every outcome is a ``raw_posts.status``: done (became a job), duplicate, not_job, resume,
  closed, opportunity, suspicious, no_text, no_contact, low_quality, skipped_backfill, error.
* Extract runs BEFORE dedup (ROADMAP lists dedup first): dedup needs the extracted title
  (Bosqich 5 note), and only publishable jobs enter the dedup index — otherwise a copy WITHOUT a
  contact seen first would make the later copy WITH a contact a "duplicate", and the job would
  never reach the channel.
* Collecting window (ROADMAP 1b): a new job waits ``publisher.hold_minutes`` after it was posted
  (``jobs.next_retry_at``). A duplicate that arrives meanwhile and is more complete (contact,
  salary, place, confidence) takes the job over: the job row gets its fields, caption and source
  link; the old post becomes the duplicate. A job already sending/published is never touched.
  After the 14-day dedup window the same ad is a new job again.
* Crash safety: the result of one post is written in ONE transaction; until then the post stays
  ``new`` and is processed again after a restart. A bug on one post -> ``error`` + admin notice,
  the loop goes on. A DB error (locked) leaves the post ``new`` for the next round.
"""

from __future__ import annotations

import html
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ayvona.config import Settings
from ayvona.db.models import (
    Job,
    JobOrigin,
    JobStatus,
    ParseMethod,
    RawPost,
    RawPostStatus,
    Source,
)
from ayvona.db.repositories import raw_posts_repo
from ayvona.processing.classify import Classification, Classifier, PostInput, PostKind, merge_album
from ayvona.processing.clean import Cleaner
from ayvona.processing.dedup import WINDOW, DedupEntry, DedupIndex, DedupMatch, make_entry
from ayvona.processing.extract import Extraction, Extractor
from ayvona.processing.formatter import FormattedPost, Formatter, telegram_post_url
from ayvona.services.notifier import Notifier
from ayvona.timeutil import ensure_utc, utcnow

KIND_STATUS: dict[PostKind, RawPostStatus] = {
    PostKind.NOT_JOB: RawPostStatus.NOT_JOB,
    PostKind.RESUME: RawPostStatus.RESUME,
    PostKind.CLOSED: RawPostStatus.CLOSED,
    PostKind.OPPORTUNITY: RawPostStatus.OPPORTUNITY,
    PostKind.SUSPICIOUS: RawPostStatus.SUSPICIOUS,
    PostKind.NO_TEXT: RawPostStatus.NO_TEXT,
}
PREVIEW_LEN = 300


# --------------------------------------------------------------------------- data
@dataclass(slots=True)
class LogicalPost:
    """One post as the channel showed it: a single message or all parts of one album."""

    rows: list[RawPost]
    source: Source
    input: PostInput
    late_part: bool = False  # album parts that came after the album was processed

    @property
    def primary(self) -> RawPost:
        """The part that carries the caption (album) — it represents the post."""
        return next((r for r in self.rows if r.text.strip()), self.rows[0])

    @property
    def posted_at(self) -> datetime:
        p = self.primary
        return ensure_utc(p.posted_at or p.fetched_at)

    @property
    def is_backfill(self) -> bool:
        return any(r.is_backfill for r in self.rows)

    @property
    def url(self) -> str | None:
        return telegram_post_url(self.source.identifier, self.primary.external_id)

    @property
    def label(self) -> str:
        return f"{self.source.identifier}/{self.primary.external_id}"


@dataclass(slots=True)
class PipelineStats:
    posts: int = 0
    statuses: Counter[str] = field(default_factory=Counter)
    new_jobs: int = 0
    replaced: int = 0
    db_errors: int = 0

    def summary(self) -> str:
        parts = ", ".join(f"{k}={v}" for k, v in self.statuses.most_common()) or "-"
        return f"{self.posts} post ({parts}), yangi job {self.new_jobs}, almashdi {self.replaced}"


@dataclass(frozen=True, slots=True)
class Completeness:
    """How much a reader gets from a version of an ad (for the collecting window)."""

    direct_contact: bool  # phone / @username (not only email / apply link)
    salary_number: bool
    salary_text: bool
    region: bool
    place: bool
    title: bool
    confidence: float

    @property
    def score(self) -> float:
        return (
            (2.0 if self.direct_contact else 1.0)
            + (1.0 if self.salary_number else 0.5 if self.salary_text else 0.0)
            + (0.5 if self.region else 0.0)
            + (0.5 if self.place else 0.0)
            + (0.5 if self.title else 0.0)
            + self.confidence
        )

    @classmethod
    def of_extraction(cls, ex: Extraction) -> Completeness:
        return cls(
            direct_contact=bool(ex.phones or ex.usernames),
            salary_number=ex.salary_min is not None or ex.salary_max is not None,
            salary_text=bool(ex.salary_text),
            region=bool(ex.region),
            place=bool(ex.district or ex.address),
            title=bool(ex.title),
            confidence=ex.confidence,
        )

    @classmethod
    def of_job(cls, job: Job) -> Completeness:
        return cls(
            direct_contact=bool(job.contact_phone or job.contact_username),
            salary_number=job.salary_min is not None or job.salary_max is not None,
            salary_text=bool(job.salary_text),
            region=bool(job.region),
            place=bool(job.city),
            title=bool(job.title),
            confidence=job.confidence or 0.0,
        )


def _cut(value: str | None, limit: int) -> str | None:
    return value[:limit] if value else value


def job_fields(ex: Extraction, description: str, out: FormattedPost) -> dict[str, Any]:
    """``jobs`` columns of one aggregator job (everything except ids / outbox state)."""
    return {
        "title": _cut(ex.title_uz or ex.title, 255),
        "company": _cut(ex.company, 255),
        "category": ex.category,
        "profession": ex.profession,
        "salary_min": ex.salary_min,
        "salary_max": ex.salary_max,
        "currency": ex.currency,
        "salary_period": ex.salary_period,
        "salary_text": _cut(ex.salary_text, 255),
        "region": ex.region,
        "city": _cut(ex.district or ex.address, 128),
        "is_remote": ex.is_remote,
        "schedule": ex.schedule,
        "requirements": ex.requirements,
        "description": description,
        "contact_phone": _cut(ex.phones[0], 20) if ex.phones else None,
        "contact_username": _cut(ex.usernames[0], 64) if ex.usernames else None,
        "parse_method": ParseMethod.FALLBACK if out.fallback else ParseMethod.REGEX,
        "confidence": ex.confidence,
        "formatted_text": out.html,
    }


def buttons_json(out: FormattedPost, job_id: int) -> list[list[dict[str, str]]]:
    return [[{"text": b.text, "url": b.url} for b in row] for row in out.buttons(job_id)]


def entry_from_row(row: RawPost) -> DedupEntry:
    """Rebuild the dedup entry stored on a raw post."""
    return DedupEntry(
        key=row.id,
        posted_at=ensure_utc(row.posted_at or row.fetched_at),
        text=row.dedup_text or "",
        content_hash=row.content_hash or "",
        title=row.dedup_title or "",
        contacts=frozenset(row.dedup_contacts or ()),
        fingerprint=row.fingerprint,
    )


# --------------------------------------------------------------------------- pipeline
class Pipeline:
    """Build once per process; call :meth:`run_once` in a loop."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        notifier: Notifier | None = None,
    ) -> None:
        self.settings = settings
        self.sf = session_factory
        self.notifier = notifier
        self.cfg = settings.app.worker
        self.publisher_cfg = settings.app.publisher
        self.classifier = Classifier(settings.filters, settings.source_rules)
        self.extractor = Extractor(settings)
        self.cleaner = Cleaner(settings.source_rules)
        self.formatter = Formatter(settings)
        self.index = DedupIndex()
        self._index_loaded_at: datetime | None = None
        self._config_own: set[str] = set(settings.source_rules.defaults.extra_own_usernames)
        for s in settings.app.sources:
            self._config_own.add(s.identifier)
            self._config_own.update(s.own_usernames)
        for name, rule in settings.source_rules.sources.items():
            self._config_own.add(name)
            self._config_own.update(rule.extra_own_usernames)
        self._own: set[str] = set(self._config_own)

    # ------------------------------------------------------------------ dedup index
    async def load_index(self, now: datetime | None = None) -> int:
        """(Re)build the in-memory dedup index from ``raw_posts`` of the last 14 days."""
        now = now or utcnow()
        index = DedupIndex()
        async with self.sf() as s:
            rows = await raw_posts_repo.dedup_entries_since(s, now - WINDOW)
        for row in rows:
            index.add(entry_from_row(row), row.duplicate_of)
        self.index = index
        self._index_loaded_at = now
        logger.info("Dublikat indeksi yuklandi: {} ta e'lon (oxirgi 14 kun)", len(rows))
        return len(rows)

    async def _refresh_own_usernames(self, session: AsyncSession) -> None:
        """Every channel's own accounts are not contacts (bot-added channels too)."""
        own = set(self._config_own)
        for src in (await session.scalars(select(Source))).all():
            own.add(src.identifier)
            own.update(src.own_usernames or ())
        self._own = own

    # ------------------------------------------------------------------ grouping
    async def _collect(self, session: AsyncSession, now: datetime) -> list[LogicalPost]:
        cutoff = now - timedelta(seconds=self.cfg.album_wait_seconds)
        rows = await raw_posts_repo.list_by_status(
            session, RawPostStatus.NEW, fetched_before=cutoff, limit=self.cfg.batch_size
        )
        sources = {s.id: s for s in (await session.scalars(select(Source))).all()}
        posts: list[LogicalPost] = []
        seen_albums: set[tuple[int, int]] = set()
        for row in rows:
            src = sources[row.source_id]
            if row.grouped_id is None:
                posts.append(self._logical([row], src))
                continue
            album = (row.source_id, row.grouped_id)
            if album in seen_albums:
                continue
            seen_albums.add(album)
            parts = await raw_posts_repo.album_parts(session, *album)
            new = [p for p in parts if p.status == RawPostStatus.NEW]
            if any(ensure_utc(p.fetched_at) >= cutoff for p in new):
                continue  # a part came just now; wait for the rest of the album
            posts.append(self._logical(new, src, late_part=len(new) < len(parts)))
        return posts

    @staticmethod
    def _logical(rows: list[RawPost], src: Source, *, late_part: bool = False) -> LogicalPost:
        own = tuple(src.own_usernames or ())
        parts = [
            PostInput(
                text=r.text or "",
                source=src.identifier,
                extra=r.extra or None,
                has_media=r.has_media,
                posted_at=ensure_utc(r.posted_at or r.fetched_at),
                own_usernames=own,
            )
            for r in rows
        ]
        post_input = merge_album(parts) if len(parts) > 1 else parts[0]
        return LogicalPost(rows, src, post_input, late_part)

    # ------------------------------------------------------------------ main
    async def run_once(self, now: datetime | None = None) -> PipelineStats:
        """Process every post that is ready (at most ``batch_size`` raw posts)."""
        now = now or utcnow()
        stats = PipelineStats()
        reload_after = timedelta(hours=self.cfg.dedup_reload_hours)
        if self._index_loaded_at is None or now - self._index_loaded_at >= reload_after:
            await self.load_index(now)
        async with self.sf() as s:
            await self._refresh_own_usernames(s)
            posts = await self._collect(s, now)
        for post in posts:
            try:
                status = await self._process(post, now, stats)
            except OperationalError as e:  # DB locked / disk: leave it "new", try next round
                stats.db_errors += 1
                logger.error("{}: bazaga yozilmadi, keyingi aylanishda qayta: {}", post.label, e)
                break
            except Exception as e:
                status = RawPostStatus.ERROR
                await self._mark_error(post, e)
            stats.posts += 1
            stats.statuses[status.value] += 1
        if stats.posts:
            logger.info("Pipeline: {}", stats.summary())
        return stats

    async def _process(
        self, post: LogicalPost, now: datetime, stats: PipelineStats
    ) -> RawPostStatus:
        if post.is_backfill and not self.publisher_cfg.publish_backfill:
            await self._set_status(post, RawPostStatus.SKIPPED_BACKFILL)
            return RawPostStatus.SKIPPED_BACKFILL

        cls = self.classifier.classify(post.input, now)
        if cls.kind is not PostKind.JOB:
            status = KIND_STATUS[cls.kind]
            await self._set_status(post, status, ", ".join(cls.reasons)[:500] or None)
            await self._notify_kind(post, cls)
            return status

        ex = self.extractor.extract(post.input)
        if not ex.has_contact:
            await self._set_status(post, RawPostStatus.NO_CONTACT)
            return RawPostStatus.NO_CONTACT
        if ex.low_quality:
            await self._set_status(post, RawPostStatus.LOW_QUALITY, ", ".join(ex.reasons))
            return RawPostStatus.LOW_QUALITY

        entry = make_entry(
            post.primary.id,
            post.posted_at,
            cls.clean_text,
            [*cls.contacts.phones, *cls.contacts.usernames],
            title=ex.title,
            ignore_usernames=self._own,
        )
        match = self.index.find(entry)
        cleaned = self.cleaner.clean(
            post.input.text,
            post.input.extra,
            source=post.source.identifier,
            own_usernames=post.input.own_usernames,
        )
        out = self.formatter.format(ex, cleaned, source_url=post.url)
        fields = job_fields(ex, cleaned.text, out)

        async with self.sf() as s, s.begin():
            job = await self._group_job(s, match) if match else None
            if job is None:
                status = await self._new_job(s, post, now, fields, out)
                stats.new_jobs += 1
            elif await self._take_over(s, post, job, ex, fields, out):
                status = RawPostStatus.DONE
                stats.replaced += 1
                logger.info(
                    "{}: to'liqroq nusxa — job #{} endi shu post bilan chiqadi", post.label, job.id
                )
            else:
                status = RawPostStatus.DUPLICATE
                await self._set_rows(
                    s, post, status, job_id=job.id, duplicate_of=match.original if match else None
                )
            await self._store_entry(s, post, entry, match)
        self.index.add(entry, match.original if match else None)
        return status

    # ------------------------------------------------------------------ job rows
    async def _group_job(self, s: AsyncSession, match: DedupMatch) -> Job | None:
        """The job of the dedup group ``match`` belongs to (via the matched post or the root)."""
        for key in (match.matched, match.original):
            row = await s.get(RawPost, key)
            if row is not None and row.job_id is not None:
                job = await s.get(Job, row.job_id)
                if job is not None:
                    return job
        return None  # data inconsistent — publish it rather than lose it

    async def _new_job(
        self,
        s: AsyncSession,
        post: LogicalPost,
        now: datetime,
        fields: dict[str, Any],
        out: FormattedPost,
    ) -> RawPostStatus:
        hold = timedelta(minutes=self.publisher_cfg.hold_minutes)
        job = Job(
            origin=JobOrigin.AGGREGATOR,
            raw_post_id=post.primary.id,
            status=JobStatus.QUEUED,
            attempts=0,
            next_retry_at=max(post.posted_at + hold, now),
            **fields,
        )
        s.add(job)
        await s.flush()
        job.buttons = buttons_json(out, job.id)
        await self._set_rows(s, post, RawPostStatus.DONE, job_id=job.id)
        return RawPostStatus.DONE

    async def _take_over(
        self,
        s: AsyncSession,
        post: LogicalPost,
        job: Job,
        ex: Extraction,
        fields: dict[str, Any],
        out: FormattedPost,
    ) -> bool:
        """Collecting window: a fuller copy replaces the not-yet-sent version of the job."""
        if job.status != JobStatus.QUEUED or job.attempts:
            return False
        if Completeness.of_extraction(ex).score <= Completeness.of_job(job).score:
            return False
        result = await s.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == JobStatus.QUEUED, Job.attempts == 0)
            .values(raw_post_id=post.primary.id, buttons=buttons_json(out, job.id), **fields)
            .execution_options(synchronize_session=False)
        )
        if (result.rowcount or 0) != 1:
            return False  # the publisher took it just now
        await s.execute(
            update(RawPost)
            .where(RawPost.job_id == job.id, RawPost.status == RawPostStatus.DONE)
            .values(status=RawPostStatus.DUPLICATE, duplicate_of=post.primary.id)
            .execution_options(synchronize_session=False)
        )
        await self._set_rows(s, post, RawPostStatus.DONE, job_id=job.id)
        return True

    # ------------------------------------------------------------------ raw post rows
    @staticmethod
    async def _set_rows(
        s: AsyncSession,
        post: LogicalPost,
        status: RawPostStatus,
        *,
        error: str | None = None,
        job_id: int | None = None,
        duplicate_of: int | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status, "error": error}
        if job_id is not None:
            values["job_id"] = job_id
        if duplicate_of is not None:
            values["duplicate_of"] = duplicate_of
        await s.execute(
            update(RawPost)
            .where(RawPost.id.in_([r.id for r in post.rows]))
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    async def _set_status(
        self, post: LogicalPost, status: RawPostStatus, note: str | None = None
    ) -> None:
        async with self.sf() as s, s.begin():
            await self._set_rows(s, post, status, error=note)

    @staticmethod
    async def _store_entry(
        s: AsyncSession, post: LogicalPost, entry: DedupEntry, match: DedupMatch | None
    ) -> None:
        values: dict[str, Any] = {
            "dedup_text": entry.text,
            "dedup_title": entry.title[:255],
            "dedup_contacts": sorted(entry.contacts),
            "fingerprint": entry.fingerprint,
            "content_hash": entry.content_hash,
        }
        if match is not None:
            values["duplicate_of"] = match.original
        await s.execute(
            update(RawPost)
            .where(RawPost.id == post.primary.id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    async def _mark_error(self, post: LogicalPost, e: Exception) -> None:
        error = f"{type(e).__name__}: {e}"
        logger.opt(exception=e).error("{}: qayta ishlashda xato", post.label)
        try:
            await self._set_status(post, RawPostStatus.ERROR, error[:2000])
        except Exception:
            logger.exception("{}: error statusi ham yozilmadi", post.label)
        await self._notify(
            f"❌ <b>Postni qayta ishlashda xato</b> (kanalga chiqmadi)\n{self._link(post)}\n"
            f"<code>{html.escape(error[:500])}</code>",
            key=f"pipeline_error:{type(e).__name__}:{post.source.id}",
        )

    # ------------------------------------------------------------------ admin notices
    @staticmethod
    def _link(post: LogicalPost) -> str:
        label = html.escape(post.label)
        return f'<a href="{html.escape(post.url)}">{label}</a>' if post.url else label

    async def _notify(self, text: str, *, key: str | None = None) -> None:
        if self.notifier is not None:
            await self.notifier.send(text, key=key)

    async def _notify_kind(self, post: LogicalPost, cls: Classification) -> None:
        if cls.kind is PostKind.SUSPICIOUS:
            preview = html.escape(post.input.text.strip()[:PREVIEW_LEN])
            reasons = html.escape(", ".join(cls.reasons))
            await self._notify(
                f"⚠️ <b>Shubhali e'lon</b> — kanalga chiqmadi\n{self._link(post)}\n"
                f"Sabab: {reasons}\n\n{preview}"
            )
        elif cls.kind is PostKind.NO_TEXT and not post.late_part:
            await self._notify(
                f"🖼 <b>Matnsiz post</b> (faqat rasm/fayl) — kanalga chiqmadi\n{self._link(post)}"
            )
