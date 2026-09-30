# Ayvona Jobs — To'liq reja (Claude Code bilan)

Bu faylda loyihaning boshidan oxirigacha **har bir bosqichi** va Claude Code'ga beriladigan **tayyor prompt**lar bor.
Har safar menga (chatdagi Claude'ga) murojaat qilish shart emas: bosqichni ochasiz → promptni ko'chirasiz → Claude Code qiladi.

---

## Claude Code'ni qanday ishlatamiz

### Qaysi model qachon (Claude Pro tarifi)
Pro'da limit bor (har 5 soatlik oyna + haftalik). Kuchli model limitni tezroq yeydi, shuning uchun:

| Vaziyat | Model | Qanday yoqiladi |
|---|---|---|
| **Ko'p bosqichlar uchun asosiy tanlov** — Opus reja tuzadi, Sonnet kod yozadi | `opusplan` | `/model opusplan` |
| Murakkab joylar: ishonchlilik, regex parser, outbox, FSM forma, Gemini | **Opus 5.5** | `/model opus` |
| Oddiy kod, testlar, handlerlar, hujjat | **Sonnet 5** | `/model sonnet` |
| Mayda ishlar: nom o'zgartirish, format, kichik tuzatish | **Haiku 4.5** | `/model haiku` |

> Model nomlari vaqt o'tishi bilan yangilanadi. `/model` buyrug'i menyusida hozirgi ro'yxatni ko'rasiz.
> Har bir bosqichda qaysi modelni tavsiya qilganim ko'rsatilgan.

### Har bir bosqich tartibi (oltin qoida)
1. VS Code'da loyiha papkasini oching → terminalda `claude` yozing.
2. `/clear` — yangi bosqichni **toza sessiya**da boshlang (limit tejaladi, chalkashlik bo'lmaydi).
3. `/model ...` — jadvaldagi modelni tanlang.
4. **Shift+Tab** — *plan mode*ga o'ting (Claude avval reja ko'rsatadi, kod yozmaydi).
5. Bosqich promptini qo'ying. Rejani o'qing → ma'qul bo'lsa "ha, bajar" deng.
6. Tugagach, bosqichdagi **"Tekshirish"** qismini o'zingiz bajaring.
7. Hammasi ishlasa: `git add .` → `git commit -m "..."` → `git push`.
8. Sessiya juda uzun bo'lib ketsa: `/compact`.

`CLAUDE.md` har sessiyada avtomatik o'qiladi — qoidalarni har safar takrorlash shart emas.

---

## Funksiyalar ro'yxati (kelishilgan)

**Aggregator (1-qism)**
- [x] Telegram kanallardan o'qish (Telethon), oxirgi ID, o'chib qolsa qolganlarini olish (laptopda ishlayapti)
- [x] SQLite, dublikat tekshiruvi (4 qatlam)
- [x] Kategoriya (kalit so'zlar, lotin/kirill/rus) + "Boshqa"
- [ ] Har kategoriya uchun rasm _(hozir vaqtinchalik rangli rasmlar; haqiqiylari — docs/IMAGES.md)_
- [x] Regex bilan bezash (lavozim, maosh, manzil, aloqa...) yoki tozalangan fallback
- [x] Avtomatik joylash (navbat, qayta urinish, admin'ga xabar, 24 soatdan eskisi chiqmaydi)
- [x] Hashtaglar: `#dasturchi #toshkent` — kanal ichida bosib qidirish uchun
- [ ] Kengaytiriladigan manbalar (keyin 2–3 sayt) _(`BaseSource` + registry tayyor; saytlar — Bosqich 16)_

**Ommaviy bot @ayvona_jobs_bot (2-qism)** — asosiy menyu: 📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar
- [ ] E'lon joylash: qadamma-qadam forma, **aloqa majburiy** (telefon tugmasi yoki @username), ko'rib chiqish, tasdiqlash
- [ ] Limitlar (masalan kuniga 2 e'lon), spam / taqiqlangan so'z / **firibgarlik** filtrlari ("oldindan to'lov", "chet elga viza uchun pul"...)
- [ ] Ish qidirish: kategoriya → hudud → maosh → natijalar (eng yangisi birinchi), kalit so'z bilan qidirish
- [ ] ⭐ Saqlanganlar + ulashish
- [ ] 🔔 Ish obunasi: "dasturchi, Toshkent, 5 mln+" → yangi mos e'lon chiqsa bot xabar beradi
- [ ] E'lonni yopish ("Ish topildi" tugmasi) + 30 kundan keyin qidiruvdan avtomatik chiqish
- [ ] Admin: `/stats /queue /failed /retry /pause /resume /ban /unban /addword /delword`
      _(birinchi oltitasi tayyor — Bosqich 8; `/ban /unban /addword /delword` — Bosqich 11)_
- [ ] Manbalarni bot orqali boshqarish: `/addsource /sources` (qo'shish, o'chirish, pauza — kodga tegmasdan)
      _(kod tayyor — haqiqiy botda tekshirilgach belgilang)_
- [x] Kanal postida tugmalar: "📩 Murojaat" · "⭐ Saqlash" · "🔍 Boshqa ishlar" (botga deep link)
      _(tugmalar chiqyapti; "Saqlash" / "Boshqa ishlar" bot tomoni — Bosqich 10–12)_

**AI (3-qism, ixtiyoriy)** — Gemini faqat regex uddalay olmaganda, kesh, fallback.

---

## BOSQICH 0 — Tayyorgarlik (qo'lda, AI'siz) ⏱ 1–2 soat

**Kompyuterga o'rnating:**
- [x] Python 3.12 — uv o'zi boshqaradi (python.org shart emas; ikkinchi Windows foydalanuvchisi — docs/HANDOFF.md)
- [x] Git — git-scm.com
- [x] VS Code — code.visualstudio.com
- [x] uv (2026-09-29, Claude o'rnatdi; Python 3.12 ni uv o'zi boshqaradi) — PowerShell'da: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- [x] Claude Code — docs.claude.com'dagi Windows ko'rsatmasi bo'yicha, keyin `claude` bilan Pro akkauntga kiring

**Telegram:**
- [x] Kanal yarating: nomi **Ayvona Jobs**, username **@ayvonajobs** (bo'sh bo'lsa)
- [x] @BotFather → `/newbot` → username **@ayvona_jobs_bot**.
      ⚠️ Bot username'i albatta `bot` bilan tugashi kerak, shuning uchun `@ayvonajobs` faqat kanalga bo'ladi.
- [x] Botni kanalga **admin** qiling (post joylash + tahrirlash huquqi)
- [ ] Admin chat: o'zingiz uchun yopiq guruh yarating, botni qo'shing (xatolar, backup shu yerga keladi)
      _(`.env` → `ADMIN_CHAT_ID` to'ldirilganini tekshirib belgilang)_
- [x] my.telegram.org → API development tools → `API_ID` va `API_HASH` oling
      (tavsiya: alohida SIM'dagi ikkinchi Telegram akkaunt bilan)
- [x] O'z Telegram ID'ingizni biling (@userinfobot)

**Git:**
```powershell
cd "D:\Coding projects\ayvona"
git init
git branch -M main
git remote add origin https://github.com/sabdur4hmonov/ayvonajobs.git
# GitHub'dagi repo bo'sh bo'lmasa (README bor bo'lsa):
git pull origin main --allow-unrelated-histories
```
- [ ] GitHub'da repo'ni **Private** qiling (Settings → Danger zone)

---

## BOSQICH 1 — Loyiha skeleti ⏱ 30 daq · Model: `sonnet`

- [x] Bajarildi — 2026-09-29 (tafsilot: `docs/PROGRESS.md`)

```text
CLAUDE.md va docs/ARCHITECTURE.md ni o'qi. Loyiha skeletini yarat:
- uv bilan pyproject.toml (Python 3.12, src layout, paket nomi "ayvona"), kerakli kutubxonalar:
  telethon, aiogram>=3, sqlalchemy[asyncio]>=2, aiosqlite, alembic, pydantic-settings, pyyaml,
  rapidfuzz, loguru; dev: pytest, pytest-asyncio, ruff.
- CLAUDE.md dagi papka tuzilmasini bo'sh __init__.py'lar bilan yarat.
- src/ayvona/config.py: .env dan (API_ID, API_HASH, TELETHON_SESSION, BOT_TOKEN, CHANNEL_ID,
  ADMIN_IDS, ADMIN_CHAT_ID, DB_PATH, LOG_LEVEL, TZ) va config/*.yaml dan sozlamalarni o'qiydigan pydantic-settings.
- config/settings.yaml: sources ro'yxati BO'SH (izoh bilan: qanday qo'shiladi), poll_interval_seconds: 90,
  initial_backfill: 0, publish_interval_seconds: 60, max_publish_attempts: 8.
- config/categories.yaml, regions.yaml, filters.yaml — hozircha 3-4 ta namunaviy yozuv bilan.
- .env.example (izohlar bilan), .gitignore (.env, *.session, data/, .venv, __pycache__).
- loguru logging: konsol + data/logs/ ga kunlik aylanuvchi fayl.
- README.md: o'zbekcha, qanday o'rnatish va ishga tushirish (PowerShell buyruqlari).
- ruff sozlamasi, bitta oddiy test (config yuklanadimi).
Oxirida menga o'zbekcha tushuntir: har bir papka nima uchun, .env ni qanday to'ldirishim kerak.
```
**Tekshirish:** `uv sync` → `uv run pytest` → yashil. `.env.example` dan nusxa olib `.env` yarating va to'ldiring.
**Commit:** `chore: project skeleton`

---

## BOSQICH 2 — Baza modellari + migratsiya ⏱ 45 daq · Model: `opusplan`

- [x] Bajarildi — 2026-09-29 (tafsilot: `docs/PROGRESS.md`)

```text
docs/ARCHITECTURE.md 4-bo'limidagi HAMMA jadvallarni SQLAlchemy 2.0 (async, Mapped[] uslubi) modellari
sifatida src/ayvona/db/models.py da yoz. Statuslar uchun Enum ishlat (3-bo'lim).
- db/session.py: async engine (aiosqlite), har ulanishda PRAGMA journal_mode=WAL, busy_timeout=5000,
  foreign_keys=ON. Session factory.
- Alembic'ni sozla (async), birinchi migratsiyani yarat. jobs_fts (FTS5) uchun migratsiyada raw SQL
  va jobs bilan sinxronlovchi triggerlar.
- db/repositories/: sources_repo, raw_posts_repo — keyingi bosqichga kerak bo'ladigan funksiyalar.
- Indekslar: raw_posts(status), jobs(status, next_retry_at), jobs(category, region, published_at), UNIQUE'lar.
- Testlar: vaqtinchalik bazada modellar yaratiladi, UNIQUE(source_id, external_id) dublikatni rad etadi.
Menga o'zbekcha tushuntir: "model", "migratsiya" nima va nega kerak.
```
**Tekshirish:** `uv run alembic upgrade head` → `data/ayvona.db` paydo bo'ladi. VS Code'ga "SQLite Viewer" extension o'rnatib jadvallarni ko'ring.
**Commit:** `feat(db): models and initial migration`

---

## BOSQICH 3 — Telethon collector (BIRINCHI ASOSIY QADAM) ⏱ 1–2 soat · Model: `opus`

- [x] Kod + testlar bajarildi — 2026-09-29 (soxta manba bilan; tafsilot: `docs/PROGRESS.md`)
- [x] Haqiqiy Telegram'da tekshirish — 2026-09-30 (laptopda ~20 kanalni o'qiyapti)

```text
Collector'ni yoz (ARCHITECTURE 2- va 6-bo'lim). Ishonchlilik eng muhim.
1. scripts/login_telethon.py — bir martalik kirish (telefon, kod, 2FA parol), session data/ ga saqlanadi.
2. sources/base.py: RawItem dataclass (external_id, grouped_id, text, has_media, media_type, posted_at)
   va BaseSource(ABC) — async fetch_new(since) -> list[RawItem].
3. sources/telegram_source.py: TelegramSource — iter_messages(entity, min_id=last_seen_id, reverse=True).
   Birinchi ishga tushishda last_seen_id bo'lmasa, settings.initial_backfill ta oxirgi postni oladi
   (0 bo'lsa faqat hozirgi eng oxirgi ID'ni eslab qoladi). Albomlarni grouped_id bilan saqla.
   Servis xabarlari va bo'sh postlarni o'tkazib yubor, lekin rasm-only postlarni saqla (has_media=True, text="").
4. sources/registry.py: config'dagi type bo'yicha manba klassini qaytaradi (keyin "web" qo'shiladi).
5. apps/collector.py: settings.yaml dagi manbalarni sources jadvaliga sinxronla, keyin cheksiz sikl:
   har manba uchun fetch → BITTA tranzaksiyada raw_posts ga INSERT OR IGNORE + last_seen_id yangilash.
   Manbalar orasida 2-3 soniya kutish. FloodWaitError → aytilgan vaqtcha kut. Bitta manba xatosi
   boshqalarini to'xtatmasin (error_count, last_error yoziladi). Har daqiqada kv_store ga heartbeat.
   Ctrl+C bilan toza to'xtashi kerak.
6. Testlar: soxta (fake) manba bilan — o'chib yonishdan keyin qolgan postlar olinadi, dublikat yozilmaydi,
   last_seen_id faqat muvaffaqiyatli commit'dan keyin o'zgaradi.
Kod ishlab bo'lgach, menga o'zbekcha qadam-baqadam: login qilish, settings.yaml ga kanal qo'shish,
collector'ni ishga tushirish va bazada postlarni ko'rish.
```
**Tekshirish:** settings.yaml'ga 1–2 test kanal qo'shing → collector'ni yoqing → bazada `raw_posts` to'ladi →
collector'ni o'chiring, 10 daqiqa kuting, yoqing → oradagi postlar ham kelgan bo'lishi kerak.
**Commit:** `feat(collector): telethon source with catch-up`

---

## BOSQICH 4 — Real misollar → testlar, normalize, klassifikator, dedup ⏱ 1–2 soat · Model: `opusplan`

- [x] Bajarildi — 2026-09-29 (tafsilot: `docs/PROGRESS.md`; extract testlari xfail — Bosqich 5)

> ✅ Tayyor: `docs/POST_EXAMPLES.md` (41 ta real misol + kutilgan natija), `docs/SOURCE_ANALYSIS.md`,
> `config/source_rules.yaml`, `config/filters.yaml` — 19 kanaldan 377 post tahlili asosida.

```text
docs/SOURCE_ANALYSIS.md, docs/POST_EXAMPLES.md, config/filters.yaml va config/source_rules.yaml ni o'qi.
1) POST_EXAMPLES dagi 41 misolning har birini tests/fixtures/posts/<kanal>_<id>.json ga ko'chir:
   {"source": "@kanal", "external_id": "...", "text": "...", "extra": {links, buttons}, "expected": {...}}.
   Matn va extra ni POST_EXAMPLES dan emas, data/ayvona.db dagi raw_posts dan ol (aynan bo'lsin).
2) processing/normalize.py: NFKC (𝗨𝗫 → UX), keycap raqamlar (3️⃣ → 3), kichik harf, o'zbek kirill→lotin
   (ruscha matnni buzmasdan: faqat o'zbekcha harflar ў қ ғ ҳ bo'lsa yoki kontekst o'zbekcha bo'lsa),
   o‘ oʻ o' o` → o', emoji va ortiqcha bo'shliqlarni olib tashlash. Asl matn ham saqlanib qoladi.
3) processing/classify.py: kind = job | not_job | resume | closed | opportunity | suspicious
   (SOURCE_ANALYSIS 3-bo'lim tartibi, filters.yaml markerlari, source_rules.yaml dagi job/non_job teglari,
   'Ariza muddati' o'tgan bo'lsa closed). So'zlarni so'z chegarasi bilan qidir ("grant" ≠ "emigrant").
   Matnsiz albom qismlari grouped_id bo'yicha birlashtiriladi.
4) processing/dedup.py: SOURCE_ANALYSIS 8-bo'lim — tozalangan matn bo'yicha, 14 kunlik oyna, content_hash +
   fingerprint (lavozim + birinchi telefon/username) + rapidfuzz ≥ 90%. Birinchisi qoladi, qolgani duplicate.
   data/ayvona.db dagi 377 post ustida sinab ko'r: ≈ 22 guruh topilishi kerak — natijani menga ayt.
5) processing/language.py: e'lon tilini aniqla — uz_latin | uz_cyrillic | ru | en (o'zbek kirill harflari ў қ ғ ҳ
   va so'zlari bo'yicha; ruscha bilan adashtirma). Kanalga FAQAT kind=job chiqadi (resume/opportunity kerak emas).
6) Testlar: normalize, classify (41 misolning hammasida kind to'g'ri), language, dedup. extract testlari — xfail.
Menga o'zbekcha: nechta misol o'tdi, qaysilari o'tmadi va nega.
```
**Commit:** `feat(processing): normalize, classify, dedup with real fixtures`

---

## BOSQICH 5 — Regex extractor + kategoriya ⏱ 2–3 soat · Model: `opus`

- [x] Bajarildi — 2026-09-29 (tafsilot: `docs/PROGRESS.md`; 24/24 sobiq xfail o'tdi)

```text
processing/extract.py va processing/categorize.py ni yoz. tests/fixtures dagi HAMMA xfail testlar o'tishi kerak.
SOURCE_ANALYSIS 4–7 va 9-10 bo'limlaridagi HAMMA formatlarni qo'lla:
- aloqa 6 joydan: matndagi telefon/@username/t.me, extra.links (yashirin: "Aloqa uchun 👈", "Get the job.",
  "havola", "Link"), extra.buttons ("Apply here", "Qiziqish bildirish"), t.me/+998... (telefon!), email,
  forma/hh.uz/LinkedIn/telegra.ph → apply_url. own_usernames va source_rules.yaml dagi drop qoidalari —
  aloqa emas (aniq moslik bilan).
