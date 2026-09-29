# Progress log

Claude Code har bir bosqichdan keyin shu yerga yozadi: nima qilindi, qanday ishga tushiriladi, ma'lum muammolar.

| Sana | Bosqich | Nima qilindi | Eslatma |
|---|---|---|---|
| 2026-09-29 | Reja | CLAUDE.md, ARCHITECTURE, ROADMAP, POST_EXAMPLES yaratildi | Keyingi qadam: Bosqich 0 (tayyorgarlik) |
| 2026-09-29 | 1 — Skelet | pyproject (uv, src layout), papkalar, `config.py`, `config/*.yaml`, `.env.example`, `.gitignore`, loguru, README, ruff, testlar | 6 test ✅, ruff ✅ |
| 2026-09-29 | 2 — Baza | 12 ta jadval modeli (`db/models.py`), `db/session.py` (WAL, busy_timeout, foreign_keys), Alembic (async) + birinchi migratsiya + `jobs_fts` (FTS5) triggerlari, repository'lar: sources, raw_posts, kv | 25 test ✅, ruff ✅, `alembic check` ✅ |
| 2026-09-29 | 3 — Collector | `sources/base.py`, `telegram_source.py`, `registry.py`, `apps/collector.py` (`--once` rejimi bilan), `scripts/login_telethon.py`, `scripts/show_status.py`; soxta manba + soxta Telethon client bilan testlar | 66 test ✅ (5 marta ketma-ket), ruff ✅. Haqiqiy Telegram'da **tekshirilmagan** (session yo'q) |

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
