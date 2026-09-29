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
- [ ] Telegram kanallardan o'qish (Telethon), oxirgi ID, o'chib qolsa qolganlarini olish
- [ ] SQLite, dublikat tekshiruvi (4 qatlam)
- [ ] Kategoriya (kalit so'zlar, lotin/kirill/rus) + "Boshqa"
- [ ] Har kategoriya uchun rasm
- [ ] Regex bilan bezash (lavozim, maosh, manzil, aloqa...) yoki tozalangan fallback
- [ ] Avtomatik joylash (navbat, qayta urinish, admin'ga xabar)
- [ ] Hashtaglar: `#dasturchi #toshkent` — kanal ichida bosib qidirish uchun
- [ ] Kengaytiriladigan manbalar (keyin 2–3 sayt)

**Ommaviy bot @ayvonabot (2-qism)** — asosiy menyu: 📢 E'lon joylash · 🔍 Ish qidirish · ⭐ Saqlanganlar · 🔔 Obunalar
- [ ] E'lon joylash: qadamma-qadam forma, **aloqa majburiy** (telefon tugmasi yoki @username), ko'rib chiqish, tasdiqlash
- [ ] Limitlar (masalan kuniga 2 e'lon), spam / taqiqlangan so'z / **firibgarlik** filtrlari ("oldindan to'lov", "chet elga viza uchun pul"...)
- [ ] Ish qidirish: kategoriya → hudud → maosh → natijalar (eng yangisi birinchi), kalit so'z bilan qidirish
- [ ] ⭐ Saqlanganlar + ulashish
- [ ] 🔔 Ish obunasi: "dasturchi, Toshkent, 5 mln+" → yangi mos e'lon chiqsa bot xabar beradi
- [ ] E'lonni yopish ("Ish topildi" tugmasi) + 30 kundan keyin qidiruvdan avtomatik chiqish
- [ ] Admin: `/stats /queue /failed /retry /pause /resume /ban /unban /addword /delword /sources`
- [ ] Kanal postida tugmalar: "📩 Murojaat" · "⭐ Saqlash" · "🔍 Boshqa ishlar" (botga deep link)

**AI (3-qism, ixtiyoriy)** — Gemini faqat regex uddalay olmaganda, kesh, fallback.

---

## BOSQICH 0 — Tayyorgarlik (qo'lda, AI'siz) ⏱ 1–2 soat

**Kompyuterga o'rnating:**
- [ ] Python 3.12 — python.org (o'rnatishda "Add to PATH" belgisini qo'ying)
- [ ] Git — git-scm.com
- [ ] VS Code — code.visualstudio.com
- [x] uv (2026-09-29, Claude o'rnatdi; Python 3.12 ni uv o'zi boshqaradi) — PowerShell'da: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- [ ] Claude Code — docs.claude.com'dagi Windows ko'rsatmasi bo'yicha, keyin `claude` bilan Pro akkauntga kiring

**Telegram:**
- [ ] Kanal yarating: nomi **Ayvona Jobs**, username **@ayvona** (bo'sh bo'lsa)
- [ ] @BotFather → `/newbot` → username **@ayvonabot** yoki **@ayvona_jobs_bot**.
      ⚠️ Bot username'i albatta `bot` bilan tugashi kerak, shuning uchun `@ayvona` faqat kanalga bo'ladi.
- [ ] Botni kanalga **admin** qiling (post joylash + tahrirlash huquqi)
- [ ] Admin chat: o'zingiz uchun yopiq guruh yarating, botni qo'shing (xatolar, backup shu yerga keladi)
- [ ] my.telegram.org → API development tools → `API_ID` va `API_HASH` oling
      (tavsiya: alohida SIM'dagi ikkinchi Telegram akkaunt bilan)
- [ ] O'z Telegram ID'ingizni biling (@userinfobot)

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

## BOSQICH 4 — Real post misollari → testlar ⏱ 1 soat · Model: `sonnet`

> Bu bosqichdan oldin `docs/POST_EXAMPLES.md` ni to'ldiring (har kanaldan 2–3 ta post).
> Chat'dagi Claude bilan shablonni kelishib olamiz, keyin bu prompt.

```text
docs/POST_EXAMPLES.md dagi har bir misolni tests/fixtures/posts/<manba>_<n>.txt ga ko'chir va
har biri uchun tests/fixtures/posts/<manba>_<n>.expected.yaml yarat: is_job, category, title, company,
salary_min, salary_max, currency, region, city, phone, username (misoldagi "kutilgan natija"ga qarab).
Keyin processing/normalize.py yoz: kichik harf, o'zbek kirill→lotin transliteratsiya, o‘ oʻ o' o` ni bitta
shaklga, emoji va ortiqcha bo'shliqlarni olib tashlash. processing/dedup.py: content_hash, fingerprint,
rapidfuzz o'xshashlik (≥90%, oxirgi 7 kun). Hozircha faqat normalize va dedup testlarini yoz;
extract testlari keyingi bosqichda (xfail bilan qoldir).
```
**Commit:** `test: real post fixtures, normalize and dedup`

---

## BOSQICH 5 — Regex extractor + kategoriya ⏱ 2–3 soat · Model: `opus`

```text
processing/extract.py va processing/categorize.py ni yoz. tests/fixtures dagi HAMMA xfail testlar
o'tishi kerak.
Extract (normalize qilingan va asl matndan):
- phone: +998 XX XXX XX XX ning barcha yozilishlari (bo'shliq, tire, qavs, 998 siz, 9 raqamli) → +998XXXXXXXXX
- username: @..., t.me/... (lekin sources.own_usernames dagilar EMAS)
- salary: "3 mln", "3 000 000", "3.5 mln so'm", "5-7 mln", "dan/gacha", "от/до", "$500", "500 у.е.",
  "kelishiladi/договорная" → salary_min/max (so'mda), currency, salary_text
- title: "Lavozim:", "Vakansiya:", "Вакансия:", "Требуется", "ishga ... kerak" va birinchi qator evristikasi
- region/city: config/regions.yaml (14 hudud + Toshkent tumanlari, lotin/kirill/rus variantlari),
  "masofaviy/online/удаленно" → is_remote
- company, schedule, requirements — kalit so'zli qatorlardan
- confidence 0..1: title + (phone yoki username) bo'lsa ≥ 0.7
Categorize: categories.yaml dagi kalit so'zlar, title'dagi moslik 3x ball, eng yuqori ball; teng yoki 0 → "boshqa".
Kategoriyalarni kengaytir: sotuvchi, haydovchi, dasturchi, o'qituvchi, oshpaz/ofitsiant, buxgalter,
operator/call-center, ombor/yuk tashuvchi, qurilish, tibbiyot, go'zallik, menejer, marketing/SMM,
dizayner, qo'riqchi, tozalik, ishlab chiqarish, kuryer, administrator, chet elda ish, boshqa.
Har biri uchun lotin, kirill va rus kalit so'zlari.
Menga qaysi misollar yaxshi ishlamaganini va nima uchunligini tushuntir.
```
**Commit:** `feat(processing): regex extractor and categorizer`

---

## BOSQICH 6 — Tozalash, shablon, rasmlar ⏱ 1–2 soat · Model: `sonnet`

```text
processing/clean.py: manba reklamasini olib tashla — sources.own_usernames, t.me havolalari (aloqa
username'dan tashqari), "obuna bo'ling / kanalimizga / подписывайтесь / reklama uchun" qatorlari,
filters.yaml dagi spam naqshlari, ortiqcha hashtaglar va bo'sh qatorlar.
processing/formatter.py: docs/POST_EXAMPLES.md oxiridagi "KELISHILGAN SHABLON" bo'yicha HTML post.
Bo'sh maydonlar chiqmasin. Hashtaglar: #kategoriya #hudud. Imzo shablon bo'yicha.
Fallback: confidence past bo'lsa — kategoriya sarlavhasi + tozalangan original matn + aloqa + imzo.
1024 belgi limiti: ARCHITECTURE 5-bo'limdagi qisqartirish tartibi. html.escape hamma user matniga.
assets/categories/ ga har kategoriya uchun joy (hozircha oddiy placeholder rasmlar generatsiya qil,
men keyin o'zimnikiga almashtiraman) + boshqa.jpg.
Test: har bir fixture uchun formatter natijasini tests/snapshots/ ga yoz, men ko'rib chiqaman.
```
**Tekshirish:** `tests/snapshots/` dagi postlarni o'qing — shunday chiqishi sizga yoqadimi?
**Commit:** `feat(processing): cleaner and post formatter`

---

## BOSQICH 7 — Worker: pipeline + publisher ⏱ 2 soat · Model: `opus`

```text
apps/worker.py ni yoz, ichida 2 ta asyncio vazifa:
1) pipeline: status=new va fetched_at 60 soniyadan eski raw_posts ni oladi (albom qismlari yig'ilishi uchun),
   grouped_id bo'yicha birlashtiradi, is_job → dedup → extract → categorize → clean → format → jobs(queued).
   Har bir raw_post statusini ARCHITECTURE 3-bo'lim bo'yicha o'zgartir. Istisno bo'lsa: status=error,
   admin'ga xabar, sikl davom etadi. no_text postlar admin chatga forward qilinadi.
2) publisher (outbox): queued/retry jobs ni navbat bilan oladi, publish_interval_seconds ga rioya qiladi.
   Yuborishdan oldin status=sending. sendPhoto (kategoriya rasmi, category_images.telegram_file_id kesh)
   + caption HTML + inline tugmalar (📩 Murojaat — username bo'lsa, 🔍 Boshqa ishlar — bot deep link).
   Muvaffaqiyat: published, channel_message_id. TelegramRetryAfter → kut. Tarmoq xatosi → exponential
   backoff (next_retry_at). HTML parse xatosi → oddiy matn bilan qayta urin. max_publish_attempts dan
   keyin failed + admin'ga xabar. Ishga tushganda "sending" da qolganlarni qayta navbatga qo'y.
   kv_store.publisher_paused = true bo'lsa joylamaydi.
Heartbeat har daqiqada. Testlar: Bot API mock bilan — xato/qayta urinish/pauza/qayta ishga tushish.
```
**Tekshirish:** avval test kanal oching (`CHANNEL_ID` ni test kanalga qo'ying) → collector + worker yoqing → postlar chiqyaptimi?
**Commit:** `feat(worker): processing pipeline and reliable publisher`

---

## BOSQICH 8 — Admin, monitoring, backup ⏱ 1–2 soat · Model: `sonnet`

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
```
**Commit:** `feat(admin): notifications, monitoring, backups, admin commands`

---

## BOSQICH 9 — Oracle serverga chiqarish (MVP JONLI!) ⏱ 2–3 soat · Model: `sonnet`

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
- Qidiruv ustasi: Kategoriya (yoki "Hammasi") → Hudud (yoki "Hammasi", "Masofaviy") → Maosh
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
bot/handlers/alerts.py: obuna yaratish (qidiruv ustasi bilan bir xil qadamlar + ixtiyoriy kalit so'z),
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
- Kunlik AI chaqiruvlari soni /stats da.
Testlar: AI mock — muvaffaqiyat, 429, timeout, noto'g'ri JSON → hammasida e'lon chiqadi.
```
**Commit:** `feat(ai): optional gemini helper with cache and fallback`

---

## BOSQICH 16 — Veb-sayt manbalari ⏱ har sayt 1–2 soat · Model: `sonnet`

```text
<SAYT_NOMI> (<URL>) uchun sources/web/<nom>.py — WebSource: httpx (User-Agent, timeout, retry) + selectolax.
Avval saytning robots.txt va foydalanish shartlarini tekshir va menga ayt — ruxsat bo'lmasa to'xtat.
Agar sayt ochiq API yoki RSS bersa, o'shani ishlat. last_seen_id = oxirgi e'lon ID/URL.
So'rovlar oralig'i kamida 10 daqiqa. HTML'ni RawItem ga aylantir (matn + asl havola).
registry.py ga "web:<nom>" tipini qo'sh. Saqlangan HTML namunasi bilan test.
```

---

## KELAJAK (startap bosqichi) — hozir qilmaymiz, faqat yo'nalish
- **Telegram Mini App** — chiroyli qidiruv interfeysi (bepul: GitHub Pages / Cloudflare Pages)
- **Veb-sayt** ayvona.uz — SEO orqali Google'dan trafik
- **PostgreSQL** — foydalanuvchilar ko'payganda (SQLAlchemy tufayli ko'chish oson)
- **Rus tili** interfeysi (`texts.py` tayyor)
- **Rezyume bo'limi** — ish qidiruvchilar profili, ish beruvchilar ko'radi
- **Daromad** (keyinroq): pullik "📌 TOP e'lon", ish beruvchi obunasi, kompaniya sahifasi
- Analitika: qaysi kategoriyada talab ko'p — ish beruvchilarga hisobot
