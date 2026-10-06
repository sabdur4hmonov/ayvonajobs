# DEPLOY — Ayvona Jobs'ni tayyor Oracle Cloud VM'ga qo'yish

Bu fayl **server allaqachon yaratilgan va ishlab turgan** holat uchun qisqa, buyruqma-buyruq yo'riqnoma.
Oracle akkaunt ochish, SSH kalit yaratish, "Out of capacity", backup'dan tiklash va boshqa tafsilotlar —
[deploy/SETUP_ORACLE.md](deploy/SETUP_ORACLE.md) da (u Ubuntu uchun yozilgan; bu yerda Oracle Linux ham bor).

**Arxitektura (Docker yo'q):** 4 ta Python jarayon, har biri systemd servisi — `ayvona-collector`, `ayvona-worker`,
`ayvona-bot` (majburiy) va `ayvona-web` (ixtiyoriy sayt, `127.0.0.1:8080`, oldida Caddy + Let's Encrypt).
Baza — bitta SQLite fayl (`data/ayvona.db`). Bot **long polling** ishlatadi: collector/worker/bot uchun hech qanday
kiruvchi port kerak emas. 80/443 faqat sayt uchun ochiladi.

> **Qaysi buyruq qayerda:**
> `# 💻 PowerShell` — o'z kompyuteringizda · `# 🐧 admin` — serverda oddiy foydalanuvchi
> (Ubuntu: `ubuntu`, Oracle Linux: `opc`) · `# 🐧 ayvona` — serverda `sudo -iu ayvona` dan keyin.
> `<IP>` — serverning Public IP manzili, `<domen>` — saytingiz manzili (masalan `ayvona.duckdns.org`).

> ⚠️ Bu yo'riqnoma Ubuntu 24.04 uchun loyiha muallifi tomonidan yozilgan qo'llanmaga asoslangan.
> **Oracle Linux qismlari haqiqiy serverda sinalmagan** — xato chiqsa, matnini to'liq saqlang.

---

## 0. Boshlashdan oldin (kompyuterda)

1. Serverning OS'ini va shape'ini bilib oling: OCI Console → Compute → Instances → instance → **Image** va **Shape**.
   - `VM.Standard.A1.Flex` (ARM, 6 GB+) — tavsiya etilgan.
   - `VM.Standard.E2.1.Micro` (1 GB RAM) bo'lsa — 3-qadamdagi **swap**ni albatta qo'shing.
2. Laptopdagi **collector, worker va bot'ni to'xtating** (har oynada Ctrl+C) va keyin ularni laptopda **yoqmang**:
   bitta Telethon session va bitta `BOT_TOKEN` faqat bitta joyda ishlashi mumkin
   (aks holda `AUTH_KEY_DUPLICATED` / `TelegramConflictError`).
3. Kodning hammasi GitHub'da ekanini tekshiring: `git status` toza va `git log origin/main -1` laptopdagi bilan bir xil.

---

## 1. Serverga ulanish

```powershell
# 💻 PowerShell
ssh -i "$HOME\.ssh\<kalit_fayli>" ubuntu@<IP>     # Ubuntu
ssh -i "$HOME\.ssh\<kalit_fayli>" opc@<IP>        # Oracle Linux
```

## 2. Kerakli paketlar

**Ubuntu:**
```bash
# 🐧 admin
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl sqlite3 fonts-dejavu-core fail2ban
```

**Oracle Linux 8/9:**
```bash
# 🐧 admin
sudo dnf -y update
sudo dnf install -y git curl tar sqlite dejavu-sans-fonts policycoreutils-python-utils
# fail2ban EPEL'da (ixtiyoriy). OL8 bo'lsa: oracle-epel-release-el8
sudo dnf install -y oracle-epel-release-el9 && sudo dnf install -y fail2ban && sudo systemctl enable --now fail2ban
```

## 3. Vaqt, loglar, (kerak bo'lsa) swap — ikkala OS uchun bir xil

```bash
# 🐧 admin
sudo timedatectl set-timezone Asia/Tashkent
timedatectl                         # "System clock synchronized: yes" bo'lishi kerak
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' | sudo tee /etc/systemd/journald.conf.d/ayvona.conf
sudo systemctl restart systemd-journald
```

Faqat 1 GB RAM'li server (E2.1.Micro) bo'lsa — 2 GB swap:
```bash
# 🐧 admin
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

## 4. `ayvona` foydalanuvchisi va uv

```bash
# 🐧 admin
sudo useradd --create-home --shell /bin/bash ayvona
sudo -iu ayvona
```
```bash
# 🐧 ayvona
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
which uv                            # /home/ayvona/.local/bin/uv bo'lishi SHART (systemd fayllari shu yo'lni kutadi)
exit
```

**Faqat Oracle Linux (SELinux):** systemd uy papkasidagi dasturni ishga tushirishga ruxsat bermaydi
(servis `status=203/EXEC` bilan yiqiladi). uv papkasiga "dastur" belgisini beramiz:
```bash
# 🐧 admin (Oracle Linux)
getenforce                          # "Enforcing" bo'lsa quyidagilar kerak
sudo semanage fcontext -a -t bin_t '/home/ayvona/\.local/bin(/.*)?'
sudo restorecon -Rv /home/ayvona/.local/bin
```

## 5. Kodni olish

Repo hozir **public** — oddiy `https` clone yetadi. (Keyin private qilsangiz — deploy key:
[deploy/SETUP_ORACLE.md §7](deploy/SETUP_ORACLE.md#7-qadam-private-reponi-deploy-key-bilan-clone-qilish).)

```bash
# 🐧 admin
sudo -iu ayvona git clone https://github.com/sabdur4hmonov/ayvonajobs.git /home/ayvona/ayvona
sudo -iu ayvona git -C /home/ayvona/ayvona log -1 --oneline     # laptopdagi oxirgi commit bilan bir xilmi?
```

Papka nomi aynan `/home/ayvona/ayvona` bo'lsin — systemd fayllari va `scripts/deploy.sh` shu yo'lni kutadi.

## 6. Maxfiy fayllarni ko'chirish (`.env`, session, baza)

Kompyuterda bazaning to'g'ri nusxasini oling (WAL ichidagilar ham tushadi) va yuboring:
```powershell
# 💻 PowerShell
cd "D:\Coding projects\ayvona"
uv run python -c "import sqlite3; s=sqlite3.connect('data/ayvona.db'); d=sqlite3.connect('data/ayvona-copy.db'); s.backup(d); d.close(); s.close()"
$K = "$HOME\.ssh\<kalit_fayli>"; $U = "ubuntu@<IP>"        # Oracle Linux: "opc@<IP>"
scp -i $K .env data\ayvona.session data\ayvona-copy.db "${U}:~/"
Remove-Item data\ayvona-copy.db
```

Serverda to'g'ri joyga va to'g'ri huquq bilan:
```bash
# 🐧 admin
sudo -u ayvona mkdir -p /home/ayvona/ayvona/data
sudo install -o ayvona -g ayvona -m 600 ~/.env            /home/ayvona/ayvona/.env
sudo install -o ayvona -g ayvona -m 600 ~/ayvona.session  /home/ayvona/ayvona/data/ayvona.session
sudo install -o ayvona -g ayvona -m 600 ~/ayvona-copy.db  /home/ayvona/ayvona/data/ayvona.db
rm ~/.env ~/ayvona.session ~/ayvona-copy.db
```

`.env` ni tekshiring (`sudo -iu ayvona nano ~/ayvona/.env`). Majburiy: `API_ID`, `API_HASH`, `BOT_TOKEN`,
`CHANNEL_ID` (haqiqiy kanal), `ADMIN_IDS`, `ADMIN_CHAT_ID`. Ixtiyoriy: `GEMINI_API_KEY`, `HH_ACCESS_TOKEN`,
`HH_USER_AGENT`. To'liq ro'yxat va izohlar — [.env.example](.env.example).

> Session'ni ko'chirmasdan, serverda yangi login ham mumkin (7-qadamdagi `uv sync` dan keyin):
> `uv run python scripts/login_telethon.py` — Telegram yuborgan kodni kiritasiz.

## 7. Kutubxonalar, migratsiya, tekshiruv

```bash
# 🐧 admin
sudo -iu ayvona
```
```bash
# 🐧 ayvona
cd ~/ayvona
uv sync --locked                                  # Python 3.12 + kutubxonalar (1–3 daqiqa)
uv run alembic upgrade head                       # baza sxemasi: oxirida "b8d4f0a2c6e9 (head)"
uv run alembic current
uv run python scripts/make_placeholder_images.py  # vaqtinchalik post rasmlari (haqiqiylari yo'q bo'lsa)
uv run python -m ayvona.apps.collector --once     # kanallarni bir marta o'qib chiqadi — xatosiz tugashi kerak
uv run python scripts/show_status.py              # manbalar, heartbeat, oxirgi postlar
exit
```
(Xohlasangiz `uv run pytest` — 860 ta test, 5–6 daqiqa; kichik serverda sekin bo'ladi.)

## 8. systemd servislar (ishga tushirish + avtomatik qayta yonish)

```bash
# 🐧 admin
sudo cp /home/ayvona/ayvona/deploy/systemd/ayvona-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
systemctl status ayvona-collector ayvona-worker ayvona-bot --no-pager
```

Har uchalasi `active (running)` bo'lishi kerak. Servislar: `Restart=always`, `RestartSec=10` (yiqilsa 10 s da
qayta yonadi), server reboot bo'lsa o'zi yonadi. Loglar: `journalctl -u 'ayvona-*' -f`.

**Sog'liq tekshiruvi:** jarayonlar har daqiqada bazaga heartbeat yozadi; worker ularni kuzatadi va biri jim qolsa
admin chatga xabar yuboradi. Botda admin sifatida `/stats` — navbat, xatolar, heartbeat'lar.

---

## 9. (Ixtiyoriy) Veb-sayt: domen + HTTPS (Let's Encrypt)

### 9.1 Domen
- Bepul: **duckdns.org** → subdomen → `current ip` = `<IP>`.
- O'z domeningiz bo'lsa: DNS'da `A` yozuv `<domen>` → `<IP>`.
- Tekshirish: `nslookup <domen>` serverning IP'sini qaytarsin (Caddy sertifikat olishi uchun shart).

### 9.2 OCI tarmog'ida 80 va 443 ni ochish
OCI'da trafik **Security List** yoki **NSG** (Network Security Group) qoidalaridan biri ruxsat bersa o'tadi.
Qaysi biri ishlatilayotganini bilish: Instance → **Attached VNICs** → VNIC → *Network security groups* (bo'sh bo'lsa —
faqat Security List).

- **Security List:** ☰ → Networking → Virtual cloud networks → VCN → **Subnets** → public subnet →
  **Security Lists** → Default Security List → **Add Ingress Rules**:
  Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port Range `80`. Yana bitta qoida — `443`.
- **NSG ishlatilsa:** ☰ → Networking → Virtual cloud networks → VCN → **Network Security Groups** → NSG →
  **Add Rules** → Ingress, Source CIDR `0.0.0.0/0`, TCP, port `80`; yana bitta — `443`.

### 9.3 Server ichidagi firewall

**Ubuntu** (Oracle image'ida iptables qoidalari bor; `ufw` ni YOQMANG — SSH'dan qulflanib qolasiz):
```bash
# 🐧 admin (Ubuntu)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo apt install -y iptables-persistent          # "Save current rules?" → Yes
sudo netfilter-persistent save
sudo iptables -L INPUT -n --line-numbers         # 80 va 443 oxirgi REJECT qatoridan YUQORIDA bo'lsin
```

**Oracle Linux** (firewalld):
```bash
# 🐧 admin (Oracle Linux)
sudo firewall-cmd --permanent --add-service=http --add-service=https
sudo firewall-cmd --reload
sudo firewall-cmd --list-services                # http https ssh ...
```

### 9.4 Caddy (reverse proxy + avtomatik Let's Encrypt sertifikat)

**Ubuntu:**
```bash
# 🐧 admin (Ubuntu)
sudo apt install -y caddy
```

**Oracle Linux** (Caddy rasmiy COPR reposi; sinalmagan — ishlamasa caddyserver.com/docs/install):
```bash
# 🐧 admin (Oracle Linux)
sudo dnf install -y 'dnf-command(copr)'
sudo dnf copr enable -y @caddy/caddy epel-9-$(arch)     # OL8: epel-8-$(arch)
sudo dnf install -y caddy
sudo setsebool -P httpd_can_network_connect 1           # SELinux: Caddy 127.0.0.1:8080 ga ulana olsin
```

Ikkala OS:
```bash
# 🐧 admin
sudo cp /home/ayvona/ayvona/deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo sed -i 's/ayvona\.duckdns\.org/<domen>/' /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy && sudo systemctl reload caddy
```

### 9.5 Sayt servisi
1. `config/settings.yaml` → `website.base_url: "https://<domen>"` — **kompyuterda** o'zgartirib, commit + push qiling
   (serverda tahrirlasangiz keyingi `git pull` to'xtab qoladi). Keyin serverda 10-qadamdagi `deploy.sh`.
2. Servisni yoqish:
```bash
# 🐧 admin
sudo systemctl enable --now ayvona-web
curl -s http://127.0.0.1:8080/healthz             # "ok"
curl -sI https://<domen> | head -1                # "HTTP/2 200"
```

---

## 10. Yangilash (keyingi deploy'lar)

```powershell
# 💻 PowerShell — o'zgarishlarni main'ga push qiling
uv run pytest ; uv run ruff check .
git push
```
```bash
# 🐧 admin
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
```
`deploy.sh`: `git pull --ff-only` → yoqilgan servislarni to'xtatadi → baza zaxirasi (`data/backups/deploy/`, oxirgi 5)
→ `uv sync --locked` → `alembic upgrade head` → o'zgargan systemd fayllarni yangilaydi → servislarni qayta yoqadi.
Oxirida `✅ Deploy tugadi` va har servis yonida `active`. Orqaga qaytish: [deploy/SETUP_ORACLE.md §13](deploy/SETUP_ORACLE.md).

> Server `main` branch'idan yangilanadi. Boshqa branch'dagi o'zgarishlar (masalan `deploy-ready`) avval `main` ga
> merge qilinishi kerak.

## 11. Tez-tez uchraydigan muammolar

| Belgi | Yechim |
|---|---|
| Servis `status=203/EXEC` (Oracle Linux) | SELinux — 4-qadamdagi `semanage` + `restorecon`. |
| Logda "Baza tayyor emas yoki eski versiyada" | `sudo -iu ayvona` → `cd ~/ayvona && uv run alembic upgrade head` → servisni restart. |
| `AUTH_KEY_DUPLICATED` | Session ikki joyda ishladi. Laptopdagi collector'ni o'chiring; serverda `uv run python scripts/login_telethon.py`. |
| `TelegramConflictError` | Shu `BOT_TOKEN` bilan boshqa joyda bot ishlayapti — o'shani to'xtating. |
| Bot har 10 s qayta yonyapti | `.env` da `BOT_TOKEN` bo'sh — to'ldiring yoki `ayvona-bot` ni o'chirib turing. |
| Sayt ochilmaydi | `nslookup <domen>`; OCI 80/443 (9.2); server firewall (9.3); `journalctl -u caddy -n 50`. |
| Caddy sertifikat ololmayapti | 80-port tashqaridan ochiq bo'lishi va domen `<IP>` ga qarashi shart. |
| Xotira tugayapti (1 GB server) | 3-qadamdagi swap; `ayvona-web` ni o'chirib turing. |
