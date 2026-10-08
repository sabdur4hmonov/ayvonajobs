# DEPLOY — Ayvona Jobs: Oracle Cloud E2.1.Micro (1 GB RAM) + Ubuntu 24.04

Bu qo'llanma **server allaqachon yaratilgan** holat uchun: "VM yangi yaratildi" dan "bot ishlayapti" gacha.
Hammasi bepul (Always Free). Sinalmagan joylar `⚠️ sinalmagan` deb belgilangan.

**Nima o'rnatiladi:** 3 ta Python jarayon (systemd servislari) — `ayvona-collector`, `ayvona-worker`, `ayvona-bot`;
bitta SQLite fayl (`data/ayvona.db`); kunlik zaxira taymeri. Veb-sayt (`ayvona-web` + Caddy) **ixtiyoriy** va
standart holatda o'chiq: 1 GB da har 100 MB muhim. Bot "long polling" ishlatadi — kiruvchi port kerak emas
(faqat 22/SSH). 80/443 faqat saytni yoqsangiz.

> **Qaysi buyruq qayerda:** `# 🐧 server` — SSH orqali serverda (`ubuntu` foydalanuvchi) ·
> `# 💻 PowerShell` — Windows kompyuteringizda. `<IP>` — serverning Public IP manzili (OCI Console → Compute →
> Instances), `<kalit>` — SSH maxfiy kalit fayli.

## Tezkor xulosa (to'rt qadam)

```text
1) serverda:      bash server-setup.sh                       (5–15 daqiqa, bir marta)
2) kompyuterda:   .\scripts\push-secrets-from-windows.ps1 ... (.env + session + baza)
3) serverda:      sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
4) serverda:      sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
```

---

## 0. Boshlashdan oldin

1. **Shape'ni tekshiring:** OCI Console → Compute → Instances → serveringiz → *Shape* = `VM.Standard.E2.1.Micro`,
   *Image* = Ubuntu 24.04. (Boshqa shape yoki OS bo'lsa — pastdagi ilovaga qarang.)
2. **Kompyuterdagi jarayonlarni to'xtating:** collector, worker va bot oynalarida **Ctrl+C**. Bitta Telethon
   session va bitta `BOT_TOKEN` faqat **bitta joyda** ishlay oladi (aks holda `AUTH_KEY_DUPLICATED` /
   `TelegramConflictError`). Serverga ko'chirgandan keyin kompyuterda ularni **qayta yoqmang**.
3. Kod GitHub'da (`main`) ekanini tekshiring — server faqat GitHub'dan oladi.

## 1. Serverga kirish va tayyorlash (bir marta)

```powershell
# 💻 PowerShell
ssh -i "$HOME\.ssh\<kalit>" ubuntu@<IP>
```

```bash
# 🐧 server
curl -fsSLO https://raw.githubusercontent.com/sabdur4hmonov/ayvonajobs/main/scripts/server-setup.sh
bash server-setup.sh
```

Skript **qayta ishga tushirilsa ham xavfsiz** (har qadamni avval tekshiradi). Nima qiladi:

| Qadam | Nima |
|---|---|
| 2 GB **swap** + `vm.swappiness=10` | 1 GB RAM uchun zaxira; fstab'ga yoziladi (qayta yoqilganda qoladi) |
| apt yangilash, `git curl sqlite3 unattended-upgrades iptables-persistent fonts-dejavu-core` | kompilyator **kerak emas** (hamma kutubxona tayyor wheel) |
| vaqt zonasi `Asia/Tashkent`, **journald ≤ 200 MB** | loglar 47 GB diskni to'ldirmaydi (fayl loglari 14 kundan keyin o'chadi) |
| `ayvona` foydalanuvchisi, `uv`, repo clone → `/home/ayvona/ayvona` | servislar shu yo'lni kutadi |
| `uv sync --locked --no-dev --compile-bytecode` | dev kutubxonalarsiz; oldindan kompilyatsiya xotirani kamaytiradi (pastda) |
| `alembic upgrade head` | bo'sh baza yaratadi (3-qadamda haqiqiysi bilan almashtiriladi) |
| systemd unitlar (**yoqilmaydi**), kunlik zaxira taymeri (yoqiladi) | servislar `.env` va session kelgunicha ishga tushmaydi |
| OOM himoyasi: sshd `OOMScoreAdjust=-900`, ilova servislari `+500` | xotira tugasa avval ilova o'ladi, SSH emas |
| firewall: **faqat 22** (iptables, `netfilter-persistent save`) | `ufw` yoqilmaydi (Oracle iptables bilan to'qnashadi) |
| `unattended-upgrades` | xavfsizlik yangilanishlari avtomatik; server o'zi qayta yonmaydi |

Bayroqlar: `--with-web --domain <nom>` (sayt), `--with-fail2ban`, `--swap-gb N`, `--skip-upgrade`, `--branch X`.
Oxirida skript **KEYINGI QADAMLAR** blokini chop etadi. Agar "reboot kerak" desa: `sudo reboot`, 1 daqiqadan keyin
qayta ulaning.

> SSH'da parol bilan kirish yoqilgan bo'lsa skript ogohlantiradi, lekin **o'zgartirmaydi** (qulflanib qolmaslik
> uchun). Repo private bo'lib qolsa: `scp scripts/server-setup.sh` bilan yuboring va `--repo` ga deploy-key
> manzilini bering ([deploy/SETUP_ORACLE.md §7](deploy/SETUP_ORACLE.md)).

