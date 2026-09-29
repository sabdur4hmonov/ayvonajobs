# Ayvona Jobs

O'zbekiston uchun Telegram ish e'lonlari tizimi:

1. **Aggregator** — manba Telegram kanallardan ish e'lonlarini o'qiydi, dublikatlarni olib tashlaydi,
   kategoriyaga ajratadi, chiroyli qilib **@ayvona** kanaliga avtomatik joylaydi.
2. **@ayvonabot** — ommaviy bot: e'lon joylash, ish qidirish, saqlanganlar, obunalar.

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
uv run python -m ayvona.apps.collector    # kanallarni o'qiydi (to'xtatish: Ctrl+C)
```

Keyingi bosqichlarda: `uv run python -m ayvona.apps.worker` va `uv run python -m ayvona.apps.bot`.

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
| `src/ayvona/bot/` | @ayvonabot (aiogram) |
| `src/ayvona/services/` | Obunalar, eskirish, backup, statistika, admin xabarlari |
| `src/ayvona/ai/` | Gemini (keyin, ixtiyoriy) |
| `src/ayvona/apps/` | Ishga tushadigan jarayonlar: collector, worker, bot |
| `config/` | Sozlamalar (maxfiy emas): manbalar, kategoriyalar, hududlar, filtrlar |
| `migrations/` | Alembic migratsiyalari (baza tuzilmasining versiyalari) |
| `assets/categories/` | Har kategoriya uchun rasm |
| `scripts/` | Yordamchi skriptlar (Telegram login) |
| `tests/` | Testlar |
| `deploy/` | Serverga chiqarish (Oracle, systemd) |
| `data/` | **git'ga tushmaydi**: baza, session, loglar, backup'lar |
