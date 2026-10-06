# STATUS — Ayvona Jobs (2026-10-06): 1 GB Oracle serverga tayyorlash

Maqsad: loyiha **VM.Standard.E2.1.Micro (1/8 OCPU, 1 GB RAM, Ubuntu 24.04)** da ishonchli ishlasin va deploy
**bitta skript + bitta qo'llanma** bilan bo'lsin. Hammasi bepul. To'liq buyruqlar: [DEPLOY.md](DEPLOY.md).

## 1. Nima o'zgardi

**Yangi fayllar**
- `scripts/server-setup.sh` — yangi Ubuntu 24.04 uchun bir martalik, qayta ishga tushirsa xavfsiz o'rnatuvchi
- `scripts/push-secrets-from-windows.ps1` — `.env` + session + baza'ni serverga yuboradi (xavfsiz nusxa, lokal jarayon tekshiruvi)
- `scripts/healthcheck.sh` — servislar, xotira/swap/disk, bazadagi oxirgi faollik (collector/publisher), navbat
- `scripts/backup.sh`, `deploy/systemd/ayvona-backup.service` + `.timer` — kunlik SQLite zaxirasi (7 kun, lokal)
- `src/ayvona/litebot.py` — collector uchun yengil (`httpx`) admin-xabar mijozi (aiogram o'rniga)
- `src/ayvona/sources/identifiers.py` — `normalize_identifier` (Telethon'siz modulga ko'chirildi)
- `tests/test_litebot.py` — LiteBot va "qaysi jarayon nimani import qilmaydi" himoyasi

**O'zgargan fayllar**
- `deploy/systemd/ayvona-{collector,worker,bot,web}.service` — xotira/CPU chegaralari, `OOMScoreAdjust`, `.venv/bin/python` to'g'ridan-to'g'ri
- `scripts/deploy.sh` — `uv sync --locked --no-dev --compile-bytecode`, zaxira unitlari, healthcheck eslatmasi
- `src/ayvona/ai/{client,helper}.py`, `config.py`, `config/settings.yaml` — Gemini: eksponensial kutish, `Retry-After`, `.env` dan limitlar
- `src/ayvona/apps/collector.py`, `services/notifier.py`, `services/sources_admin.py`, `sources/telegram_source.py` — lazy importlar
- `.env.example` (yangi: `GEMINI_DAILY_LIMIT`, `GEMINI_MIN_INTERVAL_SECONDS`, `WEBSITE_BASE_URL`), `DEPLOY.md` (qayta yozildi), `deploy/SETUP_ORACLE.md` (yuqorisiga eslatma), `tests/test_ai.py`, `tests/test_config.py`

**Tekshiruv:** `uv sync --locked` toza nusxada ✅ · `pytest` **874 passed** (oldin 860) ✅ · `ruff check` toza ✅ ·
`bash -n` va `shellcheck` (ogohlantirish darajasigacha toza; faqat uslub eslatmalari) barcha `.sh` va serverda ishlaydigan
`apply.sh` uchun ✅ · PowerShell sintaksisi ✅ · push skripti `-DryRun` bilan lokal sinaldi: ishlayotgan `python -m ayvona.apps.*`
bo'lsa **rad etadi**, bo'lmasa xavfsiz nusxa + butunlik tekshiruvi ✅ · `backup.sh` (zaxira, gzip, 7 tagacha tozalash,
tiklash) va `healthcheck.sh` lokal sinaldi ✅ — `sqlite3` o'rniga Python bilan yozilgan almashtirgich ishlatildi
(haqiqiy `sqlite3` CLI sinalmadi).

## 2. Xotira o'lchovlari va tanlangan limitlar

O'lchov (Windows, Python 3.12, haqiqiy baza nusxasi, tarmoqsiz; har jarayon o'z xotirasini o'zi o'lchadi). ⚠️ **Linux'da
boshqacha** (odatda biroz kam); collector va bot soxta Telegram bilan o'lchandi — haqiqiy ulanish 10–30 MB qo'shishi mumkin.

| Servis | O'lchangan (WS / private) | MemoryHigh | MemoryMax | CPUWeight / Nice |
|---|---|---|---|---|
| collector | 112 / 92 MB | 140 MB | 180 MB | 50 / 10 |
| worker | 232 / 211 MB | 250 MB | 300 MB | 100 / 5 |
| bot | 216 / 195 MB | 230 MB | 270 MB | 200 / 0 |
| web (ixtiyoriy, standart O'CHIQ) | 96 / 76 MB | 100 MB | 130 MB | 50 / 10 |
| **jami, websiz** | **560 / 498 MB** | **620 MB** | **750 MB** | |

Hammasida `Restart=always`, `RestartSec=10`, `OOMScoreAdjust=500`; sshd'ga `-900` (setup qo'yadi) — xotira tugasa SSH emas,
ilova servisi o'ladi. 2 GB swap, `vm.swappiness=10`.