- telefon: 5-bo'limdagi barcha yozilishlar → +998XXXXXXXXX; operator kodlari ro'yxati + shahar kodlari (65–79);
  noma'lum kod bo'lsa faqat yonida "tel/telefon/aloqa/bog'lanish" bo'lsa qabul qil.
- maosh: 6-bo'limdagi barcha formatlar, salary_period (month/day/week/hour), USD alohida currency,
  aql-hush tekshiruvi (xato raqam → faqat salary_text). "Depozit" maosh emas.
- title, company, schedule, requirements — qolip kalitlari (Lavozim:, Position:, Job Title:, Вакансия:,
  📊Lavozim:, 👔 Position:, ☑️ Lavozim:, 📌 ...), bo'lmasa birinchi mazmunli qator; "—" = bo'sh.
- region/district: regions.yaml ni to'ldir (14 hudud + toshkent_vil + Toshkent tumanlari + metro/mo'ljallar,
  lotin/kirill/rus/ingliz variantlari, xato yozilishlar: Sergili, Yunsobot, Yunusabad), ko'p shahar → "ko'p hudud",
  Remote/online/uydan turib → is_remote.
- multi: bir postda bir necha lavozim (ro'yxat, 1️⃣ 2️⃣, bir necha "... kerak" bloki) → positions ro'yxati.
- confidence 0..1: title + aloqa bo'lsa ≥ 0.7.
Categorize: config/categories.yaml TAYYOR (19 kategoriya → 64 kasb, teglar, feature_tags). Natija:
(category, profession | None, feature_tags). Kasb kalit so'zlari → kasb va uning kategoriyasi; title 3x ball;
kasb topilmasa kategoriya darajasida (chet_el kalit so'zlari); hech narsa → boshqa. Kalit so'zlarni real postlarga
qarab to'ldir (lotin + kirill + rus + ingliz). feature_tags (masofaviy, tajribasiz, talabalar_uchun, yotoqjoy,
yarim_stavka) INKOR bilan: "yotoqxona yo'q", "talabalar qabul qilinmaydi" → teg YO'Q. jobs jadvaliga
profession ustunini qo'sh (Alembic migratsiya).
Lavozimni o'zbekchaga o'girish: config/title_translations.yaml (exact, keyin words) — ru/en e'lonlar uchun.
Menga qaysi misollar o'tmaganini va nima uchunligini tushuntir.
```
**Commit:** `feat(processing): regex extractor and categorizer`

---

## BOSQICH 6 — Tozalash, shablon, rasmlar ⏱ 1–2 soat · Model: `sonnet`

- [x] Bajarildi — 2026-09-29 (tafsilot: `docs/PROGRESS.md`; ko'rib chiqish: `tests/snapshots/`, `scripts/preview_posts.py`)

```text
processing/clean.py: config/source_rules.yaml ni o'qi (defaults + har kanal: cut_from, strip_lines, exact_lines,
header_lines, header_junk_words, drop_trailing_hashtags, extra_own_usernames). Xavfsizlik: kesishdan keyin
matnning 40% dan kami qolsa — kesma, log yoz. utm_*/text= parametrlarini havolalardan olib tashla.
Aloqa @username va telefonlar HECH QACHON o'chmasin. Admin bot orqali qo'shgan kanalga faqat defaults.
processing/formatter.py: docs/POST_EXAMPLES.md oxiridagi "KELISHILGAN SHABLON" — AYNAN shunday:
bo'sh maydon chiqmaydi, maosh yo'q → "Kelishiladi", ko'p vakansiya → "📌 Lavozimlar:" ro'yxati,
teglar: #kasb #kategoriya #hudud + ko'pi bilan 2 ta feature teg (jami ≤ 5, takror yo'q), imzo, eng oxirida <i><a href="https://t.me/<kanal>/<id>">manba</a></i>
(faqat aggregator postlarida). 1024 belgi: avval talablar/tafsilotlar qisqaradi; lavozim, maosh, manzil,
aloqa, imzo, manba — hech qachon. html.escape hamma matnga.
Fallback: confidence past bo'lsa — kategoriya sarlavhasi + tozalangan matn + aloqa + imzo + manba.
TIL QOIDASI (SOURCE_ANALYSIS 11-bo'lim): post doim o'zbekcha va lotinda.
- uz_cyrillic → butun matn lotinga transliteratsiya (to'g'ri qoidalar: ш→sh, ч→ch, ў→o', ғ→g', қ→q, ҳ→h, ё→yo, ю→yu, я→ya,
  е so'z boshida → ye, ц→s/ts, ъ→').
- ru / en → faqat o'zbekcha maydonlar (lavozim lug'at orqali, maosh, manzil, ish vaqti, aloqa), erkin matn qo'yilmaydi,
  o'rniga "📝 To'liq ma'lumot: asl e'londa" (asl postga havola). Fallback ru/en uchun ham shu.
