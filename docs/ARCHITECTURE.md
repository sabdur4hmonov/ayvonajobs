# Ayvona Jobs — Arxitektura

Bu fayl tizim qanday qurilganini tushuntiradi: qaysi qism nima qiladi, ma'lumotlar qayerda saqlanadi va
nega hech bir e'lon yo'qolmaydi.

---

## 1. Umumiy sxema

```mermaid
flowchart LR
    subgraph Manbalar
      TG[Telegram kanallar]
      WEB[Veb-saytlar - keyin]
    end
    subgraph Collector
      C[collector.py<br/>Telethon, har 60-120s]
    end
    subgraph Worker
      P[pipeline<br/>classify → extract → dedup → clean → format]
      PUB[publisher<br/>navbatdan kanalga]
      AL[alerts / expiry / backup / stats]
    end
    subgraph Bot
      B[@ayvona_jobs_bot<br/>aiogram]
    end
    DB[(SQLite<br/>ayvona.db)]
    CH[[Kanal @ayvonajobs]]
    ADM[Admin chat]

    TG --> C --> DB
    WEB -.-> C
    DB --> P --> DB
    B -- user e'loni --> DB
    DB --> PUB --> CH
    PUB -- xato --> ADM
    AL --> ADM
    B -- qidiruv/saqlash/obuna --> DB
    AL -- mos ish topildi --> B
```

**3 ta alohida jarayon (process)** ishlaydi. Biri yiqilsa, qolganlari ishlashda davom etadi,
systemd uni avtomatik qayta yoqadi:

| Jarayon | Vazifasi | Kutubxona |
|---|---|---|
| `collector` | Manbalardan yangi postlarni olib, **xom holda** bazaga yozadi | Telethon |
| `worker` | Xom postlarni qayta ishlaydi, navbatdagi e'lonlarni kanalga joylaydi, obunachilarga xabar, eskirgan e'lonlar, backup | aiogram (Bot API) |
| `bot` | Ommaviy bot: e'lon joylash, qidiruv, saqlanganlar, obunalar, admin buyruqlari | aiogram |

