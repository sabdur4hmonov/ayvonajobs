#!/usr/bin/env bash
# =====================================================================
#  Ayvona Jobs — YANGI Ubuntu 24.04 serverni tayyorlash (Oracle Cloud Always Free, VM.Standard.E2.1.Micro,
#  1 GB RAM). Bir marta ishga tushiriladi; qayta ishga tushirsa ham xavfsiz (har qadam avval tekshiradi).
#
#  Ishlatish (serverda, standart `ubuntu` foydalanuvchida — sudo bilan):
#    curl -fsSLO https://raw.githubusercontent.com/sabdur4hmonov/ayvonajobs/main/scripts/server-setup.sh
#    bash server-setup.sh
#  Veb-sayt bilan (ixtiyoriy, qo'shimcha ~100 MB xotira + Caddy):
#    bash server-setup.sh --with-web --domain ayvona.duckdns.org
#
#  Bayroqlar:
#    --with-web             veb-sayt servisini va Caddy'ni (avtomatik HTTPS) o'rnatadi; 80/443 ni ochadi
#    --domain NOM           --with-web bilan majburiy: sayt manzili (masalan ayvona.duckdns.org)
#    --with-fail2ban        SSH'ga parol terib buzishga urinishlarni bloklaydi (ixtiyoriy)
#    --swap-gb N            swap fayl hajmi (standart 2); swap allaqachon bo'lsa tegilmaydi
#    --branch NOM           qaysi git branch (standart main)
#    --repo URL             repo manzili (standart public HTTPS)
#    --skip-upgrade         `apt upgrade` ni o'tkazib yuboradi
#
#  Nima qiladi (tartib bilan): swap + vm.swappiness=10 · apt yangilash + paketlar · vaqt zonasi
#  Asia/Tashkent · journald hajmi cheklovi · `ayvona` foydalanuvchisi · uv · repo clone ·
#  `uv sync --locked --no-dev --compile-bytecode` · alembic migratsiyalari · systemd unitlar ·
#  OOM himoyasi (sshd o'ldirilmasin) · firewall (faqat 22; --with-web bilan 80/443) · unattended-upgrades.
#
#  Nima QILMAYDI: servislarni yoqmaydi/ishga tushirmaydi (avval .env, session va baza kerak —
#  scripts/push-secrets-from-windows.ps1), sshd sozlamalariga tegmaydi, hech qanday maxfiy narsa so'ramaydi.
# =====================================================================