Tugmalar ro'yxatini ham qaytar: 📩 Murojaat (username bo'lsa), 🔗 Ariza topshirish (apply_url bo'lsa),
⭐ Saqlash va 🔍 Boshqa ishlar (bot deep link).
RASMLAR (docs/IMAGES.md): processing/images.py — pick_image(category, profession): assets/images/<kat>/<kasb>/
→ assets/images/<kat>/ → assets/images/boshqa/; har papkada 3–4 variant NAVBAT BILAN (round-robin, hisoblagich
bazada, restart'dan keyin ham davom etadi — mavjud category_images jadvalini Alembic migratsiya bilan
ARCHITECTURE dagi images jadvaliga kengaytir), papkadagi fayllar har safar qayta o'qiladi. Bo'sh papkalar uchun
scripts/make_placeholder_images.py — Pillow bilan 3 ta vaqtinchalik rasm (1280×720, har kategoriyaga o'z rangi,
o'rtada kasb nomi, burchakda "Ayvona Jobs"), fayl nomi placeholder_*.jpg; haqiqiy rasm qo'shilsa placeholder'lar
ishlatilmaydi.
Test: 41 fixture uchun natijani tests/snapshots/<kanal>_<id>.html ga yoz.
```
**Tekshirish:** `tests/snapshots/` dagi postlarni o'qing — shunday chiqishi sizga yoqadimi? Menga (chatdagi Claude'ga) 3–4 tasini tashlang, birga ko'rib chiqamiz.
**Commit:** `feat(processing): cleaner and post formatter`

---

## BOSQICH 7 — Worker: pipeline + publisher ⏱ 2 soat · Model: `opus`

- [x] Kod + testlar bajarildi — 2026-09-29 (Bot API mock bilan; tafsilot: `docs/PROGRESS.md`)
- [x] Kanalda tekshirish — 2026-09-30 (real postlar @ayvonajobs ga chiqyapti)
- [x] `publisher.max_age_hours` (24 soatdan eski e'lon chiqmaydi, `skipped_old`) — 2026-09-30

```text
apps/worker.py ni yoz, ichida 2 ta asyncio vazifa:
0) MUHIM: bazadagi hozirgi raw_posts (initial_backfill bilan olingan test postlari, fetched_at <= worker
   birinchi ishga tushgan vaqt) kanalga CHIQMASIN: birinchi ishga tushishda ularni status=skipped_backfill qil
   (bir martalik migratsiya yoki kv_store bayrog'i). Keyin backfill bilan kelgan postlar ham faqat
   settings.publisher.publish_backfill=true bo'lsa chiqadi (standart false).
1) pipeline: status=new va fetched_at 60 soniyadan eski raw_posts ni oladi (albom qismlari yig'ilishi uchun),
   grouped_id bo'yicha birlashtiradi → classify → (job bo'lsa) clean → dedup → extract → categorize → format →
   jobs(queued). Boshqa turlar: statusi not_job/resume/closed/opportunity/suspicious/duplicate/no_contact.
   suspicious va no_text — admin chatga yuboriladi. Istisno bo'lsa: status=error, admin'ga xabar, sikl davom etadi.
1b) YIG'ISH OYNASI (bir e'lon 2-3 kanalda chiqsa): yangi job darhol emas, settings.publisher.hold_minutes
   (standart 20) dan keyin chiqadi. Shu vaqt ichida kelgan dublikat ORIGINALDAN TO'LIQROQ bo'lsa (aloqa, maosh,
   manzil bor; confidence yuqori) — dublikat asosiy job bo'ladi, eskisi duplicate. Chiqib bo'lgan postga tegilmaydi.
   Manba havolasi — tanlangan versiyaning kanali. 14 kundan keyin yana chiqsa — yangi e'lon (vakansiya hali ochiq).
