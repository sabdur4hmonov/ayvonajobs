# STATUS — Ayvona Jobs (audit: 2026-10-06)

Audit `main` = `6c67d27` ustida qilindi. Bu fayl va `DEPLOY.md` faqat `deploy-ready` branch'ida (main'ga merge qilinmagan).
Kod o'zgartirilmadi — faqat hujjatlar qo'shildi.

## 1. HOLAT

Loyiha **kod jihatidan tayyor, lekin hali hech qachon serverda ishlamagan**. Bosqich 0–17 yozilgan,
860 ta test o'tadi. Aggregator (collector → worker → kanal) laptopda haqiqiy Telegram bilan ishlagan:
bazada 20 ta kanal, 1306 ta post, kanalga 45 ta e'lon chiqqan. Ammo worker va bot oxirgi marta **2026-09-30** da,
collector **2026-10-01** da ishlagan. Ommaviy bot (Bosqich 10–14), Gemini (15), veb-manbalar (16) va sayt (17)
faqat mock bilan sinalgan: `users` jadvali bo'sh, `ai_cache` bo'sh. Oxirgi ish (2026-10-02): avval bazani yangi
migratsiyaga ko'tarish — baza hozir `b8d4f0a2c6e9 (head)` da, HANDOFF.md dagi "1-ish" bajarilgan. Keyin kanalga
chiqarish tezligini sozlash: postlar orasida 5 daqiqa, 23:00–07:00 tungi tanaffus, `/stats` da navbat ETA.
Keyingi rejadagi qadam — botni telefonda sinash va Oracle serverga chiqarish edi.

Git: lokal `main` va GitHub `main` **bir xil** (0 ahead / 0 behind), ishchi papka toza, boshqa branch, stash yoki tag yo'q.

## 2. TAYYOR (ishlaydi)

| Qism | Holat | Dalil |
|---|---|---|
| Collector (Telethon, 20 kanal, cursor, catch-up) | ✅ jonli sinalgan | `apps/collector.py`, bazada 1306 post |
| Qayta ishlash: normalize, dedup, classify, extract, kategoriya, format | ✅ jonli sinalgan | `processing/`, 341 `done`, 98 `duplicate` |
| Publisher → @ayvonajobs (navbat, retry, 24 soat qoidasi) | ✅ jonli sinalgan | `publisher/outbox.py`, 45 `published` |
| 5 daqiqa oraliq + tungi tanaffus + `/stats` ETA | ✅ faqat testlarda | `6c67d27`, `tests/test_publisher.py` |
| Admin buyruqlari, monitoring, kunlik backup | ✅ kod + test | `bot/handlers/admin*.py`, `services/heartbeat.py`, `services/backup.py` |
| Migratsiyalar (8 ta) | ✅ toza bazada head'gacha; `alembic check` — model va sxema mos | `migrations/versions/` |
| Veb-sayt (o'qish uchun) | ✅ lokal ishga tushirib tekshirildi: `/`, `/ish`, `/soha/*`, `sitemap.xml`, `robots.txt`, `/healthz` → 200 | `apps/web.py`, `web/app.py` |
| Deploy: systemd (4 servis), Caddy + Let's Encrypt, `deploy.sh`, Oracle qo'llanma | ✅ fayllar bor; **haqiqiy serverda sinalmagan** | `deploy/`, `scripts/deploy.sh`, `DEPLOY.md` |
| Sifat | ✅ `uv sync --locked` toza klonda, **860 passed**, `ruff check` toza | audit, 2026-10-06 |
| Sirlar | ✅ git tarixida `.env`/session/baza/token yo'q; `.env.example` to'liq | audit |

## 3. ISHLAMAYAPTI / TUGALLANMAGAN (muhimlik tartibida)

| # | Ish | Ta'siri | Hajm |
|---|---|---|---|
| 1 | Serverga chiqarish (DEPLOY.md 1–8) — serverda hech qachon ishga tushmagan; Oracle Linux qismlari va `deploy.sh` jonli sinalmagan | **deploy'ni to'sadi** | o'rta (1–2 soat) |
| 2 | `.env`, `data/ayvona.session` va bazani serverga ko'chirish; laptopdagi jarayonlarni butunlay to'xtatish | **deploy'ni to'sadi** | kichik |
| 3 | Ommaviy botni telefonda sinash: e'lon joylash, qidiruv, saqlash, obuna, yopish (Bosqich 10–14 — faqat mock) | kutsa bo'ladi (bot ishlaydi, lekin xatolar jonli chiqishi mumkin) | o'rta |
| 4 | Eski navbat: 295 `queued` va 432 `new` post 24 soatdan eski — serverda `skipped_old` bo'ladi, kanalga chiqmaydi (kutilgan xatti-harakat) | kutsa bo'ladi | — |
| 5 | Gemini: kalit `.env` da bor, lekin hech qachon jonli ishlamagan | kutsa bo'ladi | kichik |
| 6 | Veb-manbalar (Himalayas, Remotive, Jobicy, Remote OK, Oson Ish, hh.uz) — hammasi o'chiq; Oson Ish HTML tuzilishi tekshirilmagan; hh.uz token kutyapti; vacancy.gov.uz yo'q | kutsa bo'ladi | kichik–o'rta |
| 7 | Sayt: domen + `website.base_url` (hozir bo'sh — canonical/sitemap'da to'liq manzil bo'lmaydi) | sayt uchun kerak, bot uchun emas | kichik |
| 8 | Haqiqiy post rasmlari: 249 ta faylning hammasi vaqtinchalik (placeholder) | kutsa bo'ladi | o'rta (dizayn ishi) |
| 9 | Saytdan e'lon joylash, Telegram Login Widget, saytda saqlanganlar/obunalar, admin panel | kutsa bo'ladi | katta |
| 10 | `ruff format --check`: 3 fayl formatlanmagan (`apps/bot.py`, `apps/worker.py`, `bot/texts.py`) — faqat ko'rinish | kutsa bo'ladi | kichik |
| 11 | Hujjatlar mos emas: ROADMAP'da `/addsource` belgilanmagan (kod bor); "Admin chat" belgilanmagan (`ADMIN_CHAT_ID` to'ldirilgan); SETUP_ORACLE.md repo'ni private deydi (aslida public) | kutsa bo'ladi | kichik |
| 12 | `/healthz` faqat "ok" qaytaradi, bazani tekshirmaydi (asosiy kuzatuv — heartbeat + `/stats`) | kutsa bo'ladi | kichik |
| 13 | Bot FSM xotirada: bot qayta yonsa, yarim to'ldirilgan forma yo'qoladi (yuborilganlar saqlanadi) | kutsa bo'ladi | o'rta |

