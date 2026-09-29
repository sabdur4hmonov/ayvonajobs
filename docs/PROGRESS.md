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
    (apply_url), 2-qator `⭐ Saqlash` (`t.me/ayvonabot?start=save_<id>`; job id kerak — Bosqich 7 da beriladi) +
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

---

## Sardor uchun

Kompyuter yoniga qaytganingizda qilishingiz kerak bo'lgan narsalar (batafsil — fayl oxirida):

- [ ] **Git muallifini sozlang** (bir marta):
      `git config --global user.name "Sardor"` va `git config --global user.email "sizning@email"`
- [ ] Yangi PowerShell oynasini oching va `uv --version` ishlashini tekshiring (uv PATH'ga qo'shildi).
- [ ] **Telegram API kalitlari:** my.telegram.org → `API_ID`, `API_HASH` (tavsiya: ikkinchi akkaunt) → `.env` ga.
- [ ] **Bir martalik login:** `uv run python scripts/login_telethon.py` (men uni ishga tushirmadim — siz aytgandek).
- [ ] **Manba kanallarni tanlang** va `config/settings.yaml` ga yozing (qaysi kanallar — sizning qaroringiz).
- [ ] **Qaror kerak — `initial_backfill`:** yangi kanal qo'shilganda eski postlar olinsinmi? Hozir `0`
      (faqat bundan keyingilari). Test uchun `5` qo'yib ko'rsangiz, darhol natija ko'rasiz.
- [ ] Haqiqiy Telegram'da tekshirgach, ROADMAP'dagi Bosqich 3 "Haqiqiy Telegram'da tekshirish" katagini belgilang.
- [ ] `docs/POST_EXAMPLES.md` ni to'ldiring — Bosqich 4 uchun kerak (har kanaldan 2–3 ta post).
- [ ] Hali `git push` qilinmagan (siz aytgandek). Ko'rib chiqqach: `git push -u origin main`.
- [ ] **Bosqich 5 migratsiyasi:** `uv run alembic upgrade head` (jobs jadvaliga `profession`, `salary_period`).
- [ ] **Qaror kerak — 742** (2 oy bepul amaliyot, keyin haq): job qildim. Kerak bo'lmasa `config/filters.yaml` dagi
      `opportunity_strong_exceptions` ni o'chiring.
- [ ] **Bosqich 6 migratsiyasi:** `uv run alembic upgrade head` (`category_images` → `images` jadvali).
- [ ] **Vaqtinchalik rasmlar:** `uv run python scripts/make_placeholder_images.py` (allaqachon bir marta ishga tushirdim —
      249 ta rasm `assets\images\` da; git'ga tushmaydi).
- [ ] **Postlar ko'rinishini ko'ring:** `uv run python scripts/preview_posts.py` → `start data\preview.html`
      (309 ta e'lon kanaldagidek). Yoki `tests\snapshots\*.html`. Yoqmagan 3–4 tasini chatdagi Claude'ga tashlang.

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