2) publisher (outbox): queued/retry jobs ni navbat bilan oladi, publish_interval_seconds ga rioya qiladi.
   Yuborishdan oldin status=sending. sendPhoto (pick_image(category, profession); har fayl uchun telegram_file_id kesh — fayl o'zgarsa kesh yangilanadi)
   + caption HTML + formatter bergan tugmalar. Link preview O'CHIQ (manba havolasi kartochka bo'lib chiqmasin).
   Muvaffaqiyat: published, channel_message_id. TelegramRetryAfter → kut. Tarmoq xatosi → exponential
   backoff (next_retry_at). HTML parse xatosi → oddiy matn bilan qayta urin. max_publish_attempts dan
   keyin failed + admin'ga xabar. Ishga tushganda "sending" da qolganlarni qayta navbatga qo'y.
   kv_store.publisher_paused = true bo'lsa joylamaydi.
Heartbeat har daqiqada. Testlar: Bot API mock bilan — xato/qayta urinish/pauza/qayta ishga tushish/backfill skip.
```
**Tekshirish:** avval test kanal oching (`CHANNEL_ID` ni test kanalga qo'ying) → collector + worker yoqing → postlar chiqyaptimi?
**Commit:** `feat(worker): processing pipeline and reliable publisher`

---

## BOSQICH 8 — Admin, monitoring, backup ⏱ 1–2 soat · Model: `sonnet`

- [x] Kod + testlar bajarildi — 2026-09-30 (Bot API mock bilan; tafsilot: `docs/PROGRESS.md`)
- [ ] Haqiqiy bot bilan tekshirish (Sardor: `docs/PROGRESS.md` oxiridagi "Qanday sinab ko'rasiz")

```text
1) services/notifier.py — admin chatga xabar (xatolar, failed postlar, jim qolgan jarayonlar), bir xil xato
   10 daqiqada bir martadan ko'p yuborilmasin.
