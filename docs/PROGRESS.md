# Progress log

Claude Code har bir bosqichdan keyin shu yerga yozadi: nima qilindi, qanday ishga tushiriladi, ma'lum muammolar.

| Sana | Bosqich | Nima qilindi | Eslatma |
|---|---|---|---|
| 2026-09-29 | Reja | CLAUDE.md, ARCHITECTURE, ROADMAP, POST_EXAMPLES yaratildi | Keyingi qadam: Bosqich 0 (tayyorgarlik) |
| 2026-09-29 | 1 — Skelet | pyproject (uv, src layout), papkalar, `config.py`, `config/*.yaml`, `.env.example`, `.gitignore`, loguru, README, ruff, testlar | 6 test ✅, ruff ✅ |

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

---

## Sardor uchun

Kompyuter yoniga qaytganingizda qilishingiz kerak bo'lgan narsalar (batafsil — fayl oxirida):

- [ ] **Git muallifini sozlang** (bir marta):
      `git config --global user.name "Sardor"` va `git config --global user.email "sizning@email"`
- [ ] Yangi PowerShell oynasini oching va `uv --version` ishlashini tekshiring (uv PATH'ga qo'shildi).
