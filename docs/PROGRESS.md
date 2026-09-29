# Progress log

Claude Code har bir bosqichdan keyin shu yerga yozadi: nima qilindi, qanday ishga tushiriladi, ma'lum muammolar.

| Sana | Bosqich | Nima qilindi | Eslatma |
|---|---|---|---|
| 2026-09-29 | Reja | CLAUDE.md, ARCHITECTURE, ROADMAP, POST_EXAMPLES yaratildi | Keyingi qadam: Bosqich 0 (tayyorgarlik) |
| 2026-09-29 | 1 — Skelet | pyproject (uv, src layout), papkalar, `config.py`, `config/*.yaml`, `.env.example`, `.gitignore`, loguru, README, ruff, testlar | 6 test ✅, ruff ✅ |
| 2026-09-29 | 2 — Baza | 12 ta jadval modeli (`db/models.py`), `db/session.py` (WAL, busy_timeout, foreign_keys), Alembic (async) + birinchi migratsiya + `jobs_fts` (FTS5) triggerlari, repository'lar: sources, raw_posts, kv | 25 test ✅, ruff ✅, `alembic check` ✅ |

---

## Qarorlar (Sardor yo'qligida Claude qabul qilgan)

Sardor bu safar reja tasdig'ini kutmaslikni aytdi. Shuning uchun har bir muhim qaror shu yerda, sababi bilan.
Birortasi yoqmasa — ayting, o'zgartiramiz.

### Bosqich 1
1. **uv va Python o'rnatildi.** Kompyuterda na Python, na uv yo'q edi, `uv run pytest` esa har bosqichda shart.
   ROADMAP Bosqich 0 dagi rasmiy buyruq bilan uv o'rnatildi (`C:\Users\codebysardor\.local\bin`),
   Python 3.12.14 ni uv o'zi yuklab oldi. Alohida python.org o'rnatish shart emas.
2. **Build backend: hatchling**, paket `src/ayvona` (src layout). `uv sync` paketni "editable" o'rnatadi.
3. **`settings.yaml` bo'limlarga ajratildi**: `collector:` va `publisher:` (ROADMAP'da tekis kalitlar edi).
   Sabab: keyin `ai:`, `bot:`, `limits:` bo'limlari qo'shiladi — tartibli bo'ladi. Qiymatlar o'sha:
   `poll_interval_seconds: 90`, `initial_backfill: 0`, `publish_interval_seconds: 60`, `max_publish_attempts: 8`.
   Qo'shimcha: `fetch_limit`, `delay_between_sources_seconds`, `fetch_timeout_seconds`, `heartbeat_interval_seconds`.
4. **`.env` dagi hamma qiymat ixtiyoriy** (bo'sh bo'lsa `None`). Shunda testlar va `alembic` `.env` siz ishlaydi.
   Kerakli qiymat yo'q bo'lsa, uni ishlatadigan jarayon (masalan collector) aniq o'zbekcha xato bilan to'xtaydi.
   Nisbiy yo'llar (`DB_PATH`, `TELETHON_SESSION`) loyiha papkasiga nisbatan olinadi — qaysi papkadan
   ishga tushirsangiz ham bir xil ishlaydi.
5. **`tzdata` kutubxonasi qo'shildi** — Windows'da `Asia/Tashkent` vaqt zonasi bazasi yo'q.
6. **`[tool.uv] link-mode = "copy"`** — loyiha D: da, uv keshi C: da; ogohlantirish chiqmasligi uchun.
7. **Loglar**: konsol + `data/logs/<jarayon>_<sana>.log`, har kuni yangi fayl, 14 kun saqlanadi.
   Fayllarga o'zgaruvchilar qiymati yozilmaydi (`diagnose=False`) — token/parol logga tushib qolmasin.
8. **`.gitattributes`: hamma fayllar LF** qator oxiri bilan. Server Linux — CRLF bilan shell skriptlar buziladi.
   VS Code LF fayllarni bemalol ochadi.
9. **Git muallifi**: kompyuterda `git config user.name/email` sozlanmagan. Global sozlamani o'zgartirmadim —
   commit'lar `git -c user.name=... -c user.email=...` bilan qilindi (quyida "Sardor uchun" ga qarang).

### Bosqich 2
1. **Vaqt har doim UTC.** Maxsus `UTCDateTime` turi: bazaga UTC yozadi, o'qiganda "timezone-aware" UTC qaytaradi.
   Vaqt zonasisiz (naive) `datetime` yozishga urinish — xato (tasodifan mahalliy vaqt yozilib qolmasin).
