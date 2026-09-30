"""Database models (SQLAlchemy 2.0, typed ``Mapped[]`` style).

Tables follow docs/ARCHITECTURE.md §4, status values follow §3.
All datetimes are UTC (see :class:`ayvona.db.types.UTCDateTime`).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ayvona.db.types import UTCDateTime, str_enum
from ayvona.timeutil import utcnow

# Stable constraint names -> Alembic batch migrations on SQLite can find and alter them later.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime(), dict[str, Any]: JSON, list[Any]: JSON}


# =========================================================================== enums
class SourceType(StrEnum):
    """Base kind of a source; ``sources.type`` may add a suffix: ``"web:hh_uz"``."""

    TELEGRAM = "telegram"
    WEB = "web"

    @classmethod
    def of(cls, type_key: str) -> SourceType:
        """``"web:hh_uz"`` -> ``WEB``. Raises ``ValueError`` for unknown kinds."""
        return cls(type_key.split(":", 1)[0].strip().lower())


class SourceStatus(StrEnum):
    """Life cycle of a source row (``enabled`` is the admin's pause switch on top of it)."""

    ACTIVE = "active"
    # Added from the bot (/addsource); the collector checks it (exists? readable?) first.
    PENDING = "pending"
    REJECTED = "rejected"  # the check failed (reason in ``last_error``)
    DELETED = "deleted"  # removed by the admin; kept because raw_posts reference it


class SourceAddedVia(StrEnum):
    YAML = "yaml"
    BOT = "bot"


class RawPostStatus(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    # A job ad that became (or replaced the source of) a row in ``jobs`` (``raw_posts.job_id``).
    DONE = "done"
    DUPLICATE = "duplicate"
    NOT_JOB = "not_job"
    RESUME = "resume"
    CLOSED = "closed"
    OPPORTUNITY = "opportunity"
    SUSPICIOUS = "suspicious"
    NO_TEXT = "no_text"
    # A job ad without any phone / @username / email / apply link: never published.
    NO_CONTACT = "no_contact"
    # A job ad with neither a title nor a salary found (extract.py): not published,
    # listed in the admin report.
    LOW_QUALITY = "low_quality"
    # Old posts that must not reach the channel (ROADMAP Bosqich 7, step 0): everything in the DB
    # before the worker's first start, and history taken when a source is added
    # (unless ``publisher.publish_backfill``).
    SKIPPED_BACKFILL = "skipped_backfill"
    ERROR = "error"


class JobOrigin(StrEnum):
    AGGREGATOR = "aggregator"
    USER = "user"


class JobStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    QUEUED = "queued"
    SENDING = "sending"
    RETRY = "retry"
    PUBLISHED = "published"
    FAILED = "failed"
    # Its source post is older than ``publisher.max_age_hours``: never published, kept in the DB.
    SKIPPED_OLD = "skipped_old"
    REJECTED = "rejected"
    CLOSED = "closed"
    EXPIRED = "expired"


class ParseMethod(StrEnum):
    REGEX = "regex"
    FALLBACK = "fallback"
    GEMINI = "gemini"
    FORM = "form"


class FilterKind(StrEnum):
    BAN = "ban"
    SPAM = "spam"
    SCAM = "scam"


# =========================================================================== aggregator
class Source(Base):
    """A place we read job posts from (Telegram channel, later a website)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Registry key: "telegram" or "web:<site>" (e.g. "web:hh_uz"). Base kind = SourceType.
    type: Mapped[str] = mapped_column(String(64), default=SourceType.TELEGRAM.value)
    identifier: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("1"))
    # String so web sources can store a URL/ID; Telegram stores the message id as text.
    last_seen_id: Mapped[str | None] = mapped_column(String(255))
    last_checked_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    own_usernames: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Bosqich 8: the DB is the source of truth; settings.yaml only seeds new rows.
    status: Mapped[SourceStatus] = mapped_column(
        str_enum(SourceStatus, 16),
        default=SourceStatus.ACTIVE,
        server_default=SourceStatus.ACTIVE.value,
    )
    added_via: Mapped[SourceAddedVia] = mapped_column(
        str_enum(SourceAddedVia, 8),
        default=SourceAddedVia.YAML,
        server_default=SourceAddedVia.YAML.value,
    )
    added_by: Mapped[int | None] = mapped_column(BigInteger)  # admin's Telegram id
    # Old posts to take on the first poll (bot: 0 / 5 / 20); None = collector.initial_backfill
    backfill_request: Mapped[int | None] = mapped_column(Integer)
    # Websites (Bosqich 16): how often to check, requests per day
    check_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    daily_limit: Mapped[int | None] = mapped_column(Integer)


class RawPost(Base):
    """A post exactly as fetched. Never deleted (archived after 90 days, later)."""

    __tablename__ = "raw_posts"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        Index("ix_raw_posts_status_fetched_at", "status", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))
    external_id: Mapped[str] = mapped_column(String(255))
    grouped_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(Text, default="", server_default=sql_text("''"))
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("0"))
    media_type: Mapped[str | None] = mapped_column(String(32))
    # Things that are not in plain text but matter later: hidden links, URL buttons, ...
    extra: Mapped[dict[str, Any] | None]
    posted_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[RawPostStatus] = mapped_column(
        str_enum(RawPostStatus), default=RawPostStatus.NEW, server_default=RawPostStatus.NEW.value
    )
    error: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    # Taken from the channel's history when the source was added (not a fresh post).
    is_backfill: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("0"))
    # Worker (Bosqich 7): the job this post became or repeats; the post it repeats (dedup root).
    job_id: Mapped[int | None] = mapped_column(Integer, index=True)
    duplicate_of: Mapped[int | None] = mapped_column(Integer)
    # Dedup index entry (processing/dedup.py), kept so the index is rebuilt after a restart.
    dedup_text: Mapped[str | None] = mapped_column(Text)
    dedup_title: Mapped[str | None] = mapped_column(String(255))
    dedup_contacts: Mapped[list[Any] | None]
    fingerprint: Mapped[str | None] = mapped_column(String(64))


class Job(Base):
    """A ready job ad — from the aggregator or submitted by a user. Also the publishing outbox."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_next_retry_at", "status", "next_retry_at"),
        Index("ix_jobs_category_region_published_at", "category", "region", "published_at"),
        # Hard rule 7: a user-submitted job must have a contact.
        CheckConstraint(
            "origin != 'user' OR contact_phone IS NOT NULL OR contact_username IS NOT NULL",
            name="user_job_has_contact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    origin: Mapped[JobOrigin] = mapped_column(str_enum(JobOrigin))
    raw_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_posts.id", ondelete="SET NULL"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.tg_id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), default="boshqa", server_default="boshqa")
    # config/categories.yaml profession key ("kassir"); None = only the category is known
    profession: Mapped[str | None] = mapped_column(String(64))

    salary_min: Mapped[int | None] = mapped_column(BigInteger)  # in so'm, for search
    salary_max: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(8))
    salary_period: Mapped[str | None] = mapped_column(String(8))  # month | week | day | hour
    salary_text: Mapped[str | None] = mapped_column(String(255))

    region: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("0"))

    schedule: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_username: Mapped[str | None] = mapped_column(String(64))

    parse_method: Mapped[ParseMethod] = mapped_column(str_enum(ParseMethod))
    confidence: Mapped[float] = mapped_column(Float, default=0.0, server_default=sql_text("0"))

    formatted_text: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    # Folded title + company + city + description (Cyrillic -> Latin, lowercase, no apostrophes):
    # the only column jobs_fts indexes (normalize.search_text); keyword queries are folded the same.
    search_text: Mapped[str | None] = mapped_column(Text)

    # Inline keyboard of the channel post: [[{"text": ..., "url": ...}, ...], ...]
    buttons: Mapped[list[Any] | None]

    # outbox
    status: Mapped[JobStatus] = mapped_column(str_enum(JobStatus), default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    # Earliest time the publisher may send it: the collecting window (publisher.hold_minutes)
    # for a new job, the backoff time after a failed attempt.
    next_retry_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)

    channel_message_id: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# =========================================================================== public bot
