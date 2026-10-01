"""Application settings.

Two sources:
* ``.env``          — secrets and per-machine values (API keys, tokens, paths).
* ``config/*.yaml`` — behaviour (sources, intervals, keywords). Safe to commit.

Use :func:`get_settings` everywhere; it loads once and caches.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# src/ayvona/config.py -> parents[2] is the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


def resolve_path(path: Path | str, base: Path = PROJECT_ROOT) -> Path:
    """Return ``path`` as absolute; relative paths are taken relative to ``base``."""
    p = Path(path)
    return p if p.is_absolute() else (base / p)


# --------------------------------------------------------------------------- .env
class EnvSettings(BaseSettings):
    """Values from environment / ``.env``. All optional, so tests and tooling work without it."""

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    api_id: int | None = None
    api_hash: SecretStr | None = None
    telethon_session: str = "data/ayvona"
    bot_token: SecretStr | None = None
    channel_id: str | None = None
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    admin_chat_id: int | None = None
    db_path: str = "data/ayvona.db"
    log_level: str = "INFO"
    tz: str = "Asia/Tashkent"
    # Gemini (Bosqich 15, optional): empty key = everything works with regex only.
    gemini_api_key: SecretStr | None = None
    # Extra keys, comma separated — used ONLY if gemini_allow_key_rotation (default off).
    gemini_api_keys: SecretStr | None = None
    gemini_allow_key_rotation: bool = False
    gemini_model: str = "gemini-flash-latest"
    # hh.uz official API (Bosqich 16): the app token from dev.hh.ru; empty = the source is off.
    hh_access_token: SecretStr | None = None
    hh_user_agent: str = ""

    @field_validator(
        "api_id",
        "admin_chat_id",
        "api_hash",
        "bot_token",
        "channel_id",
        "gemini_api_key",
        "gemini_api_keys",
        "hh_access_token",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        """``API_ID=`` (left blank in .env) means "not set", not a validation error."""
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v: Any) -> Any:
        """Accept ``"1, 2,3"`` (comma separated) as well as a real list."""
        if v is None:
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(x) for x in v.replace(";", ",").split(",") if x.strip()]
        return v

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("tz")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown timezone: {v!r}") from e
        return v


# --------------------------------------------------------------------------- YAML models
class SourceConfig(BaseModel):
    """One entry of ``sources:`` in settings.yaml."""

    type: str = "telegram"
    identifier: str
    title: str | None = None
    enabled: bool = True
    own_usernames: list[str] = Field(default_factory=list)

    @field_validator("identifier")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("identifier must not be empty")
        return v

    @field_validator("type")
    @classmethod
    def _known_kind(cls, v: str) -> str:
        """``telegram`` or ``web:<site>``."""
        v = v.strip().lower()
        if v.split(":", 1)[0] not in {"telegram", "web"}:
            raise ValueError(f"unknown source type {v!r} (expected 'telegram' or 'web:<site>')")
        return v


class CollectorConfig(BaseModel):
    poll_interval_seconds: float = 90
    initial_backfill: int = Field(default=0, ge=0)
    fetch_limit: int = Field(default=200, ge=1)
    delay_between_sources_seconds: float = 2.5
    fetch_timeout_seconds: float = 120
    heartbeat_interval_seconds: float = 60


class PublisherConfig(BaseModel):
    publish_interval_seconds: float = 60
    max_publish_attempts: int = Field(default=8, ge=1)
    # A new job waits this long before publishing: a fuller copy from another channel may come.
    hold_minutes: float = Field(default=20, ge=0)
    # Publish posts taken from a channel's history when the source was added (initial_backfill)?
    publish_backfill: bool = False
    # A job whose source post appeared more than this long ago is never published
    # (``skipped_old``; kept in the DB). Age = raw_posts.posted_at, else fetched_at. 0 = off.
    max_age_hours: float = Field(default=24, ge=0)
    # Network / server error: wait retry_base * 2^(attempt-1) seconds, at most retry_max.
    retry_base_seconds: float = Field(default=30, gt=0)
    retry_max_seconds: float = Field(default=3600, gt=0)
    # Bad token / bot not admin / no channel: nothing is sent for this long (no attempt used).
    config_error_pause_seconds: float = Field(default=300, gt=0)
    # Publisher checks the queue this often when it is empty.
    idle_poll_seconds: float = Field(default=5, gt=0)

    def too_old_before(self, now: datetime) -> datetime | None:
        """Source posts older than this are not published (``None``: the rule is off)."""
        return now - timedelta(hours=self.max_age_hours) if self.max_age_hours > 0 else None


class WorkerConfig(BaseModel):
    """The processing pipeline (apps/worker.py)."""

    poll_interval_seconds: float = Field(default=15, gt=0)
    # Album parts arrive one by one: a post is processed only this long after it was fetched.
    album_wait_seconds: float = Field(default=60, ge=0)
    batch_size: int = Field(default=50, ge=1)
    heartbeat_interval_seconds: float = Field(default=60, gt=0)
    # The in-memory dedup index is rebuilt from the DB this often (drops entries > 14 days old).
    dedup_reload_hours: float = Field(default=6, gt=0)
    # On start, queued / retry jobs get the caption + buttons of the current formatter / branding
    # (services/reformat.py) — a formatter change never publishes old texts.
    reformat_queued_on_start: bool = True


class MonitoringConfig(BaseModel):
    """services/heartbeat.py — the worker watches the other processes and the sources."""

    check_interval_minutes: float = Field(default=5, gt=0)
    heartbeat_stale_minutes: float = Field(default=10, gt=0)
    source_silence_hours: float = Field(default=24, gt=0)
    source_error_threshold: int = Field(default=5, ge=1)


class BackupConfig(BaseModel):
    """services/backup.py — daily copy of the DB (SQLite backup API)."""

    enabled: bool = True
    hour: int = Field(default=3, ge=0, le=23)  # Asia/Tashkent
    minute: int = Field(default=0, ge=0, le=59)
    keep: int = Field(default=7, ge=1)
    dir: str = "data/backups"
    send_to_admin: bool = True
    max_send_mb: float = Field(default=45, gt=0)  # Bot API upload limit is 50 MB


class BrandingConfig(BaseModel):
    """Our channel and bot (post signature, deep-link buttons). Usernames without ``@``.

    No defaults on purpose: the real usernames live only in ``config/settings.yaml``.
    """

    channel_username: str
    channel_title: str
    bot_username: str

    @field_validator("channel_username", "bot_username")
    @classmethod
    def _no_at(cls, v: str) -> str:
        return v.strip().lstrip("@")


class BotConfig(BaseModel):
    """The public bot (bot/): middlewares and menus."""

    # A user's updates closer than this are dropped (flood protection). Admins are never limited.
    throttle_seconds: float = Field(default=1.0, ge=0)
    # users.last_active_at / username are written at most this often per user.
    touch_interval_seconds: float = Field(default=60, ge=0)


class PostingConfig(BaseModel):
    """📢 E'lon joylash — jobs submitted by users (services/job_submission.py)."""

    max_per_day: int = Field(default=2, ge=1)  # per user, rolling 24 hours
    min_interval_minutes: float = Field(default=10, ge=0)
    max_waiting: int = Field(default=1, ge=1)  # pending_review / queued / sending at once
    # auto: only scam words go to the admin; suspicious_only: + a new user's first job;
    # all: every job is checked by an admin first.
    moderation: Literal["auto", "suspicious_only", "all"] = "suspicious_only"
    max_links: int = Field(default=2, ge=0)  # more links than this = spam
    max_caps_ratio: float = Field(default=0.6, gt=0, le=1)  # of letters, texts of 20+ letters
    max_emoji: int = Field(default=10, ge=0)
    duplicate_days: int = Field(default=14, ge=1)
    # field lengths (characters)
    max_title: int = Field(default=100, ge=10)
    max_short_field: int = Field(default=150, ge=10)  # company, salary, city, schedule
    max_requirements: int = Field(default=600, ge=50)