## 2. Maxfiy fayllarni yuborish (`.env`, session, baza)

Avval **sinov** (serverga ulanmaydi: tekshiradi va nusxa oladi):

```powershell
# 💻 PowerShell
cd "D:\Coding projects\ayvona"
.\scripts\push-secrets-from-windows.ps1 -HostName <IP> -KeyFile "$HOME\.ssh\<kalit>" -DryRun
```

Keyin haqiqiysi:

```powershell
# 💻 PowerShell
.\scripts\push-secrets-from-windows.ps1 -HostName <IP> -KeyFile "$HOME\.ssh\<kalit>"
```

Skript: (1) kompyuterda `python -m ayvona.apps.*` ishlayotgan bo'lsa **to'xtaydi**; (2) baza va session'ning
**xavfsiz nusxasini** (`sqlite backup`, butunlik tekshiruvi bilan) oladi — tirik fayl nusxalanmaydi; (3) `scp` bilan
yuboradi, serverda egasi `ayvona`, huquq `600`; (4) `alembic upgrade head`; (5) vaqtincha nusxalarni o'chiradi.
Hech qanday maxfiy qiymat chop etilmaydi. Serverdagi baza bo'sh bo'lmasa yoki servislar ishlayotgan bo'lsa `-Force`
kerak (eski baza `data/backups/pre-push/` ga saqlanadi). `-Start` — yuborgach servislarni ham yoqadi.

> Session'ni ko'chirmay serverda yangi login ham mumkin:
> `sudo -iu ayvona` → `cd ~/ayvona && .venv/bin/python scripts/login_telethon.py`.

## 3. Servislarni yoqish va tekshirish

```bash
# 🐧 server
sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
```

Kuting: 1/8 OCPU da aiogram/telethon yuklanishi **30–60 soniya** olishi mumkin. Keyin:

```bash
# 🐧 server
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
journalctl -u 'ayvona-*' -f            # jonli loglar (chiqish: Ctrl+C)
```

`healthcheck.sh` ko'rsatadi: servislar (`active`, xotira, qayta yonishlar), xotira/swap/disk, bazadagi heartbeat'lar,
collector oxirgi sikli, oxirgi o'qilgan post va oxirgi kanalga chiqqan e'lon, navbat. `NATIJA: muammo yo'q` kerak.
Birinchi daqiqada heartbeat "FAIL" bo'lsa — servislar hali yuklanmoqda, 1–2 daqiqadan keyin qayta ishga tushiring.

Telegram'da: botga `/start`, admin sifatida `/stats` (navbat, AI hisoblagichi), kanalda postlar. Postlar orasida
5 daqiqa va 23:00–07:00 tungi tanaffus bor (`config/settings.yaml`) — jimlik normal.
**Eng muhim tekshiruv:** kompyuteringizni o'chiring — postlar baribir chiqyaptimi?

## 4. Xotira: o'lchovlar va chegaralar

**Qanday o'lchandi** (2026-10-06, Windows, Python 3.12, haqiqiy baza nusxasi, tarmoqsiz): har jarayon o'z xotirasini
o'zi o'lchadi (`GetProcessMemoryInfo`, working set / private bytes). Worker — haqiqiy kutilayotgan 432 post ustida,
web — sahifalarni so'rab, bot — soxta Bot API bilan 2400 xabar, collector — soxta manbalar bilan (haqiqiy Telegram'ga
ulanilmadi). ⚠️ **Linux'dagi son boshqacha bo'ladi** (odatda biroz kam), haqiqiy tarmoq buferlari esa 10–30 MB
qo'shadi — shuning uchun chegaralar zaxira bilan qo'yilgan; serverda `healthcheck.sh` haqiqiy sonlarni ko'rsatadi.