2) services/heartbeat.py — worker har 5 daqiqada tekshiradi: collector/bot heartbeat 10 daqiqadan eski bo'lsa ogohlantir.
   Har manba uchun: 24 soatda birorta ham post kelmasa — ogohlantir (kanal o'chgan yoki bizni bloklagan bo'lishi mumkin).
3) services/backup.py — har kuni 03:00 (Toshkent) sqlite backup API bilan nusxa, data/backups/ da oxirgi 7 ta,
   admin chatga document sifatida yuborish.
4) Admin buyruqlari (faqat ADMIN_IDS): /stats (bugun/hafta: keldi, chiqdi, dublikat, xato, kategoriyalar bo'yicha),
   /sources (holati, oxirgi post vaqti), /queue, /failed, /retry <id|all>, /pause, /resume.
   Bu handlerlarni bot/handlers/admin.py ga yoz — ommaviy bot bilan bitta botda bo'ladi.
   Hozircha apps/bot.py faqat admin handlerlari bilan ishga tushsin.
5) MANBALARNI BOT ORQALI BOSHQARISH (admin profildan, kodga tegmasdan):
   - Endi manbalar ro'yxatining asosiy joyi — BAZA (sources jadvali). settings.yaml faqat boshlang'ich
     ro'yxat (seed): yaml'dagi yangi manba bazaga qo'shiladi, lekin yaml'da YO'Q manba o'chirilmaydi.
     sources jadvaliga added_via ('yaml'|'bot') va added_by ustunlarini qo'sh (Alembic migratsiya).
   - Collector har siklda manbalar ro'yxatini bazadan qayta o'qisin — restart'siz yangi kanal ishlay boshlasin.
   - /addsource <@username | t.me/kanal | t.me/+taklif_link> : bot so'rovni bazaga "pending" qilib yozadi,
     collector uni tekshiradi (kanal bormi, o'qib bo'ladimi; taklif link bo'lsa Telethon akkaunt kanalga
     qo'shiladi), keyin admin'ga "✅ Qo'shildi: <kanal nomi>, oxirgi post ID ..." yoki xato sababini yozadi.
     Qo'shishda so'raladi: eski postlardan nechtasini olish (0 / 5 / 20 tugmalari).
   - /sources — ro'yxat, har biri yonida inline tugmalar: [⏸ O'chirish] [▶️ Yoqish] [🗑 O'chirish] [📊 Statistika].
     O'chirilgan manba bazadan o'chmaydi (enabled=false), postlari saqlanib qoladi.
   - /addsource web:<nom> — kodi yozilgan saytni yoqadi (hh, osonish, himalayas...).
   - /addsource rss:<URL> — RSS/Atom lentasi bor HAR QANDAY saytni kodsiz qo'shadi (Bosqich 16.0 da yoziladi;
     hozircha buyruq "tez orada" deb javob bersin). Admin sayt nomini va kunlik limitni tugma bilan tanlaydi.
   - /sources ro'yxatida Telegram kanallar va saytlar birga ko'rinadi; saytlar uchun ham [⏸] [▶️] [🗑] [📊]
     va "tekshirish oralig'i" (15 daq / 30 daq / 1 soat) tugmalari.
   - Faqat ADMIN_IDS ishlata oladi; har o'zgarish logga yoziladi.
