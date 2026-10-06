#!/usr/bin/env bash
# =====================================================================
#  Ayvona Jobs — kunlik SQLite zaxirasi (faqat serverda saqlanadi, bepul).
#
#  systemd taymeri (ayvona-backup.timer) har kuni 03:30 da ishga tushiradi; qo'lda ham bo'ladi:
#    sudo systemctl start ayvona-backup        yoki    bash scripts/backup.sh
#
#  Nima qiladi: `sqlite3 .backup` (WAL ichidagi yozuvlar ham to'liq tushadi, servislarni to'xtatish
#  shart emas) -> butunlik tekshiruvi (integrity_check) -> gzip -> faqat oxirgi 7 tasi qoladi.
#  Joyi: data/backups/daily/ayvona-YYYY-MM-DD.db.gz  (worker'ning o'z zaxirasi — data/backups/ —
#  alohida va unga tegmaydi).
#
#  Tiklash:  sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot
#            gunzip -c data/backups/daily/ayvona-<sana>.db.gz > data/ayvona.db
#            rm -f data/ayvona.db-wal data/ayvona.db-shm ; sudo systemctl start ...
# =====================================================================
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/ayvona/ayvona}"
KEEP="${KEEP:-7}"

# DB_PATH ni .env dan o'qiymiz (fayl "source" qilinmaydi — ichida nima borligi bizga kerak emas).
db_rel="data/ayvona.db"
if [[ -f "${APP_DIR}/.env" ]]; then
    from_env="$(grep -E '^DB_PATH=' "${APP_DIR}/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r"'"'" || true)"
    [[ -n "${from_env}" ]] && db_rel="${from_env}"
fi
case "${db_rel}" in
    /*) DB="${db_rel}" ;;
    *) DB="${APP_DIR}/${db_rel}" ;;
esac
DEST_DIR="${BACKUP_DIR:-${APP_DIR}/data/backups/daily}"

if [[ ! -f "${DB}" ]]; then
    echo "baza topilmadi (${DB}) — zaxira olinmadi"
    exit 0
fi
command -v sqlite3 >/dev/null || { echo "sqlite3 o'rnatilmagan: sudo apt install -y sqlite3" >&2; exit 1; }

mkdir -p "${DEST_DIR}"
stamp="$(date +%F)"
tmp="${DEST_DIR}/.ayvona-${stamp}.db.tmp"
final="${DEST_DIR}/ayvona-${stamp}.db.gz"
trap 'rm -f "${tmp}" "${tmp}-wal" "${tmp}-shm"' EXIT

rm -f "${tmp}"
sqlite3 "${DB}" ".timeout 15000" ".backup '${tmp}'"

result="$(sqlite3 "${tmp}" 'PRAGMA integrity_check;')"
if [[ "${result}" != "ok" ]]; then
    echo "❌ zaxira buzuq (integrity_check: ${result}) — saqlanmadi" >&2
    exit 1
fi

gzip -c "${tmp}" > "${final}.partial"
mv -f "${final}.partial" "${final}"
echo "✅ zaxira: ${final} ($(du -h "${final}" | cut -f1))"

# Faqat oxirgi ${KEEP} ta qoladi (eng yangisidan hisoblab).
ls -1t "${DEST_DIR}"/ayvona-*.db.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f --
echo "saqlanayotgan zaxiralar: $(ls -1 "${DEST_DIR}"/ayvona-*.db.gz | wc -l) ta"
