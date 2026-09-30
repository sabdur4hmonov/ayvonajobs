# HANDOFF — qayerda to'xtadik (yangilangan: 2026-09-30)

Yangi sessiya yoki boshqa Windows foydalanuvchisi shu faylni birinchi o'qisin, keyin CLAUDE.md va docs/PROGRESS.md.

## Hozirgi holat
- Bosqich 0–8 tayyor (collector, worker/pipeline/publisher, admin/monitoring/backup). Bosqich 9 uchun deploy hujjatlari tayyor
  (`deploy/SETUP_ORACLE.md`), server hali YO'Q.
- Kanal: **@ayvonajobs** · Bot: **@ayvona_jobs_bot** (username'lar `config/settings.yaml` → `branding`).
- Hozircha hamma narsa **laptopda** ishlaydi (collector + worker + bot, 3 ta PowerShell oynasi), kanalga real postlar chiqyapti.
- Worker start'da navbatni hozirgi formatter bilan avtomatik qayta yasaydi (`worker.reformat_queued_on_start`).

## Avtonom ish (2026-09-30 kechasi, Sardor dam olyapti) — tartib bilan
Qoidalar: collector/worker/bot ISHGA TUSHIRILMAYDI, `data/ayvona.db` ga tegilmaydi (migratsiya faqat nusxada sinaladi),
har band alohida commit + push, qarorlar PROGRESS.md ga, savol berilmaydi.
- [x] 0. Monitoring: collector o'chiq → bitta "Collector jim" (kanal-jimlik xabarlari yo'q)
- [x] 1. Bosqich 10 — ommaviy bot asosi (menyu, deep link'lar, ⭐ saqlanganlar, middleware'lar)
- [x] 2. Bosqich 11 — e'lon joylash formasi (limitlar, filtrlar, moderatsiya, muallifga havola)
- [x] 3. Bosqich 12 — qidiruv + saqlanganlar (migratsiya `f2b6d8a4c1e3`: `jobs.search_text`, FTS5 qayta qurildi)
- [x] 4. Bosqich 13 — obunalar (migratsiya `a7c3e9f1b5d8`; yuborish worker ichida)
- [ ] 5. Bosqich 14 — yopish, muddat, to'liq statistika
Oxirida Sardorga bitta hisobot (ertalabki PowerShell buyruqlari bilan).

## Keyingi ishlar (tartib bilan — bittadan)
1. [ ] Worker'ni qayta yoqish, kanalda yangi postlar `@ayvona_jobs_bot` / `@ayvonajobs` bilan chiqayotganini tekshirish.
2. [x] `publisher.max_age_hours: 24` qoidasi (24 soatdan eski e'lon kanalga chiqmaydi, status `skipped_old`) — 2026-09-30, PROGRESS.md oxirida.
3. [ ] `git push` (oxirgi commit'lar GitHub'da ekanini tekshirish: `git log origin/main..HEAD`).
4. [ ] Oracle akkaunt ochish (SETUP_ORACLE.md 1–4-qadam). Region: Zurich/Stockholm/Milan/Marseille/Madrid. Visa/Mastercard.
5. [ ] Kanalni 1 kun kuzatish; yoqmagan postlarni Claude'ga tashlash.
6. [ ] Bosqich 10 (ommaviy bot) — ROADMAP'dagi prompt, "Mavjud kodni hisobga ol" bo'limi bilan, `/model sonnet`.
7. [ ] Serverga chiqarish (SETUP_ORACLE.md 5–10-qadam), keyin haqiqiy ochilish.
8. [ ] Rasmlar: 19 kategoriya × 3 rasm (1280×720) → `assets/images/<kategoriya>/`.
Keyin: Bosqich 11–16, oxirida 17 (o'z veb-sayti).

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
- ⚠️ Bir vaqtda ikki foydalanuvchida collector/worker/bot ISHLATMANG (bitta Telethon session va bitta BOT_TOKEN — bitta joyda).
  "Switch user" jarayonlarni to'xtatmaydi; "Sign out" to'xtatadi.