2. **Statuslar Python `StrEnum`**, bazada oddiy matn (`"new"`, `"queued"`...). Bazada CHECK cheklovi
   qo'yilmadi: keyin yangi status qo'shish uchun SQLite'da butun jadvalni qayta qurish kerak bo'lardi.
   Noto'g'ri qiymatni Python baribir rad etadi.
3. **Qat'iy qoida 7 bazada ham himoyalangan:** `jobs` da CHECK — `origin='user'` bo'lsa telefon yoki
   @username bo'lishi shart. Aggregator'ning fallback postlarida aloqa bo'lmasligi mumkin — ruxsat.
4. **`raw_posts.extra` (JSON) ustuni qo'shildi** (ARCHITECTURE'da yo'q edi). Telegram postlarida aloqa ko'pincha
   *yashirin havola* ("HR bilan bog'lanish" so'ziga bog'langan `t.me/...`) yoki URL tugmada bo'ladi — oddiy
   matnda ko'rinmaydi. Xom post keyin qayta yuklanmaydi, shuning uchun bu ma'lumot hozir saqlanishi kerak
   ("hech bir e'lon yo'qolmasin"). Keyin extract bosqichi shu yerdan ham aloqa qidiradi.
5. **`sources.last_seen_id` matn (string)** — web manbalar URL saqlashi uchun. Telegram uchun raqam matn sifatida.
6. **`favorites` va `alert_deliveries` da kompozit PRIMARY KEY** (user_id+job_id, subscription_id+job_id) —
   bu UNIQUE'ning o'zi, alohida `id` kerak emas. Bitta alert ikki marta ketmaydi.
7. **Qo'shimcha ustunlar:** `jobs.created_at/updated_at`, `sources.created_at`, `filter_words.created_at`,
   `category_images.updated_at`, `kv_store.updated_at` — statistika va nosozliklarni tekshirish uchun.
8. **Indekslar:** `raw_posts(status, fetched_at)` (status bo'yicha qidiruvni ham qoplaydi), `jobs(status,
   next_retry_at)`, `jobs(category, region, published_at)`, `content_hash`, `fingerprint`, `grouped_id`, FK'lar.
9. **FTS5 SQL migratsiya faylining ichida** (app kodidan import qilinmaydi — eski migratsiya hech qachon
   o'zgarmasligi kerak). `alembic revision --autogenerate` `jobs_fts*` jadvallarini e'tiborsiz qoldiradi.
   Tokenizer `unicode61 remove_diacritics 2`. ⚠️ Kirill/lotin muammosi: "сотувчи" bilan qidirsa "sotuvchi"
   topilmaydi — Bosqich 12 da qidiruv uchun normalize qilingan matn ustuni qo'shish kerak bo'ladi.
10. **Alembic `render_as_batch=True`** — SQLite'da ustunni o'zgartirish/o'chirish faqat jadvalni qayta qurish
    orqali bo'ladi; batch rejim buni avtomatik qiladi. Cheklovlar nomlari barqaror (naming convention).
11. **Jarayonlar migratsiyani o'zi ishga tushirmaydi.** 3 ta jarayon bir vaqtda yonganda migratsiya "poygasi"
    bo'lmasligi uchun `uv run alembic upgrade head` qo'lda (keyin `deploy.sh` da) ishga tushiriladi.
    Baza tayyor bo'lmasa, collector aniq xabar bilan to'xtaydi.
12. **Repository'lar hozircha SQLite'ga xos** `INSERT ... ON CONFLICT DO NOTHING` ishlatadi. PostgreSQL'ga
    ko'chganda faqat `db/repositories/` dagi importni almashtirish kerak (PostgreSQL ham shu sintaksisni qo'llaydi).
13. **`sources/base.py` (RawItem) Bosqich 2 da yaratildi** — `raw_posts_repo` unga tayanadi.
14. **Testlar:** har test uchun migratsiya qilingan toza vaqtinchalik baza (migratsiya bir marta, keyin nusxa).
    "Model o'zgardi, migratsiya yo'q" holatini ham test ushlaydi (`test_migration_matches_models`).

---

## Sardor uchun

Kompyuter yoniga qaytganingizda qilishingiz kerak bo'lgan narsalar (batafsil — fayl oxirida):

- [ ] **Git muallifini sozlang** (bir marta):
      `git config --global user.name "Sardor"` va `git config --global user.email "sizning@email"`
- [ ] Yangi PowerShell oynasini oching va `uv --version` ishlashini tekshiring (uv PATH'ga qo'shildi).
