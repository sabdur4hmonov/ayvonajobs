# Bosqich 9 tayyorgarligi — qisqa xulosa (2026-09-29)

> Bu fayl PROGRESS.md o'rniga yozildi (parallel sessiya o'sha paytda PROGRESS/ROADMAP ustida ishlayotgan edi).
> Bosqich 9 tugagach, shu yerdagi asosiy gaplarni PROGRESS.md ga ko'chirib, bu faylni o'chirsa bo'ladi.

## Nima qilindi
- `deploy/SETUP_ORACLE.md` — o'zbekcha, qadamma-qadam qo'llanma (0–14): Oracle akkaunt (karta, MFA,
  Home Region), SSH kalit (PowerShell), A1 1 OCPU / 6 GB instance, "Out of capacity", ulanish, apt/NTP/vaqt zonasi,
  firewall, `ayvona` foydalanuvchi, uv, deploy key + clone, .env/session/baza'ni scp bilan ko'chirish, alembic,
  systemd, journalctl, yangilash, backup'dan tiklash, muammolar jadvali.
- `deploy/systemd/ayvona-{collector,worker,bot}.service` — `User=ayvona`, `Restart=always`, `RestartSec=10`,
  `StartLimitIntervalSec=0`, `uv run --no-sync python -m ayvona.apps.<nom>`, yengil himoya (`ProtectSystem=full`, ...).
- `scripts/deploy.sh` — git pull → yoqilgan servislarni stop → baza zaxirasi (`data/backups/deploy/`, oxirgi 5) →
  `uv sync --locked` → `alembic upgrade head` → o'zgargan unit fayllarni `/etc/systemd/system/` ga → start + holat.
  Ishga tushirish: `sudo bash /home/ayvona/ayvona/scripts/deploy.sh`. Stub'lar bilan (Git Bash'da) sinaldi: oddiy
  yo'l, zaxiralarni tozalash va xato yo'li ishladi. Haqiqiy Ubuntu'da hali sinalmagan.
- Oracle qoidalari 2026-09-29 da tekshirildi: A1 Always Free endi **2 OCPU / 12 GB** (2026-06-15 dan; eski 4/24).
  Idle reclamation: 7 kun CPU p95 < 20% **va** tarmoq < 20% **va** xotira < 20% (A1) bo'lsa qaytarib olinishi mumkin.

## Muhim qarorlar
- Uchala servis birga enable qilinadi (Bosqich 7/8 tayyor: 461967f, c08c7df). Faqat `BOT_TOKEN` bo'sh bo'lsa
  bot yoqilmaydi (aks holda har 10 soniyada qayta yonadi); worker tokensiz ham ishlaydi.
- Uchala jarayon baza eng oxirgi Alembic head'da bo'lmasa ishga tushmaydi — `deploy.sh` restart'dan oldin
  `alembic upgrade head` qiladi.
- `deploy.sh` faqat enable qilingan servislarni to'xtatadi/yoqadi (masalan, token yo'qligi sababli yoqilmagan bot'ga tegmaydi).
- Servislar `uv run --no-sync`: kutubxonalarni faqat `deploy.sh` o'rnatadi (3 servis bir vaqtda sync qilmasin).
- Deploy paytida servislar to'xtatiladi (migratsiya jonli bazada ishlamasin). Collector cursor'dan davom etadi.
- Deploy zaxiralari `data/backups/deploy/` da. Kunlik backup'lar — `data/backups/ayvona_YYYY-MM-DD.db` (worker,
  oxirgi 7); ularning tozalovchisi faqat `^ayvona_\d{4}-\d{2}-\d{2}\.db$` ni o'chiradi, `deploy/` ga tegmaydi.
- Firewall: hech qanday port ochilmaydi (bot long polling). `ufw` ishlatilmaydi (Oracle iptables bilan to'qnashadi).
- Server vaqt zonasi `Asia/Tashkent` (faqat log o'qish qulayligi uchun; kod UTC da ishlaydi).

## Sardor nima qilishi kerak
1. Oracle akkaunt oching (SETUP_ORACLE.md, 1-qadam) — hozirdan boshlasa bo'ladi, kod tayyor bo'lishini kutmasdan.
2. Instance yarating (2–4-qadamlar). "Out of capacity" bo'lsa — bir necha kun qayta urinish normal.
3. Bu fayllarni commit qiling (faqat o'z yo'llari bilan, `git add .` emas):
   ```powershell
   git add deploy/ scripts/deploy.sh
   git commit -m "chore(deploy): oracle vps setup and systemd units"
   git push
   ```
4. Bosqich 7 va 8 commit qilingan — `git push` qilib, 5–10-qadamlarni bajarish mumkin (server sozlash, clone, scp, systemd).
5. Birinchi hafta: Oracle **Metrics** da Memory Utilization'ni kuzating (14-bo'lim) — idle reclamation xavfi.

## Ochiq savollar / keyin hal qilinadi
- **Idle reclamation:** 3 ta jarayon 6 GB ning 20% (1.2 GB) idan kam ishlatishi ehtimoli katta. 1 hafta o'lchab,
  kerak bo'lsa shape'ni 1 OCPU / 3 GB ga tushirish (yoki boshqa yechim) — birga qaror qilamiz.
- **PAYG:** faqat "Out of capacity" uzoq davom etsa, Budget alert bilan. "100% bepul" qoidasi sababli — Sardor qarori.
- ROADMAP Bosqich 9 checkbox'i va PROGRESS.md yozuvi — Bosqich 9 haqiqatan serverda ishga tushgach.