# Butun skript main() ichida: bash avval hammasini o'qib oladi, shuning uchun `git pull` shu faylni
# yangilasa ham, ish o'rtasida buzilmaydi.
main() {
    set -Eeuo pipefail

    local app_user="ayvona"
    local app_home="/home/${app_user}"
    local app_dir="${app_home}/ayvona"
    local uv="${app_home}/.local/bin/uv"
    local repo="https://github.com/sabdur4hmonov/ayvonajobs.git"
    local branch="main"
    local swap_gb=2
    local with_web=0 domain="" with_fail2ban=0 skip_upgrade=0

    while (($#)); do
        case "$1" in
            --with-web) with_web=1 ;;
            --domain) domain="${2:-}"; shift ;;
            --with-fail2ban) with_fail2ban=1 ;;
            --swap-gb) swap_gb="${2:-}"; shift ;;
            --branch) branch="${2:-}"; shift ;;
            --repo) repo="${2:-}"; shift ;;
            --skip-upgrade) skip_upgrade=1 ;;
            -h | --help) sed -n '2,32p' "${BASH_SOURCE[0]}" 2>/dev/null | sed 's/^# \{0,1\}//'; return 0 ;;
            *) echo "❌ noma'lum bayroq: $1  (--help)" >&2; return 2 ;;
        esac
        shift
    done

    # ------------------------------------------------------------ yordamchilar
    local SUDO=""
    [[ "${EUID}" -ne 0 ]] && SUDO="sudo"
    step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
    info() { printf '    %s\n' "$*"; }
    warn() { printf '    \033[33m⚠️  %s\033[0m\n' "$*"; WARNINGS+=("$*"); }
    local -a WARNINGS=()
    as_app() { ${SUDO} -u "${app_user}" -H -- bash -c 'cd "$HOME" && exec "$@"' _ "$@"; }
    # sudo muhit o'zgaruvchilarini tashlab yuboradi, shuning uchun `env` bilan beramiz; yangi VM'da
    # unattended-upgrades dpkg qulfini birinchi daqiqalarda ushlab turadi — 5 daqiqagacha kutamiz.
    apt() {
        ${SUDO} env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 \
            apt-get -o DPkg::Lock::Timeout=300 -y "$@"
    }
    in_app_dir() { ${SUDO} -u "${app_user}" -H -- bash -c 'cd "$1" && shift && exec "$@"' _ "${app_dir}" "$@"; }

    trap 'echo; echo "❌ Xato (qator ${LINENO}). Yuqoridagi xabarni o'"'"'qing; tuzatib, skriptni qayta ishga tushiring — u qolgan joyidan davom etadi." >&2' ERR

    # ------------------------------------------------------------ tekshiruvlar
    step "0/14 Tekshiruvlar"
    if ((with_web)) && [[ ! "${domain}" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$ ]]; then
        echo "❌ --with-web uchun --domain kerak (masalan: --domain ayvona.duckdns.org)" >&2
        return 2
    fi
    [[ "${swap_gb}" =~ ^[0-9]+$ ]] || { echo "❌ --swap-gb butun son bo'lsin" >&2; return 2; }
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        if [[ "${ID:-}" != "ubuntu" ]]; then
            echo "❌ Bu skript Ubuntu uchun (siz: ${PRETTY_NAME:-?}). Oracle Linux: DEPLOY.md oxiridagi ilova." >&2
            return 1
        fi
        [[ "${VERSION_ID:-}" == "24.04" ]] || warn "Ubuntu ${VERSION_ID:-?} — skript 24.04 uchun sinalgan, davom etamiz"
    fi
    if [[ -n "${SUDO}" ]] && ! sudo -n true 2>/dev/null; then
        info "sudo parol so'rashi mumkin (Oracle Ubuntu'da odatda so'ramaydi)"
        sudo -v
    fi
    local mem_mb disk_free_gb
    mem_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
    disk_free_gb="$(df -BG --output=avail / | tail -n 1 | tr -dc '0-9')"
    info "server: $(uname -m), RAM ${mem_mb} MB, bo'sh disk ${disk_free_gb} GB"
    ((disk_free_gb >= 5)) || { echo "❌ Diskda kamida 5 GB bo'sh joy kerak" >&2; return 1; }

    # ------------------------------------------------------------ swap
    step "1/14 Swap (${swap_gb} GB) va vm.swappiness=10"
    if swapon --show --noheadings | grep -q .; then
        info "swap allaqachon bor — tegilmaydi:"
        swapon --show | sed 's/^/      /'
    elif ((swap_gb == 0)); then
        warn "swap o'chirilgan (--swap-gb 0): 1 GB serverda OOM xavfi yuqori"
    else
        local swapfile="/swapfile"
        if [[ ! -f "${swapfile}" ]]; then
            ${SUDO} fallocate -l "${swap_gb}G" "${swapfile}" || ${SUDO} dd if=/dev/zero of="${swapfile}" bs=1M count="$((swap_gb * 1024))" status=none
            ${SUDO} chmod 600 "${swapfile}"
            ${SUDO} mkswap "${swapfile}" >/dev/null
        fi
        ${SUDO} swapon "${swapfile}"
        grep -qE '^/swapfile[[:space:]]' /etc/fstab || echo "/swapfile none swap sw 0 0" | ${SUDO} tee -a /etc/fstab >/dev/null
        info "swap yaratildi va fstab'ga yozildi (qayta yoqilganda ham qoladi)"
    fi
    printf 'vm.swappiness=10\nvm.vfs_cache_pressure=50\n' | ${SUDO} tee /etc/sysctl.d/99-ayvona.conf >/dev/null
    ${SUDO} sysctl -q -p /etc/sysctl.d/99-ayvona.conf
    info "swappiness=$(cat /proc/sys/vm/swappiness)"

    # ------------------------------------------------------------ apt
    step "2/14 Paketlar (apt)"
    apt update
    if ((skip_upgrade)); then
        info "apt upgrade o'tkazib yuborildi (--skip-upgrade)"
    else
        apt upgrade -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold
    fi
    # Kompilyator kerak emas: hamma kutubxona tayyor (wheel) holda keladi, pyaes — sof Python.
    apt install --no-install-recommends \
        git curl ca-certificates gnupg sqlite3 unattended-upgrades fonts-dejavu-core iptables-persistent
    if ((with_fail2ban)); then
        apt install --no-install-recommends fail2ban
        ${SUDO} systemctl enable --now fail2ban
        info "fail2ban yoqildi (sshd jail standart)"
    fi

    # ------------------------------------------------------------ vaqt zonasi, journald
    step "3/14 Vaqt zonasi (Asia/Tashkent) va journald hajmi"
    ${SUDO} timedatectl set-timezone Asia/Tashkent
    info "$(timedatectl show -p Timezone -p NTPSynchronized | tr '\n' ' ')"
    ${SUDO} mkdir -p /etc/systemd/journald.conf.d
    printf '[Journal]\nSystemMaxUse=200M\nRuntimeMaxUse=50M\nMaxRetentionSec=14day\n' \
        | ${SUDO} tee /etc/systemd/journald.conf.d/ayvona.conf >/dev/null
    ${SUDO} systemctl restart systemd-journald
    info "journald: ko'pi bilan 200 MB (disk to'lmaydi); fayl loglari 14 kundan keyin o'zi o'chadi"

    # ------------------------------------------------------------ foydalanuvchi
    step "4/14 '${app_user}' foydalanuvchisi"
    if id "${app_user}" >/dev/null 2>&1; then
        info "bor"
    else
        ${SUDO} useradd --create-home --shell /bin/bash "${app_user}"
        info "yaratildi (parolsiz, faqat sudo -iu ${app_user} orqali kiriladi)"
    fi

    # ------------------------------------------------------------ uv
    step "5/14 uv (Python menejeri)"
    if [[ -x "${uv}" ]]; then
        info "bor: $(as_app "${uv}" --version)"
    else
        as_app bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
        info "o'rnatildi: $(as_app "${uv}" --version)"
    fi

    # ------------------------------------------------------------ repo
    step "6/14 Kod (${repo}, branch ${branch})"
    if [[ -d "${app_dir}/.git" ]]; then
        in_app_dir git fetch --quiet origin "${branch}"
        in_app_dir git checkout --quiet "${branch}"
        in_app_dir git pull --ff-only --quiet origin "${branch}"
        info "yangilandi"
    else
        as_app git clone --quiet --branch "${branch}" "${repo}" "${app_dir}"
        info "clone qilindi"
    fi
    info "$(in_app_dir git log -1 --oneline)"

    # ------------------------------------------------------------ python
    step "7/14 Python va kutubxonalar (uv sync --locked --no-dev --compile-bytecode)"
    # --no-dev: pytest/ruff kerak emas. --compile-bytecode: .pyc oldindan tayyor — aks holda har yangi
    # kutubxona birinchi ishga tushganda ~100 MB qo'shimcha xotira ishlatib kompilyatsiya qiladi (o'lchandi).
    in_app_dir "${uv}" sync --locked --no-dev --compile-bytecode
    info "$(in_app_dir .venv/bin/python --version)"

    # ------------------------------------------------------------ data, migratsiya
    step "8/14 data/ papkasi, baza migratsiyalari, vaqtinchalik rasmlar"
    in_app_dir mkdir -p data/logs data/backups
    in_app_dir chmod 700 data
    in_app_dir .venv/bin/alembic upgrade head 2>&1 | tail -n 3
    in_app_dir .venv/bin/python scripts/make_placeholder_images.py | tail -n 1
    info "Eslatma: bu yerda bo'sh baza yaratildi (agar yo'q bo'lsa). Haqiqiy bazani kompyuterdan"
    info "push-secrets-from-windows.ps1 yuboradi va bo'sh bazani almashtiradi."

    # ------------------------------------------------------------ systemd
    step "9/14 systemd unitlar (yoqilmaydi, ishga tushirilmaydi)"
    local f changed=0
    for f in "${app_dir}"/deploy/systemd/ayvona-*.service "${app_dir}"/deploy/systemd/ayvona-*.timer; do
        [[ -f "${f}" ]] || continue
        if ! cmp -s "${f}" "/etc/systemd/system/$(basename "${f}")"; then
            ${SUDO} install -m 644 "${f}" "/etc/systemd/system/$(basename "${f}")"
            changed=1
        fi
    done
    ${SUDO} systemctl daemon-reload
    ${SUDO} systemctl enable ayvona-backup.timer >/dev/null 2>&1
    ${SUDO} systemctl start ayvona-backup.timer
    info "o'rnatildi: collector, worker, bot, web, backup (kunlik zaxira taymeri yoqildi)"
    if ((changed)); then info "unit fayllar yangilandi"; fi

    # ------------------------------------------------------------ OOM himoyasi
    step "10/14 OOM himoyasi: xotira tugasa sshd emas, ilova servislari o'ldiriladi"
    ${SUDO} mkdir -p /etc/systemd/system/ssh.service.d
    printf '[Service]\nOOMScoreAdjust=-900\n' | ${SUDO} tee /etc/systemd/system/ssh.service.d/ayvona-oom.conf >/dev/null
    ${SUDO} systemctl daemon-reload
    local sshd_pid
    sshd_pid="$(pgrep -o -x sshd || true)"
    if [[ -n "${sshd_pid}" ]]; then
        echo -900 | ${SUDO} tee "/proc/${sshd_pid}/oom_score_adj" >/dev/null || true
        info "ishlab turgan sshd (pid ${sshd_pid}) oom_score_adj=$(cat "/proc/${sshd_pid}/oom_score_adj" 2>/dev/null || echo '?')"
    fi
    info "servislar: OOMScoreAdjust=500 + MemoryHigh/MemoryMax (deploy/systemd/*.service)"

    # ------------------------------------------------------------ firewall
    step "11/14 Firewall (iptables)"
    # Oracle'ning Ubuntu image'i: INPUT zanjirida ESTABLISHED, icmp, lo, 22-port, oxirida REJECT bor.
    # Hech narsani o'chirmaymiz va `ufw` YOQMAYMIZ — faqat kerakli ACCEPT qoidasini REJECT'dan OLDIN qo'shamiz.
    # Qoida bor-yo'qligini `iptables -S` matnidan qidiramiz (`-C` qoidadagi modullar tartibiga sezgir).
    port_open() { ${SUDO} iptables -S INPUT | grep -Eq -- "--dport $1 .*-j ACCEPT"; }
    ensure_port() {
        local port="$1"
        if port_open "${port}"; then
            info "port ${port}: allaqachon ochiq"
            return 0
        fi
        local pos
        pos="$(${SUDO} iptables -L INPUT --line-numbers -n | awk '$2 == "REJECT" || $2 == "DROP" {print $1; exit}')"
        if [[ -n "${pos}" ]]; then
            ${SUDO} iptables -I INPUT "${pos}" -m state --state NEW -p tcp --dport "${port}" -j ACCEPT
        else
            ${SUDO} iptables -A INPUT -m state --state NEW -p tcp --dport "${port}" -j ACCEPT
        fi
        info "port ${port}: ochildi"
    }
    if port_open 22; then
        info "22 (SSH): ochiq"
    else
        warn "iptables'da 22-port qoidasi topilmadi — tegmadim (SSH'dan qulflanib qolmaslik uchun). Tekshiring: sudo iptables -L INPUT -n"
    fi
    if ((with_web)); then
        ensure_port 80
        ensure_port 443
    else
        info "80/443 ochilmaydi (--with-web yo'q) — bot va collector kiruvchi port talab qilmaydi"
    fi
    ${SUDO} netfilter-persistent save >/dev/null
    info "qoidalar saqlandi (/etc/iptables/rules.v4) — qayta yoqilganda ham qoladi"
    ${SUDO} iptables -L INPUT -n --line-numbers | sed 's/^/      /'

    # ------------------------------------------------------------ SSH tekshiruvi
    step "12/14 SSH tekshiruvi (o'zgartirilmaydi)"
    local pw
    pw="$(${SUDO} sshd -T 2>/dev/null | awk '/^passwordauthentication/ {print $2}')"
    if [[ "${pw}" == "no" ]]; then
        info "parol bilan kirish o'chiq (faqat SSH kalit) ✔"
    else
        warn "SSH'da parol bilan kirish YOQILGAN (${pw:-unknown}). Kalit bilan kirishingizga ishonch hosil qilgach /etc/ssh/sshd_config.d/ ga PasswordAuthentication no yozing — skript bunga tegmaydi (qulflanib qolmaslik uchun)."
    fi

    # ------------------------------------------------------------ unattended-upgrades
    step "13/14 Avtomatik xavfsizlik yangilanishlari (unattended-upgrades)"
    printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
        | ${SUDO} tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
    info "yoqildi (server o'zi qayta yoqilmaydi: Automatic-Reboot standart o'chiq)"

    # ------------------------------------------------------------ web (ixtiyoriy)
    step "14/14 Veb-sayt (Caddy + HTTPS)"
    if ((with_web)); then
        if ! command -v caddy >/dev/null; then
            if curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | ${SUDO} gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
                && curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | ${SUDO} tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null \
                && apt update && apt install caddy; then
                info "Caddy rasmiy repodan o'rnatildi"
            else
                warn "Caddy rasmiy repodan o'rnatilmadi — Ubuntu paketi bilan urinaman"
                apt install caddy
            fi
        fi
        ${SUDO} install -m 644 "${app_dir}/deploy/Caddyfile.example" /etc/caddy/Caddyfile
        ${SUDO} sed -i "s/ayvona\\.duckdns\\.org/${domain}/g" /etc/caddy/Caddyfile
        if ! caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
            warn "Caddyfile tekshiruvdan o'tmadi — qo'lda ko'ring: caddy validate --config /etc/caddy/Caddyfile"
        fi
        ${SUDO} systemctl enable caddy >/dev/null 2>&1
        ${SUDO} systemctl restart caddy
        # Saytning ochiq manzili (canonical/sitemap) — .env kompyuterdan keladi, shuning uchun systemd drop-in'da.
        ${SUDO} mkdir -p /etc/systemd/system/ayvona-web.service.d
        printf '[Service]\nEnvironment=WEBSITE_BASE_URL=https://%s\n' "${domain}" \
            | ${SUDO} tee /etc/systemd/system/ayvona-web.service.d/domain.conf >/dev/null
        ${SUDO} systemctl daemon-reload
        info "Caddy sozlandi: https://${domain} -> 127.0.0.1:8080. ayvona-web hali yoqilmagan (pastdagi qadamlarda)."
        warn "OCI konsolida 80 va 443 uchun Ingress qoidasi (Security List yoki NSG) kerak — aks holda sertifikat olinmaydi. DuckDNS'da ${domain} serverning ochiq IP'siga qarasin."
    else
        info "o'tkazib yuborildi (--with-web yo'q): sayt va Caddy o'rnatilmadi, xotira tejaldi"
    fi

    trap - ERR

    # ------------------------------------------------------------ yakun
    local web_cmd="" web_check=""
    if ((with_web)); then
        web_cmd=" ayvona-web"
        web_check="
     curl -s http://127.0.0.1:8080/healthz ; echo      # \"ok\"
     curl -sI https://${domain} | head -n 1             # HTTP/2 200"
    fi
    echo
    echo "======================================================================"
    echo " ✅ Server tayyor. Servislar HALI ISHGA TUSHMAGAN — sabab: .env, session va baza kerak."
    echo "======================================================================"
    if ((${#WARNINGS[@]})); then
        echo " Ogohlantirishlar:"
        printf '   - %s\n' "${WARNINGS[@]}"
        echo
    fi
    if [[ -f /var/run/reboot-required ]]; then
        echo " ⚠️  Yangilanishdan keyin qayta yoqish kerak:  sudo reboot   (1 daqiqadan so'ng qayta ulaning)"
        echo
    fi
    cat <<EOF
 KEYINGI QADAMLAR
  1) OCI konsolida (cloud.oracle.com): Instance -> VCN -> Security List (yoki NSG) -> Ingress.
     Hozircha faqat 22 (SSH) kerak — u standart holatda ochiq.$( ((with_web)) && echo "
     --with-web uchun 80 va 443 (TCP, 0.0.0.0/0) QO'SHING.")
  2) Kompyuterda (Windows PowerShell), loyiha papkasida — .env, session va bazani yuboring:
       cd "D:\\Coding projects\\ayvona"
       .\\scripts\\push-secrets-from-windows.ps1 -HostName <IP> -KeyFile "\$HOME\\.ssh\\<kalit>"
  3) Serverda servislarni yoqing:
       sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot${web_cmd}
  4) Tekshiring (1–2 daqiqadan keyin):
       sudo bash ${app_dir}/scripts/healthcheck.sh${web_check}
       journalctl -u 'ayvona-*' -f          # jonli loglar (chiqish: Ctrl+C)
  5) Yangilash keyinroq:  sudo bash ${app_dir}/scripts/deploy.sh
 Hammasi: ${app_dir}/DEPLOY.md
EOF
}

main "$@"
