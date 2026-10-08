# CLAUDE.md — Ayvona Jobs

This file is loaded automatically by Claude Code in every session. Keep it short and current.

> **Start here:** read `docs/HANDOFF.md` (current state + next steps + multi-user notes), then `docs/PROGRESS.md`.

## What this project is
**Ayvona Jobs** ("I wanna job") — a Telegram job-board system for Uzbekistan.
1. **Aggregator** — reads job posts from source Telegram channels (Telethon, user account), dedups, categorizes,
   reformats them with regex (no AI in v1) and auto-publishes to our channel **@ayvonajobs** via Bot API.
2. **Public bot** (**@ayvona_jobs_bot** — bot usernames must end in "bot") — main menu:
   📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar.
   Anyone can submit a job via a step-by-step form; job seekers search by category / region / salary / keyword
   (newest first), save favorites, and subscribe to alerts.
3. **Gemini (later, optional helper)** — only for posts regex could not parse; cached; any error → regex fallback.

Full plan: `docs/ROADMAP.md`. Architecture and DB models: `docs/ARCHITECTURE.md`. Progress log: `docs/PROGRESS.md`.
Real post samples: `docs/POST_EXAMPLES.md` and `tests/fixtures/posts/`.

## The owner
Sardor is a **beginner** developer on **Windows** (PowerShell, VS Code). Therefore:
- Explain every step simply, in **Uzbek (latin)**. Technical terms may stay in English.
- Always give exact commands for **PowerShell** (not bash) when he must run something locally.
- After finishing a task, tell him: what changed, how to run it, how to check it works.
- Don't make big changes he didn't ask for. If a decision is needed, ask first.

## Hard rules (non-negotiable)
1. **100% free.** No paid APIs, hosting or services. Hosting = Oracle Cloud Always Free VPS (Ubuntu, systemd).
2. **Never lose a job post.** Reliability > speed. Every post is stored in the DB *before* any processing.
   Every stage is a DB status transition; a crash at any point must be recoverable on restart.
   Prefer at-least-once delivery (a rare duplicate is better than a missed post), but guard with dedup.
3. **Fully automatic** publishing for the aggregator. No manual approval per post.
4. **AI is optional.** The system must work 100% without Gemini. AI failure/limit → silent fallback.
5. **Secrets never in git**: `.env`, `*.session`, `data/`. Check `.gitignore` before every commit.
6. **Sources are pluggable**: every source implements `BaseSource`; adding a website must not change the pipeline.
7. Every user-submitted job **must** have a contact: phone (+998…) or Telegram @username.
8. **Channel output = job vacancies only, always in Uzbek Latin.** Resumes, courses, grants, events are never posted.
   Uzbek Cyrillic → transliterated; Russian/English → Uzbek fields only (see docs/SOURCE_ANALYSIS.md §11).
9. **Admin manages sources from the bot, never by editing code/YAML**: add/remove/pause Telegram channels
   and websites (`/addsource`, `/sources`). DB is the source of truth. Every new source type must be manageable this way.
- The public bot and the future website (Phase 17) share ONE business logic: search, posting rules, filters and favorites live in `services/` (no logic inside handlers), so the website reuses it.
10. **The admin gets ONE kind of push: a new user ad waiting for approval.** Errors, monitoring, backups, stats,
    suspicious posts go to the log only (`services/notifier.py` gate; `ADMIN_EXTRA_NOTIFICATIONS=true` restores the old
    messages). Commands the admin types (`/stats`, `/why`, ...) answer as usual. Never add a new unprompted admin message.
11. **An approved user ad is published at once** (`js.approve(publish_now=True)` claims it as `sending`, then
    `Publisher.publish_claimed`) — never through the queue; on a Telegram error it goes back to the queue, never lost.
12. **Jobs are ranked** (`processing/priority.py`, `config/settings.yaml → priority:`): tier 1 office / high pay, 2 normal,
    3 low-skill. Queue order = tier, then newest; tier 3 is capped per day; each tier has its own age limit.
    **Projects** (`jobs.kind = 'project'`, bot menu "🧩 Loyihalar") are not ranked and never appear in job search,
    alerts, the website or the priority backfill — every query over published jobs must filter `kind = 'job'`.
13. **Migrations are additive and data preserving** (nullable / server-default columns); test each on a copy of the real DB.
    The three `jobs` columns families added so far: `active_days`, `priority_*`, `kind` + project columns; plus the new
    table `admin_alert_deliveries`.
14. **Pictures change only with the admin's explicit OK** (`/images review`, `services/image_review.py`): old file backed
    up to `data/images_backup/`, source + licence in `<name>.json`; stock APIs only with a key in `.env`; never scrape.
