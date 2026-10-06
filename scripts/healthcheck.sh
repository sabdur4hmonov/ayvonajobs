#!/usr/bin/env bash
# =====================================================================
#  Ayvona Jobs — serverning sog'lig'ini tekshirish (bir ekranda).
#
#    sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
#
#  (sudo kerak: /home/ayvona boshqa foydalanuvchiga yopiq. Baza va zaxira papkasi esa `ayvona`
#  foydalanuvchisi nomidan o'qiladi: root'ning o'zi SQLite'ni ochsa, root egali -shm fayl qolib,
#  servislarni buzishi mumkin.)
#
#  Ko'rsatadi: servislar (systemd), xotira va swap, disk, bazadagi oxirgi faollik (collector sikli,
#  heartbeat'lar, oxirgi o'qilgan va oxirgi kanalga chiqqan e'lon, navbat).
#  Chiqish kodi: 0 = hammasi joyida (ogohlantirishlar bo'lishi mumkin), 1 = muammo bor.
#  Hech narsani o'zgartirmaydi (baza faqat o'qish rejimida ochiladi).
# =====================================================================
set -u

APP_DIR="${APP_DIR:-/home/ayvona/ayvona}"
HEARTBEAT_STALE_MIN="${HEARTBEAT_STALE_MIN:-10}"   # config: monitoring.heartbeat_stale_minutes
CYCLE_STALE_MIN="${CYCLE_STALE_MIN:-15}"
PROBLEMS=0
WARNINGS=0

# data/ papkasi (huquq 700) va bazaga faqat `ayvona` kira oladi: boshqa foydalanuvchi bo'lsak, shunday ochamiz.
AS_APP=()
if [[ "$(id -un)" != "ayvona" ]] && id ayvona >/dev/null 2>&1; then
    AS_APP=(sudo -n -u ayvona)
fi
as_app() { "${AS_APP[@]}" "$@"; }

red()   { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }
yellow(){ printf '\033[33m%s\033[0m' "$1"; }
ok()    { echo "  $(green OK)    $1"; }
warn()  { echo "  $(yellow WARN)  $1"; WARNINGS=$((WARNINGS + 1)); }
bad()   { echo "  $(red FAIL)  $1"; PROBLEMS=$((PROBLEMS + 1)); }

now_s="$(date -u +%s)"

# "2026-10-02 14:18:23.65" yoki "2026-10-02T14:18:23+00:00" (UTC) -> necha daqiqa oldin
age_min() {
    local ts="${1:0:19}"
    ts="${ts/T/ }"
    local then_s
    then_s="$(date -u -d "${ts} UTC" +%s 2>/dev/null)" || { echo -1; return; }
    echo $(((now_s - then_s) / 60))
}
human() {  # daqiqa -> "5 daqiqa" / "3.2 soat" / "2.1 kun"
    local m="$1"
    if ((m < 0)); then echo "noma'lum"
    elif ((m < 120)); then echo "${m} daqiqa oldin"
    elif ((m < 2880)); then awk -v m="$m" 'BEGIN{printf "%.1f soat oldin", m/60}'
    else awk -v m="$m" 'BEGIN{printf "%.1f kun oldin", m/1440}'
    fi
}

echo "== Ayvona healthcheck  $(date '+%F %T %Z')  host: $(hostname)"

# ---------------------------------------------------------------- servislar
echo
echo "Servislar:"
for unit in ayvona-collector ayvona-worker ayvona-bot; do
    state="$(systemctl is-active "${unit}" 2>/dev/null || true)"
    mem="$(systemctl show -p MemoryCurrent --value "${unit}" 2>/dev/null || true)"
    if [[ "${mem}" =~ ^[0-9]+$ ]]; then mem="$((mem / 1024 / 1024)) MB"; else mem="-"; fi
    restarts="$(systemctl show -p NRestarts --value "${unit}" 2>/dev/null || echo 0)"
    if [[ "${state}" == "active" ]]; then
        ok "${unit}: active (xotira ${mem}, qayta yonishlar: ${restarts})"
        [[ "${restarts}" =~ ^[0-9]+$ && "${restarts}" -ge 5 ]] && warn "${unit}: ${restarts} marta qayta yongan — journalctl -u ${unit} -n 50"
    else
        bad "${unit}: ${state:-unknown} — sudo systemctl status ${unit}; journalctl -u ${unit} -n 50 --no-pager"
    fi
done
# Ixtiyoriy: faqat yoqilgan bo'lsa tekshiriladi
for unit in ayvona-web caddy; do
    if systemctl is-enabled --quiet "${unit}" 2>/dev/null; then
        state="$(systemctl is-active "${unit}" 2>/dev/null || true)"
        [[ "${state}" == "active" ]] && ok "${unit}: active" || bad "${unit}: ${state}"
    fi
done
if systemctl is-enabled --quiet ayvona-backup.timer 2>/dev/null; then
    next="$(systemctl list-timers ayvona-backup.timer --no-legend 2>/dev/null | awk '{print $1, $2}' | head -n 1)"
    ok "ayvona-backup.timer: yoqilgan (keyingisi: ${next:-?})"
else
    warn "ayvona-backup.timer yoqilmagan — kunlik zaxira olinmayapti (sudo systemctl enable --now ayvona-backup.timer)"
fi
last_backup="$(as_app bash -c 'ls -1t "$1"/data/backups/daily/ayvona-*.db.gz 2>/dev/null | head -n 1' _ "${APP_DIR}" || true)"
if [[ -n "${last_backup}" ]]; then
    b_age=$(((now_s - $(as_app stat -c %Y "${last_backup}")) / 60))
    if ((b_age > 2 * 24 * 60)); then warn "oxirgi zaxira $(human "${b_age}") (${last_backup##*/})"; else ok "oxirgi zaxira $(human "${b_age}") (${last_backup##*/})"; fi
