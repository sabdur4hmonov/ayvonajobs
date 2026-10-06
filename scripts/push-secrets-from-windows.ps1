<#
.SYNOPSIS
  Ayvona Jobs: .env, Telegram session va bazani Windows kompyuterdan serverga yuboradi (scp).

.DESCRIPTION
  Oldin serverda scripts/server-setup.sh ishlagan bo'lishi kerak. Bu skript:
    1) kompyuterda hech qanday ayvona jarayoni (collector/worker/bot/web) ishlamayotganini tekshiradi
       va ishlayotgan bo'lsa TO'XTAYDI (bitta Telethon session va bitta BOT_TOKEN faqat bitta joyda
       yashay oladi: aks holda AUTH_KEY_DUPLICATED / TelegramConflictError);
    2) baza va session'ning XAVFSIZ nusxasini oladi (sqlite backup API: WAL ichidagi yozuvlar ham tushadi,
       tirik fayl nusxalanmaydi) va butunligini tekshiradi;
    3) fayllarni serverga yuboradi, huquqini 600 qiladi, egasini 'ayvona' ga o'tkazadi;
    4) serverda `alembic upgrade head` ni ishga tushiradi.
  Maxfiy qiymatlar hech qayerda chop etilmaydi (faqat fayl nomlari va yozuvlar soni).
  Serverda bazada allaqachon ma'lumot bo'lsa yoki servislar ishlayotgan bo'lsa -Force kerak
  (eski baza avval data/backups/pre-push/ ga saqlanadi).

.PARAMETER HostName   Serverning ochiq IP manzili yoki nomi.
.PARAMETER KeyFile    Maxfiy SSH kalit fayli (masalan $HOME\.ssh\oracle_ayvona).
.PARAMETER User       Serverdagi foydalanuvchi (Ubuntu: ubuntu).
.PARAMETER ProjectDir Loyiha papkasi (standart: shu skriptning bir daraja tepasi).
.PARAMETER Start      Yuborgandan keyin servislarni ham yoqadi (collector, worker, bot).
.PARAMETER Force      Serverdagi bo'sh bo'lmagan bazani / ishlayotgan servislarni almashtirishga ruxsat.
.PARAMETER DryRun     Hech narsa yubormaydi: faqat tekshiruvlar va xavfsiz nusxa (serverga ulanmaydi).

.EXAMPLE
  cd "D:\Coding projects\ayvona"
  .\scripts\push-secrets-from-windows.ps1 -HostName 141.147.12.34 -KeyFile "$HOME\.ssh\oracle_ayvona"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$HostName,
    [Parameter(Mandatory = $true)][string]$KeyFile,
    [string]$User = "ubuntu",
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot),
    [switch]$Start,
    [switch]$Force,
    [switch]$DryRun
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
    Write-Host ""
    Write-Host "XATO: $msg" -ForegroundColor Red
    exit 1
}
function Step([string]$msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Native([string]$what, [scriptblock]$cmd) {
    & $cmd
    if ($LASTEXITCODE -ne 0) { Fail "$what muvaffaqiyatsiz tugadi (kod $LASTEXITCODE)" }
}

# ------------------------------------------------------------------ 0. kirish ma'lumotlari
Step "0/5 Tekshiruvlar"
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir "alembic.ini"))) {
    Fail "$ProjectDir ayvona loyihasiga o'xshamaydi (alembic.ini yo'q). -ProjectDir ni to'g'ri bering."
}
if (-not (Test-Path -LiteralPath $KeyFile)) { Fail "SSH kalit fayli topilmadi: $KeyFile" }
foreach ($tool in @("ssh", "scp")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Fail "$tool topilmadi. Windows: Settings > System > Optional features > OpenSSH Client."
    }
}

