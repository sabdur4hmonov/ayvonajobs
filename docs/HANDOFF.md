# HANDOFF — qayerda to'xtadik (yangilangan: 2026-10-01)

Yangi sessiya yoki boshqa Windows foydalanuvchisi shu faylni birinchi o'qisin, keyin CLAUDE.md va docs/PROGRESS.md.

## Hozirgi holat
- Bosqich 0–14 kodi tayyor (Bosqich 10–14 — 2026-09-30 kechasi avtonom yozildi, Bot API mock bilan sinaldi, **haqiqiy
  botda hali tekshirilmagan**). Bosqich 9 uchun deploy hujjatlari tayyor (`deploy/SETUP_ORACLE.md`), server hali YO'Q.
- Kanal: **@ayvonajobs** · Bot: **@ayvona_jobs_bot** (username'lar `config/settings.yaml` → `branding`).
- Hozircha hamma narsa **laptopda** (collector + worker + bot, 3 ta PowerShell oynasi).
- ⚠️ **Baza hali eski versiyada (`e5a9c2f7b3d1`)**, kod esa 3 ta yangi migratsiyani kutadi: `f2b6d8a4c1e3` (qidiruv),
  `a7c3e9f1b5d8` (obunalar), `b8d4f0a2c6e9` (muddat eslatmasi). Jarayonlarni to'xtatib `uv run alembic upgrade head`
  qilmaguncha yangi worker/bot ishga tushmaydi ("Baza tayyor emas yoki eski versiyada" deydi). Hozir ishlab turgan eski
  jarayonlar xotiradagi eski kod bilan ishlashda davom etadi.
- Testlar: **783 passed**, `ruff check` toza. Hamma commit'lar GitHub'da (`git push` qilindi).

## Avtonom ish (2026-09-30 kechasi) — bajarildi
- [x] 0. Monitoring: collector o'chiq → bitta "Collector jim" (`4a03ce0`)
- [x] 1. Bosqich 10 — ommaviy bot asosi (`2876b31`)
- [x] 2. Bosqich 11 — e'lon joylash formasi (`b0bd1f1`)
- [x] 3. Bosqich 12 — qidiruv + saqlanganlar (`d645ef4`)
- [x] 4. Bosqich 13 — obunalar (`a50da11`)
- [x] 5. Bosqich 14 — yopish, muddat, to'liq statistika (oxirgi commit)
Qarorlar va sabablari — PROGRESS.md dagi har bosqich bo'limida; ertalabki buyruqlar — PROGRESS.md oxirida.

## Avtonom ish — ikkinchi tun (2026-10-01)
Qoidalar o'sha: jarayonlar ishga tushirilmaydi, haqiqiy baza/.env/session'ga tegilmaydi, haqiqiy saytlarga/Gemini'ga
so'rov yo'q (faqat mock va `tests/fixtures/web/`), har vazifa alohida commit + push.
- [x] 1. Bosqich 15 — Gemini yordamchi (`ai/`, `/ai`)
- [ ] 2. Bosqich 16 — veb-manbalar: RSS → Himalayas → Remotive → Jobicy → Remote OK → Oson Ish → hh.uz → (vacancy.gov.uz)
- [ ] 3. Bosqich 17 — o'z veb-sayti (FastAPI + Jinja2, read-only birinchi)
- [ ] 4. Deploy tayyorligi (SETUP_ORACLE.md, systemd, deploy.sh; toza klonda `uv sync --locked` + testlar)
- [ ] 5. Hujjatlarni yakunlash + Sardorga hisobot

## Keyingi ishlar (tartib bilan — bittadan)
1. [ ] **Migratsiya + qayta ishga tushirish** (PROGRESS.md oxiridagi "TUNGI ISH HISOBOTI" dagi buyruqlar).
2. [ ] Botni telefonda sinash (o'sha yerdagi ro'yxat). "Yangi foydalanuvchi" tekshiruvini **ikkinchi akkaunt** bilan
       sinang — admin e'loni tekshiruvsiz navbatga tushadi.
3. [ ] Oracle akkaunt ochish (SETUP_ORACLE.md 1–4-qadam). Region: Zurich/Stockholm/Milan/Marseille/Madrid. Visa/Mastercard.
4. [ ] Kanalni 1 kun kuzatish; yoqmagan postlarni Claude'ga tashlash.
5. [ ] Serverga chiqarish (SETUP_ORACLE.md 5–10-qadam), keyin haqiqiy ochilish.
6. [ ] Rasmlar: 19 kategoriya × 3 rasm (1280×720) → `assets/images/<kategoriya>/`.
Keyin: Bosqich 15 (Gemini, ixtiyoriy), 16 (saytlar), 17 (o'z veb-sayti — `services/` dagi mantiqni ishlatadi).

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