else
    warn "hali kunlik zaxira yo'q (data/backups/daily/)"
fi

# ---------------------------------------------------------------- xotira, swap, disk
echo
echo "Xotira va disk:"
read -r mem_total mem_avail < <(awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {print int(t/1024), int(a/1024)}' /proc/meminfo)
read -r swap_total swap_free < <(awk '/SwapTotal/ {t=$2} /SwapFree/ {f=$2} END {print int(t/1024), int(f/1024)}' /proc/meminfo)
swap_used=$((swap_total - swap_free))
if ((mem_avail < 80)); then bad "bo'sh xotira: ${mem_avail} MB / ${mem_total} MB (OOM xavfi)"; else ok "bo'sh xotira: ${mem_avail} MB / ${mem_total} MB"; fi
if ((swap_total == 0)); then
    bad "swap yo'q — 1 GB serverda shart (scripts/server-setup.sh yaratadi)"
elif ((swap_used > swap_total * 3 / 4)); then
    warn "swap deyarli to'la: ${swap_used} / ${swap_total} MB"
else
    ok "swap: ${swap_used} / ${swap_total} MB ishlatilgan"
fi
disk_pct="$(df --output=pcent / | tail -n 1 | tr -dc '0-9')"
disk_line="$(df -h --output=used,size,pcent / | tail -n 1 | xargs)"
if ((disk_pct >= 90)); then bad "disk: ${disk_line} (to'lib qolmoqda)"; elif ((disk_pct >= 80)); then warn "disk: ${disk_line}"; else ok "disk: ${disk_line}"; fi
oom="$(journalctl -k --since '24 hours ago' --no-pager 2>/dev/null | grep -ci 'out of memory\|oom-kill' || true)"
if [[ "${oom}" =~ ^[0-9]+$ ]] && ((oom > 0)); then warn "oxirgi 24 soatda OOM hodisalari: ${oom} (journalctl -k | grep -i oom)"; fi

# ---------------------------------------------------------------- baza
echo
echo "Baza (oxirgi faollik):"
db_rel="data/ayvona.db"
if as_app test -f "${APP_DIR}/.env"; then
    from_env="$(as_app grep -E '^DB_PATH=' "${APP_DIR}/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r"'"'" || true)"
    [[ -n "${from_env}" ]] && db_rel="${from_env}"
fi
case "${db_rel}" in /*) DB="${db_rel}" ;; *) DB="${APP_DIR}/${db_rel}" ;; esac

if ! command -v sqlite3 >/dev/null; then
    warn "sqlite3 yo'q — baza tekshirilmadi (sudo apt install -y sqlite3)"
elif ! as_app test -f "${DB}"; then
    bad "baza topilmadi (yoki o'qib bo'lmaydi — sudo bilan ishga tushiring): ${DB}"
else
    q() { as_app sqlite3 -readonly -cmd ".timeout 3000" "${DB}" "$1" 2>/dev/null; }
    for proc in collector worker bot; do
        hb="$(q "select value from kv_store where key='heartbeat:${proc}'")"
        if [[ -z "${hb}" ]]; then
            warn "heartbeat:${proc} hali yozilmagan"
        else
            m="$(age_min "${hb}")"
            if ((m < 0 || m > HEARTBEAT_STALE_MIN)); then bad "heartbeat:${proc}: $(human "${m}") (chegara ${HEARTBEAT_STALE_MIN} daqiqa)"; else ok "heartbeat:${proc}: $(human "${m}")"; fi
        fi
    done
    cyc="$(q "select value from kv_store where key='collector:last_cycle_at'")"
    if [[ -n "${cyc}" ]]; then
        m="$(age_min "${cyc}")"
        if ((m < 0 || m > CYCLE_STALE_MIN)); then bad "collector oxirgi sikli: $(human "${m}")"; else ok "collector oxirgi sikli: $(human "${m}")"; fi
    fi
    raw="$(q "select max(fetched_at) from raw_posts")"
    [[ -n "${raw}" ]] && ok "oxirgi o'qilgan post (collector): $(human "$(age_min "${raw}")")" || warn "hali post o'qilmagan"
    pub="$(q "select max(published_at) from jobs where status='published'")"
    queued="$(q "select count(*) from jobs where status in ('queued','retry')")"
    if [[ -n "${pub}" ]]; then
        m="$(age_min "${pub}")"
        # tungi tanaffus (23:00-07:00) va 5 daqiqalik oraliq tufayli bir necha soat jim bo'lishi normal
        if ((m > 12 * 60 && ${queued:-0} > 0)); then warn "oxirgi kanal posti $(human "${m}"), navbatda ${queued} ta — publisher ishlayaptimi?"; else ok "oxirgi kanal posti: $(human "${m}")"; fi
    else
        warn "kanalga hali post chiqmagan"
    fi
    echo "  ----  navbat: ${queued:-0} ta; e'lonlar holati: $(q "select status || '=' || count(*) from jobs group by status" | tr '\n' ' ')"
    q "pragma quick_check" | grep -qx ok && ok "baza butunligi (quick_check): ok" || bad "baza quick_check muvaffaqiyatsiz"
fi

echo
if ((PROBLEMS > 0)); then
    echo "$(red "NATIJA: ${PROBLEMS} ta muammo"), ${WARNINGS} ta ogohlantirish"
    exit 1
fi
echo "$(green "NATIJA: muammo yo'q"), ${WARNINGS} ta ogohlantirish"
exit 0