Xotirani kamaytirgan narsalar (o'lchab): **collector `aiogram` ni yuklamaydi** (import xotirasi 235 → 95 MB, `LiteBot`),
**bot `telethon` ni yuklamaydi** (234 → 199 MB), **`--compile-bytecode`** (Telethon importidagi ~225 MB sakrash yo'qoladi,
barqaror xotira 89 → 52 MB — aks holda `MemoryMax` bilan o'ldirilish ehtimoli bor edi), `uv run` o'rniga to'g'ridan-to'g'ri
`.venv/bin/python` (⚠️ `uv` jarayonining xotirasi o'lchanmadi), `MALLOC_ARENA_MAX=2`, `--no-dev`, sayt/Caddy ixtiyoriy.
Worker parallelligi: kamaytiradigan narsa topilmadi (hammasi allaqachon ketma-ket).

**Qaror (qilinmadi):** eng katta xarajat — `aiogram` o'zi (~130 MB worker'da va yana shuncha bot'da). Ikkalasini bitta
jarayonga birlashtirish ~200 MB tejardi, lekin bu ishlayotgan mantiqni o'zgartiradi (signal, heartbeat, qayta yonish) va
haqiqiy Telegram'da sinab bo'lmaydi. Birinchi hafta `healthcheck.sh` da xotira yetmasa — keyingi qadam shu.

## 3. Serverga qo'yish — aniq buyruqlar (copy-paste)

```powershell
# 💻 PowerShell — oldin collector/worker/bot oynalarida Ctrl+C (kompyuterda ular BIR HAM yonmasin)
ssh -i "$HOME\.ssh\<kalit>" ubuntu@<IP>
```
```bash
# 🐧 server (ubuntu) — 5–15 daqiqa; "KEYINGI QADAMLAR" blokini chop etadi
curl -fsSLO https://raw.githubusercontent.com/sabdur4hmonov/ayvonajobs/main/scripts/server-setup.sh
bash server-setup.sh
exit
```
```powershell
# 💻 PowerShell — avval sinov (serverga ulanmaydi), keyin haqiqiysi
cd "D:\Coding projects\ayvona"
.\scripts\push-secrets-from-windows.ps1 -HostName <IP> -KeyFile "$HOME\.ssh\<kalit>" -DryRun
.\scripts\push-secrets-from-windows.ps1 -HostName <IP> -KeyFile "$HOME\.ssh\<kalit>"
```
```bash
# 🐧 server (ubuntu) — "reboot kerak" desa avval: sudo reboot
sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh       # 1–2 daqiqadan keyin
journalctl -u 'ayvona-*' -f
```
Keyin: `sudo bash /home/ayvona/ayvona/scripts/deploy.sh` (yangilash). Sayt kerak bo'lsa: DEPLOY.md, Ilova B.

## 4. Qolgan risklar va menga kerak bo'ladigan narsalar

**Sinalmagan (hammasi birinchi jonli ishga tushirishda aniqlanadi):**
- `server-setup.sh` haqiqiy Ubuntu 24.04 da **ishga tushirilmadi** (laptopda ishga tushirish taqiqlangan edi) — faqat
  sintaksis, shellcheck va iptables/massiv mantiqi namunaviy matnda sinaldi. Oracle image'idagi iptables va `netfilter-persistent`
  haqidagi taxminlar hujjatdan; Caddy rasmiy repo qadamlari ham sinalmagan (ishlamasa Ubuntu paketiga o'tadi).
- Push skriptining serverdagi qismi (`apply.sh`) faqat shellcheck bilan tekshirildi; `ssh/scp` haqiqiy serverga ulanmadi.
- systemd chegaralari va xotira sonlari Linux'da o'lchanmadi (Windows o'lchovi + zaxira). OOM yuz bersa:
  `journalctl -k | grep -i oom`, `healthcheck.sh`.
- Ommaviy bot, Gemini, veb-manbalar (Bosqich 10–17) hali hech qachon haqiqiy Telegram/Gemini bilan ishlamagan (oldingi audit).
- 1/8 OCPU: startda aiogram/telethon yuklanishi 30–60 s olishi mumkin; collector sikli sekin bo'lishi mumkin.

**Oracle idle xavfi** (7 kun CPU/tarmoq < 20% bo'lsa qaytarib olinishi mumkin): soxta yuk qo'shilmadi; DEPLOY.md 9-bo'lim —
qonuniy faollik, OCI Metrics'ni kuzatish, ogohlantirish, zaxira/tiklash. Joriy qoidani Oracle sahifasida tekshiring.

**Menga/sizga kerak:** (1) serverning **Public IP** va **SSH kalit fayli**; (2) Gemini kaliti — `.env` da **allaqachon bor**
(qiymatni ko'rmadim), kunlik chegarani xohlasangiz `GEMINI_DAILY_LIMIT`; (3) **DuckDNS tokeni kerak emas** — Caddy HTTP-01
bilan sertifikat oladi; faqat saytni yoqsangiz: DuckDNS'da subdomen → IP, OCI'da 80/443 Ingress qoidasi; (4) hh.uz tokeni
(ixtiyoriy).

**Savol bermay tanlangan eng oddiy bepul variantlar:** Docker o'rniga mavjud systemd; yo'l `/home/ayvona/ayvona` (barcha
unitlar/`deploy.sh` shuni kutadi; `/opt` emas); servislar `uv run` o'rniga `.venv/bin/python`; saytsiz va fail2ban'siz
(bayroq bilan); SSH sozlamalariga tegilmadi (faqat ogohlantirish); zaxira worker'nikidan alohida (`data/backups/daily/`,
taymer, lokal); repo public bo'lib qoldi (clone HTTPS); setup skripti bo'sh baza yaratadi va push skripti uni
almashtiradi; `deploy-ready` → `main` merge qilindi va push qilindi.