| Servis | O'lchangan (WS / private) | `MemoryHigh` (yumshoq) | `MemoryMax` (qattiq) | CPUWeight / Nice |
|---|---|---|---|---|
| collector | 112 / 92 MB | 140 MB | 180 MB | 50 / 10 |
| worker | 232 / 211 MB | 250 MB | 300 MB | 100 / 5 |
| bot | 216 / 195 MB | 230 MB | 270 MB | 200 / 0 |
| web (ixtiyoriy) | 96 / 76 MB | 100 MB | 130 MB | 50 / 10 |
| **jami (websiz)** | **560 / 498 MB** | **620 MB** | **750 MB** | |

`MemoryHigh` oshsa jarayon sekinlashadi (kernel xotirani qaytarib oladi), o'ldirilmaydi; `MemoryMax` oshsa **faqat shu
servis** o'chiriladi va 10 s da qayta yonadi (`Restart=always`). Barcha servislarda `OOMScoreAdjust=500`, sshd'da `-900`.
Chegarani o'zgartirish (unit faylga tegmasdan): `sudo systemctl edit ayvona-worker` → `[Service]` ostiga
`MemoryHigh=300M` yozing → saqlang.

**Xotirani kamaytirish uchun nima qilindi** (mantiq o'zgarmadi):
- **collector `aiogram` ni yuklamaydi:** u faqat admin xabarlari uchun Bot API'ga murojaat qiladi — endi yengil `httpx`
  mijozi (`src/ayvona/litebot.py`). Import xotirasi **235 → 95 MB**. Bot `telethon` ni yuklamaydi (**234 → 199 MB**).
  `tests/test_litebot.py` bu qoidani himoya qiladi (collector'da aiogram, botda telethon bo'lsa test yiqiladi).
- **`--compile-bytecode`:** `.pyc` oldindan tayyor bo'lmasa, Telethon importi vaqtida xotira ~225 MB gacha sakraydi
  (kompilyatsiya) va keyin 89 MB ga tushadi; oldindan tayyor bo'lsa ~52 MB va sakrash yo'q. Bu `MemoryMax` bilan
  o'ldirilishning eng ko'p uchraydigan sababi bo'lardi.
- Servislar `uv run` o'rniga `.venv/bin/python` ni to'g'ridan-to'g'ri ishga tushiradi (qo'shimcha `uv` jarayoni yo'q;
  ⚠️ uning xotirasi o'lchanmadi), `MALLOC_ARENA_MAX=2`, `uv sync --no-dev` (pytest/ruff yo'q).
- Veb-sayt va Caddy standart **o'chiq**.
- Worker parallelligi: pipeline va publisher bitta jarayonda ketma-ket ishlaydi, Gemini so'rovlari ham ketma-ket
  (parallel so'rov yo'q) — kamaytiradigan narsa topilmadi.
- Eng katta qolgan xarajat — `aiogram` kutubxonasining o'zi (~130 MB, worker va bot'da alohida). Ularni bitta jarayonga
  birlashtirish ~200 MB tejardi, lekin bu mantiqni o'zgartirish — **qilinmadi** (STATUS.md, "Qaror").

## 5. Gemini (ixtiyoriy) va bepul tarif chegaralari