# ------------------------------------------------------------------ 1. lokal jarayonlar
# Faqat python/uv jarayonlari `-m ayvona.apps.<nom>` bilan: boshqa dasturlar (terminal, muharrir)
# buyruq matnida shu so'zni eslatishi mumkin - ular hisobga olinmaydi.
$running = @(Get-CimInstance Win32_Process |
        Where-Object {
            $_.ProcessId -ne $PID -and $_.CommandLine -and
            $_.Name -match '^(python|pythonw|py|uv)[\d.]*\.exe$' -and
            $_.CommandLine -match '(^|\s)-m\s+ayvona\.apps\.(collector|worker|bot|web)\b'
        })
if ($running.Count -gt 0) {
    Write-Host "Kompyuterda ayvona jarayonlari ishlayapti:" -ForegroundColor Yellow
    $running | ForEach-Object { Write-Host ("  pid {0}: {1}" -f $_.ProcessId, ($_.CommandLine -replace '\s+', ' ')) }
    Fail ("Avval ularni to'xtating (oynada Ctrl+C yoki: Stop-Process -Id " + (($running | ForEach-Object { $_.ProcessId }) -join ",") +
        "). Bitta session va bitta bot tokeni faqat bitta joyda ishlay oladi - serverga ko'chirgandan keyin " +
        "kompyuterda collector/worker/bot'ni BIR HAM ISHGA TUSHIRMANG.")
}
Write-Host "  kompyuterda ayvona jarayonlari yo'q - OK"