15. **The one exception to rule 10: an admin's own subscriptions are unfiltered** (`services/admin_alerts.py`,
    `ADMIN_UNFILTERED_ALERTS`, default on). They match `raw_posts` text (words only, no Gemini) BEFORE every pipeline
    filter, so a post is delivered whether or not it is ever published, with a status line saying why. Deduplicated per
    admin and post in `admin_alert_deliveries` (written before the send); hourly cap + digest. The normal alerts skip
    these subscriptions; non-admin subscriptions are untouched. `/alerts` lists them.
16. **A channel post never links to the source channel for "more".** When the caption lost anything (or the text is
    much longer than its fields, or the source is Russian / English) the post gets the "📖 To'liq ma'lumot" button ->
    `/start job_<id>` -> the bot's full card (`jobs.full_html`, same template, nothing shortened). The small "manba"
    attribution in the signature stays. Texts are cut only with `formatter.truncate_units` (after a whole line /
    sentence / list item); title, salary, place and contacts are never cut; a doubtful field is dropped, not guessed
    (company slogans, salaries that cannot be so'm, meaningless requirements). All word lists live in config.

## Stack
- Python **3.12**, managed with **uv** (`uv sync`, `uv run ...`, `uv add ...`)
- Telethon 1.x (reading channels) · aiogram 3.x (Bot API: publishing + public bot)
- SQLAlchemy 2.x (async) + aiosqlite + Alembic migrations · SQLite in **WAL mode**, `busy_timeout=5000`
  (DB access only through `src/ayvona/db/` so we can move to PostgreSQL later)
- SQLite FTS5 for keyword search · rapidfuzz for near-duplicate detection
- pydantic-settings (`.env`) + YAML configs in `config/` · loguru for logging
- pytest + pytest-asyncio · ruff (lint + format)
- Later: google-genai (Gemini), httpx + selectolax (web sources)

## Layout (short)
```
src/ayvona/
  config.py            settings from .env + config/*.yaml
  db/                  models.py, session.py, repositories/
  sources/             base.py, telegram_source.py, registry.py, (web/ later)
  processing/          normalize, dedup, extract, categorize, clean, formatter, pipeline
  publisher/           outbox worker → Bot API
  bot/                 aiogram public bot: handlers/, keyboards, states, middlewares, texts.py
  services/            alerts, expiry, stats, backup, notifier (admin alerts), heartbeat
  ai/                  gemini client + cache (later)
  apps/                entrypoints: collector.py, worker.py, bot.py
config/                settings.yaml, categories.yaml, regions.yaml, filters.yaml, source_rules.yaml,
                       extract.yaml, title_translations.yaml
assets/images/         <category>/<profession>/ 3–4 variants each, rotated (docs/IMAGES.md)
tests/                 fixtures/posts/*.txt + unit tests
deploy/                systemd units + Oracle setup guide
data/                  (gitignored) ayvona.db, *.session, backups/
```
Three processes: `uv run python -m ayvona.apps.collector`, `... .worker`, `... .bot` (+ optional `... .web`, the website).
Extra packages: `ai/` (optional Gemini helper), `sources/web/` (websites, APIs, RSS), `web/` (FastAPI site).

## Conventions
- Type hints everywhere; small functions; docstrings in English, user-facing texts in Uzbek (latin) in `bot/texts.py`.
- All times stored in **UTC**; displayed in `Asia/Tashkent`.
- Text matching: normalize first (lowercase, Uzbek cyrillic→latin transliteration, unify o‘/o'/oʻ, strip emoji).
  Keywords in configs must cover Uzbek latin, Uzbek cyrillic and Russian variants.
- Telegram limits: photo caption ≤ 1024 chars, message ≤ 4096; channel posting ≈ 20/min → configurable interval.
  Handle `RetryAfter` / `FloodWaitError` by sleeping the given time. Cache uploaded image `file_id`s.
- Parse mode: HTML (escape user text with `html.escape`).
- Config values (intervals, limits, keywords) live in YAML/.env, never hard-coded.

## Workflow for every task
1. Read the relevant phase in `docs/ROADMAP.md` and `docs/PROGRESS.md`.
2. For non-trivial work: propose a short plan first, wait for OK.
3. Write code + tests. Run `uv run pytest` and `uv run ruff check .` — both must pass.
4. Update `docs/PROGRESS.md` (what was done, how to run, known issues) and tick the box in ROADMAP.
5. Suggest a commit message (Conventional Commits, e.g. `feat(collector): ...`). Don't push unless asked.

## Commands (PowerShell)
```powershell
uv sync                                   # install deps
uv run python scripts/login_telethon.py   # one-time Telegram login → data/*.session
uv run alembic upgrade head               # apply DB migrations
uv run python -m ayvona.apps.collector    # run collector
uv run pytest                             # tests
uv run ruff check . ; uv run ruff format .
```
