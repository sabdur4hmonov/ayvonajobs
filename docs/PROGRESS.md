# Progress log

Claude Code har bir bosqichdan keyin shu yerga yozadi: nima qilindi, qanday ishga tushiriladi, ma'lum muammolar.

| Sana | Bosqich | Nima qilindi | Eslatma |
|---|---|---|---|
| 2026-09-29 | Reja | CLAUDE.md, ARCHITECTURE, ROADMAP, POST_EXAMPLES yaratildi | Keyingi qadam: Bosqich 0 (tayyorgarlik) |
| 2026-09-29 | 1 — Skelet | pyproject (uv, src layout), papkalar, `config.py`, `config/*.yaml`, `.env.example`, `.gitignore`, loguru, README, ruff, testlar | 6 test ✅, ruff ✅ |
| 2026-09-29 | 2 — Baza | 12 ta jadval modeli (`db/models.py`), `db/session.py` (WAL, busy_timeout, foreign_keys), Alembic (async) + birinchi migratsiya + `jobs_fts` (FTS5) triggerlari, repository'lar: sources, raw_posts, kv | 25 test ✅, ruff ✅, `alembic check` ✅ |
| 2026-09-29 | 3 — Collector | `sources/base.py`, `telegram_source.py`, `registry.py`, `apps/collector.py` (`--once` rejimi bilan), `scripts/login_telethon.py`, `scripts/show_status.py`; soxta manba + soxta Telethon client bilan testlar | 66 test ✅ (5 marta ketma-ket), ruff ✅. Haqiqiy Telegram'da **tekshirilmagan** (session yo'q) |
| 2026-09-29 | 4 — Normalize, classify, dedup | 41 fixture (`tests/fixtures/posts/`, bazadan aynan) + 10 dedup fixture; `processing/`: `normalize`, `language`, `keywords`, `contacts`, `boilerplate`, `classify`, `dedup`; `scripts/export_fixtures.py`, `scripts/dedup_report.py` | 251 test ✅ + 24 xfail (extract — Bosqich 5), ruff ✅. **41/41** kind to'g'ri. 377 postda: 27 dublikat guruh (14 kunlik oyna) |
| 2026-09-29 | 5 — Extractor, kategoriya | `processing/`: `extract`, `salary`, `location`, `categorize` (+ `contacts` kengaytirildi); `config/extract.yaml` (yangi), `regions.yaml` (14 hudud, tumanlar, mo'ljallar), `categories.yaml` kalit so'zlari; `jobs.profession` + `jobs.salary_period` (migratsiya `b5e1a7c3d9f2`); `low_quality` statusi; `scripts/extract_report.py`; 735/742 qoida tuzatildi | 370 test ✅ (0 xfail — **24/24 o'tdi**), ruff ✅. 313 job'dan: 2 tasi aloqasiz, 3 tasi low_quality, 309 tasi kanalga chiqadi |
| 2026-09-29 | 6 — Tozalash, shablon, rasmlar | `processing/`: `clean`, `formatter`, `images`; `db/repositories/images_repo.py`; `images` jadvali (migratsiya `c7a4e2d8f1b6`, `category_images` o'rniga); `settings.yaml`: `branding`, `formatter`, `images`; `Extraction.address`; `scripts/make_placeholder_images.py` (Pillow), `scripts/preview_posts.py`; 43 ta snapshot `tests/snapshots/` | 524 test ✅, ruff ✅. Bazadagi 309 e'lon: 285 to'liq shablon, 24 fallback, eng uzuni 1022/1024 |
| 2026-09-29 | 7 — Worker: pipeline + publisher | 5450 filtri (`not_job_strong_markers`); `processing/pipeline.py`, `publisher/outbox.py`, `services/notifier.py`, `botapi.py`, `apps/worker.py`, `apps/runtime.py`, `db/repositories/jobs_repo.py`; migratsiya `d3f8b1c6a2e4` (raw_posts: backfill, dedup, job_id; jobs.buttons); `settings.yaml`: `worker:`, `publisher:` kengaydi; Bot API mock (`tests/fake_bot.py`) | 582 test ✅, ruff ✅. Bazaning NUSXASIDA: 374 post → 284 job navbatga, 24 dublikat, 2 aloqasiz, 2 past sifat. Haqiqiy Telegram'ga **hech narsa yuborilmadi** |
| 2026-09-30 | 8 — Admin, monitoring, backup | `bot/`: `setup.py`, `filters.py`, `texts.py`, `handlers/admin.py`, `admin_sources.py`, `admin_images.py`; `apps/bot.py`; `services/`: `heartbeat.py`, `backup.py`, `stats.py`, `sources_admin.py`; collector manbalarni har siklda bazadan o'qiydi + `pending` kanallarni tekshiradi; migratsiya `e5a9c2f7b3d1` (sources boshqaruvi); `scripts/find_chat_ids.py`, `scripts/backup_now.py` | 632 test ✅, ruff ✅. Haqiqiy Telegram'ga **hech narsa yuborilmadi** |
| 2026-09-30 | 9 — Deploy hujjatlari | `deploy/SETUP_ORACLE.md`, `deploy/systemd/*.service`, `deploy/NOTES.md`, `scripts/deploy.sh` | Server hali yo'q |
| 2026-09-30 | Tuzatish | Haqiqiy username'lar `branding` dan, matnda heshteg yo'q, manzilda vergul | 677 test ✅ |
| 2026-09-30 | Tuzatish | `scripts/reformat_queued.py` + worker start'ida navbatni qayta formatlash | 685 test ✅. Laptopda 3 jarayon ishlayapti, kanalga real postlar chiqyapti |
| 2026-09-30 | `max_age_hours` | 24 soatdan eski e'lon kanalga chiqmaydi (`jobs.status=skipped_old`), `/retry` va `/stats` da ko'rinadi | 694 test ✅, ruff ✅ |
| 2026-09-30 | Monitoring | Collector o'chiq → bitta "Collector jim" (kanal-jimlik xabarlari yo'q) | 696 test ✅ |
| 2026-09-30 | 10 — Ommaviy bot asosi | /start + users, menyu, deep link'lar, ⭐ saqlanganlar, middleware'lar (throttling, ban) | 711 test ✅ |
| 2026-09-30 | 11 — E'lon joylash | 8 qadamli forma, aloqa majburiy, limitlar, filtrlar, moderatsiya, muallifga havola | 747 test ✅ |
| 2026-09-30 | 12 — Qidiruv | Usta + so'z bilan (FTS5, kirill/lotin), USD kursi; migratsiya `f2b6d8a4c1e3` | 762 test ✅ |
| 2026-10-01 | 13 — Obunalar | Obuna ustasi, worker'da yuborish, kunlik limit + dayjest; migratsiya `a7c3e9f1b5d8` | 771 test ✅ |
| 2026-10-01 | 14 — Yopish, muddat, statistika | 📋 Mening e'lonlarim, kanal posti "YOPILDI", 21/30 kun muddat + eslatma, /stats, /addword /delword /words /ban /unban /broadcast; migratsiya `b8d4f0a2c6e9` | 783 test ✅ |

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

### Bosqich 3
1. **`fetch_new()` `list[RawItem]` emas, `FetchResult(items, cursor)` qaytaradi** (ARCHITECTURE 6-bo'limdan
   farq). Sabab: postsiz ham kursor oldinga siljishi kerak bo'lgan holatlar bor — birinchi ishga tushish
   (`initial_backfill: 0` → faqat oxirgi ID eslab qolinadi) va oxirgi xabarlar servis xabari bo'lsa
   (ularni har siklda qayta o'qimaslik uchun).
2. **Ishonchlilik:** tarmoq so'rovi tranzaksiyadan *tashqarida*; keyin `raw_posts` INSERT (dublikat bo'lsa
   jim o'tkazib yuboriladi) + `last_seen_id` — **bitta tranzaksiyada**. Istalgan joyda xato/o'chish bo'lsa,
   ikkalasi ham saqlanmaydi va keyingi siklda o'sha postlar qayta olinadi. Raqamli kursor hech qachon
   orqaga ketmaydi.
3. **Katta "qarz" bo'laklab olinadi:** collector uzoq o'chiq tursa, har siklda kanal boshiga `fetch_limit`
   (200) tadan eng eskisidan boshlab olinadi — hech narsa tashlab ketilmaydi.
4. **Xatolar tarqalmaydi:** bitta manba xatosi (tarmoq, kanal topilmadi, timeout 120 s) faqat o'sha manbaning
   `error_count/last_error` iga yoziladi. Baza vaqtincha band bo'lsa ham jarayon yiqilmaydi.
5. **FloodWait:** Telethon 60 s gacha bo'lgan kutishlarni o'zi bajaradi; undan uzog'ida collector aytilgan
   vaqt + 1 s kutadi (bitta akkaunt — hamma kanallar uchun). Kutish Ctrl+C/SIGTERM bilan to'xtatiladi.
6. **Yashirin havolalar va URL tugmalar** `raw_posts.extra` ga saqlanadi (Bosqich 2, 4-qaror). Havola
   ko'rinishi (link preview) media hisoblanmaydi. Faqat rasmli postlar saqlanadi (`text=""`, `has_media=True`),
   servis xabarlari va bo'sh postlar o'tkazib yuboriladi. Albomlar `grouped_id` bilan.
7. **`sources.type` oddiy matn** (`"telegram"`, keyin `"web:hh_uz"`) — ROADMAP 16 dagi registry kalitlari
   uchun. Buning uchun Bosqich 2 dagi birinchi migratsiya fayli tahrirlandi (bu ustun VARCHAR(64) bo'ldi).
   Hali hech qayerda haqiqiy baza yo'q edi, shuning uchun alohida migratsiya shart emas.
8. **Heartbeat:** ishga tushishi bilan darhol, keyin har 60 s — `kv_store` dagi `heartbeat:collector`.
   Har sikl oxirida `collector:last_cycle_at` ham yoziladi (heartbeat tirik, lekin sikl osilib qolgan
   holatni keyin monitoring ajrata olishi uchun). Testda topilgan poyga xatosi tuzatildi: `--once`
   rejimida heartbeat yozilmay qolishi mumkin edi.
9. **`--once` bayrog'i** — bitta sikl qilib chiqadi. Tekshirish va sozlash uchun qulay.
10. **Collector hech qachon telefon/kod so'ramaydi** — faqat mavjud session bilan ulanadi. Session yo'q
    yoki eskirgan bo'lsa, o'zbekcha xabar bilan to'xtaydi. Login — faqat `scripts/login_telethon.py`.
11. **settings.yaml ↔ baza sinxroni:** ro'yxatdan olib tashlangan kanal o'chirilmaydi, `enabled=false`
    bo'ladi (eski postlar unga bog'langan). Kursor sinxronda saqlanib qoladi. Identifikator `@kanal`,
    `kanal`, `t.me/kanal`, `https://t.me/s/kanal` yoki `-100...` ko'rinishida bo'lishi mumkin.
12. **Qo'shimcha: `scripts/show_status.py`** — manbalar holati, heartbeat va oxirgi postlarni ko'rsatadi
    (SQLite Viewer o'rnatmasdan tekshirish uchun).

**Ma'lum cheklovlar (keyingi bosqichlar uchun):**
- Manba kanalda post keyin **tahrirlansa yoki o'chirilsa**, biz buni bilmaymiz (birinchi olingan versiya saqlanadi).
- Haqiqiy Telegram bilan hali sinalmagan — `iter_messages(min_id, reverse=True)` xatti-harakati Telethon
  hujjatiga ko'ra yozilgan va soxta client bilan test qilingan.
- Windows'da faqat Ctrl+C ishlaydi; serverda (Linux) SIGTERM ham toza to'xtatadi.

### Bosqich 4
Sardor tasdiqlagan qarorlar: aloqasiz job → `has_contact=False` (`no_contact` statusini Bosqich 7 qo'yadi);
`no_text` turi (matnsiz albom qismlari birlashtiriladi, yolg'iz rasm → `no_text`).

1. **Ikki xil matn shakli.** `normalize()` — o'zbek kirill → lotin, ruscha o'zgarmaydi (har qator alohida
   hal qilinadi). `fold()` — hamma kirill → lotin, faqat kalit so'z qidirish uchun (config so'zlari ham
   `fold` qilinadi, shuning uchun "иш излаяпман" lotincha postda ham topiladi).
2. **So'z chegarasi faqat boshida:** "grant" ≠ "emigrant", lekin "vakansiya" → "vakansiyalar",
   "forum" → "forumga" topiladi (o'zbek tilidagi qo'shimchalar uchun).
3. **Kanal "imzosi" tasnifdan oldin olib tashlanadi** (`boilerplate.py`, `source_rules.yaml` dagi
   `cut_from/strip_lines/...`). Aks holda "Agar vakansiya sizga mos bo'lmasa..." footeri har reklamaga
   job ball qo'shardi. 40% xavfsizlik qoidasi ham shu yerda. Bosqich 6 dagi `clean.py` shu qoidalarni
   asl matnga qo'llaydi.
4. **Tasnif tartibi:** no_text → closed (marker yoki `Ariza muddati` o'tgan) → resume → suspicious →
   haq to'lanmaydigan amaliyot → kanal teglari → opportunity/reklama (job ball < 4 bo'lsa) → job (ball ≥ 2).
   Reklama uchun **reklama belgilari soni ≥ job ball** bo'lishi kerak ("xodimlarga 50% chegirma" haqiqiy
   e'lonni reklamaga aylantirmasin).
5. **Config o'zgarishlari** (`filters.yaml`): job markerlar qo'shildi (kk, oklad, vazifalar, tajriba shart
   emas, we're hiring, в поисках, ...); `"исмим:"` ikki nuqta bilan (maslahat postidagi "Mening ismim Ali"
   rezyume emas); `scam_exceptions` ("mijozlardan oldindan to'lovlarni qabul qilib" — ish vazifasi, scam emas);
   `opportunity_strong_markers` (haq to'lanmaydigan amaliyot — ball qancha bo'lsa ham); maosh jadvali /
   yangilik markerlari (edustaffs/6799). `source_rules.yaml`: @kasbdoruz uchun `require_job_hashtag: true`
   (`#vakansiya` siz post — maslahat).
6. **Dedup** (`dedup.py`), 14 kun: `hash` (aynan bir xil tozalangan matn) → `fingerprint` (lavozim + birinchi
   aloqa, matn ≥ 70%) → `fuzzy` (≥ 90% + lavozim ≥ 85 YOKI umumiy aloqa). Xavfsizlik: lavozimlar aniq har xil
   (< 50) bo'lsa umumiy aloqa hisobga olinmaydi (@jobs_fba da admin kontakti hamma e'londa); 85–90% oralig'ida
   IKKALASI ham shart (lavozim ≥ 85 VA umumiy aloqa). Dublikatlar ham indeksga qo'shiladi — qayta postlar
   zanjiri birinchi postga bog'lanadi. Lavozim hozircha taxminiy (`guess_title`), Bosqich 5 da extract'dan.
7. **Aloqa topish** (`contacts.py`) — yengil versiya (telefon, @username, t.me, email, yashirin havola,
   tugma, `t.me/+998...` = telefon, bot `?start=` = ariza havolasi). Bosqich 5 kengaytiradi.
8. **Fixture'lar bazadan** `scripts/export_fixtures.py` bilan (LF, UTF-8). Yangi misol:
   `uv run python scripts/export_fixtures.py @kanal 123`. `expected` qo'lda to'ldiriladi.
9. `tests/test_config.py` dagi `sources == []` tekshiruvi olib tashlandi — settings.yaml da endi 19 kanal bor.

**Natija:** 41/41 misolda kind to'g'ri, til 40/40 (#18 kanal menyusi aralash — til belgilanmadi).
Butun baza (377 → 374 post, albomlar birlashtirildi): job 311, not_job 35, closed 11, opportunity 9,
no_text 4, suspicious 2, resume 2. Dedup: **27 guruh, 33 dublikat post** (1 kunlik oynada 18 guruh;
SOURCE_ANALYSIS 22 degan edi — farq ehtiyotkorlikdan: shubhali juftlar dublikat deyilmaydi).

**Ma'lum cheklovlar:**
- `digitalitvacancy/735` (Anorbank vakansiyalar ro'yxati, faqat "havola" lar) → not_job (ball 1) — o'tkazib yuboriladi.
- `digitalitvacancy/734` (intervyu maslahati) va `Ish_Toshkent/6745` (kanallar papkasi reklamasi) → job,
  lekin aloqasiz → Bosqich 7 da `no_contact`, kanalga chiqmaydi.
- Ko'rib chiqish uchun: `uv run python scripts/dedup_report.py --review` (ball ≤ 2 yoki aloqasiz job'lar),
  `--kinds` (hamma e'lon bo'lmaganlar va sababi).

### Bosqich 5
Sardor qarorlari (bosqich boshida qo'llandi):
1. **`digitalitvacancy/735` (Anorbank) endi job.** Yangi qoida (`classify.py`, 5b-qadam): **lavozimlar ro'yxati,
   har biriga alohida ariza havolasi** (yashirin "(havola)" → hh.uz, forma, telegra.ph; kamida 2 ta har xil havola)
   → job. Qoida closed/resume/scam/haq to'lanmaydigan amaliyotdan keyin turadi. Havolalar matndagi tartib bo'yicha
   qatorlarga bog'lanadi (bir xil "(havola)" matni 11 marta takrorlanadi).
   **Hamma not_job/opportunity postlar (34 + 9 = 43 ta) bittalab ko'rildi.** Yana bittasi e'lon chiqdi:
   **`digitalitvacancy/742`** ("Dastlabki 2 oy bepul amaliyot, 3-oydan haq to'lanadi, rasmiy shartnoma") —
   `opportunity_strong_exceptions` (filters.yaml) qo'shildi: "bepul amaliyot" + "haq to'lanadi" → hal qiluvchi emas.
   ⚠️ Bu munozarali: faqat yaxshi natija ko'rsatganlarga to'lanadi. Yoqmasa — `filters.yaml` dan o'chiring.
   Qolgan 41 tasi to'g'ri: hazil/AI yangiliklar (@unilance teglari), maslahat va huquqiy postlar, kurs/bot
   reklamalari, tadbir/forum/Dev Camp, grant/fellowship/UNDP stipendiya, Uzum akademiyasi, xizmat reklamasi,
   kanal menyusi, "vakansiyalar yopildi" e'loni, matnsiz forma havolasi (@NextHireX/2513–2514, 2531–2532).
   Ikkala post `tests/fixtures/regressions/` ga qo'shildi (41 ta asosiy misol o'zgarmasin deb alohida papka).
2. **POST_EXAMPLES #2 (25039)**: `salary_period` olib tashlandi, `salary_min/max: null`, `salary_text: "250 000"`.
   Qo'shimcha qarorim: son bo'lmasa **`currency` ham `null`** (valyuta faqat son bilan ma'noli). `make_examples.py`,
   fixture va POST_EXAMPLES.md yangilandi. ⚠️ `data/make_examples.py` gitignore'da — o'zgarish faqat kompyuteringizda.
3. **regions.yaml**: "Rakat / Ракат" → `toshkent_sh` mo'ljali (tuman aniq emas).
4. **`low_quality` statusi** (`RawPostStatus.LOW_QUALITY`, oddiy VARCHAR — migratsiya shart emas): job, lekin lavozim
   ham, maosh ham topilmagan → kanalga chiqmaydi, admin hisobotida. `Extraction.publish = aloqa bor VA low_quality
   emas`. #19 (Crafers, 40829): kind job, `publish: false`; forma havolasi `apply_url` sifatida saqlanadi (admin ko'radi).
   Hozir 3 ta: 40829, 40838 (Crafers qayta posti), Ish_Toshkent/6745 (aslida kanallar papkasi reklamasi).

Bosqich 5 ning o'z qarorlari:
5. **Hammasi qatorma-qator.** Har qatorning 2 shakli: `display` (o'qiladigan: NFKC, emoji yo'q, harf va alifbo
   saqlanadi) va `folded` (qidiruv uchun). So'zlar soni bir xil — folded'dagi topilma display'ga so'z o'rni bo'yicha
   qaytariladi. Shuning uchun lavozim/kompaniya **asl alifboda** qoladi ("моддий ашёвий хисобчи") — lotinga
   o'girish Bosqich 6 formatter'da. `normalize_lines()` va `boilerplate.keep_mask()` shu uchun qo'shildi
   (`normalize()`/`strip_boilerplate()` natijasi o'zgarmadi — dedup soni ham o'sha 27 guruh).
6. **Qolip kalitlari, "... kerak" iboralari, ro'yxat sarlavhalari, maosh so'zlari — `config/extract.yaml`** da (kodda
   emas). Lavozim tartibi: `Lavozim:/Position:/Вакансия:` kaliti → "X kerak / ищет X / We are looking for X" (birinchi
   8 qator) → "Требуется:" + keyingi qator → kasb nomi bor qisqa birinchi qator → kasb nomi (categories.yaml).
   "Maktabga Ayol oshpaz" → "Ayol oshpaz" (joy/maqsad qismi kesiladi), "Sotuv menejer yigitlar" → "Sotuv menejer",
   "mas'uliyatli va chaqqon xodimlar" → lavozim emas.
7. **Maosh asl valyutada saqlanadi** (USD — USD, so'mga aylantirilmaydi). ARCHITECTURE "so'mga keltirilgan" degan edi;
   kurs bilan qidiruv — keyin (Bosqich 12, `kv_store.usd_rate`). Aql-hush chegaralari valyuta+davr bo'yicha
   (`salary.py: SANE_RANGES`): oylik so'm 500 ming–200 mln, kunlik 30 ming–5 mln, oylik USD 50–30 000 ...
   Chegaradan tashqari → son yo'q, faqat `salary_text`. Davr topilmasa — `month`. "Fiks + KPI" → faqat min.
   Diapazondagi xato yozuv ("4 000 000-10 00 0000") juftiga qarab tuzatiladi → 10 000 000.
8. **Hudud**: eng uzun moslik ustun ("Toshkent viloyati", "Samarqand Darvoza" — Toshkentdagi mo'ljal);
   "X ko'chasi" — hudud emas; @username/havola ichidagi "tashkent" — hudud emas. Toshkent sh. + Toshkent vil. = bitta
   hudud (ko'p ovoz olgani); boshqa 2+ hudud → `kop_hudud` (`regions` ro'yxatida hammasi — teglar uchun).
   `is_remote`: yolg'iz "online" emas ("online do'kon"); qatorda "office/ofisda" bo'lsa — masofaviy emas.
9. **Kategoriya balli**: kasb = 3×(lavozimdagi so'zlar) + (matndagi so'zlar), kategoriya = eng yaxshi kasbi +
   kategoriya darajasidagi so'zlar ("restoran", "ombor", "bank", "o'quv markaz"...); uzun moslik qisqasini yutadi
   ("marketing manager" ichidagi "manager" hisoblanmaydi); teng bo'lsa — postda birinchi kelgani. 2 harfli so'zlar
   ("qa", "hr", "it") faqat butun so'z ("qarashga" ≠ QA). Natijada "boshqa" 27 → 7.
   🐞 Topilgan eski xato: `categories.yaml` da `0,5 stavka` YAML'da ikki elementga bo'linib ketgan edi — tuzatildi.
10. **Ko'p vakansiya** (`positions`, `multi`): "Ochiq vakansiyalar:" + ro'yxat → har qatorda ariza havolasi →
    1️⃣ 2️⃣ bloklar → har biri o'z maoshi/manzili bor bir necha "... kerak" bloki (bir lavozimning 1-/2-smenasi
    ko'p vakansiya emas). Sarlavha = kompaniya (bitta bo'lsa) yoki "Bir nechta vakansiya".
11. **Aloqa** (`contacts.py`): noma'lum operator kodi faqat qatorda "tel/aloqa/bog'lanish" bo'lsa; havola ichidagi
    raqamlar telefon emas; `t.me/user?text=...` — username (Yandex Eats), `?start=` — ariza havolasi; LinkedIn post
    havolasi — apply_url (@unilance); Instagram/Facebook/YouTube hech qachon apply_url emas; `apply_url` ball bo'yicha
    tanlanadi (forma/hh.uz/telegra.ph/.../apply > "Apply here" tugmasi > matndagi havola), footer "Jobs/Platform" —
    aloqa emas; `utm_*`, `hhtm*`, `source` parametrlari olib tashlanadi. Username asl yozilishida (`@HR_KONIDA`).
12. **`confidence`**: lavozim (kalit/ibora/ro'yxat) 0.35, (kasb nomidan) 0.2, aloqa 0.35, maosh 0.1, hudud 0.1,
    kompaniya/ish vaqti 0.1. Lavozim + aloqa ≥ 0.7 ✅.
13. **`title_uz`**: ru/en e'lonlar uchun `title_translations.yaml` (exact, keyin so'zma-so'z). "Fleet Specialist" →
    "Avtopark mutaxassisi".
14. **Baza**: `jobs.profession`, `jobs.salary_period` — migratsiya `b5e1a7c3d9f2`. Oddiy `ADD COLUMN` (batch rejim
    `jobs` ni qayta qurib FTS5 triggerlarini o'chirib yuborardi). Bazaning nusxasida upgrade/downgrade sinaldi.
    **Sizning bazangizga hali qo'llanmagan** — pastda buyruq.
15. `scripts/dedup_report.py` Windows konsolida emoji'da yiqilardi (cp1251) — UTF-8 chiqishga o'tkazildi.

**Natija:** 24/24 sobiq xfail o'tdi (2 tasining kutilgan natijasi Sardor qarori bo'yicha o'zgardi: 25039, 40829).
374 post (313 job): telefon 135 (job'da 129), @username 239 (223), apply_url 79 (67), email 9 (9);
**aloqasiz: 36 post, shundan job — 2 ta** (734 maslahat, 6745 papka reklamasi — ikkalasi aslida e'lon emas).
Job'larda: lavozim 299/313, maosh soni 190, hudud 276, ko'p vakansiyali 11, low_quality 3, kanalga chiqadi 309.
Ko'rish: `uv run python scripts/extract_report.py` (`--jobs`, `--no-contact`, `--low`).

**Ma'lum cheklovlar:**
- 14 job'da lavozim topilmadi (faqat kategoriya) — confidence < 0.7 → Bosqich 6 fallback shablon (masalan 5555 —
  bitta uzun paragraf, 25042 — kasb nomi yo'q kirill sarlavha).
- Dedup hali `guess_title` ishlatadi — Bosqich 7 pipeline'da `make_entry(title=extraction.title)` beriladi.
- "Har video uchun 50 000" kabi KPI summalar maosh bilan aralashsa, aql-hush tekshiruvi sonlarni tashlaydi (faqat matn).
- Ko'p vakansiyali postning kategoriyasi — eng yaxshi / birinchi lavozimniki (v1 qarori, SOURCE_ANALYSIS §9).

### Bosqich 6
1. **`clean.py` qator qarorlarini `boilerplate.keep_mask()` dan oladi** (Bosqich 4) — classify/dedup/extract bilan
   aynan bir xil qatorlar o'chadi. Asl matnning emoji va alifbosi saqlanadi (faqat NFKC, keycap, apostrof bir xil).
   `header_lines` qo'shimcha qo'llanadi. 40% qoidasi ishlasa — `logger.warning` (bazada 2 ta: Crafers 40829/40838).
2. **Aloqa hech qachon o'chmaydi:** o'chirilgan qatorda telefon yoki (kanalniki bo'lmagan) @username bo'lsa va u
   qolgan matnda yo'q bo'lsa — qator qaytariladi (`restored_lines`, log). Bazadagi 313 job'da **0 marta** kerak bo'ldi
   (qoidalar aloqani kesmaydi), lekin himoya turibdi. Yashirin havolalar: reklama (`drop_link_patterns`, bo'sh matnli,
   kanalning o'z akkaunti) va o'chgan qatordagilari tashlanadi; URL tugmalar qoladi. `utm_*`, `text=` ... olib tashlanadi.
   Bot orqali qo'shilgan kanal: `clean(..., only_defaults=True)` (YAML'da bo'lmagan kanalga baribir faqat defaults tushadi).
3. **Shablon — POST_EXAMPLES dagi bilan aynan** (test `test_full_template_matches_the_agreed_example` belgima-belgi
   tekshiradi). Qo'shimcha qatorlar (shablonda yo'q edi):
   - `📧 Email:` — aloqa faqat email bo'lsa ham ko'rinsin;
   - `🔗 Ariza: ariza topshirish` (havola) — **faqat** telefon/username/email bo'lmasa (masalan hh.uz e'lonlari), aks
     holda ariza havolasi faqat tugmada;
   - `📝 To'liq ma'lumot: asl e'londa` — ru/en e'lonlarda va fallback matni qisqartirilganda.
4. **Maosh ko'rinishi:** `4 000 000 – 6 000 000 so'm`, faqat min → `4 000 000 so'mdan`, faqat max → `so'mgacha`,
   USD → `500 – 800 $`, davr → `(kunlik)` / `(haftalik)` / `(soatbay)` (oylik — yozilmaydi), matnda KPI/bonus bo'lsa
   `+ KPI` / `+ bonus`. Son yo'q: "kelishiladi" so'zlari (`extract.yaml: salary_negotiable`) → `Kelishiladi`, aks holda
   o'zbekcha `salary_text` (masalan 25039: `250 000` — sizning Bosqich 5 qaroringiz). ru/en da son yo'q → `Kelishiladi`.
5. **Manzil:** `Extraction.address` qo'shildi ("Manzil:" yorlig'i qiymati). Bor bo'lsa — o'sha (shahar/viloyat nomi
   bo'lmasa oldiga hudud qo'shiladi: `Toshkent sh., Chilonzor 9-kvartal`), yo'q bo'lsa — `Toshkent sh., Chilonzor tumani`
   ("tumani" faqat Toshkent shahri uchun; viloyatlardagi nomlar ko'pincha shahar). Masofaviy → `Masofaviy, ...`.
   Ko'p hudud → hudud nomlari (≤ 3). ru/en da erkin manzil matni ko'rsatilmaydi — faqat bizning hudud nomlari.
6. **Til qoidasi:**
   - Kanalda **kirill harf umuman chiqmaydi** — o'zbek postidagi ruscha qator ham lotinga o'giriladi (test hamma real
     postda tekshiradi). Lavozim kichik harf bilan boshlansa — bosh harf (`Moddiy ashyoviy xisobchi`).
   - ru lavozim: lug'atda **butun** lavozim bo'lsa — tarjima; bo'lmasa **kasb nomi** (`Sotuv menejeri`), u ham bo'lmasa —
     so'zma-so'z. Sabab: ruschani so'zma-so'z o'girish rus grammatikasini qoldiradi ("Menejer po rabote s ...").
   - en lavozim: lug'at (exact, keyin so'zma-so'z); tarjima qilinmagan so'zlar **asl harf kattaligida** qoladi
     (`UX/UI dizayner`, avval `Ux/ui dizayner` edi — `TitleTranslator` ga ko'chirildi, extract ham shundan foydalanadi).
   - ru/en ish vaqti: faqat vaqt va kunlar (`с 10:00 до 19:00, 5/2` → `10:00–19:00, 5/2`), so'z bo'lsa — ko'rsatilmaydi.
7. **Teglar:** `#kasb #kategoriya #hudud(lar)` + ≤ 2 belgi-teg, jami ≤ 5, takror yo'q (operator = operator → bitta).
   Ko'p hududda har hudud tegi (5 tagacha, keyin belgi-teglar sig'maydi). `#boshqa` ham yoziladi (izchillik uchun).
8. **Fallback** (`confidence < formatter.min_confidence`, 0.7): `💼 Yangi ish e'loni — <kategoriya>` + tozalangan matn
   (manbaning `#teg` qatorlari va **faqat aloqani takrorlaydigan** qatorlar — "TELEFON : +998..." — olib tashlanadi,
   chunki pastda `📞 Aloqa` bor) + aloqa. Yashirin havolalar matnga `<a>` bo'lib qaytadi. ru/en fallback'da matn yo'q —
   lavozim (bo'lsa), maosh, manzil va `📝 To'liq ma'lumot`.
9. **1024 belgi Telegram hisobida** (UTF-16: emoji = 2). Qisqartirish tartibi: fallback matni → talablar (qisqarib,
   25 belgidan kam qolsa — o'chadi) → lavozimlar ro'yxati (`… va yana N ta`) → ish vaqti/kompaniya/manzil qisqaradi →
   ish vaqti o'chadi → teglar. Lavozim, maosh, aloqa, imzo, manba — hech qachon. Talablar oldindan 400, manzil 120
   belgigacha. Hamma matn `html.escape`.
10. **Tugmalar:** `FormattedPost.buttons(job_id)` — 1-qator `📩 Murojaat` (birinchi @username) + `🔗 Ariza topshirish`
    (apply_url), 2-qator `⭐ Saqlash` (`t.me/ayvona_jobs_bot?start=save_<id>`; job id kerak — Bosqich 7 da beriladi) +
    `🔍 Boshqa ishlar` (`?start=search`). Kanal/bot nomlari `settings.yaml: branding` da (kodda emas).
11. **Rasmlar:** `category_images` (bitta rasm/kategoriya) → **`images`** jadvali (ARCHITECTURE §4): kasb, fayl yo'li,
    sha256, `telegram_file_id`, `times_used`, `last_used_at`, `is_placeholder`. Navbat = **eng uzoq ishlatilmagani**
    (1→2→3→1; restart'dan keyin ham). Fayl o'zgarsa (hash) — `file_id` o'chadi; eski faylning kech kelgan `file_id` si
    yangi faylga yozilmaydi. Haqiqiy rasm har doim vaqtinchalikdan ustun — batafsil `docs/IMAGES.md`.
    Hech rasm bo'lmasa `pick_image` → `None` (Bosqich 7 publisher shunda matnni rasmsiz yuboradi).
12. **Vaqtinchalik rasmlar git'ga tushmaydi** (`.gitignore`): 249 ta fayl (~9 MB) repo'ni og'irlashtirardi, skript esa
    har joyda 10 soniyada yasaydi. ⚠️ **Bosqich 9 (`deploy.sh`) da `make_placeholder_images.py` ni chaqirish kerak.**
13. **Pillow** qo'shildi (`uv add pillow`) — skript uchun; Bosqich 8 `/addimage` ham ishlatadi.
14. **Snapshot testi:** `tests/snapshots/<kanal>_<id>.html` (43 ta: 41 misol + 2 regressiya). E'lon bo'lmaganlar uchun
    faqat "kanalga chiqmaydi (kind=...)" izohi. Ataylab o'zgartirilgandan keyin yangilash buyrug'i test faylining boshida.
15. **Bosqich 5 ga tegishli topilma (tuzatmadim):** `@Buxgalteriyaishorinlarii/5450` ("Video darsliklar mavzusi" —
    kurs reklamasi) job deb tasniflangan va fallback bilan chiqadi. Filtr so'zi kerak (masalan "video darslik").

**Natija:** 41 misoldan 23 tasi kanalga chiqadi (21 to'liq shablon + 2 fallback), 17 tasi e'lon emas, 1 tasi (40829)
low_quality; 2 regressiya misoli (735, 742) — to'liq shablon. Bazadagi 309 ta chiqadigan e'lon: **285 to'liq shablon, 24 fallback**, 10 tasi qisqartirildi (hammasi
fallback matni), eng uzuni 1022/1024.

**Ma'lum cheklovlar:**
- Ko'p vakansiyali postda maosh/manzil — umumiy (birinchi topilgani), har lavozimniki alohida emas.
- ru/en e'lonning talablari ko'rsatilmaydi (Bosqich 15 Gemini tarjima qiladi).
- Fallback'da manbaning emojilari va KATTA HARFLI sarlavhalari saqlanadi (asl matn shunday).

### Bosqich 7 oldidan — kurs reklamasi (@Buxgalteriyaishorinlarii/5450)
1. **Nega oddiy filtr so'zi yetmadi:** 5450 da "video darslik" reklama belgisi allaqachon bor edi, lekin 74 ta 1C dars
   nomi ichida "oylik ish haqini hisoblash", "ish grafigini to'ldirish", "daromad solig'i" bor → job ball **4**.
   Reklama qoidasi esa faqat ball < 4 bo'lsa ishlaydi (haqiqiy e'londagi "chegirma" so'zi uni buzmasligi uchun).
2. **Yechim:** `filters.yaml` ga yangi ro'yxat **`not_job_strong_markers`** — hal qiluvchi reklama belgilari (ball qancha
   bo'lsa ham `not_job`), xuddi `opportunity_strong_markers` kabi. `classify.py` da bitta qoida (4b-qadam, scam va
   haq to'lanmaydigan amaliyotdan keyin). Ichida faqat **kurs sarlavhasiga xos** iboralar: "video darsliklar mavzusi",
   "bo'yicha videoqo'llanma", "темы видеоуроков" ... "kurs dasturi", "dars mavzulari" ataylab qo'shilmadi — "kurs dasturini
   bilish" o'qituvchi e'lonida uchraydi (so'z faqat boshidan solishtiriladi). Oddiy `not_job_markers` ga ham
   "videoqo'llanma", "videodarslik", "видеоурок" qo'shildi (kuchsiz e'lonlar uchun).
3. **Bazani tekshirdim:** 374 postdagi 313 job'dan **113 tasida** "dars/kurs/video/o'quv/trening/sertifikat" so'zlari
   bor — hammasini bittalab ko'rdim: o'qituvchi, o'quv markazga administrator/sotuv menejeri, videograf, mentor, trener
   e'lonlari — **hammasi haqiqiy ish**. Kurs reklamasi faqat **5450** edi. Eski va yangi `filters.yaml` bilan butun bazani
   solishtirdim: **faqat 5450 o'zgardi** (job → not_job). Endi: job 312, not_job 35 (+ boshqalar o'sha).
4. 5450 `tests/fixtures/regressions/` ga qo'shildi (41 asosiy misol o'zgarmadi, 41/41 o'tadi) + snapshot.
5. ℹ️ `vakansiya` belgisi 5450 da `@Reklama_vakansiyaa` username'i ichidan topilgan — username ichidagi so'zlar job ball
   qo'shmasligi kerak edi. Tuzatmadim (boshqa e'lonlarning balli o'zgarib ketishi mumkin); kerak bo'lsa alohida ko'ramiz.

### Bosqich 7 — Worker: pipeline + publisher
Sardor reja tasdig'ini kutmaslikni aytdi — qarorlar va sabablari:

1. **0-band (eski postlar chiqmasin):** worker **birinchi marta** ishga tushganda bazadagi hamma `new` postlar
   `skipped_backfill` bo'ladi (`kv_store`: `worker:backfill_skipped_at` = vaqt + soni; ikkinchi marta ishlamaydi).
   Keyin: collector yangi kanalning **birinchi** o'qishida olgan tarixiy postlar `raw_posts.is_backfill=1` bo'ladi va
   `publisher.publish_backfill: false` (standart) bo'lsa kanalga chiqmaydi. ⚠️ Collector uzoq o'chib qolib, keyin
   qolganlarini olsa — bu backfill EMAS, ular chiqadi ("hech bir e'lon yo'qolmasin").
   Sizning bazangizdagi 377 post worker birinchi yonganda `skipped_backfill` bo'ladi — siz aytgandek.
2. **Tartib: classify → extract → dedup → clean → format** (ROADMAP'da dedup extract'dan oldin). Sabab: dedup'ga extract
   bergan lavozim kerak (Bosqich 5 eslatmasi) va dedup indeksiga **faqat kanalga chiqadigan** e'lonlar kiradi. Aks holda
   birinchi kelgan ALOQASIZ nusxa keyingi aloqali nusxani "dublikat" qilib qo'yardi va e'lon umuman chiqmasdi.
3. **Statuslar:** `done` (job bo'ldi), `duplicate`, `not_job`, `resume`, `closed`, `opportunity`, `suspicious`, `no_text`,
   `no_contact`, `low_quality`, `skipped_backfill`, `error`. Status ustuni oddiy VARCHAR — yangi statuslar migratsiyasiz.
   E'lon bo'lmaganlarning sababi (`job:kerak, ad:chegirma` ...) `raw_posts.error` ustuniga yoziladi (tekshirish uchun).
   Admin chatga: `suspicious` (sabab + matn boshi), `no_text` (albomning kechikkan rasmi — yuborilmaydi) va xatolar.
4. **Albomlar:** post kelganidan 60 s o'tgach ishlanadi; albomning **bitta qismi** ham yangi bo'lsa — butun albom kutadi.
   Albom ishlangandan keyin kelgan qism — alohida post (matnsiz bo'lsa `no_text`, admin'ga xabarsiz).
5. **Ishonchlilik:** bitta post natijasi (statuslar + job + dedup ma'lumoti) — **bitta tranzaksiya**. Kod xatosi → faqat
   o'sha post `error` + admin'ga xabar, qolganlari davom etadi. Baza band (`OperationalError`) → post `new` bo'lib qoladi,
   keyingi aylanishda qayta. `processing` / `sending` da qolganlar ishga tushganda qayta navbatga.
6. **Dublikat indeksi** xotirada (tez), lekin bazada ham saqlanadi (`raw_posts.dedup_text/title/contacts/fingerprint`) —
   restart'dan keyin oxirgi 14 kunlik e'lonlardan qayta quriladi, har 6 soatda yangilanadi (eskilari tushib ketadi).
   Har bir guruh postida `raw_posts.job_id` (qaysi job) va `duplicate_of` (qaysi postni takrorlaydi).
7. **1b — yig'ish oynasi:** yangi job `next_retry_at = e'lon qilingan vaqt + 20 daqiqa` dan oldin chiqmaydi (collector
   kechikib olgan eski post uchun — darhol). Shu vaqt ichida dublikat kelsa va u **to'liqroq** bo'lsa: to'liqlik bali =
   telefon/@username 2 (faqat email/havola 1) + maosh soni 1 (faqat matn 0.5) + hudud 0.5 + manzil/tuman 0.5 + lavozim 0.5 +
   confidence. Ball **qat'iy katta** bo'lsa — job maydonlari, matni, tugmalari va **manba havolasi** yangi postniki bo'ladi,
   eski post `duplicate`. Kutish vaqti uzaymaydi. `sending`/`published`/urinish bo'lgan job'ga tegilmaydi (shartli UPDATE —
   publisher bilan poyga bo'lmaydi). 14 kundan keyin — yangi e'lon.
8. **Publisher:** navbatdan eng oldin "vaqti kelgan" job (`next_retry_at` bo'yicha) → `sending` (shartli UPDATE) → rasm
   (`pick_image`) → `sendPhoto` (kesh `file_id` yoki fayl) + HTML caption + tugmalar; rasm yo'q → `sendMessage`, link preview
   o'chiq. Postlar orasida 60 s. Xatolar:
   - `TelegramRetryAfter` → urinish sanalmaydi, aytilgan vaqt + 1 s hamma narsa kutadi;
   - HTML xatosi → oddiy matn bilan qayta (havolalar `matn (url)` bo'lib); eskirgan `file_id` → fayl qayta yuklanadi;
     caption uzun → matnli xabar;
   - **sozlama xatosi** (token rad etildi, bot kanalda admin emas, kanal topilmadi) → urinish sanalMAYDI, job navbatda
     qoladi, admin'ga xabar, 5 daqiqa hech narsa yuborilmaydi. Sabab: bot kanaldan chiqarilsa, 8 urinishda hamma e'lon
     `failed` bo'lib ketardi;
   - tarmoq/server/boshqa xato → urinish +1, kutish 30 s, 60 s, 120 s ... (1 soatgacha); 8-urinishdan keyin `failed` +
     admin'ga xabar (`/retry <id>` — Bosqich 8). Tarmoq xatosidan keyin publisher o'sha vaqtcha to'xtaydi (aks holda
     internet yo'qligida har bir job urinishini birin-ketin yeb qo'yardi).
9. **Tokensiz ishlash:** `BOT_TOKEN` yo'q/noto'g'ri yoki `CHANNEL_ID` yo'q → worker yiqilmaydi, o'zbekcha tushuntirish logga
   yoziladi, pipeline ishlayveradi, e'lonlar `queued` bo'lib kutadi (token qo'shilgach chiqadi). `ADMIN_CHAT_ID` yo'q →
   admin xabarlari faqat logda. `--no-publish` bayrog'i — token bo'lsa ham kanalga tegmaslik.
10. **Admin xabarlari (`services/notifier.py`)** — Bosqich 8 ning 1-bandi shu yerda qilindi (worker'ga kerak edi): bir xil
    xabar 10 daqiqada 1 marta; oxirgi yuborilgan vaqt `kv_store` da (`notify:<hash>`) — restart va 3 jarayon uchun umumiy.
    Xabar yuborish hech qachon xato tashlamaydi.
11. **`.env.example`: `CHANNEL_ID` endi bo'sh** (avval `@ayvona` edi) — token qo'shilgan zahoti haqiqiy kanalga tasodifan
    chiqib ketmasin. Sizning `.env` ingizda `CHANNEL_ID` to'ldirilgan — unga tegmadim, "Sardor uchun" ga qarang.
12. **Kod tuzilishi:** collector'dagi `stop_aware_sleep` va signal handler `apps/runtime.py` ga ko'chirildi (worker va bot
    ham ishlatadi). `botapi.py` — token/kanal tekshiruvi va o'zbekcha xato matnlari bir joyda.
13. **Testlar — Bot API mock:** `tests/fake_bot.py` — haqiqiy aiogram `Bot`, lekin HTTP session soxta: tarmoqqa umuman
    chiqmaydi, har so'rovni yozib oladi, xatolarni Telegram'ning haqiqiy JSON javobi ko'rinishida qaytaradi (aiogram o'zi
    `TelegramRetryAfter`, `TelegramForbiddenError` ... ga aylantiradi). 54 ta yangi test: pipeline (statuslar, albom,
    backfill, dedup, yig'ish oynasi, restart), publisher (rasm + file_id kesh, flood, tarmoq, HTML, sozlama xatosi, pauza,
    `sending` dan tiklanish), worker (to'liq aylanish, tokensiz, toza to'xtash), notifier.

**Natija (bazaning NUSXASIDA, asl `data/ayvona.db` ga tegilmadi):** 374 post (377 raw) → **284 ta job navbatga**
(22 tasi fallback shablon), 24 dublikat, 2 `no_contact` (734, 6745), 2 `low_quality` (Crafers), not_job 35, closed 11,
opportunity 8, no_text 4, suspicious 2, resume 2 — 14 soniyada. Yig'ish oynasida almashish 0 (qayta postlar asosan aynan
bir xil matn). Haqiqiy baza hali eski migratsiyada — `alembic upgrade head` kerak.

**Ma'lum cheklovlar:**
- Kanaldagi post chiqqandan keyin manbada tahrirlansa/o'chirilsa — bilmaymiz (Bosqich 3 dagi kabi).
- `error` statusidagi postlarni qayta ishlash buyrug'i hali yo'q. Kerak bo'lsa: bazada `status='new'` qilish.
- `expires_at` hali qo'yilmaydi — Bosqich 14 (21/30 kun).


### Bosqich 8 — Admin, monitoring, backup
Sardor reja tasdig'ini kutmaslikni aytdi — qarorlar va sabablari:

1. **Admin xabarlari** (`services/notifier.py`) Bosqich 7 da yozilgan edi; endi `chat_id` ham oladi — `/addsource`
   natijasi so'ragan admin'ning o'ziga boradi (admin guruhga emas).
2. **Monitoring** (`services/heartbeat.py`), har 5 daqiqada: collector/bot "tirikman" belgisi 10 daqiqadan eski →
   ogohlantirish; manbadan 24 soat post kelmasa → ogohlantirish; manba ketma-ket 5 marta xato bersa → ogohlantirish.
   - **Har muammo uchun bitta xabar** + tiklanganda "✅ ... yana ishlayapti" (holat `kv_store` da `monitor:*`).
     Sabab: 10 daqiqalik takror filtri bilan ham har 10 daqiqada bir xil xabar kelaverardi.
   - Hali **hech qachon** ishlamagan jarayon (masalan bot hali yoqilmagan) — ogohlantirilmaydi.
   - Worker collector va botni kuzatadi, **bot esa worker'ni** — har jarayonni boshqasi kuzatadi.
   - Yangi qo'shilgan, hali posti yo'q kanal: 24 soat qo'shilgan vaqtdan hisoblanadi.
3. **Backup** (`services/backup.py`): worker ichida, har kuni 03:00 (Toshkent). SQLite backup API — collector/bot
   yozib turganda ham to'g'ri nusxa. Fayl avval `*.tmp` ga yoziladi, keyin nomlanadi (yarim fayl backup bo'lib qolmaydi).
   Nom: **`data/backups/ayvona_YYYY-MM-DD.db`**, oxirgi 7 tasi qoladi — o'chirishda **faqat shu nomdagi** fayllarga tegiladi
   (`data/backups/deploy/` — `scripts/deploy.sh` niki, Bosqich 9 sessiyasi bilan kelishildi). Worker 03:00 da o'chiq
   bo'lsa — yoqilganda o'sha kuni qilinadi (`kv_store: backup:last_date`). Admin chatga fayl bo'lib boradi (45 MB gacha).
   Qo'lda: `uv run python scripts/backup_now.py [--send]`.
4. **Admin buyruqlari** (faqat `ADMIN_IDS`): `/stats` (bugun / 7 kun: keldi, chiqdi, dublikat, e'lon emas, shubhali,
   aloqasiz, past sifat, xato; kategoriyalar; jarayonlar holati), `/queue`, `/failed`, `/retry <id…|all>`, `/pause`,
   `/resume`, `/help`, `/cancel`. "Bugun" = Toshkent vaqti bilan yarim tundan. Admin bo'lmaganlarga faqat `/start` ga
   "bot tez orada" javobi (Bosqich 10 gacha). `/` menyusi faqat adminlarga ko'rinadi (`set_my_commands`).
   Handler'lar 3 faylga bo'lindi: `admin.py` (umumiy), `admin_sources.py`, `admin_images.py` — bitta fayl 700+ qator bo'lardi.
5. **Manbalar bazadan boshqariladi** (migratsiya `e5a9c2f7b3d1`: `sources.status`, `added_via`, `added_by`,
   `backfill_request`, `check_interval_minutes`, `daily_limit`):
   - `settings.yaml` endi **faqat boshlang'ich ro'yxat**: yangi kanal bazaga qo'shiladi; YAML'dan olib tashlangan kanal
     o'chirilmaydi; admin botda pauza/o'chirgan kanalni YAML **qayta yoqmaydi** (avval har ishga tushishda yoqib yuborardi).
   - Collector har siklda ro'yxatni bazadan o'qiydi (`SourcePool`) — restart kerak emas; ishlab turgan manba qayta
     yaratilmaydi, pauza qilingani yopiladi.
   - `/addsource @kanal | t.me/kanal | t.me/+taklif` → "eski postlardan nechta: 0 / 5 / 20" → bazaga `pending`.
     Collector keyingi siklda tekshiradi (kanal bormi, o'qib bo'ladimi; taklif havolasi → o'quvchi akkaunt kanalga
     qo'shiladi) → `active` yoki `rejected` + sabab; admin'ga "✅ Qo'shildi: ..., oxirgi post ID ..." yoki "❌ sabab".
     Vaqtinchalik muammo (flood, tarmoq) — `pending` qoladi, keyingi siklda qayta. Guruh/foydalanuvchi — rad etiladi
     (faqat kanallar). Yopiq kanal identifikatori `-100<id>` bo'lib saqlanadi.
   - ⚠️ **Qaror — eski postlar:** 5/20 tanlansa ham ular bazaga olinadi, lekin kanalga faqat
     `publisher.publish_backfill: true` bo'lsa chiqadi (Bosqich 7 qoidasi bilan bir xil). Bazada ular dublikat va keyin
     qidiruv uchun foydali. Tugmani bosishdan oldin shu haqda yozib qo'yiladi. Kerak bo'lsa — sozlamani yoqing.
   - `/addsource web:<nom>` — kodi yozilgan sayt bo'lsa yoqadi (hozir yo'q → "kod hali yozilmagan"); `rss:<URL>` → "tez orada".
   - `/sources` — ro'yxat (✅ ⏸ ⏳ ❌, oxirgi post qachon), bosilsa kartochka: [⏸ Pauza]/[▶️ Yoqish] [🗑 O'chirish]
     [📊 Statistika] [⬅️ Ro'yxat]; saytlar uchun [15 daq] [30 daq] [1 soat]; rad etilgan uchun [🔁 Qayta tekshirish].
     ROADMAP'dagi "[⏸ O'chirish]" o'rniga **"⏸ Pauza"** — "🗑 O'chirish" bilan adashmasin. O'chirish tasdiq so'raydi,
     qator bazada qoladi (`status='deleted'`), postlari saqlanadi. Har o'zgarish logga: `admin <id>: manba ... -> pause`.
6. **Rasmlar** (`/images`, `/images <kasb>`, `/addimage <kasb|kategoriya>`, `#oshpaz` ham bo'ladi): faqat
   `assets/images/` dagi fayllar o'zgaradi — tanlash qoidasi (`processing/images.py`) va post uslubiga **tegilmadi**.
   `/addimage` da rasm Pillow bilan tekshiriladi, `1.jpg, 2.jpg ...` bo'lib saqlanadi; haqiqiy rasm o'zi vaqtinchaliklardan
   ustun. 🗑 bosilgan rasm **o'chirilmaydi**, `data/images_trash/` ga ko'chiriladi (qaytarsa bo'ladi).
7. **`apps/bot.py`** — faqat admin handlerlari + heartbeat + worker monitoringi. `BOT_TOKEN` yo'q/noto'g'ri → o'zbekcha
   xabar bilan chiqadi (yiqilmaydi). `ADMIN_IDS` bo'sh → ogohlantirish. FSM — `MemoryStorage` (restart faqat yarim
   qolgan `/addimage` ni unutadi; Bosqich 10 da doimiy saqlashga o'tish mumkin).
8. **Qo'shimcha himoya:** jarayonlar endi baza **oxirgi migratsiyada** ekanini tekshiradi. Sabab: `git pull` dan keyin
   `alembic upgrade head` unutilsa, eski bazada yangi ustunlar yo'qligidan xato berardi. Hozirgi bazangiz eski
   versiyada — worker/bot "Baza tayyor emas yoki eski versiyada. Avval: uv run alembic upgrade head" deb chiqadi.
9. **Yordamchi skriptlar:** `scripts/find_chat_ids.py` (bot token qo'yilgach kanal/guruh/o'z ID'ingizni topadi,
   hech narsa yubormaydi), `scripts/backup_now.py`.
10. **Test xatosi va tuzatish:** birinchi worker testi monitoring bilan ishga tushib, sizning haqiqiy bazangizdan
    **o'qish rejimida** nusxa olib `data/backups/ayvona_2026-09-29.db` ga yozib qo'ydi (asl bazaga tegmadi). Men uni
    darhol o'chirdim; test sozlamalari endi hech qachon `data/ayvona.db` ga ishora qilmaydi (backup testlarda o'chiq,
    faqat vaqtinchalik papkada).
11. **Testlar** (+50): `test_admin_bot.py` (aiogram Dispatcher'ga soxta update'lar, javoblar Bot API mock'da — faqat
    admin, /stats /queue /retry /pause, /addsource oqimi, /sources tugmalari, /images, /addimage, rasmni o'chirish),
    `test_monitoring.py` (jim jarayon/manba bir marta + tiklanish, backup nusxasi/tozalash/03:00/xato, statistika),
    `test_sources_admin.py` (kiritma tahlili, soxta Telethon bilan tekshiruv, taklif havolasi, collector bazani qayta o'qishi).

**Natija:** 632 test ✅, ruff ✅. Haqiqiy Telegram'ga hech narsa yuborilmadi. `uv run python -m ayvona.apps.bot` va
`... worker` sizning muhitingizda ishga tushirib ko'rildi: token yo'q / baza eski → aniq xabar, yiqilmaydi, bazaga yozmaydi.

**Ma'lum cheklovlar:**
- Saytlar uchun kunlik limit (`daily_limit`) ustuni bor, lekin tugmasi yo'q — Bosqich 16 da (RSS bilan birga).
- Monitoring `collector` jimligini faqat worker ishlaganda sezadi (worker'ni esa bot kuzatadi).
- `/stats` dagi "chiqmadi" — shu davrda `failed` bo'lib qolganlar (umumiy soni `/failed` da).

---

## Sardor uchun

Yangilangan: 2026-09-30. Keyingi ishlar tartibi — `docs/HANDOFF.md`.

**Bajarilgan** (ro'yxatdan olib tashlandi): git muallifi, uv, Telegram API kalitlari va login, manba kanallar (~20),
POST_EXAMPLES, barcha migratsiyalar (baza `e5a9c2f7b3d1` da), vaqtinchalik rasmlar, bot + haqiqiy kanal `.env` da,
laptopda 3 jarayon ishlayapti, `git push` (1626806 gacha).

Hali ochiq:
- [ ] ⚠️ **Migratsiya (Bosqich 12+):** jarayonlarni to'xtatib `uv run alembic upgrade head`, keyin qayta yoqish
      (batafsil — fayl oxiridagi tungi ish hisobotida).
- [ ] **Qaror kerak — `initial_backfill`:** yangi kanal qo'shilganda eski postlar olinsinmi? Hozir `0` (faqat keyingilari).
- [ ] **Qaror kerak — `/addsource` dagi eski postlar** kanalga chiqsinmi? Hozir yo'q (`publisher.publish_backfill: false`).
      Eslatma: chiqsa ham, manbada 24 soatdan oldin chiqqanlari baribir chiqmaydi (`publisher.max_age_hours`).
- [ ] **Qaror kerak — 742** (2 oy bepul amaliyot, keyin haq): job qildim. Kerak bo'lmasa `config/filters.yaml` dagi
      `opportunity_strong_exceptions` ni o'chiring.
- [ ] **`ADMIN_CHAT_ID`** to'ldirilganini tekshiring (xatolar va kunlik backup admin guruhga keladi):
      `uv run python scripts/find_chat_ids.py` (bot jarayoni to'xtatilgan bo'lsin).
- [ ] **Bot bilan to'liq tekshiruv** (fayl oxiridagi "Qanday sinab ko'rasiz") → ROADMAP Bosqich 8 katagi.
- [ ] **Postlar ko'rinishi:** `uv run python scripts/preview_posts.py` → `start data\preview.html`. Yoqmaganlarini Claude'ga tashlang.
- [ ] `.pytest_cache` papkasiga yozish ruxsati yo'q ("Access is denied" ogohlantirishi, testlarga ta'sir qilmaydi) —
      papka boshqa Windows foydalanuvchisiniki (docs/HANDOFF.md → ruxsatlar).

---

## YAKUNIY XULOSA (2026-09-29)

### 1) Nima qilindi

Uchta bosqich ketma-ket bajarildi, har biri alohida lokal commit:

| Commit | Bosqich | Qisqacha |
|---|---|---|
| `chore: project skeleton` | 1 | uv loyiha, papkalar tuzilmasi, sozlamalar (`.env` + `config/*.yaml`), loglar, README, testlar |
| `feat(db): models and initial migration` | 2 | 12 ta jadval, WAL rejimidagi SQLite, Alembic migratsiya, FTS5 qidiruv jadvali, repository'lar |
| `feat(collector): telethon source with catch-up` | 3 | Telegram kanallarni o'qiydigan collector, login skripti, holatni ko'rish skripti |

Jami **66 ta test** o'tadi, `ruff check` toza. Hamma narsa soxta manba va vaqtinchalik baza bilan
tekshirildi — haqiqiy Telegram'ga ulanilmadi, `login_telethon.py` ishga tushirilmadi.

Qisqacha tushuntirishlar (ROADMAP so'raganidek):
- **Model** — bazadagi jadvalning Python'dagi ko'rinishi. Masalan `RawPost` klassi = `raw_posts` jadvali,
  uning har bir maydoni = ustun. Kodda SQL yozmasdan `RawPost(text="...")` deb ishlaymiz.
- **Migratsiya** — baza tuzilmasining "versiyasi". Model o'zgarsa (yangi ustun), migratsiya fayli bazani
  eski holatdan yangisiga o'tkazadi — ma'lumot yo'qolmaydi. `alembic upgrade head` = "bazani eng oxirgi
  versiyaga keltir". Serverda ham, kompyuteringizda ham baza bir xil tuzilmada bo'ladi.
- **Papkalar** — `README.md` oxiridagi jadvalda.

### 2) Siz nimalarni qilishingiz kerak (PowerShell)

Hammasini loyiha papkasida bajaring:

```powershell
cd "D:\Coding projects\ayvona"
```

**a) Bir martalik sozlash**
```powershell
git config --global user.name "Sardor"
git config --global user.email "sizning@email.com"
uv --version                          # ishlamasa: PowerShell'ni yopib qayta oching
uv sync                               # kutubxonalar (allaqachon o'rnatilgan, lekin zarar qilmaydi)
```

**b) `.env` faylini to'ldirish**
```powershell
Copy-Item .env.example .env
notepad .env
```
Kamida shularni to'ldiring: `API_ID=...`, `API_HASH=...` (my.telegram.org → API development tools).
`BOT_TOKEN`, `CHANNEL_ID`, `ADMIN_IDS`, `ADMIN_CHAT_ID` — Bosqich 7–8 da kerak bo'ladi, hozir bo'sh qolsa ham bo'ladi.

**c) Bazani yaratish**
```powershell
uv run alembic upgrade head           # data\ayvona.db paydo bo'ladi
```

**d) Telegram'ga kirish (bir marta)**
```powershell
uv run python scripts/login_telethon.py
```
Telefon (+998...), Telegram yuborgan kod va 2FA parol (bo'lsa) so'raladi. Natija: `data\ayvona.session`.
⚠️ Bu fayl = akkauntingizga to'liq kirish. Hech kimga bermang (git'ga tushmaydi — `.gitignore` da bor).

**e) Kanal qo'shish** — `config\settings.yaml` ni oching:
```powershell
code config\settings.yaml             # yoki: notepad config\settings.yaml
```
`sources: []` qatorini shunday almashtiring:
```yaml
sources:
  - type: telegram
    identifier: "@kanal_nomi"
    own_usernames: ["@kanal_nomi"]
  - type: telegram
    identifier: "@ikkinchi_kanal"
    own_usernames: ["@ikkinchi_kanal"]
```
Sinov uchun darhol natija ko'rish istasangiz, o'sha faylda `initial_backfill: 0` ni `5` qiling
(har kanaldan oxirgi 5 ta post olinadi). Keyin `0` ga qaytarsangiz bo'ladi.

### 3) Collector'ni qanday tekshirasiz

**Qadam 1 — bitta aylanish:**
```powershell
uv run python -m ayvona.apps.collector --once
```
Logda ko'rishingiz kerak: `Telegram'ga ulandi: ...`, `Faol manbalar: ['@kanal_nomi', ...]`, va
`@kanal_nomi: N ta yangi post ... last_seen_id=...`. Xato bo'lsa — o'zbekcha tushuntirish chiqadi
(masalan "API_ID to'ldirilmagan" yoki "session topilmadi").

**Qadam 2 — bazada nima bor:**
```powershell
uv run python scripts/show_status.py
```
Manbalar (postlar soni, `last_seen_id`, xatolar), heartbeat va oxirgi 10 ta post chiqadi.
Istasangiz VS Code'da "SQLite Viewer" extension bilan `data\ayvona.db` → `raw_posts` jadvalini oching.

**Qadam 3 — doimiy ishlatish:**
```powershell
uv run python -m ayvona.apps.collector
```
Har 90 soniyada kanallarni tekshiradi. To'xtatish: **Ctrl+C**.

**Qadam 4 — "o'chib yonish" testi (eng muhimi):**
1. Collector ishlab turganida `show_status.py` bilan postlar sonini eslab qoling.
2. Ctrl+C bilan to'xtating, **10 daqiqa** kuting (bu vaqtda kanalga yangi postlar chiqsin).
3. Qayta yoqing: `uv run python -m ayvona.apps.collector --once`
4. `uv run python scripts/show_status.py` — oradagi hamma postlar kelgan bo'lishi, hech biri ikki marta
   yozilmagan bo'lishi kerak. `last_seen_id` kanaldagi oxirgi post ID'siga teng bo'ladi.

**Testlar (kod o'zgargandan keyin):**
```powershell
uv run pytest
uv run ruff check .
```

Loglar: `data\logs\collector_<sana>.log`. Muammo bo'lsa, shu faylning oxirini menga yuboring:
```powershell
Get-Content data\logs\collector_*.log -Tail 50
```


---

## YAKUNIY XULOSA — Bosqich 7–8 (2026-09-30)

### 1) Nima qilindi

| Commit | Nima |
|---|---|
| `feat(processing): cleaner and post formatter` | Bosqich 6 (avvalgi sessiya yozgan, commit qilinmagan edi) — o'zgarishsiz commit qilindi |
| `fix(processing): course topic lists are not job ads` | @Buxgalteriyaishorinlarii/5450 (kurs reklamasi) endi e'lon emas; bazada boshqa shunday post yo'q (113 ta shubhali post ko'rildi) |
| `feat(worker): processing pipeline and reliable publisher` | Bosqich 7: postlarni qayta ishlash, yig'ish oynasi (20 daq), kanalga ishonchli joylash, eski postlar chiqmaydi |
| `feat(admin): notifications, monitoring, backups, admin commands` | Bosqich 8: admin buyruqlari, manbalar va rasmlar botdan, monitoring, kunlik backup |

Qisqasi — endi tizim to'liq zanjir: **collector** kanallardan o'qiydi → **worker** tozalaydi, dublikatni ushlaydi,
chiroyli qiladi va 20 daqiqadan keyin **kanalga** joylaydi → **bot** orqali siz hammasini boshqarasiz va kuzatasiz.
Hech narsa haqiqiy Telegram'ga yuborilmadi — hammasi Bot API mock bilan sinaldi (632 test). `git push` qilinmadi.

### 2) Siz nima qilishingiz kerak (PowerShell)

Hammasi loyiha papkasida:
```powershell
cd "D:\Coding projects\ayvona"
uv sync
uv run alembic upgrade head            # bazani yangilaydi (3 ta yangi migratsiya). Majburiy!
```

**a) Bot yarating** — Telegram'da @BotFather:
1. `/newbot` → nomi: `Ayvona Jobs` → username: `ayvona_jobs_bot`.
2. Bergan tokenni nusxalang (`123456789:AAE...`). Hech kimga bermang.

**b) Test kanal va admin guruh oching** (haqiqiy @ayvonajobs emas!):
1. Yangi kanal: masalan "Ayvona TEST" (yopiq bo'lsa ham bo'ladi) → Sozlamalar → Administratorlar → botni qo'shing,
   "Xabar joylash" va "Xabarlarni tahrirlash" huquqini bering. Kanalga istalgan bitta post yozing.
2. Yangi guruh: "Ayvona admin" → botni qo'shing → guruhga `/start@ayvona_jobs_bot` yozing (bot nomingiz bilan).
3. Botga shaxsiy chatda `/start` yozing.

**c) `.env` ni to'ldiring:**
```powershell
notepad .env
```
Avval faqat token:
```
BOT_TOKEN=123456789:AAE...
CHANNEL_ID=
```
⚠️ `CHANNEL_ID` hozir sizda to'ldirilgan (ehtimol `@ayvona`) — **bo'shating**, aks holda haqiqiy kanalga yoza boshlaydi.
Saqlang, keyin ID'larni toping (bot jarayoni ishlamayotgan bo'lsin):
```powershell
uv run python scripts/find_chat_ids.py
```
Chiqqan ro'yxatdan `.env` ga yozing:
```
CHANNEL_ID=-100...        # "channel" qatori (TEST kanal)
ADMIN_CHAT_ID=-100...     # "supergroup"/"group" qatori
ADMIN_IDS=123456789       # "SIZ" qatori
```

**d) Uchta jarayonni yoqing** — uchta alohida PowerShell oynasida:
```powershell
uv run python -m ayvona.apps.collector
```
```powershell
uv run python -m ayvona.apps.worker
```
```powershell
uv run python -m ayvona.apps.bot
```
Worker birinchi yonganda bazadagi 377 ta eski postni `skipped_backfill` qiladi — ular kanalga chiqmaydi (siz aytgandek).

**e) Ko'rib chiqish kerak bo'lgan qarorlar** (yuqorida "Bosqich 7" va "Bosqich 8" bo'limlarida sabablari):
- `/addsource` da tanlangan eski postlar kanalga chiqmaydi (`publish_backfill: false`). Chiqsin desangiz — `config\settings.yaml`.
- Tugma nomi "⏸ Pauza" (ROADMAP'da "⏸ O'chirish" edi).
- `.env.example` da `CHANNEL_ID` bo'sh qilindi.

### 3) Qanday sinab ko'rasiz

**Testlar:**
```powershell
uv run pytest
uv run ruff check .
```
Kutilgan natija: `632 passed`, `All checks passed!`.

**Botda (shaxsiy chat):**
1. `/help` — buyruqlar ro'yxati chiqadi. Boshqa odam yozsa — faqat "tez orada" javobi.
2. `/stats` — Collector ✅, Worker ✅, Bot ✅ (hammasi yoqilgan bo'lsa).
3. `/sources` — 20 ta kanal; birortasini bosing → [📊 Statistika], [⏸ Pauza] → [▶️ Yoqish].
4. `/addsource @biror_ish_kanali` → [0] ni bosing → 1–2 daqiqada "✅ Qo'shildi: ..." xabari keladi.
5. `/images` — rasm bo'shliqlari; `/addimage oshpaz` → rasm yuboring → "✅ Saqlandi" → `/cancel`.

**Kanalga chiqishi:**
1. Collector yangi postlarni olgach, 1–2 daqiqada `/queue` da e'lonlar paydo bo'ladi ("Kutmoqda: N").
2. **20 daqiqa** (yig'ish oynasi) o'tgach TEST kanalga birin-ketin (1 daqiqa oraliq) rasm + matn + tugmalar bilan chiqadi.
   Kutishni istamasangiz: `config\settings.yaml` → `hold_minutes: 0` (keyin 20 ga qaytaring).
3. `/pause` — yangi post chiqmaydi, `/queue` da "⏸ PAUZA"; `/resume` — davom etadi.
4. Worker'ni Ctrl+C bilan o'chirib qayta yoqing — navbat yo'qolmaydi, davom etadi.

**Admin guruhda:**
- Shubhali e'lon kelsa "⚠️ Shubhali e'lon ..." xabari.
- Worker'ni 10+ daqiqa o'chirib qo'ysangiz — bot guruhga "🔴 Worker jim" yozadi, yoqsangiz "✅ Worker yana ishlayapti".
- Backup: `uv run python scripts/backup_now.py --send` → guruhga `ayvona_YYYY-MM-DD.db` fayli keladi
  (odatda har kuni 03:00 da o'zi).

**Hammasi test kanalda yaxshi bo'lsa:** `.env` da `CHANNEL_ID` ni haqiqiy `@ayvonajobs` ga almashtiring (bot u yerda ham admin
bo'lsin) va ROADMAP'dagi Bosqich 7 "Test kanalda tekshirish" katagini belgilang. Keyin — Bosqich 9 (server).

Muammo bo'lsa, log oxirini menga yuboring:
```powershell
Get-Content data\logs\worker_*.log -Tail 50
Get-Content data\logs\bot_*.log -Tail 50
```


---

## Tuzatish: haqiqiy username'lar, matnda heshteg yo'q, manzilda vergul (2026-09-30)

- **Username'lar:** kanal **@ayvonajobs**, bot **@ayvona_jobs_bot**. Faqat `config/settings.yaml` → `branding` da turadi
  (`config.py` da standart qiymat yo'q — yozilmasa dastur ishga tushmaydi). Post tagi:
  `🔍 Ish qidiryapsizmi? @ayvona_jobs_bot` / `📢 @ayvonajobs — Ayvona Jobs`; "⭐ Saqlash" / "🔍 Boshqa ishlar"
  tugmalari ham shu botga. Docs, deploy, README, CLAUDE.md, `.env.example` yangilandi (`.env` ga tegilmadi).
- **O'z akkauntlarimiz:** `config/source_rules.yaml` → `defaults.extra_own_usernames`:
  `@ayvonajobs`, `@ayvona_jobs_bot`, eski `@ayvona` — hech qaysi manbada e'lon aloqasi bo'lib olinmaydi.
- **Heshteglar:** faqat oxirgi teglar qatorida. Maydonlar va fallback matn ichidagi heshteg oddiy so'z bo'ladi
  ("Faqat #Erkaklar" → "Faqat erkaklar"). Manzildagi joy bo'lmagan heshteglar ("#Ayollar #Erkaklar") manzildan
  olinib, ma'nosi yo'qolmasligi uchun "📋 Talablar" boshiga yoziladi.
- **Manzil:** qismlar orasida vergul ("Samarqand viloyati, Samarqand shahri", "Toshkent sh., Yashnobod tumani"),
  "Toshkent shahri/shahar/shaxar" → "Toshkent sh.", takror shahar nomi olib tashlanadi ("Toshkent shahri Toshkent" →
  "Toshkent sh."). "Toshkent shahri bo'ylab" kabi iboralar o'zgarmaydi.
- Testlar: yangi 3 ta regression fixture (`ishtoparuz_kanal_25045`, `manavakansiya_uz_68991`, `ishlaUZ_rasmiy_11779`),
  snapshot'lar yangilandi. `uv run pytest` → 677 passed, `uv run ruff check .` toza.
- Preview (`uv run python scripts/preview_posts.py`): 680 postda matn ichida heshteg qolmadi (avval 19 ta).
- Ma'lum: manba matnidagi xatolar ("Toahkent shahri") shundayligicha qoladi.


---

## Skript: navbatdagi e'lonlarni hozirgi formatter bilan qayta formatlash (2026-09-30)

**Muammo:** formatter pipeline paytida ishlaydi, tayyor matn/tugmalar `jobs` da saqlanadi. Formatter o'zgargach
(username'lar `branding` dan, heshteg va manzil tozalash) navbatdagi joblar eski matnda qolgan edi
(footerda `@ayvonabot` / `@ayvona`, tugmalarda eski bot).

- **`scripts/reformat_queued.py [--dry-run] [--force]`** → `services/reformat.py`.
  - Faqat `queued` / `retry`. `published`, `sending`, `failed` ga tegilmaydi — UPDATE shartli
    (`status in (queued, retry)` **va** `raw_post_id` o'zgarmagan), shu orada publisher olib ketgan yoki
    to'liqroq nusxa almashtirgan job ustidan yozilmaydi.
  - `jobs` da formatter uchun yetarli maydon yo'q (til, lavozimlar ro'yxati, email, manzil qismlari...),
    shuning uchun job `raw_posts` dagi asl matndan qayta quriladi: extract → clean → format (pipeline bilan
    bir xil kod: yangi `Pipeline.render()` va `Pipeline.post_of_job()`). Dedup ishlamaydi, indeks va
    `raw_posts` ga tegilmaydi, yangi job ochilmaydi — mavjud job yangilanadi (matn, tugmalar va extract
    ustunlari: title, maosh, manzil... — matn bilan mos bo'lishi uchun).
  - Hozirgi qoidalar bo'yicha aloqasi yo'q / sifatsiz bo'lib qolgan job, foydalanuvchi e'loni (raw post yo'q)
    — o'tkazib yuboriladi (eski matn qoladi), sababi ro'yxatda chiqadi.
  - Yozishdan oldin backup: `data/backups/reformat/ayvona_YYYY-MM-DD_HHMMSS_before_reformat.db`
    (`services/backup.make_backup` ga ixtiyoriy `name` qo'shildi; kunlik backup'larga tegmaydi).
  - Worker `heartbeat` i 2.5 daqiqadan yangi bo'lsa — to'xtaydi ("avval worker'ni to'xtating");
    `--dry-run` da faqat ogohlantiradi; `--force` bilan baribir davom etadi.
  - Har job alohida tranzaksiyada; qayta ishga tushirish xavfsiz (ikkinchi marta "O'zgarishsiz").
  - Oxirida: nechta job yangilandi / o'zgarishsiz / o'tkazib yuborildi + 3 ta namuna (oldin/keyin).
- Testlar: `tests/test_reformat.py` (6 ta). `uv run pytest` → 683 passed, `uv run ruff check .` toza.
- Haqiqiy bazada `--dry-run`: 274 ta navbatdagi e'lon, 273 tasi o'zgaradi (footer, tugmalar, manzilda vergul).
  Haqiqiy yozish hali ishga tushirilmagan.

**Qanday ishlatiladi (PowerShell):**
```powershell
# 1) worker'ni to'xtating (uning oynasida Ctrl+C), 2 daqiqa kuting
uv run python scripts/reformat_queued.py --dry-run    # nima o'zgarishini ko'ring
uv run python scripts/reformat_queued.py              # backup + yangilash
# 2) worker'ni qayta yoqing
uv run python -m ayvona.apps.worker
```

**Kelajakda shu muammo bo'lmasligi uchun — qaror (bajarildi, pastda "Worker start'ida qayta formatlash"):**
"Publisher chiqarish paytida footer va tugmalarni branding'dan qayta qo'ysin" varianti **tanlanmadi**, sabablari:
1. Yarim yechim: bu safargi muammoning yarmi heshteg va manzil tozalash edi — publisher faqat footer/tugmani
   almashtirsa, ular baribir eski qolardi.
2. 1024 belgi limiti: formatter matnni footer bilan birga sig'diradi. Publisher boshqa (uzunroq) footer qo'ysa
   caption limitdan oshishi mumkin → rasm yo'qoladi yoki publisher'da formatter'ning qisqartirish mantiqini
   takrorlash kerak bo'ladi.
3. Bitta post ikki joyda yasaladi: bazadagi `formatted_text` kanaldagi postga teng bo'lmaydi (bot qidiruvi va
   kelajakdagi sayt (Bosqich 17) `formatted_text` ni ko'rsatsa — boshqacha matn).
4. Footerni saqlangan HTML'dan ajratish uchun yo sxema o'zgarishi (footersiz matn + migratsiya), yo mo'rt regex kerak.
5. Publisher — ishonchli yetkazish joyi; unga render qo'shilsa, render xatosi hamma postni `retry/failed` ga tushiradi.

**Taklif (tanlangan):** worker ishga tushganda, publisher boshlanishidan oldin shu `reformat_queued()` ni
avtomatik chaqirish. Formatter kodi ham, `branding` ham faqat qayta ishga tushirishda o'zgaradi (sozlamalar
start'da o'qiladi, deploy servislarni qayta yoqadi) — demak har qanday formatter o'zgarishi butun navbatga
o'zi qo'llanadi, post bitta joyda yasaladi, sxema o'zgarmaydi. Narxi: start'da navbatni qayta ishlash
(274 ta job — bir necha soniya).

### Worker start'ida qayta formatlash (2026-09-30)
- `apps/worker.py` → `reformat_queue()`: har start'da, publisher boshlanishidan oldin (`requeue_stuck` dan keyin)
  navbatdagi `queued` / `retry` e'lonlar hozirgi formatter va `branding` bilan qayta yasaladi (xuddi skript kabi,
  faqat backup'siz — kunlik backup bor). Xato bo'lsa worker to'xtamaydi, e'lonlar eski matnda qoladi (log'da xato).
- O'chirish: `config\settings.yaml` → `worker.reformat_queued_on_start: false`.
- Log'da: "Navbat hozirgi formatter bilan yangilandi: N ta e'londan M tasi o'zgardi ...".
- `scripts/reformat_queued.py` qoladi: `--dry-run` bilan oldindan ko'rish va backup bilan qo'lda ishlatish uchun.
- ROADMAP Bosqich 10 promptiga "Mavjud kodni hisobga ol" bo'limi qo'shildi (admin /start ushlashi, middleware
  admin'ga ta'sir qilmasligi, deep link formati, favorites mantiqi `services/` da).
- Testlar: +2 (`tests/test_reformat.py`). `uv run pytest` → 685 passed, `uv run ruff check .` toza.


---

## `publisher.max_age_hours` — eski e'lon kanalga chiqmaydi (2026-09-30)

Sardor qarorlari:
1. **Yosh manba kanalda chiqqan vaqtdan** (`raw_posts.posted_at`), u bo'sh bo'lsa `fetched_at` dan hisoblanadi.
2. Admin `/retry` qilgan eski `failed`/`retry` e'lon ham `skipped_old` bo'ladi, javobda sababi yoziladi.
3. Admin chatga xabar **yuborilmaydi** — faqat log va `/stats`.

Nima qilindi:
- `config/settings.yaml` → `publisher.max_age_hours: 24` (`0` = qoida o'chiq). `PublisherConfig.too_old_before(now)`.
- Yangi status **`jobs.status = skipped_old`** (oddiy VARCHAR — migratsiya shart emas). E'lon o'chirilmaydi, bazada qoladi
  (keyin bot qidiruvi uchun), `last_error = "eskirgan: 24 soatdan eski"`, `next_retry_at` bo'shatiladi.
- `jobs_repo.skip_old()` — bitta shartli UPDATE: faqat `queued`/`retry` (yoki `/retry` da `failed`/`retry`) va manba posti
  bor e'lonlar. `sending`, `published` ga hech qachon tegilmaydi. Foydalanuvchi e'loni (`raw_post_id` bo'sh) — qoida
  qo'llanmaydi (Bosqich 11 da hal qilinadi).
- **Publisher** har post oldidan (`publish_next`) eskirganlarni belgilaydi, keyin navbatdagi yangisini oladi.
  Chegarada (aynan 24 soat) — hali chiqadi; 24 soat + 1 soniya — `skipped_old`.
- **Worker start'ida**: `requeue_stuck` → `skip_old` → `reformat_queue` — eskirganlar qayta formatlanmaydi.
  Xato bo'lsa worker to'xtamaydi (publisher keyin baribir tekshiradi).
- **`/retry`**: eskirganlar navbatga qaytmaydi, javob: `⏳ N ta e'lon navbatga qo'yilmadi — eskirgan: 24 soatdan eski
  (kanalga chiqmaydi): #12, #15`. Qolganlari odatdagidek `🔁 N ta e'lon qayta navbatga qo'yildi.`
- **`/stats`**: yangi qator `⏳ Eskirgan (chiqmadi): bugun / 7 kun`.
- Log (worker oynasida va `data\logs\worker_*.log`):
  `N ta e'lon kanalga chiqmaydi — manbada 24 soatdan oldin chiqqan (skipped_old): #1, #2, ...` (20 tadan keyin `...`).

⚠️ Bosqich 7 dagi qoida o'zgardi: collector uzoq o'chiq tursa, qolgan postlar olinadi va qayta ishlanadi (dublikat indeksi,
bazada saqlanadi), lekin manbada 24 soatdan oldin chiqqanlari kanalga **chiqmaydi**.

Ma'lum: yig'ish oynasida to'liqroq nusxa e'lonni "olib qo'ysa" (take-over), yosh yangi nusxaning `posted_at` idan
hisoblanadi (20 daqiqalik oyna — amalda farq qilmaydi).

Testlar: +9 (`test_publisher.py` 7, `test_admin_bot.py` 1, `test_reformat.py` 1).
`uv run pytest` → **694 passed**, `uv run ruff check .` toza.


---

## Monitoring: collector o'chiq bo'lsa — bitta xabar (2026-09-30)

**Muammo:** collector to'xtasa, 24 soatdan keyin har bir kanal uchun alohida "🟡 ... dan post kelmadi" xabari kelardi
(~20 ta), garchi sabab bitta — collector o'qimayapti.

**Yechim** (`services/heartbeat.py`): kanal jimligi faqat collector **o'qib turganda** tekshiriladi:
heartbeat yangi (≤ 10 daq) **va** `collector:last_cycle_at` yangi (collector hamma kanallarni aylanib chiqqan).
- Collector o'chiq → faqat bitta "🔴 Collector jim" xabari (avvalgidek). Kanal-jimlik xabarlari yuborilmaydi.
- Qaror: `last_cycle_at` ham shart — collector qayta yongan zahoti hali kanallarni o'qib ulgurmagan bo'ladi; faqat
  heartbeat'ga qaralsa, o'sha oraliqda baribir 20 ta xabar ketishi mumkin edi.
- Qaror: jimlik belgilari (`monitor:silent:*`) collector o'chiqligida o'zgartirilmaydi — qayta o'qiy boshlaganda
  haqiqatan jim kanal bo'lsa, xabar keladi; "✅ tiklandi" xabarlari ham ortiqcha ketmaydi.
- Collector hech qachon ishlamagan bo'lsa (heartbeat yo'q) — kanal jimligi tekshirilmaydi.
- Manba xatolari ("ketma-ket N marta o'qilmadi") — o'zgarmadi (collector yozadi, haqiqiy ma'lumot).
- `kv_repo.COLLECTOR_LAST_CYCLE`, `kv_repo.get_time()` qo'shildi (kalit avval faqat `apps/collector.py` da edi).

Testlar: +2 (`test_monitoring.py`: 15 kanal + o'chiq collector → 1 xabar; haqiqatan jim kanal). 696 passed, ruff toza.


---

## Bosqich 10 — Ommaviy bot asosi (2026-09-30, avtonom)

Nima qilindi:
- **/start** — `users` jadvaliga yozadi/yangilaydi, salom + asosiy menyu (reply keyboard):
  📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar · ℹ️ Yordam. `/start` har doim yarim qolgan formani
  tozalaydi. `/help` (va ℹ️ Yordam), `/cancel`.
- **Deep link'lar** (kanal tugmalari formati o'zgarmadi): `?start=save_<id>` — saqlaydi va e'lonni ko'rsatadi;
  `?start=job_<id>` — e'lonni ko'rsatadi; `?start=search` — qidiruv (Bosqich 12).
- **E'lon kartochkasi** botda = kanaldagi matn (`jobs.formatted_text`) + tugmalar: [📩 Murojaat]/[🔗 Ariza] (kanal
  postidagi), [⭐ Saqlash ↔ ✅ Saqlangan], [📤 Ulashish] (Telegram'ning `t.me/share/url` oynasi, kanal posti havolasi bilan).
- **⭐ Saqlanganlar** — 5 tadan sahifa (⬅️ ➡️), eng oxirgi saqlangan tepada, yopilganlari "❌ Yopilgan" belgisi bilan,
  har biriga "N. Batafsil" tugmasi.
- **Middleware** (`bot/middlewares.py`, faqat shaxsiy chat): throttling (`bot.throttle_seconds: 1`), `users` yozuvi
  (`last_active_at` — `bot.touch_interval_seconds: 60` da bir marta, har xabarda emas), ban (🚫 xabari 10 daqiqada 1 marta).
  **Adminlarga ta'sir qilmaydi** (throttling ham, ban ham). Adminlar `trust_level=2` bo'ladi.
- **Mantiq `services/` da** (veb-sayt ham ishlatadi): `services/users.py`, `services/favorites.py`,
  `services/jobs_public.py` (nimani ko'rsatish mumkin: faqat kanalga chiqqan `published`; `closed`/`expired` —
  saqlanganlarda belgi bilan). Handler'lar faqat chaqiradi.
- `bot/setup.py`: admin router'lar oldin (faqat `ADMIN_IDS`), keyin ommaviy (faqat shaxsiy chat). `admin.py` endi
  `/start` ni ushlamaydi — admin ham menyu va deep link'larni ko'radi; admin yordami `/help` da.
  "/" menyusi: hammaga `/start /help /cancel`, adminlarga — admin buyruqlari ham.

Qarorlar (Sardor yo'qligida):
1. **FSM storage — MemoryStorage** (ROADMAP aytgandek). Restart faqat yarim to'ldirilgan formani unutadi (yuborilgan
   e'lon bazada). Keyin bir nechta server bo'lsa — RedisStorage yoki `kv_store` ustidagi SQLite storage.
2. **Throttling'da tashlangan xabarga javob yo'q** (flood'ga flood bilan javob bermaslik); bosilgan tugmaga "⏳ Sekinroq"
   (aks holda tugma aylanib turadi).
3. **Guruh chatlari** (admin guruh): ommaviy handler'lar ishlamaydi, `users` ga yozilmaydi.
4. Yopilgan e'lonni saqlab bo'lmaydi; kartochkasi "❌ YOPILGAN" bilan, tugmalarsiz.
5. "📢 E'lon joylash" va "🔔 Obunalar" — hozircha "tez orada" (Bosqich 11 va 13).

Testlar: `tests/test_public_bot.py` (+15). Baza o'zgarmadi (migratsiya yo'q).


---

## Bosqich 11 — 📢 E'lon joylash formasi (2026-09-30, avtonom)

Nima qilindi:
- **Forma** (`bot/handlers/post_job.py`, FSM): 1 soha (tugmalar) → 2 lavozim → 3 kompaniya (⏭) → 4 maosh
  ("🤝 Kelishiladi" yoki matn — `SalaryParser` bilan son bo'ladi) → 5 hudud (tugmalar + "🏠 Masofaviy") + manzil (⏭) →
  6 ish vaqti (⏭) → 7 talablar (⏭) → 8 **aloqa — majburiy** ("📱 Raqamni yuborish", "👤 @username ni ishlatish" yoki
  yozib: +998... / @username; hech biri bo'lmasa keyingi qadamga o'tmaydi) → **ko'rib chiqish** (kanaldagi ko'rinishning
  o'zi) → [✅ Yuborish] [✏️ Tahrirlash] [❌ Bekor qilish]. Har qadamda "⬅️ Orqaga" va "❌ Bekor qilish"; menyu tugmasi
  formadan chiqaradi. Tahrirlashda faqat tanlangan maydon so'raladi, keyin yana ko'rib chiqish.
- **Mantiq — `services/job_submission.py`** (veb-sayt ham ishlatadi): `Draft`, `render` (aggregator'ning o'sha
  `Formatter`i — o'zbek lotin, kirill o'giriladi), `check_content`, `check_limits`, `find_duplicate`, `submit`,
  `approve`, `reject`.
- **Limitlar** (`settings.yaml → posting`): 24 soatda 2 ta, orasida 10 daqiqa, bir vaqtda 1 ta kutayotgan
  (`pending_review/queued/sending/retry`). Forma boshida ham, yuborishda ham tekshiriladi. Adminlarga limit yo'q.
- **Filtrlar:** `filters.yaml` + `filter_words` jadvali (keyin `/addword`): `ban` so'zlar → rad; `spam` so'zlar,
  > 2 havola, KATTA HARF > 60% (20+ harfli matnda), > 10 emoji → rad (bazaga yozilmaydi); `scam` so'zlar
  (`scam_exceptions` hisobga olinadi) → admin tekshiruviga; dublikat (dedup.py, 14 kun, hamma e'lonlar orasida) → rad.
- **Moderatsiya** (`posting.moderation`): `auto` (faqat scam admin'ga) | `suspicious_only` (standart: scam + yangi
  foydalanuvchining birinchi e'loni) | `all`. Admin'ga (`ADMIN_CHAT_ID`, yo'q bo'lsa har bir admin'ga shaxsiy):
  e'lon + sabab + [✅ Tasdiqlash] [❌ Rad etish] [🚫 Ban] (`bot/moderation.py`). Natija muallifga yoziladi, admin
  xabari "✅ Tasdiqlandi (@admin)" bilan yangilanadi, ikkinchi bosish — "allaqachon ko'rib chiqilgan".
- Tasdiqlangan e'lon → `jobs(queued, origin=user)` → worker publisher chiqaradi → **muallifga kanal havolasi**
  (`publisher/outbox.py → _tell_author`, xato bo'lsa jim — chiqarishga ta'sir qilmaydi).
- Qat'iy qoida 7: aloqasiz e'lon `submit` da ham rad etiladi (bazadagi CHECK'dan tashqari).

Qarorlar (Sardor yo'qligida):
1. **"Kuniga 2 ta" = oxirgi 24 soat** (yarim tundan emas) — kechasi 23:59 va 00:01 da ketma-ket yuborib bo'lmaydi.
   Admin rad etgan e'lon ham limitga kiradi (spam qilib qayta-qayta yuborishning oldini oladi).
2. **Tasdiqlangan muallif `trust_level=1`** bo'ladi — keyingi e'lonlari (scam so'zi bo'lmasa) to'g'ridan-to'g'ri navbatga.
3. **Ban/spam/dublikat → bazaga yozilmaydi** (foydalanuvchiga sabab umumiy aytiladi — qaysi so'z ekanini aytmaymiz,
   aylanib o'tmasin). Scam → yoziladi (`pending_review`, sababi `jobs.last_error` da).
4. **Kategoriya tugmalari** — `categories.yaml` dagi hamma kategoriya (kasb so'ralmaydi — lavozimdan `Categorizer`
   topadi, faqat tanlangan sohaga mos bo'lsa).
5. **Faqat O'zbekiston raqami** (+998) qabul qilinadi (CLAUDE.md qoida 7).
6. **ru/en yozilgan e'lon** — formatter aggregator'dagidek ishlaydi (talablar ko'rsatilmaydi, qoida 8).
   Forma savollari o'zbekcha, shuning uchun bu kam uchraydi.
7. User e'loniga yig'ish oynasi (`hold_minutes`) va `max_age_hours` qo'llanmaydi (raw post yo'q) — darhol chiqadi.

Testlar: `tests/test_job_submission.py` (+25), `tests/test_post_job.py` (+11). Baza o'zgarmadi (migratsiya yo'q).


---

## Bosqich 12 — 🔍 Ish qidirish + ⭐ Saqlanganlar (2026-09-30, avtonom)

Nima qilindi:
- **Qidiruv ustasi** (`bot/handlers/search.py`): Soha (yoki "Hammasi") → Kasb (shu sohaning kasblari yoki "Hammasi";
  kasbi yo'q soha / "Hammasi" bo'lsa o'tkaziladi) → Hudud ("Hammasi", "🏠 Masofaviy", 14 hudud) → Maosh ("Farqi yo'q",
  2/4/6/10 mln+) → natijalar. Hammasi bitta xabarda (tugmalar bilan tahrirlanadi).
- **"🔤 So'z bilan qidirish"** — FTS5. **Kirill/lotin muammosi hal qilindi** (PROGRESS Bosqich 2, №9): yangi ustun
  `jobs.search_text` = `fold(lavozim + kompaniya + manzil + matn)` apostrofsiz; `jobs_fts` endi faqat shu ustunni
  indekslaydi (migratsiya **`f2b6d8a4c1e3`**). So'rov ham xuddi shunday o'giriladi → "СОТУВЧИ" ham, "sotuvchi" ham,
  "o'qituvchi" ham "oqituvchi" ham topiladi; har so'z prefiks ("sotuv" → "sotuvchi"). So'rov har doim xavfsiz
  (faqat harf-raqam so'zlar, qo'shtirnoqda).
- **Natijalar**: faqat `published` va muddati o'tmagan, `published_at` bo'yicha eng yangisi tepada, 5 tadan (⬅️ ➡️),
  har biri qisqa kartochka + [N. Batafsil] [⭐ Saqlash] [📤 Ulashish] + [🔄 Yangi qidiruv].
- **"🔁 Oxirgi qidiruv"** — `search_logs` dan (restart'dan keyin ham ishlaydi). Har qidiruv `search_logs` ga yoziladi
  (sahifalash yozilmaydi). Bot qayta ishga tushsa sahifa tugmasi oxirgi qidiruvdan davom etadi.
- **Maosh filtri**: `salary_max ≥ X` yoki `salary_min ≥ X`; USD — `kv_store.usd_rate` bilan so'mga.
  **Kurs** (`services/currency.py`): worker kuniga 1 marta Markaziy bankning ochiq API'sidan oladi (cbu.uz, bepul);
  xato bo'lsa eski qiymat, umuman bo'lmasa `search.usd_rate_fallback: 12800`.
- **⭐ Saqlanganlar** — Bosqich 10 da qilingan (sahifalash, o'chirish, "❌ Yopilgan" belgisi); qidiruvdagi ⭐ ham shu.
- Mantiq `services/search.py` da (veb-sayt ham ishlatadi).

Qarorlar (Sardor yo'qligida):
1. **Eski e'lonlarning `search_text`i** migratsiyada emas, **worker start'ida** to'ldiriladi (`fill_search_text`,
   500 tadan) — migratsiya app kodini import qilmasligi kerak (Bosqich 2 qarori). Worker qayta yongunicha eski e'lonlar
   faqat so'z bilan qidirishda chiqmaydi (filtrlar ishlaydi). Log: "Qidiruv uchun N ta e'lon matni tayyorlandi".
2. **Maosh filtri faqat oylik maoshlarga** (`salary_period` bo'sh yoki `month`); kunlik/soatbay e'lonlar va maoshi son
   bo'lmaganlar faqat "Farqi yo'q" da chiqadi (ROADMAP: "maoshi yo'q e'lonlar Farqi yo'q da chiqadi"). EUR/RUB — filtrda yo'q.
3. **"Ko'p hudud" e'lonlari** aniq bir hudud tanlanganda chiqmaydi (qaysi hududlar ekani saqlanmaydi) — "Hammasi" da chiqadi.
4. **Qidiruv filtrlari** FSM'da (`search`) — callback'da faqat sahifa raqami (64 bayt chegarasi).
5. Testlar hech qachon cbu.uz ga chiqmaydi (`make_settings` da `usd_rate_url: ""` — bo'sh URL = kurs yangilanmaydi).
6. Migratsiya **vaqtinchalik bazada** sinaldi (eski versiya + ma'lumot → head → FTS ishladi → integrity-check toza →
   downgrade → qayta upgrade). **Sizning `data/ayvona.db` ga tegilmadi.**

⚠️ **Ertalab kerak:** `uv run alembic upgrade head` (jarayonlar to'xtatilgan holda).

Testlar: `tests/test_search.py` (+15), `test_db.py` FTS testi yangilandi.


---

## Bosqich 13 — 🔔 Ish obunalari (2026-10-01, avtonom)

Nima qilindi:
- **"🔔 Obunalar"** (`bot/handlers/alerts.py`): ro'yxat (n/5, ✅ faol / ⏸ pauza) + har biriga [⏸/▶️ N] [🗑 N],
  [➕ Yangi obuna]. Yangi obuna ustasi qidiruvnikining o'zi: soha → kasb → hudud → maosh → ixtiyoriy kalit so'z
  (⏭ o'tkazib yuborish). Qidiruv natijalari ostida **"🔔 Shu qidiruvga obuna bo'lish"** tugmasi.
- **Yuborish — worker ichida** (`services/alerts.py → AlertService`, har 30 s): kanalga yangi chiqqan e'lonlar
  (`kv_store alerts:cursor` dan keyin) faol obunalar bilan solishtiriladi — **qidiruvning aynan o'sha qoidalari**
  (`services/search.job_matches`). Xabar: "🔔 Yangi e'lon — obunangiz: ..." + e'lon + [📩] [⭐] [📤] [🔕 Obunani to'xtatish].
- **Ikki marta yuborilmaydi:** avval `alert_deliveries` qatori yoziladi (kompozit PK), keyin xabar. Bir foydalanuvchining
  bir nechta obunasi mos kelsa — **bitta** xabar (hamma obunalar uchun qator yoziladi).
- **Kuniga 20 ta** (24 soat): qolganlari `status=digest` → kechqurun **20:00 da bitta ro'yxat** ("📬 ... yana N ta").
- **Bot API chegarasi:** sekundiga ≤ 25 xabar; "retry after" kutiladi va qayta uriniladi; foydalanuvchi botni bloklagan
  bo'lsa (Forbidden) — uning hamma obunalari o'chadi (qayta yoqsa ishlaydi).
- Migratsiya **`a7c3e9f1b5d8`**: `subscriptions.profession`, `alert_deliveries.status`.

Qarorlar (Sardor yo'qligida):
1. **Birinchi ishga tushishda eski e'lonlar yuborilmaydi** (kursor = hozir) — faqat bundan keyin chiqqanlar.
2. **Filtrsiz obuna ("hamma e'lonlar") mumkin emas** — kuniga yuzlab xabar bo'lardi; kamida bitta filtr.
3. **Qator avval yoziladi, keyin xabar yuboriladi** (at-most-once): yuborish paytida worker o'chsa, o'sha bitta xabar
   ketmay qolishi mumkin — ikki marta yuborishdan yaxshiroq (e'lonning o'zi kanalda va qidiruvda bor).
4. Dayjestda faqat hali ochiq e'lonlar (yopilgan/muddati o'tganlari tashlanadi), ko'pi bilan 20 ta.
5. Obuna xabarlari faqat token bor va `--no-publish` bo'lmaganda (worker loop rejimida) yuboriladi.

Testlar: `tests/test_alerts.py` (+9).


---

## Bosqich 14 — Yopish, muddat, to'liq statistika (2026-10-01, avtonom)

Nima qilindi:
- **"📋 Mening e'lonlarim"** (menyuga qo'shildi, `bot/handlers/my_jobs.py`): oxirgi 10 ta e'lon holati bilan
  (🕵️ tekshiruvda / ⏳ navbatda / ✅ kanalda, DD.MM gacha / ❌ yopilgan / ⌛ muddati tugagan) + [✅ Ish topildi N]
  (tasdiq so'raydi) va [🔄 Uzaytirish N]. Yopilganda **kanal posti tahrirlanadi**: boshiga "❌ YOPILDI", tugmalar olinadi
  (`services/channel.py`: rasmli post — caption, matnli — text; 1024 dan oshsa — "❌ YOPILDI" + lavozim), qidiruvdan chiqadi.
  Hali kanalga chiqmagan (tekshiruvda/navbatda) e'lonni ham yopish mumkin — u kanalga chiqmaydi.
- **Muddat** (`services/expiry.py`, worker ichida, har 30 daq): publisher endi `expires_at` qo'yadi (kanal e'loni
  **21 kun**, foydalanuvchi e'loni **30 kun**, `settings.yaml → expiry`); eski e'lonlarga worker o'zi qo'yadi
  (`published_at + kun`). Muddati o'tgani → `expired`, **qidiruvdan chiqadi, kanal postiga tegilmaydi**. Foydalanuvchiga
  **2 kun oldin** bir marta "⏳ ... Uzaytirasizmi?" [🔄 Uzaytirish (+30 kun)] [✅ Ish topildi, yopish]
  (`jobs.reminded_at`, migratsiya **`b8d4f0a2c6e9`**). Muddati tugagan e'lonni ham uzaytirsa bo'ladi.
- **/stats kengaydi:** foydalanuvchilar (jami, bugun yangi, 7 kunda faol), faol obunalar, foydalanuvchi e'lonlari,
  eng ko'p qidirilgan sohalar va hududlar (`search_logs`), manbalar bo'yicha kanalga chiqqan e'lonlar (7 kun).
- **/addword ban|spam|scam so'z**, **/delword so'z**, **/words** — `filter_words` jadvali (forma filtri darhol ishlatadi).
- **/ban &lt;id | @username&gt;**, **/unban** — admin'ni bloklab bo'lmaydi; botga hech yozmagan ID ham bloklanadi.
- **/broadcast matn** → ko'rinishi + "N ta foydalanuvchiga" → [✅ Yuborish] [❌ Bekor qilish] → fonda sekundiga 20 ta,
  bloklanganlar o'tkaziladi, tugagach hisobot. Telegram formatlari (qalin, kursiv, havola) saqlanadi.

Qarorlar (Sardor yo'qligida):
1. **Ish topildi = `closed`** (qidiruvdan chiqadi, saqlanganlarda "❌ Yopilgan"). Kanal posti o'chirilmaydi — tahrirlanadi.
2. **Muddat tugashi kanalga ta'sir qilmaydi** (ROADMAP) — faqat qidiruv, saqlanganlar belgisi, obuna xabarlari.
3. **Eslatma bir marta** yuboriladi (xato bo'lsa ham qayta urinmaydi — spam bo'lmasin); uzaytirilsa yana eslatiladi.
4. **Broadcast** bot jarayonining ichida fonda ketadi — restart bo'lsa to'xtaydi (qayta yuborish admin qaroriga).
5. `/ban` qilingan foydalanuvchining obunalari o'chirilmaydi, lekin **obuna xabarlari unga ketmaydi**
   (`services/alerts.plan_job` bloklanganlarni o'tkazib yuboradi); `/unban` dan keyin yana keladi.

Testlar: `tests/test_lifecycle.py` (+11), `test_alerts.py` (+1). **783 passed**, ruff toza.


---

## TUNGI ISH HISOBOTI — ertalab nima qilish kerak (2026-10-01)

### 1) Jarayonlarni to'xtatish
Uchala PowerShell oynasida (collector, worker, bot) **Ctrl+C** bosing va "... to'xtadi." chiqishini kuting.

### 2) Bazani yangilash (avval nusxa)
```powershell
cd "D:\Coding projects\ayvona"
uv sync
uv run python scripts/backup_now.py
uv run alembic upgrade head
```
`alembic` oxirida shu 3 qator chiqishi kerak: `e5a9c2f7b3d1 -> f2b6d8a4c1e3`, `f2b6d8a4c1e3 -> a7c3e9f1b5d8`,
`a7c3e9f1b5d8 -> b8d4f0a2c6e9`. Xato chiqsa — hech narsani yoqmang, xabarni Claude'ga yuboring (nusxa
`data\backups\` da).

### 3) Qayta yoqish — uchta alohida oynada
```powershell
uv run python -m ayvona.apps.collector
```
```powershell
uv run python -m ayvona.apps.worker
```
```powershell
uv run python -m ayvona.apps.bot
```
Worker logida birinchi yonishda (bir marta) ko'rinadi:
- `Qidiruv uchun N ta e'lon matni tayyorlandi (search_text)`
- `Muddat: N ta e'longa muddat qo'yildi, 0 ta eslatma, M ta e'lon qidiruvdan chiqdi` (21 kundan eskilar)
- `USD kursi yangilandi: 1 $ = ... so'm` (internet bo'lsa)

### 4) Botni telefonda sinash (@ayvona_jobs_bot)
1. `/start` → salom + 6 ta tugma: 📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar ·
   📋 Mening e'lonlarim · ℹ️ Yordam.
2. **🔍 Ish qidirish** → soha → kasb → hudud → maosh → natijalar (5 tadan, ⬅️ ➡️). "N. Batafsil", "⭐ Saqlash",
   "📤 Ulashish". "🔤 So'z bilan qidirish" → `сотувчи` yozing — lotincha e'lonlar ham chiqishi kerak.
3. Kanaldagi istalgan postning **⭐ Saqlash** tugmasi → bot ochiladi, "⭐ Saqlandi" → **⭐ Saqlanganlar** da ko'rinadi.
4. **🔔 Obunalar** → ➕ Yangi obuna → soha/hudud/maosh → ⏭. Mos e'lon kanalga chiqqach (≈30 s ichida) xabar keladi.
   Qidiruv natijalari ostidagi "🔔 Shu qidiruvga obuna bo'lish" ham ishlaydi.
5. **📢 E'lon joylash** → 8 savol → ko'rib chiqish → ✅ Yuborish. ⚠️ Siz adminsiz — sizning e'loningiz tekshiruvsiz
   navbatga tushadi. **Tekshiruvni sinash uchun ikkinchi Telegram akkaunt** bilan yuboring: admin guruhga (yoki
   sizga) "🆕 Yangi e'lon — tekshiring" + [✅ Tasdiqlash] [❌ Rad etish] [🚫 Ban] keladi → ✅ → 1–2 daqiqada kanalda,
   muallifga havola.
6. **📋 Mening e'lonlarim** → "✅ Ish topildi 1" → "Ha, yopish" → kanaldagi post boshida "❌ YOPILDI", tugmalar yo'q.
7. Admin: `/stats` (pastda yangi qism: foydalanuvchilar, obunalar, qidiruvlar, manbalar), `/words`,
   `/addword scam garov puli`, `/delword garov puli`, `/ban @username`, `/unban @username`.
   ⚠️ `/broadcast` — **hamma foydalanuvchilarga** ketadi; sinash kerak bo'lsa, tasdiqlash oynasida "❌ Bekor qilish".

### 5) Testlar (xohlasangiz)
```powershell
uv run pytest
uv run ruff check .
```
Kutilgan: `783 passed`, `All checks passed!`.

### Ochiq qolgan joylar
- Hammasi Bot API **mock** bilan sinalgan — haqiqiy Telegram'da birinchi marta ertalab ishlaydi.
- Migratsiyalar faqat **vaqtinchalik bazada** sinaldi (sizning `data/ayvona.db` ga tegilmadi — shuning uchun avval
  `backup_now.py`).
- Forma, qidiruv va obuna holati (FSM) xotirada — bot qayta yonsa yarim to'ldirilgan forma unutiladi (yuborilganlar
  bazada). Serverda bir nechta nusxa bo'lsa — boshqa storage kerak bo'ladi.
- Obuna va eslatma xabarlari worker'dan ketadi: worker `--no-publish` yoki tokensiz bo'lsa — ketmaydi.
- "Ko'p hudud" e'lonlari aniq hudud qidiruvida chiqmaydi; kunlik/soatbay maoshlar maosh filtrida hisobga olinmaydi.