class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    lang: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("0"))
    # 0 = new, 1 = trusted, 2 = admin
    trust_level: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_active_at: Mapped[datetime | None]


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.tg_id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Subscription(Base):
    """A job alert: "notify me about <category> in <region> paying <min_salary>+"."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    category: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64))  # regions.yaml key or "remote"
    min_salary: Mapped[int | None] = mapped_column(BigInteger)
    keyword: Mapped[str | None] = mapped_column(String(255))
    # False = paused by the user, or the user blocked the bot (Forbidden)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("1"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    profession: Mapped[str | None] = mapped_column(String(64))  # Bosqich 13


class AlertStatus(StrEnum):
    SENT = "sent"
    DIGEST = "digest"  # over the user's daily limit: waits for the evening digest
    DIGEST_SENT = "digest_sent"


class AlertDelivery(Base):
    """One alert. The composite PK guarantees a job is never alerted twice per subscription."""

    __tablename__ = "alert_deliveries"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    sent_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[AlertStatus] = mapped_column(
        str_enum(AlertStatus, 16), default=AlertStatus.SENT, server_default=AlertStatus.SENT.value
    )


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.tg_id", ondelete="SET NULL"), index=True
    )
    filters: Mapped[dict[str, Any]] = mapped_column(default=dict)
    results_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


# =========================================================================== shared
class Image(Base):
    """One picture file under ``assets/images/<category>/[<profession>/]`` (docs/IMAGES.md).

    ``times_used`` / ``last_used_at`` drive the rotation (least recently used goes next, so the
    order survives restarts). ``telegram_file_id`` is reused after the first upload and reset
    when ``file_hash`` changes (the file was replaced).
    """

    __tablename__ = "images"
    __table_args__ = (Index("ix_images_category_profession", "category", "profession"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64))
    profession: Mapped[str | None] = mapped_column(String(64))  # None = a category picture
    # Relative to the images root, "/" separators: "tibbiyot/shifokor/1.jpg"
    file_path: Mapped[str] = mapped_column(String(512), unique=True)
    file_hash: Mapped[str | None] = mapped_column(String(64))  # sha256
    telegram_file_id: Mapped[str | None] = mapped_column(String(255))
    is_placeholder: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sql_text("0")
    )
    times_used: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    last_used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class FilterWord(Base):
    __tablename__ = "filter_words"
    __table_args__ = (UniqueConstraint("word", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(255))
    kind: Mapped[FilterKind] = mapped_column(str_enum(FilterKind))
    added_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AICache(Base):
    __tablename__ = "ai_cache"

    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class KVStore(Base):
    """Small key/value settings and state: ``publisher_paused``, ``usd_rate``, heartbeats..."""

    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# jobs_fts (SQLite FTS5 virtual table + sync triggers) is not an ORM model: it is created by raw SQL
# in the initial Alembic migration and ignored by autogenerate (see migrations/env.py).
FTS_TABLE_PREFIX = "jobs_fts"