class SearchConfig(BaseModel):
    """🔍 Ish qidirish (services/search.py) and the USD rate for salary filters."""

    page_size: int = Field(default=5, ge=1, le=10)
    # "2 mln+" ... buttons of the salary step (so'm per month)
    salary_steps: list[int] = Field(
        default_factory=lambda: [2_000_000, 4_000_000, 6_000_000, 10_000_000]
    )
    # USD salaries are compared in so'm: kv_store.usd_rate (cbu.uz, once a day), else this.
    usd_rate_fallback: float = Field(default=12_800, gt=0)
    usd_rate_url: str = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
    usd_rate_refresh_hours: float = Field(default=24, gt=0)


class AlertsConfig(BaseModel):
    """🔔 Job alerts (services/alerts.py, runs in the worker)."""

    max_per_user: int = Field(default=5, ge=1)  # subscriptions per user
    # alert messages per user per 24 h; the rest go to the evening digest
    daily_limit: int = Field(default=20, ge=1)
    digest_hour: int = Field(default=20, ge=0, le=23)  # Asia/Tashkent
    digest_max_items: int = Field(default=20, ge=1)
    per_second: float = Field(default=25, gt=0, le=30)  # Bot API: ~30 messages/s in total
    poll_seconds: float = Field(default=30, gt=0)  # how often newly published jobs are checked