## 4. SERVERGA QO'YISH

**Hozir qo'ysa bo'ladimi? Ha — kod tomondan to'siq yo'q.** `main` branch'i o'zi yetarli (`deploy-ready` faqat
hujjat qo'shadi). Qolgan to'siqlar faqat sizda: serverga SSH, `.env` + session + bazani ko'chirish va laptopdagi
collector/worker/bot'ni to'xtatish. Ogohlantirish: bu birinchi jonli server, shuning uchun birinchi soatda loglarni kuzating.

Ubuntu uchun qisqa yo'l (Oracle Linux, firewall, domen/HTTPS — to'liq [DEPLOY.md](DEPLOY.md) da):

```bash
# 🐧 server (ubuntu)
sudo apt update && sudo apt install -y git curl sqlite3 fonts-dejavu-core fail2ban
sudo timedatectl set-timezone Asia/Tashkent
sudo useradd --create-home --shell /bin/bash ayvona
sudo -iu ayvona bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -iu ayvona git clone https://github.com/sabdur4hmonov/ayvonajobs.git /home/ayvona/ayvona
```
```powershell
# 💻 PowerShell (laptop) — avval collector/worker/bot'ni Ctrl+C bilan to'xtating
cd "D:\Coding projects\ayvona"
uv run python -c "import sqlite3; s=sqlite3.connect('data/ayvona.db'); d=sqlite3.connect('data/ayvona-copy.db'); s.backup(d); d.close(); s.close()"
scp -i "$HOME\.ssh\<kalit>" .env data\ayvona.session data\ayvona-copy.db "ubuntu@<IP>:~/"
```
```bash
# 🐧 server (ubuntu)
sudo -u ayvona mkdir -p /home/ayvona/ayvona/data
sudo install -o ayvona -g ayvona -m 600 ~/.env           /home/ayvona/ayvona/.env
sudo install -o ayvona -g ayvona -m 600 ~/ayvona.session /home/ayvona/ayvona/data/ayvona.session
sudo install -o ayvona -g ayvona -m 600 ~/ayvona-copy.db /home/ayvona/ayvona/data/ayvona.db
rm ~/.env ~/ayvona.session ~/ayvona-copy.db
sudo -iu ayvona bash -c 'cd ~/ayvona && ~/.local/bin/uv sync --locked && ~/.local/bin/uv run alembic upgrade head && ~/.local/bin/uv run python scripts/make_placeholder_images.py && ~/.local/bin/uv run python -m ayvona.apps.collector --once'
sudo cp /home/ayvona/ayvona/deploy/systemd/ayvona-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
systemctl status ayvona-collector ayvona-worker ayvona-bot --no-pager
```
Keyingi yangilashlar: `git push` (laptop) → `sudo bash /home/ayvona/ayvona/scripts/deploy.sh` (server).