# ------------------------------------------------------------------ 2. fayllar
function Read-EnvValue([string]$envFile, [string]$name, [string]$default) {
    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -Last 1
    if (-not $line) { return $default }
    $v = ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($v)) { return $default }
    return $v
}
$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path -LiteralPath $envFile)) { Fail ".env topilmadi: $envFile" }
$dbRel = (Read-EnvValue $envFile "DB_PATH" "data/ayvona.db") -replace "\\", "/"
$sessRel = (Read-EnvValue $envFile "TELETHON_SESSION" "data/ayvona") -replace "\\", "/"
foreach ($p in @($dbRel, $sessRel)) {
    if ($p -match '^[A-Za-z]:' -or $p.StartsWith("/") -or $p.Contains("..")) {
        Fail ".env dagi yo'l nisbiy bo'lishi kerak (masalan data/ayvona.db), topildi: $p"
    }
}
if ($sessRel.EndsWith(".session")) { $sessRel = $sessRel.Substring(0, $sessRel.Length - 8) }
$dbFile = Join-Path $ProjectDir ($dbRel -replace "/", "\")
$sessFile = Join-Path $ProjectDir (($sessRel -replace "/", "\") + ".session")
if (-not (Test-Path -LiteralPath $dbFile)) { Fail "baza topilmadi: $dbFile" }
if (-not (Test-Path -LiteralPath $sessFile)) {
    Fail "Telegram session topilmadi: $sessFile  (yoki serverda yangi login: uv run python scripts/login_telethon.py)"
}
Write-Host "  .env, baza ($dbRel), session ($sessRel.session) - topildi"

# ------------------------------------------------------------------ 3. xavfsiz nusxa
Step "1/5 Baza va session'ning xavfsiz nusxasi (sqlite backup)"
$tmp = Join-Path $env:TEMP ("ayvona-push-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $helper = Join-Path $tmp "safecopy.py"
    @'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src, timeout=30)
d = sqlite3.connect(dst)
s.backup(d)
ok = d.execute("PRAGMA integrity_check").fetchone()[0]
tables = {r[0] for r in d.execute("select name from sqlite_master where type='table'")}
info = ""
if "jobs" in tables:
    info = "jobs=%d raw_posts=%d" % (d.execute("select count(*) from jobs").fetchone()[0],
                                      d.execute("select count(*) from raw_posts").fetchone()[0])
d.close(); s.close()
print("integrity=%s %s" % (ok, info))
sys.exit(0 if ok == "ok" else 1)
'@ | Set-Content -LiteralPath $helper -Encoding ASCII

    $python = $null
    Push-Location $ProjectDir
    try {
        if (Get-Command uv -ErrorAction SilentlyContinue) { $python = @("uv", "run", "--no-sync", "python") }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { $python = @("py", "-3") }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = @("python") }
        else { Fail "python yoki uv topilmadi (xavfsiz nusxa uchun kerak)." }
        $dbCopy = Join-Path $tmp "ayvona.db"
        $sessCopy = Join-Path $tmp "ayvona.session"
        foreach ($pair in @(@($dbFile, $dbCopy, "baza"), @($sessFile, $sessCopy, "session"))) {
            $exe = $python[0]; $pre = @($python | Select-Object -Skip 1)
            $out = & $exe @pre $helper $pair[0] $pair[1]
            if ($LASTEXITCODE -ne 0) { Fail ("{0} nusxasi buzuq yoki olinmadi: {1}" -f $pair[2], $out) }
            Write-Host ("  {0}: {1}" -f $pair[2], $out)
        }
    }
    finally { Pop-Location }
    Copy-Item -LiteralPath $envFile -Destination (Join-Path $tmp ".env")

    if ($DryRun) {
        Step "DryRun: serverga ulanilmadi, hech narsa yuborilmadi"
        Write-Host "  yuborilar edi: .env, $dbRel (nusxa), $sessRel.session (nusxa) -> ${User}@${HostName}"
        Write-Host "  vaqtinchalik nusxalar o'chiriladi."
        return
    }

    # -------------------------------------------------------------- 4. yuborish
    Step "2/5 Serverga ulanish"
    $sshOpts = @("-i", $KeyFile, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=30")
    $target = "${User}@${HostName}"
    $stage = $null
    Native "ssh (ulanish)" { $script:stage = (& ssh @sshOpts $target 'umask 077; mktemp -d ~/ayvona-push.XXXXXX') | Select-Object -First 1 }
    $stage = "$stage".Trim()
    if ($stage -notmatch '^/[\w./-]+$') { Fail "serverda vaqtinchalik papka yaratilmadi (javob: '$stage')" }
    Write-Host "  ulandi; vaqtinchalik papka: $stage"

    $applyText = @'
#!/usr/bin/env bash
# Serverda ishlaydi (push-secrets-from-windows.ps1 yuboradi). Hech qanday maxfiy qiymat chop etilmaydi.
set -Eeuo pipefail
STAGE="$1"; FORCE="$2"; START="$3"; DB_REL="$4"; SESS_REL="$5"
APP=/home/ayvona/ayvona
trap 'rm -rf "$STAGE"' EXIT
as_app() { sudo -u ayvona -H -- "$@"; }

[ -d "$APP/.git" ] || { echo "ERROR: $APP topilmadi - avval serverda scripts/server-setup.sh ni ishga tushiring."; exit 10; }
active="$(systemctl is-active ayvona-collector ayvona-worker ayvona-bot ayvona-web 2>/dev/null | grep -c '^active$' || true)"
if [ "$active" -gt 0 ]; then
    if [ "$FORCE" != 1 ]; then
        echo "ERROR: serverda ayvona servislari ishlayapti ($active ta). Bazani ishlab turgan jarayon ostidan almashtirib bo'lmaydi. -Force bilan qayta urining (servislar to'xtatiladi)."
        exit 11
    fi
    echo "servislar to'xtatilmoqda (-Force)"
    sudo systemctl stop ayvona-collector ayvona-worker ayvona-bot ayvona-web 2>/dev/null || true
fi

DEST_DB="$APP/$DB_REL"
DEST_SESS="$APP/$SESS_REL.session"
stamp="$(date +%Y%m%d-%H%M%S)"
if [ -f "$DEST_DB" ]; then
    n="$(as_app sqlite3 "$DEST_DB" 'select (select count(*) from raw_posts) + (select count(*) from jobs)' 2>/dev/null || echo 0)"
    if [ "${n:-0}" -gt 0 ]; then
        if [ "$FORCE" != 1 ]; then
            echo "ERROR: serverdagi bazada ${n} ta yozuv bor. Almashtirish uchun -Force bering (eskisi avval saqlanadi)."
            exit 12
        fi
        as_app mkdir -p "$APP/data/backups/pre-push"
        as_app sqlite3 "$DEST_DB" ".backup '$APP/data/backups/pre-push/ayvona-$stamp.db'"
        echo "serverdagi eski baza saqlandi: data/backups/pre-push/ayvona-$stamp.db ($n yozuv)"
    else
        echo "serverdagi baza bo'sh (faqat migratsiyalar) - almashtiriladi"
    fi
fi

sudo install -d -o ayvona -g ayvona -m 700 "$APP/data" "$(dirname "$DEST_DB")" "$(dirname "$DEST_SESS")"
if [ -f "$APP/.env" ] && ! sudo cmp -s "$STAGE/.env" "$APP/.env"; then
    sudo install -o ayvona -g ayvona -m 600 "$APP/.env" "$APP/.env.bak-$stamp"
    echo "eski .env saqlandi: .env.bak-$stamp"
fi
sudo install -o ayvona -g ayvona -m 600 "$STAGE/.env" "$APP/.env"
sudo install -o ayvona -g ayvona -m 600 "$STAGE/ayvona.session" "$DEST_SESS"
sudo install -o ayvona -g ayvona -m 600 "$STAGE/ayvona.db" "$DEST_DB"
sudo rm -f "$DEST_DB-wal" "$DEST_DB-shm" "$DEST_SESS-journal"
echo "fayllar o'rnatildi (egasi ayvona, huquq 600)"

as_app bash -c "cd '$APP' && .venv/bin/alembic upgrade head" 2>&1 | tail -n 3
echo "baza: $(as_app sqlite3 -readonly "$DEST_DB" 'select (select version_num from alembic_version) || ", jobs=" || (select count(*) from jobs) || ", raw_posts=" || (select count(*) from raw_posts)')"
echo "butunlik: $(as_app sqlite3 -readonly "$DEST_DB" 'pragma integrity_check')"
sudo ls -l "$APP/.env" "$DEST_DB" "$DEST_SESS" | awk '{print "  " $1, $3, $9}'

if [ "$START" = 1 ]; then
    sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot
    sleep 5
    systemctl is-active ayvona-collector ayvona-worker ayvona-bot | paste -sd' ' | sed 's/^/servislar: /'
fi
'@
    $applyFile = Join-Path $tmp "apply.sh"
    [IO.File]::WriteAllText($applyFile, ($applyText -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding $false))

    Step "3/5 Fayllarni yuborish (scp)"
    Native "scp" { & scp @sshOpts (Join-Path $tmp ".env") (Join-Path $tmp "ayvona.session") (Join-Path $tmp "ayvona.db") $applyFile "${target}:${stage}/" }
    Write-Host "  yuborildi: .env, ayvona.session, ayvona.db"

    Step "4/5 Serverda o'rnatish"
    $f = if ($Force) { 1 } else { 0 }
    $s = if ($Start) { 1 } else { 0 }
    & ssh @sshOpts $target "bash '$stage/apply.sh' '$stage' $f $s '$dbRel' '$sessRel'"
    if ($LASTEXITCODE -ne 0) {
        # apply.sh o'zi vaqtinchalik papkani o'chirdi (trap); papka yaratilmay qolgan holat uchun ham:
        & ssh @sshOpts $target "rm -rf '$stage'" | Out-Null
        Fail "serverda o'rnatish to'xtadi (yuqoridagi ERROR qatorini o'qing)"
    }

    Step "5/5 Tayyor"
    Write-Host "  Kompyuterdagi nusxalar vaqtincha papkadan o'chiriladi; asl fayllaringiz joyida qoldi."
    Write-Host "  MUHIM: endi kompyuterda collector/worker/bot'ni ishga tushirmang (session va token serverda)."
    if (-not $Start) {
        Write-Host ""
        Write-Host "  Servislarni yoqish (serverda):"
        Write-Host "    sudo systemctl enable --now ayvona-collector ayvona-worker ayvona-bot"
    }
}
finally {
    # nusxalar (jumladan session) kompyuterda ham qolib ketmasin
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