class ExpiryConfig(BaseModel):
    """Job life time in search (services/expiry.py, a worker task). The channel post stays."""

    aggregator_days: int = Field(default=21, ge=1)
    user_days: int = Field(default=30, ge=1)
    remind_days_before: float = Field(default=2, ge=0)  # user jobs: "Uzaytirasizmi?"
    check_minutes: float = Field(default=30, gt=0)


class BroadcastConfig(BaseModel):
    """/broadcast (admin): a message to every user of the bot, slowly."""

    per_second: float = Field(default=20, gt=0, le=30)


class AIConfig(BaseModel):
    """Gemini helper (ai/). Works only with GEMINI_API_KEY in .env; any error -> regex result."""

    enabled: bool = True  # the admin can also switch it off at runtime: /ai (kv_store)
    # Called for a job ad whose regex confidence is below this, or that is Russian / English.
    min_confidence: float = Field(default=0.7, ge=0, le=1)
    translate_foreign: bool = True
    daily_limit: int = Field(default=200, ge=0)  # requests per day (Asia/Tashkent), all keys
    min_interval_seconds: float = Field(default=4, ge=0)  # free tier: a few requests a minute
    timeout_seconds: float = Field(default=10, gt=0)
    pause_minutes_rate_limited: float = Field(default=60, gt=0)  # after HTTP 429
    pause_minutes_error: float = Field(default=5, gt=0)  # after 5xx / timeout / network
    max_input_chars: int = Field(default=3000, ge=200)


class FormatterConfig(BaseModel):
    min_confidence: float = Field(default=0.7, ge=0, le=1)
    max_caption_length: int = Field(default=1024, ge=200)
    max_tags: int = Field(default=5, ge=1)
    max_feature_tags: int = Field(default=2, ge=0)
    max_contacts: int = Field(default=3, ge=1)


class ImagesConfig(BaseModel):
    root: str = "assets/images"
    fallback_category: str = "boshqa"