Kalit bo'lmasa hammasi regex bilan ishlaydi. Kalit bor bo'lsa (`.env` → `GEMINI_API_KEY`):
- so'rovlar **ketma-ket**, orasida kamida 4 s (`GEMINI_MIN_INTERVAL_SECONDS`), bir xil matn ikki marta yuborilmaydi (kesh);
- **kunlik chegara** `GEMINI_DAILY_LIMIT` (bo'sh = 200, Toshkent kuni). Tugagach ertagacha regex, e'lonlar to'xtamaydi;
- **429 (limit)** va 5xx/timeout'da kalit dam oladi va dam olish **ikki barobar oshadi** (60 → 120 → 240 daq …,
  ko'pi bilan 6 soat); `Retry-After` sarlavhasi hurmat qilinadi; muvaffaqiyatdan keyin boshidan boshlanadi;
- kalit ko'paytirib aylantirish standart **o'chiq** (Google shartlari).
Botda admin: `/ai` (holat, bugungi so'rovlar, o'chirish/yoqish), `/stats` da "AI bugun: N/chegara".

Telegram: collector `FloodWaitError` ni ushlaydi va Telegram aytgan vaqtcha kutadi (+1 s), keyin davom etadi
(`SourceRateLimited` → `run_cycle`); publisher va xabarnomalar `TelegramRetryAfter` ni hurmat qiladi.

## 6. Yangilash (keyingi deploy'lar)

Kompyuterda: `uv run pytest ; uv run ruff check .` → `git push` (main'ga). Serverda:

```bash
# 🐧 server
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
```

`deploy.sh`: `git pull --ff-only` → yoqilgan servislarni to'xtatadi → **baza zaxirasi** (`data/backups/deploy/`, oxirgi 5)
→ `uv sync --locked --no-dev --compile-bytecode` → `alembic upgrade head` → o'zgargan unit fayllar → servislarni
qayta yoqadi. Oxirida `✅ Deploy tugadi`.

Eng oddiy qo'lda variant (migratsiya va yangi kutubxona bo'lmasa):

```bash
# 🐧 server
sudo -iu ayvona git -C /home/ayvona/ayvona pull --ff-only
sudo systemctl restart ayvona-collector ayvona-worker ayvona-bot
```

### 6a. Yangilanish: tasdiqlash, ustuvorlik, Loyihalar, rasmlar, filtrsiz obuna (2026-10-07 / 08)

Nima o'zgardi (qisqa): tasdiqlangan foydalanuvchi e'loni **darhol** kanalga chiqadi; admin faqat "yangi e'lon
tasdiqlash" so'rovini oladi; e'lon uchun **muddat** (3/7/14/30 kun) so'raladi; e'lonlarga **ustuvorlik** (1/2/3-daraja);
yangi bo'lim **🧩 Loyihalar**; admin uchun `/images review`, `/why <id>`; admin uchun **filtrsiz obuna** (`/alerts`):
admin kasbga obuna bo'lsa, hamma kanallardan yig'ilgan mos postlar keladi — kanalga chiqmaganlari ham, sababi bilan.

```bash
# 🐧 server (ubuntu) — bitta buyruq: git pull, baza zaxirasi, kutubxonalar, MIGRATSIYA, restart
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh          # 1–2 daqiqadan keyin
```

- **Migratsiya avtomatik:** `deploy.sh` 5-qadamda `alembic upgrade head` ni o'zi ishga tushiradi: 4 ta additiv
  migratsiya (`c9e1a4b7d2f5` muddat, `d1f5b8c3a7e2` ustuvorlik, `e2a6c9d4b8f1` loyihalar, `f3c8a1d6e9b4` filtrsiz
  obuna jadvali `admin_alert_deliveries`). Mavjud e'lonlar o'zgarmaydi (faqat yangi bo'sh ustunlar va bitta yangi
  jadval; `kind` hammasida `job`). Qo'lda: `sudo -iu ayvona` → `cd ~/ayvona` → `.venv/bin/alembic upgrade head` →
  `.venv/bin/alembic current` (`f3c8a1d6e9b4 (head)` chiqsin).
- **`.env` ga hech narsa qo'shish shart emas.** Ixtiyoriy: `ADMIN_EXTRA_NOTIFICATIONS=true` (eski xabarlarni qaytaradi),
  `ADMIN_UNFILTERED_ALERTS=false` (filtrsiz obunani butunlay o'chiradi; standart: yoqilgan),
  `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY` / `PIXABAY_API_KEY` (stok rasmlar; yo'q bo'lsa rasmlarni o'zimiz chizamiz).
- **Filtrsiz obuna:** botda «🔔 Obunalar» → «➕ Yangi obuna» → soha → kasb (masalan Menejer). Siz admin bo'lganingiz
  uchun obuna 🔓 filtrsiz bo'ladi. Xabarlar worker'dan keladi (post kelgach ~1–2 daqiqada, worker qarorini kutib),
  soatiga 30 tadan ortig'i bitta ro'yxat bo'lib. Ro'yxat va o'chirish: `/alerts`. So'zlar va limitlar:
  `config/settings.yaml` → `admin_alerts:`.
- **Worker birinchi yonishda** mavjud e'lonlarga ustuvorlik beradi (logda: `Ustuvorlik hisoblandi: N ta e'lon ...`).
  Qo'lda: `sudo -iu ayvona` → `cd ~/ayvona && .venv/bin/python scripts/backfill_priority.py --dry-run` (keyin `--all` —
  `config/settings.yaml` dagi `priority:` ro'yxatlarini o'zgartirgach qayta baholash).
- Sozlamalar `config/settings.yaml` da: `priority:` (so'z ro'yxatlari, maosh chegarasi, 3-daraja kunlik chegarasi),
  `posting.duration_options`, `posting.max_description`, `posting.moderation` (`all` = hamma e'lon adminga; hozir
  `suspicious_only`). O'zgartirgach servislarni qayta yoqing.
- **Birinchi tekshiruv** (telefonda): ikkinchi akkaunt bilan «📢 E'lon joylash» → Ish → ... → muddat → yuborish; admin
  «✅ Tasdiqlash» bossa e'lon **o'sha zahoti** kanalda; «🧩 Loyiha» ham shunday; «🧩 Loyihalar» tugmasi; admin: `/why <id>`,
  `/queue` (daraja ko'rinadi). `/images review` faqat siz boshlasangiz ishlaydi. Filtrsiz obuna: «Menejer»ga obuna
  bo'ling → bir necha soat ichida «🔓 Filtrsiz obuna» xabarlari kelishi kerak (holat qatori va «🔗 Asl post» bilan).

**Faqat filtrsiz obunani qaytarish** (qolgan yangiliklar qoladi): `sudo -iu ayvona` → `cd ~/ayvona` →
`.venv/bin/alembic downgrade e2a6c9d4b8f1` → `git reset --hard 1cc90a0` → servislarni qayta yoqing. Yoki kodni
tegmasdan: `.env` ga `ADMIN_UNFILTERED_ALERTS=false` va `sudo systemctl restart ayvona-worker ayvona-bot`.

**Orqaga qaytish (migratsiya bilan):** eski kod yangi bazada **ishga tushmaydi** ("Baza tayyor emas...", u eski
migratsiyani kutadi), shuning uchun avval bazani ham qaytaring:

```bash
# 🐧 server (ubuntu)
sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot ayvona-web
sudo -iu ayvona
```
```bash
# 🐧 ayvona
cd ~/ayvona
.venv/bin/python - <<'EOF'      # loyihalar eski kodda oddiy ish bo'lib ko'rinib qoladi: oldin yopamiz
import sqlite3; c = sqlite3.connect("data/ayvona.db"); c.execute("update jobs set status='closed' where kind='project' and status in ('published','queued','retry','pending_review')"); c.commit()
EOF
.venv/bin/alembic downgrade b8d4f0a2c6e9      # yangi ustunlarni olib tashlaydi (muddat/ustuvorlik/loyiha ma'lumoti yo'qoladi)
git reset --hard 5e15946                      # shu yangilanishdan oldingi main
uv sync --locked --no-dev --compile-bytecode
exit
```
```bash
# 🐧 server
sudo systemctl start ayvona-collector ayvona-worker ayvona-bot
```
Yoki (ishonchliroq): kodni `git reset --hard 5e15946` qiling va bazani `data/backups/deploy/` dagi deploy oldidagi
nusxadan tiklang (8-bo'lim) — migratsiya ham, ma'lumot ham deploy oldingi holatga qaytadi.

### 6b. Yangilanish: post sifati va «📖 To'liq ma'lumot» (2026-10-08)

Nima o'zgardi: kanal postida endi **manba kanalga havola yo'q** ("To'liq ma'lumot: asl e'londa" o'rniga) — qisqargan,
uzun yoki ruscha/inglizcha postda **«📖 To'liq ma'lumot»** tugmasi bor, u **bizning botda** to'liq kartochkani ochadi.
Matn faqat gap/band oxirida kesiladi. Kategoriya, hudud tegi, sarlavha, maosh, kompaniya, dublikat, baqiriq tuzatildi.

```bash
# 🐧 server (ubuntu) — o'sha bitta buyruq: pull, zaxira, kutubxonalar, MIGRATSIYA, restart
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
sudo -iu ayvona bash -c 'cd ~/ayvona && .venv/bin/alembic current'   # a4d2e7f1c3b9 (head)
```

- **Migratsiya avtomatik** (`deploy.sh`): `a4d2e7f1c3b9` — `jobs.full_html` (bo'sh TEXT ustun, additiv). Eski e'lonlarda
  bo'sh qoladi: ularning bot kartochkasi avvalgidek kanal posti. **Kanalga chiqqan postlarga tegilmaydi.**
- **Navbatdagi e'lonlar** worker yonganda yangi formatter bilan qayta yasaladi (`reformat_queued_on_start`): yangi
  matn, yangi tugma, to'liq kartochka. Logda: `Navbat hozirgi formatter bilan yangilandi: ...`.
- `.env` ga hech narsa qo'shilmaydi. Yangi sozlamalar: `config/settings.yaml → tone:` (qo'pol iboralar, katta harf),
  `dedup:` (dublikat oynasi va chegaralari), `config/categories.yaml → ignore_words:` va `default_title`,
  `config/extract.yaml → company_reject_words`, `title_role_words`. O'zgartirgach: `sudo systemctl restart ayvona-worker`.
- **Orqaga qaytish:** `sudo -iu ayvona` → `cd ~/ayvona` → `.venv/bin/alembic downgrade f3c8a1d6e9b4` →
  `git reset --hard ff68d0f` → `uv sync --locked --no-dev --compile-bytecode` → servislarni qayta yoqing
  (`full_html` ustuni o'chadi; tugmasi bor postlar kanalda qoladi, ularning tugmasi botda kanal postini ko'rsatadi).

### 6c. Yangilanish: rezyumelar kanalga chiqmaydi, kanalning o'z reklama aloqasi (2026-10-08)

Nima o'zgardi: ish izlovchining posti (`#rezyume`, "Xodim: <ism>", "Portfolio:", "proyekt kerak") endi **rezyume** deb
topiladi va kanalga chiqmaydi; "e'lon joylashtirish uchun / reklama uchun: @admin" qatoridagi hisob postning aloqasi
bo'lmaydi. **Migratsiya yo'q, `.env` o'zgarmaydi** — faqat kod va `config/*.yaml`.

```bash
# 🐧 server (ubuntu)
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
```

- Qoidalar config'da: `config/filters.yaml → resume_markers / resume_line_markers / resume_structure`,
  `config/source_rules.yaml → defaults.ads_contact_phrases` va `@freelancer_Uzbek`. O'zgartirgach:
  `sudo systemctl restart ayvona-worker`.
- **Allaqachon navbatda turgan rezyumeni** (agar bor bo'lsa) ko'rish — faqat o'qiydi:

  ```bash
  # 🐧 server
  sudo -u ayvona /home/ayvona/ayvona/.venv/bin/python - <<'EOF'
  import sqlite3
  c = sqlite3.connect("file:/home/ayvona/ayvona/data/ayvona.db?mode=ro", uri=True)
  q = ("select j.id, j.status, j.title from jobs j join raw_posts r on r.id = j.raw_post_id "
       "where j.status in ('queued','retry') and (lower(r.text) like '%#rezyume%' or lower(r.text) like '%#resume%')")
  print(c.execute(q).fetchall())
  EOF
  ```

  Chiqarmaslik uchun (ixtiyoriy, avval `data/backups` bor ekanini tekshiring):
  `update jobs set status='rejected' where id in (...)` — `sudo -u ayvona` bilan.
- Kanalga chiqib bo'lgan postlarga tegilmaydi.
- **Orqaga qaytish:** `git reset --hard 6724db5` + servislarni qayta yoqing (baza o'zgarmagan).

## 7. Loglar

```bash
# 🐧 server
journalctl -u ayvona-worker -f                       # bitta servis, jonli
journalctl -u 'ayvona-*' --since "1 hour ago"        # hammasi, oxirgi soat
journalctl -u ayvona-collector -n 100 --no-pager     # oxirgi 100 qator
journalctl -u 'ayvona-*' --since today | grep -iE "error|traceback"
journalctl -k --since "24 hours ago" | grep -i oom   # xotira tugaganmi?
sudo ls -lh /home/ayvona/ayvona/data/logs/           # fayl loglari (kunlik, 14 kun)
```

Disk to'lmasligi: journald ≤ 200 MB (`/etc/systemd/journald.conf.d/ayvona.conf`), fayl loglari 14 kun, zaxiralar 7 ta.
Tekshirish: `journalctl --disk-usage`, `df -h /`.

## 8. Zaxira va orqaga qaytish

**Zaxiralar** (hammasi bepul). Admin chatga zaxira fayli **endi yuborilmaydi** (admin faqat yangi e'lon tasdiqlash so'rovini oladi) — `ADMIN_EXTRA_NOTIFICATIONS=true` bo'lsagina yuboriladi. Shuning uchun serverdan tashqaridagi nusxani o'zingiz oling (pastda):

| Qayerda | Nima | Kim |
|---|---|---|
| `data/backups/daily/ayvona-YYYY-MM-DD.db.gz` | har kuni 03:30, oxirgi **7** ta (`sqlite3 .backup` + butunlik tekshiruvi) | `ayvona-backup.timer` |
| `data/backups/ayvona_YYYY-MM-DD.db` | har kuni 03:00, oxirgi 7 ta (admin chatga faqat `ADMIN_EXTRA_NOTIFICATIONS=true` bilan) | worker |
| `data/backups/deploy/` | har deploy'dan oldin, oxirgi 5 ta | `deploy.sh` |
| `data/backups/pre-push/` | `-Force` bilan almashtirilgan eski baza | push skripti |

Qo'lda hozir: `sudo systemctl start ayvona-backup` (natija: `journalctl -u ayvona-backup -n 5 --no-pager`).
Taymer: `systemctl list-timers ayvona-backup.timer`.

**Serverdan tashqaridagi nusxa** (haftada bir marta, kompyuteringizga):

```bash
# 🐧 server (ubuntu)
sudo cp "$(ls -1t /home/ayvona/ayvona/data/backups/daily/ayvona-*.db.gz | head -n 1)" ~/ayvona-backup.db.gz
sudo chown ubuntu: ~/ayvona-backup.db.gz
```
```powershell
# 💻 PowerShell
scp -i "$HOME\.ssh\<kalit>" ubuntu@<IP>:ayvona-backup.db.gz "$HOME\Documents\ayvona-backup-$(Get-Date -Format yyyy-MM-dd).db.gz"
```

**Yomon deploy'dan orqaga qaytish (kod):**

```bash
# 🐧 server
sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot ayvona-web
sudo -iu ayvona
```
```bash
# 🐧 ayvona
cd ~/ayvona
git log --oneline -5                       # qaysi commit'ga qaytamiz? (odatda ikkinchi qator)
git reset --hard <eski_commit>
uv sync --locked --no-dev --compile-bytecode
exit
```
```bash
# 🐧 server
sudo systemctl start ayvona-collector ayvona-worker ayvona-bot
```

**Bazani tiklash** (migratsiya buzgan bo'lsa — servislar to'xtagan holatda):

```bash
# 🐧 ayvona (sudo -iu ayvona)
cd ~/ayvona
ls -lt data/backups/deploy/ data/backups/daily/                       # qaysi nusxa?
mkdir -p data/broken && mv data/ayvona.db data/ayvona.db-wal data/ayvona.db-shm data/broken/ 2>/dev/null
cp data/backups/deploy/ayvona-<YYYYMMDD-HHMMSS>.db data/ayvona.db     # deploy zaxirasi, YOKI:
gunzip -c data/backups/daily/ayvona-<YYYY-MM-DD>.db.gz > data/ayvona.db   # kunlik zaxira
.venv/bin/alembic upgrade head
```
Keyin servislarni yoqing. Eski (buzuq) baza o'chirilmaydi — `data/broken/` da qoladi. Server butunlay yo'qolsa:
1–3 qadamlarni takrorlang, bazani kompyuteringizdagi eng oxirgi zaxira nusxadan oling (`gunzip`, so'ng
`push-secrets-from-windows.ps1`; `.env` va `ayvona.session` ham kompyuteringizda saqlansin).

## 9. Oracle "idle" xavfi (server qaytarib olinishi mumkin)

Oracle uzoq vaqt deyarli ishlatilmagan Always Free instansiyalarni **qaytarib olishi** mumkin. Loyiha muallifi
2026-09-29 da tekshirgan qoida (o'zgarishi mumkin — **joriysini Oracle sahifasida tekshiring**: *Always Free Resources*,
"idle compute instances"): 7 kun davomida CPU (95-persentil) < 20% **va** tarmoq < 20% (A1 serverlarda xotira ham)
bo'lsa, instansiya "bo'sh" hisoblanadi. **E2.1.Micro** — 1/8 OCPU, bizning bot yengil: CPU/tarmoq 20% dan past
bo'lishi ehtimoli **real**. Aniq oqibat (to'xtatish yoki o'chirish) hujjatda aniq yozilmagan.

Soxta yuk yaratmaymiz. To'g'ri yo'llar:
1. **Haqiqiy ish bo'lsin:** bot, collector va (xohlasangiz) veb-sayt haqiqiy foydalanuvchilar uchun ishlaydi — bu
   o'zi qonuniy faollik. Manbalarni ko'paytirish (`/addsource`) ham haqiqiy yuk.
2. **Kuzating:** OCI Console → Compute → Instances → serveringiz → **Metrics** (CPU Utilization, Network bytes) —
   birinchi 2 haftada haftada bir qarang. Serverda: `healthcheck.sh`, `uptime`, `free -m`.
3. **Ogohlantirish (ixtiyoriy):** OCI Monitoring alarm + Notifications (email) — Free Tier ichida (⚠️ chegaralarni
   konsolda tekshiring).
4. **Yo'qotishga tayyor bo'ling:** `.env` va `ayvona.session` nusxasi kompyuterda; zaxira nusxasi kompyuteringizda (8-bo'lim).
   Server yo'qolsa 1–3 qadamlar bilan 20–30 daqiqada qayta tiklanadi.
5. Pay-As-You-Go'ga o'tish ba'zan "idle" xavfini kamaytiradi deb yoziladi, lekin karta ulanadi va noto'g'ri tanlov
   pul yechilishiga olib keladi — loyiha qoidasi "100% bepul", shuning uchun bu **sizning qaroringiz** (STATUS.md).
6. Ochiq IP o'zgarmasligi uchun: Always Free **Reserved Public IP** (instansiyaga biriktirilgan bo'lsa bepul).

## 10. Muammolar

| Belgi | Yechim |
|---|---|
| Servis `activating (auto-restart)` | `journalctl -u <servis> -n 50 --no-pager` — eng pastdagi xato. Odatda `.env` da qiymat yo'q. |
| Logda "Baza tayyor emas yoki eski versiyada" | `sudo -iu ayvona` → `cd ~/ayvona && .venv/bin/alembic upgrade head` → restart (yoki `deploy.sh`). |
| `Main process exited, code=killed, status=9/KILL` va `journalctl -k` da `oom` | `MemoryMax` ga urildi. `healthcheck.sh` da xotirani ko'ring; `systemctl edit` bilan oshiring, swap borligini tekshiring. |
| `AUTH_KEY_DUPLICATED` | Session ikki joyda ishladi. Kompyuterdagi collector'ni o'chiring; serverda `login_telethon.py` bilan qayta login. |
| `TelegramConflictError` | Shu `BOT_TOKEN` bilan boshqa joyda bot ishlayapti — o'shani to'xtating. |
| Bot har 10 s qayta yonyapti | `.env` da `BOT_TOKEN` bo'sh yoki noto'g'ri. |
| `ssh: Connection timed out` | Server RUNNING'mi; IP to'g'rimi; OCI Security List'da 22 ochiqmi; provayder 22-portni to'smayaptimi. |
| Sayt/sertifikat ishlamaydi | Ilova B: OCI 80/443, DuckDNS IP, `journalctl -u caddy -n 50`. |
| `healthcheck.sh` "FAIL heartbeat" birinchi daqiqada | Servislar yuklanmoqda (30–60 s). Keyin qayta tekshiring. |

---

## Ilova A — Oracle Linux (qisqa; ⚠️ sinalmagan)

`server-setup.sh` faqat Ubuntu uchun. Oracle Linux 8/9 da qo'lda:

```bash
# 🐧 server (opc)
sudo dnf -y update && sudo dnf install -y git curl tar sqlite dejavu-sans-fonts policycoreutils-python-utils
# swap + swappiness: 4-bandga qarang (fallocate/mkswap/swapon/fstab) — Ubuntu bilan bir xil buyruqlar
sudo useradd --create-home --shell /bin/bash ayvona
sudo -iu ayvona bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -iu ayvona git clone https://github.com/sabdur4hmonov/ayvonajobs.git /home/ayvona/ayvona
sudo -iu ayvona bash -c 'cd ~/ayvona && uv sync --locked --no-dev --compile-bytecode && .venv/bin/alembic upgrade head'
sudo cp /home/ayvona/ayvona/deploy/systemd/ayvona-* /etc/systemd/system/ && sudo systemctl daemon-reload
```

- **SELinux:** systemd uy papkasidagi `.venv/bin/python` ni ishga tushirmasa (`status=203/EXEC`):
  `sudo semanage fcontext -a -t bin_t '/home/ayvona/ayvona/\.venv/bin(/.*)?'` va
  `sudo restorecon -Rv /home/ayvona/ayvona/.venv/bin`.
- **Firewall** (firewalld, faqat sayt uchun): `sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload`.
- Keyingi qadamlar (push skripti, servislarni yoqish, healthcheck, deploy.sh) Ubuntu bilan bir xil.

## Ilova B — Veb-sayt (ixtiyoriy, +~100 MB xotira)

1. **DuckDNS:** duckdns.org → subdomen → `current ip` = `<IP>` (Reserved IP tavsiya, 9-bo'lim, 6-band).
2. **OCI konsoli:** Networking → Virtual cloud networks → VCN → Subnet → *Security Lists* (yoki *Network Security Groups*,
   instansiya VNIC'iga qaysi biri biriktirilganiga qarab) → **Add Ingress Rules**: Source `0.0.0.0/0`, TCP, port `80`;
   yana bitta — `443`. (VM ichidagi firewall'ni skript o'zi ochadi; OCI qoidasini faqat konsolda qo'shish mumkin.)
3. **Serverda:** `bash server-setup.sh --with-web --domain <nom>.duckdns.org` (qayta ishga tushirish xavfsiz) —
   Caddy'ni o'rnatadi, 80/443 ni ochadi, sayt manzilini `WEBSITE_BASE_URL` orqali systemd drop-in'ga yozadi.
4. `sudo systemctl enable --now ayvona-web` → `curl -s http://127.0.0.1:8080/healthz` ("ok") →
   `curl -sI https://<nom>.duckdns.org | head -n 1` (`HTTP/2 200`).
5. Sertifikat olinmasa: 80-port tashqaridan ochiqligi va domen `<IP>` ga qarashi shart (`journalctl -u caddy -n 50`).
