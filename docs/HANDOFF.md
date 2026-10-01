# HANDOFF — qayerda to'xtadik (yangilangan: 2026-10-01, ikkinchi tun oxiri)

Yangi sessiya yoki boshqa Windows foydalanuvchisi shu faylni birinchi o'qisin, keyin CLAUDE.md va docs/PROGRESS.md.

## Hozirgi holat
- **Bosqich 0–17 kodi tayyor** (17 — o'qish uchun versiya). 10–17 avtonom yozilgan va mock bilan sinalgan —
  **haqiqiy Telegram / Gemini / saytlarda hali ishlatilmagan**. Server hali YO'Q (hamma narsa laptopda).
- Kanal: **@ayvonajobs** · Bot: **@ayvona_jobs_bot** (username'lar `config/settings.yaml` → `branding`).
- Jarayonlar: `collector`, `worker`, `bot` (+ ixtiyoriy `web` — sayt, `127.0.0.1:8080`).
- ⚠️ **Baza eski versiyada (`e5a9c2f7b3d1`)** — 3 ta yangi migratsiya kutyapti: `f2b6d8a4c1e3` (qidiruv),
  `a7c3e9f1b5d8` (obunalar), `b8d4f0a2c6e9` (muddat eslatmasi). Jarayonlarni to'xtatib, backup bilan
  `uv run alembic upgrade head` qilinmaguncha yangi kod ishga tushmaydi (PROGRESS.md oxirida buyruqlar).
- Testlar: **837 passed**, `ruff check` toza; toza klonda `uv sync --locked` ham yashil. Hamma commit'lar GitHub'da.

## Avtonom ish — birinchi tun (2026-09-30)
Monitoring (`4a03ce0`), Bosqich 10 (`2876b31`), 11 (`b0bd1f1`), 12 (`d645ef4`), 13 (`a50da11`), 14 (`ae3f604`).

## Avtonom ish — ikkinchi tun (2026-10-01)
- [x] Bosqich 15 — Gemini yordamchi, `/ai` (`8fe9206`)
- [x] Bosqich 16 — veb-manbalar: RSS, Himalayas, Remotive, Jobicy, Remote OK, Oson Ish, hh.uz (`cb56f15`);
      vacancy.gov.uz — qo'shilmadi. Hammasi standart o'chiq — `/addsource web:<nom>` / `rss:<URL>`.
- [x] Bosqich 17 — o'z veb-sayti, o'qish uchun (`e63f7eb`)
- [x] Deploy tayyorligi (`80c5c94`) + hujjatlar (oxirgi commit)

## Keyingi ishlar (tartib bilan — bittadan)
1. [ ] **Migratsiya + qayta ishga tushirish** — PROGRESS.md oxiridagi "IKKINCHI TUN HISOBOTI".
2. [ ] Botni telefonda sinash (birinchi tun ro'yxati + `/ai`, `/addsource web:himalayas`).
3. [ ] (Ixtiyoriy) Gemini kaliti → `.env` → worker'ni qayta yoqish → `/ai`.
4. [ ] (Ixtiyoriy) hh.uz ilovasini ro'yxatdan o'tkazish (dev.hh.ru) → token `.env` ga.
5. [ ] Oracle akkaunt + server (SETUP_ORACLE.md 1–10, keyin 10a sayt uchun).
6. [ ] Kanalni 1 kun kuzatish; yoqmagan postlarni Claude'ga tashlash.
7. [ ] Rasmlar: 19 kategoriya × 3 rasm (1280×720) → `assets/images/<kategoriya>/`.
8. [ ] Bosqich 17 davomi: saytdan e'lon joylash + Telegram Login Widget (server va domen bo'lgach).

## Ikkita Windows foydalanuvchisi haqida
Loyiha `D:\Coding projects\ayvona` da (ikkala foydalanuvchiga umumiy). Foydalanuvchiga bog'liq narsalar ko'chmaydi:
- **git**: `git config --global user.name "sabdur4hmonov"` va `user.email "s.abdur4hmonov@gmail.com"` — har foydalanuvchida alohida.
  Agar "dubious ownership" chiqsa: `git config --global --add safe.directory "D:/Coding projects/ayvona"`.
- **uv va Python** har foydalanuvchiga alohida o'rnatiladi (`winget install -e --id Python.Python.3.12`, uv: https://astral.sh/uv).
  `.venv` boshqa foydalanuvchining Python yo'lini eslab qoladi — yangi foydalanuvchida: `uv sync` (kerak bo'lsa `.venv` ni qayta yaratish).
- **Claude Code** login va suhbat tarixi foydalanuvchiga bog'liq. Xotira loyiha ichida: CLAUDE.md, docs/PROGRESS.md, shu fayl.
- **GitHub push** uchun har foydalanuvchida GitHub'ga kirish (Git Credential Manager) alohida bo'ladi.
- `.env`, `data/ayvona.session`, `data/ayvona.db` git'da yo'q, lekin D: diskda — ikkala foydalanuvchi ko'radi.
  Fayl ruxsatlari to'sqinlik qilsa: papkaga ikkinchi foydalanuvchiga Full control bering.
  (Hozir `.pytest_cache` ga yozish ruxsati yo'q — testlarga ta'sir qilmaydi, faqat ogohlantirish.)
- ⚠️ Bir vaqtda ikki foydalanuvchida collector/worker/bot ISHLATMANG (bitta Telethon session va bitta BOT_TOKEN — bitta joyda).
  "Switch user" jarayonlarni to'xtatmaydi; "Sign out" to'xtatadi.