Hammasi bitta SQLite bazani ishlatadi (WAL rejimi — bir vaqtda o'qish/yozish xavfsiz).

---

## 2. "Hech bir e'lon yo'qolmasin" — qanday ta'minlanadi

1. **Avval saqla, keyin ishla.** Collector postni o'qishi bilan `raw_posts` jadvaliga yozadi. Qayta ishlash
   keyin bo'ladi. Worker yiqilsa ham post bazada turibdi.
2. **Oxirgi ko'rilgan ID.** Har bir manba uchun `sources.last_seen_id` saqlanadi. Postlarni yozish va
   `last_seen_id` ni yangilash **bitta tranzaksiyada** — ya'ni yoki ikkalasi ham bo'ladi, yoki hech biri.
3. **Polling, event emas.** Collector har 60–120 soniyada `iter_messages(min_id=last_seen_id)` bilan so'raydi.
   Telethon eventlari ba'zan tushib qoladi; polling esa kompyuter o'chib yonsa ham qolgan hamma postlarni oladi.
4. **Status zanjiri.** Har bir bosqich bazadagi statusni o'zgartiradi. Qayta ishga tushganda worker
   "tugallanmagan" statusdagi hamma narsani davom ettiradi.
5. **Outbox navbati.** Kanalga joylash `jobs` jadvalidagi navbatdan bo'ladi. Xato bo'lsa — qayta urinish
   (1 daq, 5 daq, 15 daq, 1 soat...). N marta xato bo'lsa `failed` + admin'ga xabar + `/retry` buyrug'i.
6. **At-least-once.** Yuborish oldidan status `sending` qilinadi. Agar yuborish paytida jarayon o'chib qolsa,
   qayta yonganda qayta yuboradi (kamdan-kam dublikat > yo'qolgan e'lon).
7. **Heartbeat.** Har bir jarayon har daqiqada "tirikman" deb yozadi. 10 daqiqa jim bo'lsa — admin'ga ogohlantirish.
8. **Kunlik backup.** Har kuni baza nusxasi olinadi va admin chatga fayl sifatida yuboriladi (bepul, Telegram'da saqlanadi).
9. **Rasmsiz / matnsiz postlar.** Faqat rasmdan iborat postlar ham bazaga yoziladi (`no_text` status) va
   admin'ga yuboriladi — jim tashlab yuborilmaydi.

---

## 3. Status zanjirlari

**raw_posts.status**
```
new → processing → done              (job yaratildi yoki to'liqroq nusxa sifatida job'ni oldi; raw_posts.job_id)
                 → duplicate         (oldin chiqqan; raw_posts.duplicate_of)
                 → not_job           (reklama, maslahat, yangilik — e'lon emas)
                 → resume            (ish qidiruvchining rezyumesi)
                 → closed            (vakansiya yopilgan / ariza muddati o'tgan)
                 → opportunity       (grant, kurs, tadbir, haq to'lanmaydigan amaliyot)
                 → suspicious        (firibgarlik belgilari — admin'ga)
                 → no_text           (faqat rasm — admin'ga)
                 → no_contact        (e'lon, lekin telefon / @username / email / havola yo'q — chiqmaydi)
                 → low_quality       (e'lon, lekin lavozim ham, maosh ham topilmadi — chiqmaydi, admin hisobotida)
                 → error             (kod xatosi — admin'ga; qayta ishlash uchun bazada status='new' qilinadi)
new → skipped_backfill               (worker birinchi yonguncha bo'lgan postlar va yangi kanal tarixi — chiqmaydi,
                                      publisher.publish_backfill: true bo'lmasa)
```
Sababi (`not_job` ... `low_quality`) `raw_posts.error` ustuniga yoziladi (masalan `job:kerak, ad:chegirma`).

**jobs.status**
```
pending_review → queued          (faqat user e'lonlari: scam so'z / yangi foydalanuvchi / moderation: all;
               → rejected         admin [✅]/[❌]/[🚫] tugmasi — bot/moderation.py)
                                 (ban/spam/dublikat user e'loni bazaga umuman yozilmaydi)
queued → sending → published → closed / expired
               ↘ retry (next_retry_at) → sending
               ↘ failed (admin: /retry)
queued / retry → skipped_old     (manba posti publisher.max_age_hours dan eski — kanalga chiqmaydi, bazada qoladi)
rejected (filtr yoki admin rad etdi)
```

---

## 4. Ma'lumotlar bazasi modellari (jadvallar)

> "Model" = bazadagi jadvalning Python'dagi ko'rinishi (SQLAlchemy). Quyida hammasi.

### Aggregator uchun
**sources** — manbalar
| maydon | turi | izoh |
|---|---|---|
| id | int PK | |
| type | str | `telegram` / `web` |
| identifier | str unique | `@kanal_nomi` yoki URL |
| title | str | |
| enabled | bool | |
| last_seen_id | str/int | oxirgi ko'rilgan post ID (web uchun URL/ID) |
| last_checked_at, last_success_at | datetime | |
| error_count, last_error | int, text | |
| own_usernames | json | shu kanalning o'z @username/havolalari — tozalashda olib tashlanadi |

**raw_posts** — manbadan kelgan xom post (hech qachon o'chirilmaydi, 90 kundan keyin arxivlanadi)
| maydon | izoh |
|---|---|
| id, source_id → sources | |
| external_id | kanal ichidagi post ID; **UNIQUE(source_id, external_id)** |
| grouped_id | albom (bir nechta rasm) bo'lsa |
| text, has_media, media_type | |
| posted_at, fetched_at | |
| status, error | yuqoridagi zanjir |
| content_hash | normallashtirilgan matn SHA-256 |

**jobs** — tayyor e'lon (aggregatordan ham, user'dan ham)
| maydon | izoh |
|---|---|
| id | |
| origin | `aggregator` / `user` |
| raw_post_id → raw_posts (null bo'lishi mumkin), author_id → users (null bo'lishi mumkin) | |
| title, company, category, profession | lavozim, kompaniya, kategoriya va kasb kodi (`config/categories.yaml`) |
| salary_min, salary_max, currency, salary_period, salary_text | son (asl valyutada; aql-hush tekshiruvidan o'tmasa bo'sh), davr (month/week/day/hour) + asl matn |
| region, city, is_remote | |
| schedule, requirements, description | |
| contact_phone, contact_username | |
| parse_method, confidence | `regex` / `fallback` / `gemini` / `form`, 0–1 |
| formatted_text | kanalga chiqadigan tayyor HTML |
| fingerprint | dublikat uchun (lavozim + telefon + qisqa matn) |
| search_text | so'z bilan qidiruv uchun o'girilgan matn (jobs_fts shu ustunda) |
| status, attempts, next_retry_at, last_error | outbox navbati |
| channel_message_id, published_at, expires_at, closed_at | |

### Ommaviy bot uchun
**users** — `tg_id` PK, username, full_name, phone, lang, is_banned, trust_level (0 yangi / 1 ishonchli / 2 admin),
created_at, last_active_at

**favorites** — user_id, job_id, created_at · UNIQUE(user_id, job_id)

**subscriptions** (ish obunasi / alert) — id, user_id, category, profession, region, min_salary, keyword, is_active, created_at

**alert_deliveries** — subscription_id, job_id, sent_at · UNIQUE(subscription_id, job_id) → bir xabar ikki marta ketmaydi

**search_logs** — user_id, filtrlar (json), natija soni, created_at (statistika va "nimani qidirishyapti" uchun)

### Umumiy
**images** — category, profession, file_path, file_hash, telegram_file_id, times_used, last_used_at (navbat bilan tanlash; file_id kesh — docs/IMAGES.md)

**filter_words** — word, kind (`ban` / `spam` / `scam`), added_by

**ai_cache** — text_hash PK, model, response_json, created_at

**kv_store** — key, value (masalan: `publisher_paused`, `usd_rate`, heartbeat'lar)

**jobs_fts** — FTS5 virtual jadval, faqat `jobs.search_text` ustunini indekslaydi (fold: kirill→lotin, kichik harf,
apostrofsiz — migratsiya `f2b6d8a4c1e3`), triggerlar bilan sinxron. So'rov ham shunday o'giriladi (services/search.py)

---

## 5. Qayta ishlash konveyeri (pipeline)

```
xom matn (albom qismlari birlashtirilgan)
  → backfill?   : is_backfill va publish_backfill=false → skipped_backfill
  → normalize   : kichik harf, kirill→lotin, o‘/g‘ bir xil, emoji/ortiqcha bo'shliq olib tashlash
  → classify    : e'lonmi yoki reklama/rezyume/yopilgan/imkoniyat/shubhali (config/filters.yaml)
  → extract     : regex — lavozim, kompaniya, maosh, manzil, ish vaqti, talablar, telefon, @username
                  (aloqa yo'q → no_contact; lavozim ham, maosh ham yo'q → low_quality)
  → confidence  : lavozim + aloqa topildi → yuqori; < 0.7 → fallback shablon (keyin: Gemini)
  → categorize  : categories.yaml dagi kalit so'zlar bo'yicha ball; lavozimdagi so'z 3x og'irroq; topilmasa "boshqa"
  → dedup       : 1) UNIQUE(source, external_id)  2) content_hash  3) fingerprint  4) rapidfuzz ≥ 90% (oxirgi 14 kun)
  → clean       : manba kanal reklamasi, havolalar, "obuna bo'ling", hashtaglar olib tashlanadi (aloqa @username qoladi!)
  → format      : shablon (HTML) + #kategoriya #hudud hashtaglari + imzo; ≤1024 belgi (rasm ostidagi matn limiti)
  → jobs (queued, next_retry_at = e'lon vaqti + hold_minutes — yig'ish oynasi)
```
**Nega extract dedup'dan oldin:** dedup'ga extract topgan lavozim kerak, va dedup indeksiga faqat kanalga chiqadigan
e'lonlar kiradi — aks holda oldin kelgan ALOQASIZ nusxa keyingi aloqali nusxani "dublikat" qilib qo'yardi.

**1024 belgi muammosi:** Telegram rasm ostidagi matnni 1024 belgi bilan cheklaydi. Qisqartirish tartibi:
avval "Tafsilotlar" qismi qisqartiriladi → keyin "Talablar". **Aloqa, lavozim, maosh, manzil hech qachon kesilmaydi.**

---

## 6. Manbalarni kengaytirish

```python
class BaseSource(ABC):
    type: str
    async def fetch_new(self, since: str | None) -> FetchResult: ...  # items + yangi kursor
```
- `TelegramSource` — hozir.
- `WebSource` (masalan `HhUzSource`, `OlxSource`) — keyin: httpx + selectolax, saytning `robots.txt` va
  qoidalariga rioya qilish, sekin so'rovlar (har bir sayt uchun 5–15 daqiqa).
- `registry.py` config'dagi `type` bo'yicha kerakli klassni tanlaydi. Pipeline o'zgarmaydi.
- **Manbalar ro'yxati bazada saqlanadi** (`sources` jadvali). `settings.yaml` — faqat boshlang'ich ro'yxat.
  Admin botda `/addsource` va `/sources` orqali kanal qo'shadi/o'chiradi, collector har siklda ro'yxatni
  bazadan o'qiydi (restart kerak emas). Yangi **sayt** turini qo'shish uchun esa baribir parser kodi kerak.

---

## 7. Gemini (keyingi bosqich)

- Faqat `confidence < 0.6` bo'lgan postlar uchun chaqiriladi.
- Yuborishdan oldin telefon va @username'lar yashiriladi (`[PHONE]`) — ularni regex baribir yaxshi topadi.
- Javob JSON sxema bo'yicha olinadi, `ai_cache` ga yoziladi (bir xil matn qayta yuborilmaydi).
- Circuit breaker: 429 / xato → shu kalit bugun uchun "charchagan" → darhol regex fallback. E'lon baribir chiqadi.
- Bir necha kalit: `GEMINI_API_KEYS` ro'yxati, lekin `GEMINI_ALLOW_KEY_ROTATION=false` (standart holatda o'chiq).
  ⚠️ Google limitlari **loyiha (project) bo'yicha** hisoblanadi. Limitni chetlab o'tish uchun bir necha akkaunt
  ochish Google shartlariga zid bo'lishi va ikkala akkauntning bloklanishiga olib kelishi mumkin.
  Tavsiya: bitta kalit + kesh + fallback — bizning hajm uchun yetarli.

---

## 8. Xavfsizlik va Telegram akkaunt

- Telethon **sizning Telegram akkauntingiz** nomidan ishlaydi. Tavsiya: alohida SIM bilan **ikkinchi akkaunt**.
  Faqat o'qiydi, juda tez-tez so'ramaydi → xavf past.
- `*.session` fayli = akkauntingizga to'liq kirish. Hech qachon git'ga, chatga, hech kimga bermang.
- Bot token, API_HASH faqat `.env` da. GitHub repo **private** bo'lgani ma'qul.
- Bot kanalga **admin** qilib qo'shiladi (faqat "post joylash" va "tahrirlash" huquqi).

---

## 9. Hosting (Oracle Always Free)

- 2026-yil holatiga ko'ra Ampere A1 (ARM) bepul limiti **2 OCPU / 12 GB RAM** gacha qisqartirilgan; AMD micro
  (1/8 OCPU, 1 GB) ham bor. Bizga 1 OCPU / 2–4 GB ham yetadi.
- Oracle uzoq vaqt "bo'sh" turgan Always Free serverlarni qaytarib olishi mumkin — shuning uchun kunlik backup
  admin chatga yuboriladi; server yo'qolsa, 15 daqiqada yangisiga ko'chiriladi (`deploy/SETUP_ORACLE.md`).
- Ro'yxatdan o'tishda karta tekshiruvi so'raladi (pul yechilmaydi). Ba'zi hududlarda "Out of capacity" bo'ladi —
  keyinroq qayta urinish kerak.
- Ishga tushirish: Ubuntu + uv + 3 ta systemd service (`Restart=always`).