## 5. SAVOLLAR (faqat siz hal qilasiz)

1. **Server OS va shape:** Ubuntu yoki Oracle Linux? A1 Flex (ARM, 6 GB) yoki E2.1.Micro (1 GB)? 1 GB bo'lsa swap shart.
2. **Session:** laptopdagi `ayvona.session` ni ko'chirasizmi yoki serverda yangi login qilasizmi? Ikkalasida ham laptop
   collector'i keyin shu session bilan ishlamasligi kerak.
3. **Kanal:** `.env` dagi `CHANNEL_ID` haqiqiy @ayvonajobs'mi yoki test kanal? (Men qiymatlarni ko'rmadim.)
4. **Sayt hozirmi yoki keyinmi?** Hozir bo'lsa — DuckDNS (bepul) yoki o'z domeningiz?
5. **Repo public:** ROADMAP'da "Private qiling" deyilgan, hozir public. Repo'da sir yo'q, lekin kanal ro'yxati,
   real e'lon namunalari (telefon raqamlari bilan, `tests/fixtures/`) va HANDOFF.md dagi email ochiq turibdi.
6. **Gemini:** serverda darhol yoqilsinmi? (Kalit bor, jonli sinalmagan; `/ai` bilan o'chirsa bo'ladi.)
7. **Veb-manbalar:** qaysilarini yoqamiz? hh.uz uchun dev.hh.ru da ilova ochasizmi?
8. **`deploy-ready` → `main`:** bu ikki hujjatni main'ga merge qilaymi yoki o'zingiz ko'rib chiqasizmi?

---

### Ilova: audit tafsilotlari

- **Stack:** Python 3.12 (uv, `uv.lock`), Telethon 1.45, aiogram 3, SQLAlchemy 2.1 async + aiosqlite, SQLite (WAL, FTS5),
  Alembic, FastAPI + Jinja2 + uvicorn, httpx, rapidfuzz, Pillow, loguru, pydantic-settings. Test: pytest, ruff.
- **Jarayonlar:** `python -m ayvona.apps.{collector,worker,bot,web}`. Tashqi xizmatlar: Telegram MTProto + Bot API,
  Gemini REST (ixtiyoriy), cbu.uz (USD kursi), Himalayas/Remotive/Jobicy/Remote OK/Oson Ish/hh.uz (o'chiq).
- **Sozlamalar:** `.env` (sirlar) + `config/*.yaml`. `.env` dagi 12 ta kalit to'ldirilgan; `GEMINI_MODEL`,
  `GEMINI_API_KEYS`, `HH_ACCESS_TOKEN`, `HH_USER_AGENT` yo'q (ixtiyoriy, standart qiymat ishlaydi).
- **Jarayonlar sirsiz (toza klonda):** bot va collector tushunarli xabar bilan chiqadi (exit 1), worker
  `--once --no-publish` toza ishlaydi.
- **Portlar:** faqat sayt `127.0.0.1:8080` (Caddy orqasida); `forwarded_allow_ips=127.0.0.1`. CORS kerak emas —
  sayt server tomonda HTML chizadi, ochiq API yo'q. Auth: admin buyruqlari `ADMIN_IDS` bo'yicha.
- **Lokal kuzatuv:** bu kompyuterda 8080-port boshqa dastur tomonidan band — sayt lokal sinovi 18080 da qilindi
  (loyihaga ta'siri yo'q).
- **Audit izi:** lokal bazani faqat o'qish rejimida ochdim; SQLite ikkita bo'sh yordamchi fayl (`-wal`, `-shm`)
  yaratgan edi — o'chirildi, `ayvona.db` o'zgarmadi (vaqt belgisi 2026-10-02).
