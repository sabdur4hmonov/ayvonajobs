# Ayvona Jobs — Oracle Cloud serverga chiqarish (boshlovchi uchun)

Bu qo'llanma sizni **noldan** to'liq ishlaydigan serverga olib boradi: Oracle akkaunt ochishdan tortib,
kompyuteringiz o'chiq bo'lsa ham kanalga postlar chiqib turishigacha.

> **Server allaqachon yaratilganmi (Ubuntu 24.04, `VM.Standard.E2.1.Micro`, 1 GB RAM)?** Unda shu uzun
> qo'llanma emas, [DEPLOY.md](../DEPLOY.md) ni oching: u bitta skript (`scripts/server-setup.sh`) va bitta
> PowerShell yordamchisi bilan hammasini qisqa qiladi, swap va xotira chegaralarini ham sozlaydi.
> Quyidagi matn asosan **akkaunt ochish, SSH kalit, "Out of capacity"** va umumiy ma'lumot uchun foydali.
> Unda tilga olingan `uv run ...` bilan ishga tushadigan unit fayllar va "A1, 1 OCPU / 6 GB" tavsiyasi eskirgan:
> servislar endi `.venv/bin/python` ni to'g'ridan-to'g'ri ishga tushiradi va xotira chegaralari bor.

- ⏱ Vaqt: 2–3 soat (Oracle'da "Out of capacity" bo'lsa — bir necha kun kutish mumkin, pastda yozilgan).
- 💰 Narx: **0 so'm**. Faqat "Always Free" belgili narsalarni tanlaymiz.
- 🖥 Kompyuterda: Windows 11, **PowerShell** (VS Code ichidagi terminal ham bo'ladi).
- 🐧 Serverda: Ubuntu 24.04. Serverdagi buyruqlar **bash** — ular PowerShell'da emas, SSH orqali serverda yoziladi.

> **Qaysi buyruq qayerda?** Har bir kod blokining tepasida yozilgan:
> - `# 💻 PowerShell (kompyuter)` — o'z kompyuteringizda;
> - `# 🐧 server (ubuntu)` — serverga SSH bilan ulanib, oddiy `ubuntu` foydalanuvchida;
> - `# 🐧 server (ayvona)` — serverda, `sudo -iu ayvona` dan keyin (dastur foydalanuvchisi).
>
> `<...>` ichidagi narsalarni o'zingiznikiga almashtiring (qavslarsiz), masalan `<IP>` → `141.147.12.34`.

## Mundarija

0. [Oracle qoidalari (2026) — avval o'qing](#0-oracle-qoidalari-2026--avval-oqing)
1. [Oracle akkaunt ochish](#1-qadam-oracle-akkaunt-ochish)
2. [SSH kalit yaratish (Windows)](#2-qadam-ssh-kalit-yaratish-windows-powershell)
3. [Server (instance) yaratish](#3-qadam-server-instance-yaratish)
4. [Serverga ulanish](#4-qadam-serverga-ulanish)
5. [Serverni tayyorlash: yangilash, vaqt, firewall](#5-qadam-serverni-tayyorlash)
6. [`ayvona` foydalanuvchisi va uv](#6-qadam-ayvona-foydalanuvchisi-va-uv)
7. [Private repo'ni deploy key bilan clone qilish](#7-qadam-private-reponi-deploy-key-bilan-clone-qilish)
8. [.env, session va bazani ko'chirish (scp)](#8-qadam-env-session-va-bazani-kochirish-scp)
9. [Kutubxonalar, migratsiya va sinov](#9-qadam-kutubxonalar-migratsiya-va-sinov)
10. [systemd servislarni yoqish](#10-qadam-systemd-servislarni-yoqish)
10a. [Veb-sayt: Caddy + DuckDNS (ixtiyoriy)](#10a-qadam-veb-sayt-caddy--duckdns-ixtiyoriy)
11. [Loglarni ko'rish (journalctl)](#11-qadam-loglarni-korish-journalctl)
12. [Yangilash (deploy.sh)](#12-qadam-yangilash-deploysh)
13. [Backup'dan tiklash](#13-qadam-backupdan-tiklash)
14. [Muammolar va yechimlar](#14-muammolar-va-yechimlar)

---

## 0. Oracle qoidalari (2026) — avval o'qing

2026-09-29 holatiga tekshirildi (manbalar oxirida).

**Always Free Ampere A1 (ARM server) limitlari — 2026 yil iyunda KAMAYTIRILDI:**

| | Eski (2026-06 gacha) | **Hozir** |
|---|---|---|
| Protsessor | 4 OCPU | **2 OCPU** |
| Xotira (RAM) | 24 GB | **12 GB** |
| Oylik | 3000 OCPU-soat / 18000 GB-soat | **1500 OCPU-soat / 9000 GB-soat** |
| Nechta server | 4 tagacha | **2 tagacha** (jami 2 OCPU) |

- Yangi limit 2026-06-15 dan kuchga kirdi. Foydalanuvchilarga kelgan Oracle xatiga ko'ra 2026-08-18 dan
  limitdan katta Always Free serverlar avtomatik o'chiriladi. Internetdagi eski qo'llanmalarda "4 OCPU / 24 GB"
  deb yozilgan — **ularga ishonmang**.
- Bizga **1 OCPU / 6 GB** yetarli (3–4 ta Python jarayon — collector, worker, bot va ixtiyoriy veb-sayt —
  ~0.6–1.2 GB ishlatadi). Bu limitning yarmi — xavfsiz.
- Disk: jami 200 GB bepul (server diski standart ~47–50 GB). Trafik: oyiga 10 TB — bizga juda ko'p.
- Always Free resurslar faqat **Home Region**da (akkaunt ochishda tanlanadi, **keyin o'zgartirib bo'lmaydi**).

**⚠️ Bo'sh turgan serverni Oracle qaytarib olishi mumkin (idle reclamation).** Rasmiy qoida: 7 kun davomida
quyidagilarning **uchalasi ham** bajarilsa, server "bo'sh" hisoblanadi va qaytarib olinishi mumkin:
- CPU 95-persentil < 20%,
- tarmoq < 20%,
- xotira < 20% (faqat A1 serverlar uchun).

Bizning bot yengil ishlaydi, shuning uchun bu **bizga real xavf**: CPU va tarmoq deyarli doim 20% dan past bo'ladi,
demak hammasi **xotiraga** bog'liq (6 GB ning 20% = 1.2 GB). Nima qilamiz:
1. Birinchi haftada serverning **Metrics** bo'limida "Memory Utilization" ga qarang (14-bo'lim, "Idle" qismi).
2. Agar doim 20% dan past bo'lsa — serverni kichikroq xotiraga o'tkazamiz (masalan 1 OCPU / 3 GB), shunda bir xil
   ishlatish foizda kattaroq ko'rinadi. Bu qarorni o'lchab ko'rgandan keyin birga qilamiz.
3. Har kuni avtomatik backup (Bosqich 8) admin chatga ketadi — eng yomon holatda ham baza yo'qolmaydi (13-qadam).

Oracle hujjatida "qaytarib olish" aniq nima ekani (to'xtatish yoki butunlay o'chirish) yozilmagan — shuning uchun
backup va shu qo'llanma bizning "sug'urta"mizdir.

**Pay As You Go (PAYG) haqida.** Oracle "Out of capacity" bo'lsa akkauntni PAYG'ga o'tkazishni taklif qiladi.
PAYG'da Always Free resurslar baribir bepul, lekin **karta ulangan va bepul bo'lmagan narsa yaratsangiz pul yechiladi**.
Loyiha qoidasi "100% bepul" — shuning uchun PAYG faqat oxirgi chora (14-bo'lim), va faqat Budget alert bilan.

---

## 1-qadam. Oracle akkaunt ochish

**Kerak bo'ladi:**
- Email (Gmail bo'ladi) va telefon raqam (+998… SMS keladi).
- **Visa yoki Mastercard** karta (Humo/Uzcard ishlamaydi). Bank ilovasida kartaning
  **internet/xorijiy to'lovlari yoqilgan** bo'lsin va hisobda ozgina pul bo'lsin.
  Oracle kartani tekshirish uchun kichik summani (odatda ~1 USD) vaqtincha bloklaydi va keyin qaytaradi.
  Bepul resurslar uchun hech narsa yechilmaydi.
- **VPN o'chirilgan** bo'lsin. Manzil va ism kartadagi bilan bir xil yozilsin.

**Qadamlar:**
1. Brauzerda **oracle.com/cloud/free** → **Start for free**.
2. Country: **Uzbekistan**, ism-familiya (lotincha, kartadagidek), email → **Verify my email**.
   Pochtangizga kelgan havolani bosing (Spam papkasini ham tekshiring).
3. Parol o'ylab toping (katta-kichik harf, raqam, belgi). Uni parol menejeriga yoki xavfsiz joyga yozing.
4. **Cloud Account Name** — akkaunt nomi (masalan `ayvonajobs`). Buni ham yozib qo'ying: har kirishda so'raladi.
5. **Home Region** — ⚠️ keyin o'zgartirib bo'lmaydi, bepul server faqat shu regionda bo'ladi.
   - Bot uchun serverning Toshkentga yaqinligi deyarli ahamiyatsiz (bot Telegram serverlari bilan gaplashadi,
     ular Yevropada) — shuning uchun **Yevropa regionlaridan birini** tanlang.
   - Frankfurt, Amsterdam, London kabi mashhur regionlarda A1 serverlar tez-tez "tugab qoladi".
     Kamroq mashhur Yevropa regionlari (masalan Stockholm, Milan, Madrid, Marseille, Zurich) ko'pincha bo'shroq
     bo'ladi — lekin bu kafolat emas.
6. Manzil va telefon raqam → SMS kodni kiriting.
7. **Payment verification** → karta ma'lumotlarini kiriting. "Free Tier / Always Free" ekanini ko'rasiz.
8. Shartlarni o'qib, rozilik belgisini qo'ying → **Start my free trial**.
9. "Account is being provisioned" — 5 daqiqadan bir necha soatgacha kutish mumkin. Tayyor bo'lganda
   "Your Oracle Cloud Account is ready" xati keladi.
10. Kirish: **cloud.oracle.com** → Cloud Account Name → email/parol. Birinchi kirishda Oracle
    **MFA** (ikkinchi bosqichli tasdiq) yoqishni so'rashi mumkin — telefoningizga **Oracle Mobile Authenticator**
    (yoki Google Authenticator) o'rnatib, QR kodni skanerlang.

**Karta o'tmasa ("Error processing transaction" va shunga o'xshash):**
- VPN'ni o'chiring, boshqa brauzer yoki inkognito rejimda qayta urinib ko'ring.
- Bank ilovasida onlayn va xorijiy to'lovlar yoqilganini, karta bloklanmaganini tekshiring.
- Virtual/prepaid kartalar ko'pincha rad etiladi — oddiy (plastik) debet yoki kredit karta bilan urinib ko'ring.
- Ko'p marta ketma-ket urinmang — bir necha soat kuting. Bir odamga bitta bepul akkaunt: bir nechta akkaunt
  ochishga urinmang, Oracle bloklashi mumkin.
- Baribir bo'lmasa: sahifadagi **chat/support** orqali Oracle'ga yozing.

**Muhim:** akkaunt ochilgach birinchi 30 kun "Free Trial" ($300 kredit) ham beriladi. Biz undan
**foydalanmaymiz** — faqat "Always Free-eligible" belgili resurslarni yaratamiz. 30 kundan keyin trial tugaydi,
Always Free server esa ishlashda davom etadi.

---

## 2-qadam. SSH kalit yaratish (Windows PowerShell)

SSH kalit — serverga parolsiz, xavfsiz kirish uchun "kalit juftligi": **maxfiy** (kompyuteringizda qoladi) va
**ochiq** (`.pub`, Oracle'ga beriladi).

```powershell
# 💻 PowerShell (kompyuter)
ssh -V                                   # OpenSSH bormi? "OpenSSH_for_Windows_..." chiqishi kerak
New-Item -ItemType Directory -Force "$HOME\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$HOME\.ssh\oracle_ayvona" -C "sardor-oracle"
```

- "Enter passphrase" so'raydi — kalit uchun qo'shimcha parol. Bo'sh qoldirib Enter bossangiz ham bo'ladi
  (qulayroq), lekin o'shanda `oracle_ayvona` faylini hech kimga bermang va hech qayerga yuklamang.
- Natijada 2 ta fayl: `C:\Users\<siz>\.ssh\oracle_ayvona` (**maxfiy**) va `oracle_ayvona.pub` (ochiq).

Ochiq kalitni ko'rish (3-qadamda kerak bo'ladi):

```powershell
# 💻 PowerShell (kompyuter)
Get-Content "$HOME\.ssh\oracle_ayvona.pub"
# yoki darhol clipboard'ga nusxalash:
Get-Content "$HOME\.ssh\oracle_ayvona.pub" | Set-Clipboard
```

> Agar `ssh -V` "not recognized" desa: **Settings → System → Optional features → Add a feature →
> OpenSSH Client** ni o'rnating va PowerShell'ni qayta oching.

---

## 3-qadam. Server (instance) yaratish

1. **cloud.oracle.com** ga kiring. Chap-yuqoridagi ☰ menyu → **Compute** → **Instances**.
2. Chap tomonda **Compartment** — `<akkaunt nomi> (root)` tanlangan bo'lsin → **Create instance**.
3. **Name:** `ayvona-server`.
4. **Placement:** Availability domain — standartini qoldiring (region'da AD-1/AD-2/AD-3 bo'lsa, capacity
   bo'lmaganda boshqasini sinaymiz).
5. **Image and shape:**
   - **Image → Change image → Ubuntu → Canonical Ubuntu 24.04** (Minimal emas, oddiy) → Select image.
   - **Shape → Change shape → Virtual machine → Ampere → VM.Standard.A1.Flex**.
     - Number of OCPUs: **1**, Amount of memory (GB): **6**.
     - Yonida **"Always Free-eligible"** yozuvi bo'lishi shart. Bo'lmasa — noto'g'ri narsa tanlangan.
   - Shape A1 bo'lganda image avtomatik ARM (aarch64) versiyasiga o'tadi — bu to'g'ri.
6. **Networking:** "Create new virtual cloud network" va "Create new public subnet" — standart qoldiring.
   **"Automatically assign public IPv4 address"** — yoqilgan (Yes) bo'lsin.
7. **Add SSH keys:** **Paste public keys** → 2-qadamda nusxalagan `ssh-ed25519 AAAA... sardor-oracle`
   qatorini joylang.
   > Agar Oracle kalitni qabul qilmasa, RSA kalit yarating va shuni joylang:
   > `ssh-keygen -t rsa -b 4096 -f "$HOME\.ssh\oracle_ayvona" -C "sardor-oracle"`
8. **Boot volume:** hech narsani o'zgartirmang (standart ~47–50 GB, bepul limit ichida).
   Pullik opsiyalarni (encryption with customer keys, paid backups va h.k.) yoqmang.
9. Pastdagi xulosada "Always Free-eligible" ekanini yana bir bor tekshiring → **Create**.
10. Holat **PROVISIONING** → 1–3 daqiqada **RUNNING** (yashil). Sahifadagi **Public IP address** ni
    nusxalab, yozib qo'ying — bu serveringiz manzili (`<IP>`).

### "Out of capacity" / "Out of host capacity" chiqsa

Bu xato sizda emas: Oracle'ning shu regiondagi bepul ARM serverlari vaqtincha band. Nima qilish:
1. **Boshqa Availability domain** tanlab qayta urinib ko'ring (4-bandda), agar regionda bir nechta bo'lsa.
2. **Vaqtni o'zgartiring:** kuniga bir necha marta (ertalab erta, kechasi) qayta **Create** bosing.
   Ba'zan bir necha kun kerak bo'ladi. Formani qayta to'ldirmaslik uchun xato chiqqan sahifani yopmang —
   bir oz kutib, **Create** ni qayta bosing.
3. Kichikroq so'rang: **1 OCPU / 4 GB** yoki **1 OCPU / 3 GB** bilan urinib ko'ring (keyin kattalashtirsa bo'ladi).
4. **Boshqa region tanlab bo'lmaydi** — Always Free faqat Home Region'da.
5. Oxirgi chora — **PAYG'ga o'tish** (Billing → Upgrade). Internetdagi tajribalarga ko'ra PAYG akkauntlarga
   capacity ancha oson beriladi. Faqat Always Free resurslardan foydalansangiz pul yechilmaydi, LEKIN
   darhol **Budget alert** qo'ying (Billing → Budgets → 1 USD, email ogohlantirish). Bu qadamni
   qilishdan oldin menga (Claude'ga) yozing — birga tekshiramiz.
6. Internetda "OCI capacity hunter" kabi avtomatik urinuvchi skriptlar bor — hozircha kerak emas,
   bular murakkab va API kalit talab qiladi.

---

## 4-qadam. Serverga ulanish

```powershell
# 💻 PowerShell (kompyuter)
ssh -i "$HOME\.ssh\oracle_ayvona" ubuntu@<IP>
```

- Birinchi marta: `Are you sure you want to continue connecting (yes/no)?` → `yes` yozing.
- `ubuntu@ayvona-server:~$` ko'rinsa — siz serverdasiz! Chiqish: `exit`.

**Qulaylik uchun qisqa nom** (keyin faqat `ssh ayvona-server` yozasiz). `<IP>` ni almashtirib, butun blokni
PowerShell'ga joylang:

```powershell
# 💻 PowerShell (kompyuter)
$cfg = @'

Host ayvona-server
    HostName <IP>
    User ubuntu
    IdentityFile ~/.ssh/oracle_ayvona
    ServerAliveInterval 60
'@
[System.IO.File]::AppendAllText("$HOME\.ssh\config", $cfg)
ssh ayvona-server
```

> ⚠️ `~/.ssh/config` ni `Out-File` yoki `Set-Content` bilan yozmang: Windows PowerShell 5.1 fayl boshiga
> ko'rinmas BOM belgisini qo'yadi va ssh "Bad configuration option" deb xato beradi. Yuqoridagi usul xavfsiz.

---

## 5-qadam. Serverni tayyorlash

### 5.1 Yangilash va kerakli paketlar

```bash
# 🐧 server (ubuntu)
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl sqlite3 fonts-dejavu-core fail2ban
```

- `sqlite3` — bazani qo'lda ko'rish uchun; `fonts-dejavu-core` — placeholder rasmlar uchun shrift
  (`scripts/make_placeholder_images.py` Linux'da DejaVu shriftini ishlatadi);
  `fail2ban` — SSH'ga parol terib buzishga urinayotgan botlarni avtomatik bloklaydi.
- Agar ekranda binafsha oyna chiqib "which services should be restarted?" desa — **Enter** bosing.
- Xavfsizlik yangilanishlari Ubuntu'da avtomatik o'rnatiladi (`unattended-upgrades` standart yoqilgan).
- Agar yangilashdan keyin `ls /var/run/reboot-required` fayl topsa: `sudo reboot`, 1 daqiqadan keyin qayta ulaning.

### 5.2 Vaqt zonasi va NTP (aniq vaqt)

Kodda hamma vaqt **UTC** da saqlanadi va Toshkent vaqti kodning o'zida hisoblanadi — shuning uchun server vaqt
zonasi faqat loglarni o'qishga qulaylik uchun. Toshkent vaqtini qo'yamiz:

```bash
# 🐧 server (ubuntu)
sudo timedatectl set-timezone Asia/Tashkent
timedatectl
```

Natijada quyidagilar bo'lishi kerak:
```
Time zone: Asia/Tashkent (+05, +0500)
System clock synchronized: yes
NTP service: active
```

Agar `synchronized: no` yoki `NTP service: inactive` bo'lsa:
```bash
# 🐧 server (ubuntu)
sudo apt install -y chrony
sudo systemctl enable --now chrony
timedatectl            # 1–2 daqiqadan keyin "synchronized: yes" bo'ladi
```
Nega muhim: Telegram API vaqt noto'g'ri bo'lsa ulanishni rad etadi, backup 03:00 da ishlashi ham aniq vaqtga bog'liq.

### 5.3 Loglar diskni to'ldirib yubormasligi uchun

```bash
# 🐧 server (ubuntu)
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' | sudo tee /etc/systemd/journald.conf.d/ayvona.conf
sudo systemctl restart systemd-journald
```

### 5.4 Firewall

Oracle serverida **ikki qavat** himoya bor:
1. **Oracle Security List** (Oracle saytida, VCN sozlamalarida) — standart holatda faqat **22-port (SSH)** ochiq.
2. **Ubuntu ichidagi iptables** — Oracle'ning Ubuntu image'ida allaqachon sozlangan: 22-port ochiq,
   qolgan kiruvchi ulanishlar yopiq.

**Collector, worker va bot hech qanday port ochishni talab qilmaydi:** ular Telegram'ga o'zi ulanadi
(chiquvchi ulanish), bot esa "long polling" ishlatadi (webhook emas). Faqat **veb-sayt** (ixtiyoriy, 10a-qadam)
uchun 80 va 443 portlar ochiladi — o'sha qadamda ko'rsatilgan. Shuning uchun hozir:
- ✅ Hech narsani ochmang, hech narsani o'zgartirmang.
- ❌ `ufw` o'rnatmang/yoqmang — Oracle image'idagi iptables qoidalari bilan to'qnashadi va SSH'dan
  qulflanib qolishingiz mumkin.

Tekshirish (ixtiyoriy):
```bash
# 🐧 server (ubuntu)
sudo iptables -L INPUT -n --line-numbers   # "tcp dpt:22 ACCEPT" va oxirida "REJECT" bo'lishi kerak
sudo fail2ban-client status sshd           # fail2ban ishlayaptimi
```

Parol bilan kirish Oracle Ubuntu'da standart **o'chirilgan** (faqat SSH kalit) — shunday qolsin.

---

## 6-qadam. `ayvona` foydalanuvchisi va uv

Dastur alohida, huquqi cheklangan `ayvona` foydalanuvchisi nomidan ishlaydi. Agar dasturda xato bo'lsa ham,
u tizimni buzolmaydi.

```bash
# 🐧 server (ubuntu)
sudo useradd --create-home --shell /bin/bash ayvona
sudo -iu ayvona          # endi siz "ayvona" foydalanuvchisisiz (prompt: ayvona@ayvona-server:~$)
```

uv'ni o'rnatish (Python 3.12 ni uv o'zi yuklab oladi):

```bash
# 🐧 server (ayvona)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv --version             # "uv 0.x.y" chiqishi kerak
which uv                 # /home/ayvona/.local/bin/uv — systemd fayllarida aynan shu yo'l yozilgan
```

> `ubuntu` ga qaytish: `exit`. Qayta `ayvona` bo'lish: `sudo -iu ayvona`.

---

## 7-qadam. Private repo'ni deploy key bilan clone qilish

Repo private, shuning uchun server GitHub'ga o'zini tanitishi kerak. **Deploy key** — faqat SHU bitta repo'ni
**faqat o'qish** huquqi bilan ochadigan kalit. Server buzilsa ham, boshqa repo'laringiz xavfsiz qoladi.

**Oldin (kompyuterda):** hamma o'zgarishlar commit + `git push` qilingan bo'lsin — server faqat GitHub'dagi
kodni oladi.

### 7.1 Serverda kalit yaratish

```bash
# 🐧 server (ayvona)
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "ayvona-oracle-deploy"
cat > ~/.ssh/config <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
cat ~/.ssh/github_deploy.pub      # shu qatorni to'liq nusxalang (sichqoncha bilan belgilang)
```

### 7.2 GitHub'ga qo'shish

1. Brauzerda: **github.com/sabdur4hmonov/ayvonajobs** → **Settings** → chapda **Deploy keys** → **Add deploy key**.
2. Title: `oracle-server`. Key: nusxalangan `ssh-ed25519 AAAA... ayvona-oracle-deploy` qatori.
3. **"Allow write access" ni BELGILAMANG** (server faqat o'qiydi). → **Add key**.

### 7.3 Tekshirish va clone

```bash
# 🐧 server (ayvona)
ssh -T git@github.com
# "Are you sure...?" → yes
# Kutilgan javob: "Hi sabdur4hmonov/ayvonajobs! You've successfully authenticated, but GitHub does not provide shell access."

git clone git@github.com:sabdur4hmonov/ayvonajobs.git ~/ayvona
cd ~/ayvona
git log -1 --oneline     # oxirgi commit kompyuteringizdagi bilan bir xilmi?
```

> Papka nomi ataylab `~/ayvona` (`/home/ayvona/ayvona`) — systemd fayllari va `scripts/deploy.sh` shu yo'lni kutadi.

---

## 8-qadam. .env, session va bazani ko'chirish (scp)

Bu fayllar **git'da yo'q** (maxfiy), shuning uchun ularni kompyuterdan serverga qo'lda ko'chiramiz.

### ⚠️ Avval o'qing: Telethon session haqida

`data/ayvona.session` = Telegram akkauntingizga to'liq kirish. **Bitta session faylni bir vaqtda ikki joyda
ishlatib bo'lmaydi** — Telegram buni sezsa, session'ni bekor qiladi (`AUTH_KEY_DUPLICATED`) va qayta login kerak bo'ladi.

Shuning uchun:
1. **Kompyuteringizdagi collector'ni to'xtating** (Ctrl+C) va shundan keyin kompyuterda shu session bilan
   collector'ni **ishga tushirmang**.
2. Kompyuterda keyinchalik sinash kerak bo'lsa — `.env` da `TELETHON_SESSION=data/ayvona_dev` qilib,
   `uv run python scripts/login_telethon.py` bilan **alohida** session yarating (Telegram bir akkauntda bir
   nechta session'ga ruxsat beradi; faqat bitta FAYLni ikki joyda ishlatish mumkin emas).
3. Xuddi shunday, server bot'i ishlayotganda kompyuterda **o'sha BOT_TOKEN** bilan botni ishga tushirmang
   (bitta token = bitta polling). Sinov uchun @BotFather'dan alohida test bot oching.

### 8.1 Kompyuterda: bazaning toza nusxasi

Eski bazani ko'chirsak, qo'shilgan manbalar, har kanalning "qayerda to'xtaganimiz" (cursor) va dublikat
tarixi saqlanib qoladi. Collector to'xtagan bo'lsin, keyin:

```powershell
# 💻 PowerShell (kompyuter)
cd "D:\Coding projects\ayvona"
uv run python -c "import sqlite3; s=sqlite3.connect('data/ayvona.db'); d=sqlite3.connect('data/ayvona-copy.db'); s.backup(d); d.close(); s.close()"
```

(Bu sqlite'ning backup API'si — WAL ichidagi yangi yozuvlar ham nusxaga tushadi. `Copy-Item` bilan nusxalash
xavfli: `-wal` fayldagi ma'lumot tushmay qolishi mumkin.)

### 8.2 Serverga yuborish

```powershell
# 💻 PowerShell (kompyuter), hali ham "D:\Coding projects\ayvona" ichida
scp .env ayvona-server:~/
scp data\ayvona.session ayvona-server:~/
scp data\ayvona-copy.db ayvona-server:~/
```

(`ayvona-server` — 4-qadamdagi qisqa nom. Uni sozlamagan bo'lsangiz: `scp -i "$HOME\.ssh\oracle_ayvona" .env ubuntu@<IP>:~/`.)

Fayllar `ubuntu` ning uy papkasiga tushdi. Endi ularni `ayvona` ga to'g'ri huquq bilan joylaymiz:

```bash
# 🐧 server (ubuntu)
sudo -u ayvona mkdir -p /home/ayvona/ayvona/data
sudo install -o ayvona -g ayvona -m 600 ~/.env            /home/ayvona/ayvona/.env
sudo install -o ayvona -g ayvona -m 600 ~/ayvona.session  /home/ayvona/ayvona/data/ayvona.session
sudo install -o ayvona -g ayvona -m 600 ~/ayvona-copy.db  /home/ayvona/ayvona/data/ayvona.db
rm ~/.env ~/ayvona.session ~/ayvona-copy.db               # ortiqcha nusxalarni o'chiramiz
```

Kompyuterdagi `data\ayvona-copy.db` ni ham o'chirsangiz bo'ladi: `Remove-Item data\ayvona-copy.db`.

### 8.3 .env ni tekshirish

```bash
# 🐧 server (ayvona)
cd ~/ayvona
nano .env
```

- `DB_PATH=data/ayvona.db` va `TELETHON_SESSION=data/ayvona` — shunday qolsin (loyiha papkasiga nisbatan).
- `CHANNEL_ID` — sinov kanali emas, **haqiqiy kanal** (@ayvonajobs) ekanini tekshiring.
- `BOT_TOKEN`, `ADMIN_IDS`, `ADMIN_CHAT_ID` to'ldirilgan bo'lsin.
- Ixtiyoriy (bo'sh qolsa ham hammasi ishlaydi): `GEMINI_API_KEY` (AI yordamchi), `HH_ACCESS_TOKEN` va
  `HH_USER_AGENT` (hh.uz manbasi). `GEMINI_ALLOW_KEY_ROTATION=false` shunday qolsin.
- Saqlash: **Ctrl+O**, Enter; chiqish: **Ctrl+X**.

> **Variant B (session'ni ko'chirmasdan):** serverda to'g'ridan-to'g'ri login qilish ham mumkin:
> `uv run python scripts/login_telethon.py` (9.1 dagi `uv sync` dan keyin). Telegram'ga kod keladi — kiritasiz.
> Bu yo'l ham xavfsiz: serverda o'zining alohida session'i bo'ladi.

---

## 9-qadam. Kutubxonalar, migratsiya va sinov

```bash
# 🐧 server (ayvona)
cd ~/ayvona
uv sync --locked                     # Python 3.12 + barcha kutubxonalar (uv.lock bo'yicha aynan o'sha versiyalar)
uv run alembic upgrade head          # bazani eng oxirgi sxemaga keltirish
```

- Birinchi `uv sync` 1–3 daqiqa oladi (Python'ni ham yuklab oladi). Keyingilari tez.
- `--locked` — agar `uv.lock` `pyproject.toml` bilan mos kelmasa, xato beradi. Bu yaxshi: demak kompyuterda
  `uv lock` qilib, commit qilish esdan chiqqan.

Sinovlar (server ARM protsessorda — hamma kutubxona to'g'ri ishlayotganini tekshiramiz):

```bash
# 🐧 server (ayvona)
uv run pytest
```

Hammasi `passed` bo'lsa — zo'r. Xato bo'lsa, chiqqan matnni to'liq nusxalab Claude'ga ko'rsating.

Placeholder rasmlar (git'da yo'q, har joyda qayta chiziladi — Bosqich 6):

```bash
# 🐧 server (ayvona)
uv run python scripts/make_placeholder_images.py
```

Collector'ni **bir marta** qo'lda sinash (kanallarni bir marta o'qib, chiqib ketadi):

```bash
# 🐧 server (ayvona)
uv run python -m ayvona.apps.collector --once
```

Logda manbalar o'qilgani va yangi postlar saqlangani ko'rinsa — tayyor. Endi `exit` bilan `ubuntu` ga qayting.

---

## 10-qadam. systemd servislarni yoqish

**systemd** — Linux'ning "xizmatlar boshqaruvchisi". U dasturimizni: server yoqilganda avtomatik ishga tushiradi,
yiqilsa **10 soniyadan keyin qayta ishga tushiradi** (`Restart=always`, `RestartSec=10`), loglarni saqlaydi.

Bizda 4 ta servis (`deploy/systemd/`):

| Servis | Nima qiladi | Qachon yoqamiz |
|---|---|---|
| `ayvona-collector` | kanallar, saytlar va RSS'dan postlarni o'qiydi, bazaga yozadi | doim |
| `ayvona-worker` | postlarni qayta ishlaydi (+ ixtiyoriy Gemini), kanalga joylaydi, obuna xabarlari, muddat, 03:00 backup | doim |
| `ayvona-bot` | @ayvona_jobs_bot — ommaviy menyu va admin buyruqlari | `.env` da `BOT_TOKEN` bo'lsa |
| `ayvona-web` | o'z veb-sayti (faqat o'qiydi), 127.0.0.1:8080 | xohlasangiz, 10a-qadamdan keyin |

```bash
# 🐧 server (ubuntu)
sudo cp /home/ayvona/ayvona/deploy/systemd/ayvona-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
systemctl status ayvona-collector ayvona-worker ayvona-bot --no-pager
```
(`ayvona-web` ni hozircha yoqmang — 10a-qadamda.)

- `enable` — server qayta yoqilganda avtomatik ishga tushsin; `--now` — hozir ham ishga tushir.
- `status` da har uchalasi **`Active: active (running)`** (yashil) bo'lishi kerak. Chiqish: `q`.
- ⚠️ `BOT_TOKEN` bo'sh bo'lsa, bot xabar yozib chiqib ketadi va systemd uni har 10 soniyada qayta yoqib turadi.
  Bunday holda botni hozircha yoqmang (`enable --now` dan `ayvona-bot` ni olib tashlang). Worker esa tokensiz ham
  ishlaydi: postlarni qayta ishlaydi va navbatga qo'yadi, faqat kanalga joylamaydi.
- Uchala jarayon ham baza eng oxirgi migratsiyada bo'lmasa ishga tushmaydi (logda: "Baza tayyor emas yoki eski
  versiyada"). Yechim — `uv run alembic upgrade head` (9-qadam); `deploy.sh` buni o'zi qiladi.

**Eng muhim tekshiruv:** kompyuteringizni o'chiring — kanalga postlar baribir chiqyaptimi? (worker yoqilgandan keyin.)

Foydali buyruqlar:
```bash
# 🐧 server (ubuntu)
sudo systemctl restart ayvona-collector    # qayta ishga tushirish
sudo systemctl stop ayvona-collector       # to'xtatish (enable bo'lsa, reboot'dan keyin yana yonadi)
sudo systemctl disable ayvona-collector    # avtomatik ishga tushishni o'chirish
systemctl list-units 'ayvona-*' --all      # hamma ayvona servislarining holati
```

---

## 10a-qadam. Veb-sayt: Caddy + DuckDNS (ixtiyoriy)

Sayt (`ayvona-web`) serverda faqat `127.0.0.1:8080` da ishlaydi. Tashqi dunyoga **Caddy** chiqaradi — u bepul
HTTPS sertifikatni (Let's Encrypt) o'zi oladi va yangilab turadi. Manzil — bepul **DuckDNS** subdomeni.

1. **duckdns.org** → GitHub/Google bilan kiring → subdomen yozing (masalan `ayvona`) → **add domain** →
   `current ip` ga serverning ochiq IP'sini (`<IP>`) yozing → **update ip**. Manzil: `ayvona.duckdns.org`.
2. **Oracle saytida portlarni oching:** ☰ → Networking → Virtual Cloud Networks → (sizning VCN) → Subnet →
   Security List → **Add Ingress Rules**: Source CIDR `0.0.0.0/0`, TCP, Destination port `80`; yana bir qoida — `443`.
3. **Serverda iptables** (Oracle Ubuntu'sining o'z firewall'i):
   ```bash
   # 🐧 server (ubuntu)
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo apt install -y iptables-persistent      # "Save current rules?" — Yes
   sudo netfilter-persistent save
   ```
4. **Caddy:**
   ```bash
   # 🐧 server (ubuntu)
   sudo apt install -y caddy
   sudo cp /home/ayvona/ayvona/deploy/Caddyfile.example /etc/caddy/Caddyfile
   sudo nano /etc/caddy/Caddyfile        # "ayvona.duckdns.org" ni o'z manzilingizga almashtiring
   sudo systemctl reload caddy
   ```
5. **Sayt manzili sozlamada** (`sudo -iu ayvona`, `nano ~/ayvona/config/settings.yaml`):
   `website:` → `base_url: "https://ayvona.duckdns.org"`. (Bu fayl git'da — keyingi `git pull` da konflikt bo'lmasligi
   uchun bu o'zgarishni kompyuterda qilib, push qilganingiz ma'qul.)
6. **Servisni yoqish:**
   ```bash
   # 🐧 server (ubuntu)
   sudo systemctl enable --now ayvona-web
   curl -s http://127.0.0.1:8080/healthz      # "ok"
   ```
   Brauzerda `https://ayvona.duckdns.org` — bosh sahifa ochilishi kerak. `.../sitemap.xml` ni Google Search Console'ga
   qo'shsangiz bo'ladi (bepul).

Sayt bazadan **faqat o'qiydi** — yiqilsa ham collector/worker/bot ishlayveradi. Xotira chegarasi: 300 MB.

---

## 11-qadam. Loglarni ko'rish (journalctl)

Dastur yozgan hamma narsa (loguru → stderr) **journald** ga tushadi.

```bash
# 🐧 server (ubuntu)
journalctl -u ayvona-collector -f                    # jonli kuzatish (chiqish: Ctrl+C)
journalctl -u ayvona-collector -n 100 --no-pager     # oxirgi 100 qator
journalctl -u ayvona-collector --since "1 hour ago"  # oxirgi 1 soat
journalctl -u ayvona-collector --since today         # bugungi
journalctl -u 'ayvona-*' -f                          # uchala servis birga
journalctl -u ayvona-collector --since today | grep -iE "error|exception|traceback"   # faqat xatolar
journalctl -u ayvona-collector -b                    # oxirgi reboot'dan beri
```

- Vaqtlar Toshkent vaqtida (5.2-qadam).
- "Permission denied" desa — oldiga `sudo` qo'shing.
- Dastur shuningdek fayl loglarini `/home/ayvona/ayvona/data/logs/` ga yozadi
  (`sudo -iu ayvona` → `ls ~/ayvona/data/logs`).
- Servis yiqilib-turayotgan bo'lsa (`activating (auto-restart)`), sababini topish:
  `journalctl -u ayvona-collector -n 50 --no-pager` — eng pastdagi `Traceback` / xato qatoriga qarang.

---

## 12-qadam. Yangilash (deploy.sh)

Kompyuterda kod o'zgartirdingiz → serverga chiqarish:

```powershell
# 💻 PowerShell (kompyuter)
cd "D:\Coding projects\ayvona"
uv run pytest ; uv run ruff check .      # ikkalasi ham toza bo'lsin
git push
```

```bash
# 🐧 server (ubuntu)
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
```

`scripts/deploy.sh` o'zi hammasini qiladi:
1. `git pull` (ayvona nomidan);
2. **yoqilgan** servislarni to'xtatadi (enable qilinmagan servisga tegmaydi);
3. bazaning zaxira nusxasini oladi → `data/backups/deploy/` (oxirgi 5 tasi qoladi);
4. `uv sync --locked`;
5. `alembic upgrade head` (yangi migratsiyalar — masalan Bosqich 12–14 dagi `f2b6d8a4c1e3`, `a7c3e9f1b5d8`,
   `b8d4f0a2c6e9` — shu yerda o'zi qo'llanadi);
6. bo'sh rasm papkalariga vaqtinchalik rasmlar (borlariga tegmaydi);
7. `deploy/systemd/*.service` o'zgargan bo'lsa — `/etc/systemd/system/` ga nusxalab, `daemon-reload`
   (yangi servis — masalan `ayvona-web` — avval 10a-qadamdagidek bir marta qo'lda o'rnatiladi);
8. servislarni qayta ishga tushirib, holatini (`active`) ko'rsatadi.

Collector bir necha soniya to'xtaydi — bu xavfsiz: har manbaning `last_seen_id` sidan davom etadi, post yo'qolmaydi.

Oxirida `✅ Deploy tugadi` va har servis yonida `active` chiqishi kerak. `❌` chiqsa — xato matnini o'qing
(yoki Claude'ga ko'rsating); servislar to'xtagan holatda qolgan bo'lishi mumkin, kerak bo'lsa 13.1 bo'yicha orqaga qayting.

**Ubuntu'ni yangilash** (oyiga bir marta):
```bash
# 🐧 server (ubuntu)
sudo apt update && sudo apt upgrade -y
ls /var/run/reboot-required 2>/dev/null && sudo reboot    # kerak bo'lsa qayta yoqish; servislar o'zi yonadi
```

---

## 13-qadam. Backup'dan tiklash

Backup'lar 3 joyda bo'ladi:

| Qayerda | Nima | Kim yaratadi |
|---|---|---|
| `data/backups/deploy/ayvona-YYYYMMDD-HHMMSS.db` | har deploy'dan oldingi nusxa (oxirgi 5) | `scripts/deploy.sh` |
| `data/backups/ayvona_YYYY-MM-DD.db` | har kuni 03:00 (Toshkent), oxirgi 7 kun | worker (`services/backup.py`) |
| Admin chat (Telegram) | kunlik backup fayli (document) | worker |

Qo'lda darhol backup olish (masalan, katta o'zgarishdan oldin):
```bash
# 🐧 server (ayvona)
cd ~/ayvona
uv run python scripts/backup_now.py            # data/backups/ayvona_YYYY-MM-DD.db
uv run python scripts/backup_now.py --send     # + admin chatga ham yuboradi
```

Hammasi oddiy SQLite fayl — tiklash = faylni `data/ayvona.db` o'rniga qo'yish.

### 13.1 Yomon deploy'dan keyin orqaga qaytish (kod + baza)

```bash
# 🐧 server (ubuntu)
sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot ayvona-web
sudo -iu ayvona
```
```bash
# 🐧 server (ayvona)
cd ~/ayvona
git log --oneline -5                  # qaysi commit'ga qaytamiz? (odatda ikkinchi qator)
git reset --hard <eski_commit_hash>
ls -lt data/backups/deploy/           # eng yuqoridagisi — oxirgi deploy'dan oldingi baza
BROKEN=data/broken-$(date +%Y%m%d-%H%M) && mkdir -p "$BROKEN"
mv data/ayvona.db data/ayvona.db-wal data/ayvona.db-shm "$BROKEN"/ 2>/dev/null
cp data/backups/deploy/ayvona-<YYYYMMDD-HHMMSS>.db data/ayvona.db
uv sync --locked
uv run alembic upgrade head
exit
```
```bash
# 🐧 server (ubuntu)
sudo systemctl start ayvona-collector      # + ayvona-worker ayvona-bot, agar ular yoqilgan bo'lsa
journalctl -u ayvona-collector -n 30 --no-pager
```

- Eski (buzilgan) baza **o'chirilmaydi**, `data/broken-...` ga olinadi — keyin kerak bo'lib qolishi mumkin.
- Keyingi `deploy.sh` yana eng yangi kodni oladi — shuning uchun avval kompyuterda xatoni tuzatib, push qiling.

### 13.2 Faqat bazani tiklash (kunlik backup'dan)

Yuqoridagining o'zi, faqat `git reset` qilinmaydi va fayl `data/backups/` dan olinadi:

```bash
# 🐧 server (ayvona)   — oldin ubuntu'da: sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot
cd ~/ayvona
ls -lt data/backups/
BROKEN=data/broken-$(date +%Y%m%d-%H%M) && mkdir -p "$BROKEN"
mv data/ayvona.db data/ayvona.db-wal data/ayvona.db-shm "$BROKEN"/ 2>/dev/null
cp data/backups/ayvona_<YYYY-MM-DD>.db data/ayvona.db     # masalan ayvona_2026-10-05.db
uv run alembic upgrade head           # backup eski sxemada bo'lsa — yangilaydi
exit                                   # keyin ubuntu'da: sudo systemctl start ayvona-collector ...
```


### 13.3 Admin chatdagi backup'dan (server buzilgan/yo'qolgan bo'lsa)

1. Telegram'da admin chatdan eng oxirgi backup faylini kompyuterga yuklab oling, masalan `Downloads\ayvona-backup.db`.
2. Server butunlay yo'qolgan bo'lsa (Oracle qaytarib olgan va h.k.) — 3–7 qadamlarni qaytadan bajaring.
3. 8-qadamdagidek fayllarni yuboring, faqat baza sifatida yuklab olingan backup'ni:
   ```powershell
   # 💻 PowerShell (kompyuter)
   cd "D:\Coding projects\ayvona"
   scp .env ayvona-server:~/
   scp data\ayvona.session ayvona-server:~/
   scp "$HOME\Downloads\ayvona-backup.db" ayvona-server:~/ayvona-copy.db
   ```
   va 8.2 dagi `sudo install ...` buyruqlarini bajaring (agar server ishlab turgan bo'lsa — oldin servislarni to'xtating).
4. 9-qadam (`uv sync`, `alembic upgrade head`) → 10-qadam (servislar).

Bir necha soatlik postlar backup'da bo'lmasligi mumkin — collector kanallarni backup'dagi `last_seen_id` dan qayta
o'qiydi, dedup esa dublikatlarning oldini oladi.

> 💡 **Kompyuterda doim saqlang:** `.env` va `data\ayvona.session` nusxasi (masalan, shifrlangan fleshkada yoki
> parol menejerida). Ular git'da yo'q — yo'qolsa, tokenlarni qayta olish va Telegram'ga qayta login qilish kerak bo'ladi.

---

## 14. Muammolar va yechimlar

| Belgi | Sabab va yechim |
|---|---|
| `ssh: connect to host ... Connection timed out` | IP noto'g'rimi? Server RUNNING'mi (Oracle saytida)? Wi-Fi/provayder 22-portni to'smayaptimi — telefon internetidan sinab ko'ring. |
| `Permission denied (publickey)` | `-i "$HOME\.ssh\oracle_ayvona"` ko'rsatilganmi? Foydalanuvchi `ubuntu`mi (`root` emas)? Oracle'ga to'g'ri `.pub` joylanganmi? |
| `Bad configuration option: \357\273\277...` | `~/.ssh/config` BOM bilan saqlangan. Faylni o'chirib, 4-qadamdagi usul bilan qayta yozing. |
| `ssh -T git@github.com` → `Permission denied` | Deploy key GitHub'ga qo'shilmagan yoki `~/.ssh/config` xato. 7-qadamni takrorlang (`ayvona` foydalanuvchisida!). |
| `uv: command not found` | `source ~/.local/bin/env` yoki qayta `sudo -iu ayvona`. |
| `uv sync --locked` → lock mos emas | Kompyuterda `uv lock`, commit, push → serverda qayta. |
| Logda "Baza tayyor emas yoki eski versiyada" | `sudo -iu ayvona` → `cd ~/ayvona` → `uv run alembic upgrade head` → `sudo systemctl restart ayvona-...` (yoki shunchaki `deploy.sh`). |
| Servis `activating (auto-restart)` | Dastur yiqilyapti: `journalctl -u <servis> -n 50 --no-pager` → eng pastdagi xato. Ko'pincha `.env` da bo'sh qiymat yoki fayl yo'q. |
| Logda `AUTH_KEY_DUPLICATED` | Session ikki joyda ishlatildi va bekor bo'ldi. Kompyuterdagi collector'ni o'chiring; serverda `sudo -iu ayvona` → `cd ~/ayvona` → `uv run python scripts/login_telethon.py` → `sudo systemctl restart ayvona-collector`. |
| `TelegramConflictError` (bot) | Xuddi shu BOT_TOKEN bilan boshqa joyda (kompyuterda) bot ishlayapti — o'shani to'xtating. |
| Vaqt noto'g'ri / Telegram ulanmaydi | `timedatectl` → 5.2-qadam. |
| Disk to'lyapti | `df -h` ; `journalctl --disk-usage` ; `du -sh /home/ayvona/ayvona/data/*` (sudo bilan). |

### Idle (bo'sh server) xavfini kuzatish

1. Oracle saytida: ☰ → **Compute → Instances → ayvona-server → Monitoring** (yoki **Metrics**) bo'limi.
2. **CPU Utilization** va **Memory Utilization** grafiklariga qarang (oxirgi 7 kun).
3. Agar **Memory Utilization doim 20% dan past** bo'lsa, Claude bilan birga shape'ni kichraytirishni ko'rib chiqamiz
   (Instance → **Edit → Edit shape**, server qisqa vaqt qayta yonadi).
4. Grafiklar bo'sh bo'lsa: Instance → **Oracle Cloud Agent** tab'ida "Compute Instance Monitoring" yoqilganini tekshiring.

### Kerakli fayllar va yo'llar (eslatma)

| Nima | Qayerda (serverda) |
|---|---|
| Loyiha | `/home/ayvona/ayvona` |
| Maxfiy sozlamalar | `/home/ayvona/ayvona/.env` |
| Baza, session, loglar, backup'lar | `/home/ayvona/ayvona/data/` |
| uv | `/home/ayvona/.local/bin/uv` |
| systemd fayllar | `/etc/systemd/system/ayvona-*.service` (manbasi: `deploy/systemd/`) |
| GitHub deploy key | `/home/ayvona/.ssh/github_deploy` |

---

## Manbalar (Oracle qoidalari, 2026-09-29 da tekshirildi)

- Oracle rasmiy: [Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
  — A1 limitlari (1500 OCPU-soat / 9000 GB-soat = 2 OCPU / 12 GB), idle reclamation qoidasi, 200 GB disk, 10 TB trafik,
  "out of host capacity" bo'yicha tavsiya.
- Oracle rasmiy: [Oracle Cloud Infrastructure Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- InfoQ (2026-07): [Oracle Quietly Halves Free Tier Ampere A1 Compute Limits](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
  — 2026-06-15 dagi o'zgarish, limitdan oshgan serverlarning to'xtatilishi.
- Hacker News muhokamasi: [Oracle cut its Always Free ARM limits to 2 OCPU / 12GB, enforced Aug 18](https://news.ycombinator.com/item?id=49183750)
  — Oracle xatidan iqtibos: 2026-08-18 dan limitdan oshgan serverlar avtomatik o'chiriladi (rasmiy hujjatda sana yo'q).
