#!/usr/bin/env bash
# =====================================================================
#  Ayvona Jobs — serverda yangilash (Oracle VPS, Ubuntu).
#
#  Nima qiladi:
#    1) git pull            — GitHub'dan yangi kod
#    2) servislarni to'xtatadi (faqat yoqilganlarini)
#    3) bazaning zaxira nusxasi — data/backups/deploy/*.db (oxirgi 5 tasi qoladi)
#    4) uv sync             — kutubxonalar (uv.lock bo'yicha, aynan o'sha versiyalar)
#    5) alembic upgrade head — baza migratsiyalari
#    6) vaqtinchalik rasmlar — bo'sh rasm papkalariga (git'da yo'q; borlariga tegmaydi)
#    7) systemd unit fayllar o'zgargan bo'lsa — /etc/systemd/system/ ga nusxalaydi
#    8) servislarni qayta ishga tushiradi va holatini ko'rsatadi
#
#  Servislar: ayvona-collector, ayvona-worker, ayvona-bot, ayvona-web (veb-sayt, ixtiyoriy).
#  Faqat "enable" qilinganlari to'xtatiladi/yoqiladi.
#
#  Ishlatish (serverda, ubuntu foydalanuvchisidan):
#    sudo bash /home/ayvona/ayvona/scripts/deploy.sh
#
#  Collector bir necha soniya to'xtab turadi — bu xavfsiz: qayta yoqilganda
#  har manbaning last_seen_id'sidan davom etadi, hech bir post yo'qolmaydi.
# =====================================================================

# Butun skript main() ichida: bash avval hammasini o'qib oladi, shuning uchun
# `git pull` shu faylning o'zini yangilasa ham, ish o'rtasida buzilmaydi.
main() {
    set -Eeuo pipefail
    cd /  # sudo'dan keyingi joriy papka ayvona uchun yopiq bo'lishi mumkin

    local app_user="${APP_USER:-ayvona}"
    local app_dir="${APP_DIR:-/home/${app_user}/ayvona}"
    local uv="/home/${app_user}/.local/bin/uv"
    local services=(ayvona-collector ayvona-worker ayvona-bot ayvona-web)
    local keep_backups=5

    if [[ "${EUID}" -ne 0 ]]; then
        echo "❌ sudo bilan ishga tushiring:  sudo bash ${app_dir}/scripts/deploy.sh" >&2
        exit 1
    fi
    if [[ ! -x "${uv}" ]]; then
        echo "❌ uv topilmadi: ${uv}  (deploy/SETUP_ORACLE.md, 'uv o'rnatish' bo'limi)" >&2
        exit 1
    fi

    # Buyruqni ayvona foydalanuvchisi nomidan, loyiha papkasida bajarish.
    as_app() {
        sudo -u "${app_user}" -H -- bash -c 'cd "$1" && shift && exec "$@"' _ "${app_dir}" "$@"
    }

    # Yoqilgan (enabled) servislar — yoqilmaganiga (masalan, tokensiz bot) tegmaymiz.
    local enabled=()
    local s
    for s in "${services[@]}"; do
        if systemctl is-enabled --quiet "${s}" 2>/dev/null; then
            enabled+=("${s}")
        fi
    done
    local enabled_list="${enabled[*]}"
    enabled_list="${enabled_list:-hech biri yoqilmagan}"

    on_error() {
        echo "" >&2
        echo "❌ Deploy xato bilan to'xtadi. Servislar to'xtagan holatda qolgan bo'lishi mumkin." >&2
        echo "   Xatoni yuqoridan o'qing. Tuzatgandan keyin skriptni qayta ishga tushiring." >&2
        echo "   Tezda eski holatga qaytish: deploy/SETUP_ORACLE.md, '13-qadam' (backup'dan tiklash)." >&2
    }
    trap 'on_error' ERR

    echo "==> 1/8 git pull"
    as_app git pull --ff-only
    as_app git log -1 --oneline

    echo "==> 2/8 Servislarni to'xtatish: ${enabled_list}"
    if ((${#enabled[@]})); then
        systemctl stop "${enabled[@]}"
    fi

    # Alohida papka: worker'ning kunlik backup'lari (data/backups/ayvona_YYYY-MM-DD.db) bilan aralashmasin.
    echo "==> 3/8 Baza zaxirasi (data/backups/deploy/)"
    as_app mkdir -p data/backups/deploy
    if [[ -f "${app_dir}/data/ayvona.db" ]]; then
        local stamp
        stamp="$(date -u +%Y%m%d-%H%M%S)"
        # sqlite backup API — WAL ichidagi yozuvlar ham to'liq nusxaga tushadi.
        as_app "${uv}" run --no-sync python -c \
            'import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' \
            data/ayvona.db "data/backups/deploy/ayvona-${stamp}.db"
        echo "    saqlandi: data/backups/deploy/ayvona-${stamp}.db"
        # Eskilarini o'chirish: faqat oxirgi ${keep_backups} tasi qoladi.
        as_app bash -c "ls -1t data/backups/deploy/ayvona-*.db 2>/dev/null | tail -n +$((keep_backups + 1)) | xargs -r rm -f --"
    else
        echo "    data/ayvona.db hali yo'q — o'tkazib yuborildi"
    fi

    echo "==> 4/8 uv sync --locked"
    as_app "${uv}" sync --locked

    echo "==> 5/8 alembic upgrade head"
    as_app "${uv}" run --no-sync alembic upgrade head

    echo "==> 6/8 Vaqtinchalik rasmlar (faqat bo'sh papkalarga)"
    as_app "${uv}" run --no-sync python scripts/make_placeholder_images.py | tail -n 1

    echo "==> 7/8 systemd unit fayllar"
    local changed=0 unit src dst
    for s in "${services[@]}"; do
        unit="${s}.service"
        src="${app_dir}/deploy/systemd/${unit}"
        dst="/etc/systemd/system/${unit}"
        if [[ -f "${dst}" ]] && ! cmp -s "${src}" "${dst}"; then
            install -m 644 "${src}" "${dst}"
            echo "    yangilandi: ${unit}"
            changed=1
        fi
    done
    if ((changed)); then
        systemctl daemon-reload
    else
        echo "    o'zgarish yo'q"
    fi

    echo "==> 8/8 Servislarni ishga tushirish: ${enabled_list}"
    if ((${#enabled[@]})); then
        systemctl start "${enabled[@]}"
        sleep 5
        for s in "${enabled[@]}"; do
            printf '    %-18s %s\n' "${s}" "$(systemctl is-active "${s}" || true)"
        done
    fi

    trap - ERR
    echo ""
    echo "✅ Deploy tugadi. Loglarni ko'rish:  journalctl -u ayvona-collector -n 50 --no-pager"
}

main "$@"