class AppConfig(BaseModel):
    """Content of ``config/settings.yaml``."""

    sources: list[SourceConfig] = Field(default_factory=list)
    collector: CollectorConfig = Field(default_factory=CollectorConfig)
    publisher: PublisherConfig = Field(default_factory=PublisherConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    branding: BrandingConfig
    bot: BotConfig = Field(default_factory=BotConfig)
    posting: PostingConfig = Field(default_factory=PostingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    expiry: ExpiryConfig = Field(default_factory=ExpiryConfig)
    broadcast: BroadcastConfig = Field(default_factory=BroadcastConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    formatter: FormatterConfig = Field(default_factory=FormatterConfig)
    images: ImagesConfig = Field(default_factory=ImagesConfig)

    @field_validator("sources", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return v or []


class ProfessionConfig(BaseModel):
    title: str
    keywords: list[str] = Field(default_factory=list)


class CategoryConfig(BaseModel):
    title: str
    hashtag: str
    image: str | None = None
    keywords: list[str] = Field(default_factory=list)
    professions: dict[str, ProfessionConfig] = Field(default_factory=dict)


class FeatureTagConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)


class LandmarkConfig(BaseModel):
    keywords: list[str]
    district: str | None = None


class RegionConfig(BaseModel):
    title: str
    hashtag: str
    keywords: list[str] = Field(default_factory=list)
    # district display name -> spellings
    districts: dict[str, list[str]] = Field(default_factory=dict)
    landmarks: list[LandmarkConfig] = Field(default_factory=list)


class RegionsConfig(BaseModel):
    regions: dict[str, RegionConfig] = Field(default_factory=dict)
    street_words: list[str] = Field(default_factory=list)
    multi_region: str = "kop_hudud"
    multi_region_title: str = "Ko'p hudud"
    remote_keywords: list[str] = Field(default_factory=list)
    office_keywords: list[str] = Field(default_factory=list)


class ExtractLabels(BaseModel):
    title: list[str] = Field(default_factory=list)
    company: list[str] = Field(default_factory=list)
    salary: list[str] = Field(default_factory=list)
    schedule: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    location: list[str] = Field(default_factory=list)


class HiringPhrases(BaseModel):
    before: list[str] = Field(default_factory=list)  # "Oshpaz kerak"
    after: list[str] = Field(default_factory=list)  # "Требуется повар"


class ExtractConfig(BaseModel):
    """Content of ``config/extract.yaml`` (regex extractor words)."""

    labels: ExtractLabels = Field(default_factory=ExtractLabels)
    hiring_phrases: HiringPhrases = Field(default_factory=HiringPhrases)
    position_list_headers: list[str] = Field(default_factory=list)
    salary_negotiable: list[str] = Field(default_factory=list)
    salary_periods: dict[str, list[str]] = Field(default_factory=dict)
    salary_not_salary: list[str] = Field(default_factory=list)


class TitleTranslations(BaseModel):
    """Content of ``config/title_translations.yaml``."""

    exact: dict[str, str] = Field(default_factory=dict)
    words: dict[str, str] = Field(default_factory=dict)


class FiltersConfig(BaseModel):
    ban: list[str] = Field(default_factory=list)
    spam: list[str] = Field(default_factory=list)
    scam: list[str] = Field(default_factory=list)
    scam_exceptions: list[str] = Field(default_factory=list)
    ad_patterns: list[str] = Field(default_factory=list)
    # Post kind detection (processing/classify.py)
    job_markers: list[str] = Field(default_factory=list)
    not_job_markers: list[str] = Field(default_factory=list)
    # decisive ad markers (a course topic list) -> not_job whatever the job score
    not_job_strong_markers: list[str] = Field(default_factory=list)
    resume_markers: list[str] = Field(default_factory=list)
    closed_markers: list[str] = Field(default_factory=list)
    opportunity_markers: list[str] = Field(default_factory=list)
    opportunity_strong_markers: list[str] = Field(default_factory=list)
    # "bepul amaliyot" + one of these ("3-oydan haq to'lanadi") -> not decisive
    opportunity_strong_exceptions: list[str] = Field(default_factory=list)


class SourceRule(BaseModel):
    """Per-channel cleaning / classification hints from ``config/source_rules.yaml``."""

    cut_from: list[str] = Field(default_factory=list)
    strip_lines: list[str] = Field(default_factory=list)
    exact_lines: list[str] = Field(default_factory=list)
    header_lines: list[str] = Field(default_factory=list)
    header_junk_words: list[str] = Field(default_factory=list)
    extra_own_usernames: list[str] = Field(default_factory=list)
    job_hashtags: list[str] = Field(default_factory=list)
    non_job_hashtags: list[str] = Field(default_factory=list)
    # True: a post without any of job_hashtags is not a job ad (the channel always tags its ads)
    require_job_hashtag: bool = False
    closed_markers: list[str] = Field(default_factory=list)
    drop_trailing_hashtags: bool = False
    notes: str | None = None


class SourceRuleDefaults(BaseModel):
    drop_whitespace_text_links: bool = True
    drop_link_patterns: list[str] = Field(default_factory=list)
    phone_link_pattern: str | None = None
    strip_url_params: list[str] = Field(default_factory=list)
    strip_lines: list[str] = Field(default_factory=list)
    # Our own channel / bot: never a contact of a job, whatever the source
    extra_own_usernames: list[str] = Field(default_factory=list)


class SourceRulesConfig(BaseModel):
    """Content of ``config/source_rules.yaml``."""

    defaults: SourceRuleDefaults = Field(default_factory=SourceRuleDefaults)
    sources: dict[str, SourceRule] = Field(default_factory=dict)

    def for_source(self, identifier: str | None) -> SourceRule:
        """Rules of one channel (case-insensitive, ``@`` optional); empty rules if unknown."""
        if identifier:
            key = identifier.lstrip("@").lower()
            for name, rule in self.sources.items():
                if name.lstrip("@").lower() == key:
                    return rule
        return SourceRule()

    @field_validator("sources", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return v or {}


FALLBACK_CATEGORY = "boshqa"


# --------------------------------------------------------------------------- combined
class Settings(BaseModel):
    """Everything the app needs, in one object."""

    env: EnvSettings
    app: AppConfig
    categories: dict[str, CategoryConfig]
    feature_tags: dict[str, FeatureTagConfig] = Field(default_factory=dict)
    negation_words: list[str] = Field(default_factory=list)
    regions: RegionsConfig
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    title_translations: TitleTranslations = Field(default_factory=TitleTranslations)
    filters: FiltersConfig
    source_rules: SourceRulesConfig = Field(default_factory=SourceRulesConfig)
    config_dir: Path

    @property
    def db_file(self) -> Path:
        return resolve_path(self.env.db_path)

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_file.as_posix()}"

    @property
    def session_file(self) -> Path:
        """Telethon session path without the ``.session`` suffix (Telethon adds it)."""
        return resolve_path(self.env.telethon_session)

    @property
    def data_dir(self) -> Path:
        return self.db_file.parent

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.env.tz)

    @property
    def images_dir(self) -> Path:
        return resolve_path(self.app.images.root)

    @property
    def backup_dir(self) -> Path:
        return resolve_path(self.app.backup.dir)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_settings(
    config_dir: Path | str = DEFAULT_CONFIG_DIR,
    env_file: Path | str | None = DEFAULT_ENV_FILE,
) -> Settings:
    """Load ``.env`` + ``config/*.yaml``. Raises a pydantic ``ValidationError`` on bad values."""
    config_dir = Path(config_dir)
    env = EnvSettings(_env_file=env_file)  # type: ignore[call-arg]
    app = AppConfig.model_validate(_read_yaml(config_dir / "settings.yaml"))
    categories_yaml = _read_yaml(config_dir / "categories.yaml")
    categories_raw = categories_yaml.get("categories") or {}
    categories = {k: CategoryConfig.model_validate(v) for k, v in categories_raw.items()}
    feature_tags = {
        k: FeatureTagConfig.model_validate(v)
        for k, v in (categories_yaml.get("feature_tags") or {}).items()
    }
    regions = RegionsConfig.model_validate(_read_yaml(config_dir / "regions.yaml"))
    filters = FiltersConfig.model_validate(_read_yaml(config_dir / "filters.yaml"))
    source_rules = SourceRulesConfig.model_validate(_read_yaml(config_dir / "source_rules.yaml"))
    return Settings(
        env=env,
        app=app,
        categories=categories,
        feature_tags=feature_tags,
        negation_words=categories_yaml.get("negation_words") or [],
        regions=regions,
        extract=ExtractConfig.model_validate(_read_yaml(config_dir / "extract.yaml")),
        title_translations=TitleTranslations.model_validate(
            _read_yaml(config_dir / "title_translations.yaml")
        ),
        filters=filters,
        source_rules=source_rules,
        config_dir=config_dir,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for the running process."""
    return load_settings()
