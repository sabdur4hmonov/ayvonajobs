# Ayvona Jobs

O'zbekiston uchun Telegram ish e'lonlari tizimi:

1. **Aggregator** — manba Telegram kanallardan ish e'lonlarini o'qiydi, dublikatlarni olib tashlaydi,
   kategoriyaga ajratadi, chiroyli qilib **@ayvonajobs** kanaliga avtomatik joylaydi.
2. **@ayvona_jobs_bot** — ommaviy bot: e'lon joylash, ish qidirish, saqlanganlar, obunalar.

To'liq reja: [docs/ROADMAP.md](docs/ROADMAP.md) · Arxitektura: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
Nima qilingani: [docs/PROGRESS.md](docs/PROGRESS.md)

---

## 1. O'rnatish (Windows, PowerShell)

Kerak: **Git** va **uv** (uv Python 3.12 ni o'zi yuklab oladi).

```powershell
# uv o'rnatilmagan bo'lsa (bir marta):
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Terminalni yopib qayta oching, keyin:
uv --version
```

Loyihani tayyorlash:

```powershell
cd "D:\Coding projects\ayvona"
uv sync                               # kutubxonalarni o'rnatadi (.venv papkasi paydo bo'ladi)
Copy-Item .env.example .env           # maxfiy sozlamalar faylini yaratadi
notepad .env                          # API_ID, API_HASH, BOT_TOKEN ... ni to'ldiring
```

## 2. Baza

```powershell
uv run alembic upgrade head           # data/ayvona.db ni yaratadi / yangilaydi
```

Kod yangilanganda (yangi migratsiya qo'shilganda) shu buyruqni qayta ishga tushiring.

## 3. Telegram'ga kirish (bir marta)

```powershell
uv run python scripts/login_telethon.py
```

Telefon raqam, Telegram yuborgan kod va (bo'lsa) 2FA parolni so'raydi.
Natijada `data/ayvona.session` paydo bo'ladi. **Bu fayl = akkauntingizga to'liq kirish. Hech kimga bermang.**

## 4. Kanal qo'shish

`config/settings.yaml` ni oching va `sources: []` o'rniga yozing:

```yaml
sources:
  - type: telegram
    identifier: "@kanal_nomi"
    own_usernames: ["@kanal_nomi"]
```

## 5. Ishga tushirish

```powershell
uv run python -m ayvona.apps.collector --once   # bitta aylanish qilib chiqadi (tekshirish uchun)
uv run python -m ayvona.apps.collector          # doimiy ishlaydi (to'xtatish: Ctrl+C)
uv run python scripts/show_status.py            # bazada nima bor: manbalar, heartbeat, oxirgi postlar
```

**Worker** (Bosqich 7) — yangi postlarni qayta ishlaydi va kanalga joylaydi:
```powershell
uv run python -m ayvona.apps.worker --no-publish   # faqat qayta ishlash, kanalga hech narsa ketmaydi
uv run python -m ayvona.apps.worker --once         # tayyorlarini ishlab + vaqti kelganlarini joylab, chiqadi
uv run python -m ayvona.apps.worker                # doimiy ishlaydi (to'xtatish: Ctrl+C)
```
`BOT_TOKEN` / `CHANNEL_ID` bo'lmasa worker yiqilmaydi: e'lonlar navbatda (`queued`) kutadi.
⚠️ Birinchi ishga tushishda bazadagi hamma eski postlar `skipped_backfill` bo'ladi (kanalga chiqmaydi).
Sinovni albatta **test kanal**da qiling: `.env` da `CHANNEL_ID=@sizning_test_kanalingiz`.

**Bot** (Bosqich 8) — hozircha faqat admin buyruqlari (`/help` ro'yxatni ko'rsatadi):
```powershell
uv run python -m ayvona.apps.bot                 # BOT_TOKEN va ADMIN_IDS kerak
uv run python scripts/find_chat_ids.py           # CHANNEL_ID / ADMIN_CHAT_ID / ADMIN_IDS ni topish
uv run python scripts/backup_now.py --send       # bazaning nusxasi hozir (odatda har kuni 03:00)
```
Manbalar endi **bazada** (bot: `/sources`, `/addsource`); `config/settings.yaml` faqat boshlang'ich ro'yxat.

**Post rasmlari va ko'rinishi** (Bosqich 6):
```powershell
uv run python scripts/make_placeholder_images.py   # bo'sh rasm papkalariga vaqtinchalik rasmlar (bir marta)
uv run python scripts/preview_posts.py             # bazadagi e'lonlar kanalda qanday chiqadi -> data\preview.html
start data\preview.html                            # brauzerda ochish
```
Haqiqiy rasmlarni `assets\images\<kategoriya>\<kasb>\` ga qo'ying (docs/IMAGES.md) — vaqtinchaliklari o'zi ishlatilmay qoladi.

## 5a. Gemini yordamchi (ixtiyoriy)

`.env` ga `GEMINI_API_KEY=...` (aistudio.google.com, bepul) qo'ysangiz, worker ishonchi past va ruscha/inglizcha
e'lonlarni Gemini bilan o'zbek lotinga o'giradi. Kalit bo'lmasa — hammasi avvalgidek regex bilan ishlaydi.
Botda admin: `/ai` (holat, bugungi so'rovlar, yoqish/o'chirish).

> ⚠️ **Google shartlari:** bepul limitlar loyiha (project) bo'yicha hisoblanadi. Limitni chetlab o'tish uchun bir necha
> akkaunt/kalit ochish Google shartlariga zid bo'lishi va akkauntlar bloklanishiga olib kelishi mumkin. Shuning uchun
> `GEMINI_ALLOW_KEY_ROTATION=false` (standart) — faqat bitta kalit ishlatiladi. Bizning hajmga bitta kalit + kesh yetadi.

## 5b. Tasdiqlash, ustuvorlik, Loyihalar, rasmlar (2026-10-07)

- **Tasdiqlash:** foydalanuvchi e'loni adminga «✅ Tasdiqlash / ❌ Rad etish» bilan keladi; tasdiqlansa e'lon **o'sha
  zahoti** kanalga chiqadi (navbatsiz, ikki marta chiqmaydi). Admin **faqat** shu so'rovni oladi — xatolar, monitoring,
  backup logda (`journalctl`); eskisini qaytarish: `.env` da `ADMIN_EXTRA_NOTIFICATIONS=true`.
- **Muddat:** forma «E'lon necha kun faol tursin?» (3 / 7 / 14 / 30) deb so'raydi; tugashiga yaqin «Uzaytirasizmi?» keladi.
- **Ustuvorlik:** ofis / mutaxassis kasblari va yuqori maosh — 1-daraja (birinchi chiqadi), oddiy ishchi ishlari — 3-daraja
  (oxirida, kuniga chegarali). Qoidalar `config/settings.yaml → priority:`; admin: `/why <id>`, `/queue`;
  eskilarini baholash: `uv run python scripts/backfill_priority.py [--dry-run | --all]`.
- **🧩 Loyihalar:** bir martalik pullik ishlar (bot, sayt, dizayn, tarjima). Forma avval turini so'raydi (Ish / Loyiha);
  kanalda `#loyiha` bilan, botda «🧩 Loyihalar» menyusida.
- **Rasmlar:** admin `/images review` — rasm o'rinlarini birma-bir ko'rib, taklifni tasdiqlaydi (eski rasm nusxasi
  saqlanadi). Manba: Pexels / Unsplash / Pixabay (kaliti `.env` da bo'lsa) yoki o'zimiz chizgan original rasm.

## 6. Dasturchi uchun

```powershell
uv run pytest                     # testlar
uv run ruff check .               # kod tekshiruvi
uv run ruff format .              # kodni formatlash
```

## Papkalar

| Papka | Nima uchun |
|---|---|
| `src/ayvona/config.py` | `.env` va `config/*.yaml` dan sozlamalarni o'qiydi |
| `src/ayvona/db/` | Baza: modellar (jadvallar), ulanish, repository'lar (so'rovlar) |
| `src/ayvona/sources/` | Manbalar: Telegram kanal (keyin veb-saytlar) |
| `src/ayvona/processing/` | E'lonni tahlil qilish: normalize, dedup, extract, kategoriya, format |
| `src/ayvona/publisher/` | Navbatdagi e'lonlarni kanalga joylash |
| `src/ayvona/bot/` | @ayvona_jobs_bot (aiogram) |
| `src/ayvona/services/` | Obunalar, eskirish, backup, statistika, admin xabarlari |
| `src/ayvona/ai/` | Gemini (keyin, ixtiyoriy) |
| `src/ayvona/apps/` | Ishga tushadigan jarayonlar: collector, worker, bot |
| `config/` | Sozlamalar (maxfiy emas): manbalar, kategoriyalar, hududlar, filtrlar |
| `migrations/` | Alembic migratsiyalari (baza tuzilmasining versiyalari) |
| `assets/images/` | Post rasmlari: `<kategoriya>/<kasb>/`, navbat bilan (docs/IMAGES.md) |
| `scripts/` | Yordamchi skriptlar (Telegram login, hisobotlar, rasmlar, postlar ko'rinishi) |
| `tests/` | Testlar |
| `deploy/` | Serverga chiqarish (Oracle, systemd) |
| `data/` | **git'ga tushmaydi**: baza, session, loglar, backup'lar |