6) RASMLARNI BOT ORQALI BOSHQARISH (docs/IMAGES.md): /images (bo'shliqlar va placeholder'lar ro'yxati),
   /addimage <kasb|kategoriya> → admin rasm yuboradi → tegishli papkaga saqlanadi, /images <kasb> → [🗑 O'chirish].
```
**Commit:** `feat(admin): notifications, monitoring, backups, admin commands`

---

## BOSQICH 9 — Oracle serverga chiqarish (MVP JONLI!) ⏱ 2–3 soat · Model: `sonnet`

- [x] Hujjat va fayllar tayyor — 2026-09-30 (`deploy/SETUP_ORACLE.md`, `deploy/systemd/`, `scripts/deploy.sh`)
- [ ] Oracle akkaunt + server, serverga chiqarish (docs/HANDOFF.md → keyingi ishlar)

```text
deploy/ papkasini tayyorla:
- deploy/SETUP_ORACLE.md: o'zbekcha, rasmlarsiz lekin juda batafsil: Oracle Always Free akkaunt,
  Ubuntu 24.04 (Ampere A1, 1 OCPU / 6 GB yetarli) instance yaratish, SSH kalit (Windows PowerShell'da ssh-keygen),
  ulanish, firewall, uv o'rnatish, repo'ni clone qilish (private repo uchun deploy key), .env va .session faylni
  scp bilan ko'chirish, alembic upgrade, systemd servislarni yoqish, loglarni ko'rish (journalctl),
  yangilash (git pull + restart), backup'dan tiklash.
- deploy/systemd/ayvona-collector.service, ayvona-worker.service, ayvona-bot.service
  (Restart=always, RestartSec=10, alohida "ayvona" foydalanuvchi).
- scripts/deploy.sh: git pull, uv sync, alembic upgrade, 3 servisni restart.
- Vaqt zonasi va NTP.
```
**Tekshirish:** kompyuterni o'chiring — kanalga postlar baribir chiqyaptimi? 1–2 hafta kuzating, `/stats` va
admin chatdagi xatolarga qarab kalit so'zlar va regex'ni sozlang.
**Commit:** `chore(deploy): oracle vps setup and systemd units`

> 🎉 Shu yerda **1-qism tayyor**. Keyingi bosqichlarga faqat MVP barqaror ishlagandan keyin o'ting.

---

## BOSQICH 10 — Ommaviy bot asosi ⏱ 1–2 soat · Model: `sonnet`

```text
Ommaviy botning asosini qur (aiogram 3, Router'lar):
- /start: users jadvaliga yozish/yangilash, salomlashish, asosiy menyu (reply keyboard):
  📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar · ℹ️ Yordam
- Deep link'lar: /start job_<id> (e'lonni ko'rsatish), /start save_<id> (saqlash), /start search
- Middleware'lar: ban tekshiruvi, throttling (1 so'rov/soniya), users.last_active_at
- bot/texts.py — barcha matnlar bitta joyda (keyin rus tili qo'shish oson bo'lsin)
- FSM storage: hozircha MemoryStorage (izohda: nega va keyin nimaga almashtirish mumkin)

Mavjud kodni hisobga ol:
- bot/setup.py: admin_area router public'dan oldin ulangan; admin.py dagi CommandStart adminning
  HAR QANDAY /start ini ushlaydi. O'zgartir: admin ham asosiy menyuni va deep link'larni ko'rsin
  (admin yordami — /help da qolsin).
- Ban/throttling middleware'lari admin'larga (ADMIN_IDS) ta'sir qilmasin.
- public_start va T.PUBLIC_START ("tez orada") — asosiy menyu bilan almashtiriladi.
- Kanal tugmalari allaqachon ?start=save_<id> va ?start=search ga yuboradi — shu formatni saqla.
- Saqlash (favorites) mantiqi services/ da, handler faqat chaqiradi.
```
**Commit:** `feat(bot): public bot foundation and main menu`

---

## BOSQICH 11 — 📢 E'lon joylash formasi ⏱ 2–3 soat · Model: `opus`

```text
bot/handlers/post_job.py — FSM qadamlari (har qadamda "⬅️ Orqaga" va "❌ Bekor qilish"):
1 Kategoriya (inline tugmalar) → 2 Lavozim → 3 Kompaniya (o'tkazib yuborish mumkin) → 4 Maosh (tugmalar:
"Kelishiladi" yoki matn; parse qilinadi) → 5 Hudud (tugmalar) + shahar/tuman → 6 Ish vaqti →
7 Talablar/izoh → 8 ALOQA — MAJBURIY: "📱 Raqamni yuborish" (request_contact), "@username'imni ishlat"
(agar bor bo'lsa) yoki matn bilan +998 raqam/@username; hech biri bo'lmasa keyingi qadamga o'tmaydi →
9 Ko'rib chiqish (kanaldagi ko'rinishda, formatter bilan) → "✅ Yuborish" / "✏️ Tahrirlash".
Limitlar (settings.yaml): kuniga max 2 ta e'lon, e'lonlar orasida 10 daqiqa, bir vaqtda 1 ta kutilayotgan.
Filtrlar: filters.yaml ban so'zlar → rad; spam belgilari (ko'p havola, KATTA HARF, emoji) → rad;
scam so'zlar ("oldindan to'lov", "depozit", "viza uchun pul", "предоплата") → pending_review;
dublikat (dedup.py) → rad. Moderatsiya rejimi settings'da: auto | suspicious_only | all.
Yangi foydalanuvchining (trust_level=0) birinchi e'loni suspicious_only rejimida admin'ga boradi.
Admin'ga: e'lon + [✅ Tasdiqlash] [❌ Rad etish] [🚫 Ban] tugmalari; natija foydalanuvchiga xabar qilinadi.
Tasdiqlangan e'lon jobs(queued, origin=user) → worker publisher chiqaradi → muallifga kanal havolasi yuboriladi.
Testlar: har bir filtr, limit, aloqa majburiyligi.
```
**Commit:** `feat(bot): job submission form with contact, limits, filters`

---

## BOSQICH 12 — 🔍 Ish qidirish + ⭐ Saqlanganlar ⏱ 2 soat · Model: `opusplan`

```text
bot/handlers/search.py:
- Qidiruv ustasi: Kategoriya (yoki "Hammasi") → Kasb (shu kategoriyadagi kasblar tugmalari yoki "Hammasi") → Hudud (yoki "Hammasi", "Masofaviy") → Maosh
  ("Farqi yo'q", "2 mln+", "4 mln+", "6 mln+", "10 mln+") → natijalar.
- Yoki "🔤 So'z bilan qidirish" — jobs_fts (FTS5), normalize qilingan so'rov.
- Natijalar: faqat published va muddati o'tmagan, published_at bo'yicha eng yangisi birinchi, 5 tadan sahifa
  (⬅️ ➡️), har biri qisqa kartochka + [Batafsil] [⭐ Saqlash] [📤 Ulashish (kanal post havolasi)].
- Oxirgi qidiruv filtrlarini eslab qolish ("🔁 Oxirgi qidiruv") va "🔔 Shu qidiruvga obuna bo'lish" tugmasi.
- search_logs ga yozish.
bot/handlers/favorites.py: ro'yxat (sahifalangan), o'chirish; yopilgan e'lonlar "❌ Yopilgan" belgisi bilan.
Salary filtri: salary_max >= filtr yoki salary_min >= filtr; maoshi yo'q e'lonlar "Farqi yo'q" da chiqadi.
USD maoshlar uchun kurs: kv_store.usd_rate (kunda 1 marta cbu.uz ochiq API'dan yangilash, xato bo'lsa eskisi).
```
**Commit:** `feat(bot): job search, favorites and sharing`

---

## BOSQICH 13 — 🔔 Ish obunalari ⏱ 1–2 soat · Model: `sonnet`

```text
bot/handlers/alerts.py: obuna yaratish (qidiruv ustasi bilan bir xil qadamlar: kategoriya → KASB → hudud → maosh + ixtiyoriy kalit so'z),
ro'yxat, o'chirish, pauza. Foydalanuvchiga max 5 ta obuna.
services/alerts.py (worker ichida): e'lon published bo'lgach mos obunalarni topadi, alert_deliveries UNIQUE
orqali bir xabarni ikki marta yubormaydi, foydalanuvchiga kuniga max 20 ta xabar (qolganlari kunlik
dayjestga), Bot API limitlariga rioya (sekundiga ≤ 25 xabar), bot bloklangan bo'lsa (Forbidden) obunalarni
o'chiradi.
```
**Commit:** `feat(alerts): job subscriptions and notifications`

---

## BOSQICH 14 — E'lonni yopish, muddat, to'liq statistika ⏱ 1–2 soat · Model: `sonnet`

```text
- User e'lonlari: "📋 Mening e'lonlarim" (menyuga qo'sh) → [✅ Ish topildi / yopish]. Yopilganda kanal posti
  tahrirlanadi: boshiga "❌ YOPILDI" qo'shiladi, tugmalar olib tashlanadi, qidiruvdan chiqadi.
- services/expiry.py: expires_at o'tgan e'lonlar (aggregator 21 kun, user 30 kun — settings'da) expired bo'ladi
  va qidiruvdan chiqadi (kanal postiga tegilmaydi). User'ga 2 kun oldin "Uzaytirasizmi?" xabari.
- /stats ni kengaytir: foydalanuvchilar (yangi/faol), eng ko'p qidirilgan kategoriya va hududlar,
  obunalar soni, manbalar bo'yicha e'lonlar. /broadcast (faqat admin, tasdiqlash bilan, sekin yuboradi).
- /addword /delword /ban /unban.
```
**Commit:** `feat: job closing, expiry, extended stats`

---

## BOSQICH 15 — Gemini yordamchi (ixtiyoriy) ⏱ 2 soat · Model: `opus`

> Oldin: aistudio.google.com → API key (bepul). Hozirgi bepul modellar va limitlarni AI Studio'da tekshiring.

```text
docs/ARCHITECTURE.md 7-bo'lim bo'yicha src/ayvona/ai/ ni yoz (google-genai SDK):
- Faqat extract confidence < settings.ai.min_confidence bo'lganda va settings.ai.enabled=true bo'lsa chaqiriladi.
- Yuborishdan oldin telefon/username/havolalar [PHONE]/[USER]/[LINK] bilan almashtiriladi.
- Structured output (JSON schema): is_job, title, company, category (bizning ro'yxatdan), salary_min/max,
  currency, region, city, schedule, requirements, short_description.
- ai_cache (text_hash) — bir xil matn qayta yuborilmaydi.
- Model nomi va kalitlar .env da: GEMINI_MODEL, GEMINI_API_KEYS (vergul bilan), GEMINI_ALLOW_KEY_ROTATION=false.
  Rotation false bo'lsa faqat birinchi kalit ishlatiladi. README'da Google shartlari haqida ogohlantirish yoz.
- Circuit breaker: 429/5xx/timeout (10 s) → shu kalit N daqiqa/kun oxirigacha o'chiriladi → regex fallback.
  AI hech qachon e'lon chiqishini to'xtatmaydi.
- AI natijasi regex natijasi bilan birlashtiriladi (aloqa har doim regex'dan). parse_method=gemini.
- TARJIMA: til ru/en bo'lsa (yoki confidence past bo'lsa) Gemini talablar/vazifalar/tavsifni o'zbek lotiniga
  qisqa va aniq o'giradi; natija keshlanadi. Gemini ishlamasa — Bosqich 6 dagi v1 til qoidasi.
- Kunlik AI chaqiruvlari soni /stats da.
Testlar: AI mock — muvaffaqiyat, 429, timeout, noto'g'ri JSON → hammasida e'lon chiqadi.
```
**Commit:** `feat(ai): optional gemini helper with cache and fallback`

---

## BOSQICH 16 — Veb-sayt va xalqaro manbalar ⏱ har manba 1–2 soat · Model: `sonnet` (hh.uz va Oson Ish uchun `opusplan`)

> Ro'yxat va shartlar: `docs/WEB_SOURCES.md`. Tartib: hh.uz → Oson Ish → Himalayas + Remotive → Jobicy, Remote OK → vacancy.gov.uz.
> "Xorijda ish" (@migratsiyaagentligi) allaqachon Telegram manba sifatida qo'shilgan.
> Har bir manbani ALOHIDA sessiyada qo'shing. Oldin umumiy asos (16.0), keyin har sayt.

**16.0 — umumiy asos (bir marta):**
```text
docs/WEB_SOURCES.md ni o'qi. sources/web/base.py: WebSource(BaseSource) — httpx (User-Agent "AyvonaJobsBot/1.0
(+https://t.me/ayvonajobs)", timeout, retry, 429/5xx da kutish), har manba uchun minimal so'rov oralig'i va
kunlik limit (settings.yaml: web_sources.<nom>.interval_minutes, max_requests_per_day). RawItem ga
url, apply_url, source_name ("Himalayas"), location_restrictions qo'sh. Formatter: veb-manbada oxirgi qator
<i>manba: <a href="URL">Sayt nomi</a></i>, "🔗 Ariza topshirish" tugmasi. Xalqaro masofaviy e'lonlar uchun
settings.publisher.max_remote_per_day (standart 12) va "O'zbekistondan ariza topsa bo'ladi" filtri
(Worldwide/Anywhere, Uzbekistan, Central Asia, CIS, Asia yoki UTC+5 ni qamragan vaqt mintaqasi).
Kategoriyalar: chet_el (#xorijda_ish), masofaviy teglar #masofaviy #xalqaro.
UMUMIY RSS MANBA: sources/web/rss.py — RSS/Atom lentasini o'qiydigan universal manba (feedparser yoki
xml.etree). Admin botda /addsource rss:<URL> deydi → bot lentani tekshiradi, sarlavhasini ko'rsatadi,
[✅ Qo'shish] bosilgach sources jadvaliga type="rss" bilan yoziladi; collector restart'siz o'qiy boshlaydi.
Hamma veb-manbalar botdagi /sources da boshqariladi (yoqish/o'chirish/oraliq/limit). Kod yoki YAML tahriri kerak emas.
```

**16.x — har bir sayt:**
```text
<MANBA_NOMI> ni qo'sh (docs/WEB_SOURCES.md dagi qator). Avval saytning hozirgi shartlarini, robots.txt ni
va API hujjatini tekshirib menga qisqacha ayt — ruxsat bo'lmasa yoki shartlar o'zgargan bo'lsa TO'XTA.
sources/web/<nom>.py: faqat ruxsat etilgan yo'llar, limitlarga qat'iy rioya, last_seen_id = oxirgi e'lon ID/URL.
Natijani RawItem ga aylantir (matn, maydonlar, url, apply_url). registry.py ga "web:<nom>" qo'sh.
Saqlangan javob (JSON yoki HTML) namunasi bilan test. Bot orqali /addsource web:<nom> bilan yoqiladigan bo'lsin.
```

---

## BOSQICH 17 — Ayvona Jobs O'Z VEB-SAYTI ⏱ 3–4 soat · Model: `opusplan`
**Qachon:** Bosqich 9 (server jonli) va 10–14 (ommaviy bot) barqaror ishlagandan keyin. Bot va sayt BITTA biznes-mantiq
(qidiruv, e'lon joylash, filtrlar, saqlanganlar) va BITTA baza ishlatadi — mantiq `services/` da, bot va sayt uni chaqiradi.
**Xavfsizlik:** alohida `web` jarayoni; yiqilsa collector/worker/publisher'ga ta'sir qilmaydi. Sayt bazadan faqat o'qiydi,
yozish (e'lon joylash, saqlash) faqat `services/` orqali.
**Bepul:** FastAPI + Jinja2 (server tomonda chiziladi, React yo'q), Caddy (avto HTTPS), boshida DuckDNS manzili; ayvona.uz domeni — keyin, ixtiyoriy.

```text
Bosqich 17: Ayvona Jobs veb-sayti. Avval CLAUDE.md, docs/ARCHITECTURE.md va services/ ni o'qi.
1) src/ayvona/apps/web.py — FastAPI + Jinja2 jarayoni (4-jarayon), deploy/systemd/ayvona-web.service, Caddy sozlamasi qo'llanmasi.
2) Sahifalar: bosh sahifa (yangi e'lonlar), qidiruv+filtr (kategoriya/kasb/hudud/maosh/kalit so'z, eng yangisi tepada),
   e'lon sahifasi /ish/<id>-<slug> ("Ariza topshirish" + "manba" havolasi), kategoriya/kasb/hudud sahifalari.
3) SEO: sitemap.xml, robots.txt, har e'londa JSON-LD JobPosting, sarlavha/description, muddati o'tgan e'londa valid_through.
4) E'lon joylash formasi: bot bilan BIR XIL qoidalar (limit, spam/scam filtr, aloqa majburiy) — kod takrorlanmasin, services/ dan foydalan.
   Telegram Login Widget bilan kirish (spam himoyasi). Saytdan joylangan e'lon ham kanalga chiqadi.
5) Saqlanganlar va ish alertlari: Telegram akkaunt orqali bog'lanadi, bildirishnoma botga keladi.
6) Admin panel (faqat ADMIN_IDS): manbalar, rasmlar, statistika (botdagi /sources, /images, /stats ning veb varianti).
7) Testlar, 1 GB dan kam xotira, sahifa tez (SQLite indekslar/FTS5). Real e'lonlar bilan sinab ko'r, natijani ayt.
```

---

## KELAJAK (startap bosqichi) — hozir qilmaymiz, faqat yo'nalish
- **Telegram Mini App** — chiroyli qidiruv interfeysi (bepul: GitHub Pages / Cloudflare Pages)
- **ayvona.uz domeni** (pullik, yiliga bir necha dollar) — sayt Bosqich 17 da tayyor bo'ladi
- **PostgreSQL** — foydalanuvchilar ko'payganda (SQLAlchemy tufayli ko'chish oson)
- **Rus tili** interfeysi (`texts.py` tayyor)
- **Rezyume bo'limi** — ish qidiruvchilar profili, ish beruvchilar ko'radi
- **Daromad** (keyinroq): pullik "📌 TOP e'lon", ish beruvchi obunasi, kompaniya sahifasi
- Analitika: qaysi kategoriyada talab ko'p — ish beruvchilarga hisobot
