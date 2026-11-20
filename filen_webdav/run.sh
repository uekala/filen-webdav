#!/bin/sh
# Startet einen WebDAV-Server, der einen Ordner im Filen-Laufwerk bereitstellt.
set -eu

OPTIONS=/data/options.json

opt() {
    jq -r --arg k "$1" '.[$k] // ""' "$OPTIONS"
}

fail() {
    echo "[filen-webdav] FEHLER: $*" >&2
    # Kurz warten, damit die Meldung im Protokoll steht, bevor der Watchdog neu startet.
    sleep 30
    exit 1
}

EMAIL=$(opt email)
PASSWORD=$(opt password)
API_KEY=$(opt api_key)
ROOT=$(opt root_folder)
DAV_USER=$(opt webdav_user)
DAV_PASS=$(opt webdav_password)
CACHE_MODE=$(opt cache_mode)
LOG_LEVEL=$(opt log_level)

[ -n "$EMAIL" ] || fail "Option 'email' fehlt."
[ -n "$PASSWORD" ] || fail "Option 'password' fehlt."
[ -n "$API_KEY" ] || fail "Option 'api_key' fehlt (mit 'filen export-api-key' erzeugen, siehe Dokumentation)."
[ -n "$DAV_USER" ] || fail "Option 'webdav_user' fehlt."
[ -n "$DAV_PASS" ] || fail "Option 'webdav_password' fehlt."

# Führenden Schrägstrich sicherstellen, abschließenden entfernen.
case "$ROOT" in
    /*) ;;
    *) ROOT="/$ROOT" ;;
esac
ROOT=${ROOT%/}

# rclone erwartet Passwort und API-Schlüssel verschleiert ("obscured").
export RCLONE_CONFIG=/data/rclone.conf
touch "$RCLONE_CONFIG"
export RCLONE_CONFIG_FILEN_TYPE=filen
export RCLONE_CONFIG_FILEN_EMAIL="$EMAIL"
RCLONE_CONFIG_FILEN_PASSWORD=$(rclone obscure "$PASSWORD")
RCLONE_CONFIG_FILEN_API_KEY=$(rclone obscure "$API_KEY")
export RCLONE_CONFIG_FILEN_PASSWORD RCLONE_CONFIG_FILEN_API_KEY

echo "[filen-webdav] Prüfe Anmeldung bei Filen ..."
rclone lsd filen: --max-depth 1 --log-level "$LOG_LEVEL" >/dev/null \
    || fail "Anmeldung bei Filen fehlgeschlagen. E-Mail, Passwort und API-Schlüssel prüfen."

echo "[filen-webdav] Lege Ordner '$ROOT' an (falls nötig) ..."
rclone mkdir "filen:$ROOT" --log-level "$LOG_LEVEL" \
    || fail "Ordner '$ROOT' konnte nicht angelegt werden."

mkdir -p /data/cache

echo "[filen-webdav] WebDAV-Server startet auf Port 8080, Ordner '$ROOT', Zwischenspeicher: $CACHE_MODE"
exec rclone serve webdav "filen:$ROOT" \
    --addr :8080 \
    --user "$DAV_USER" \
    --pass "$DAV_PASS" \
    --vfs-cache-mode "$CACHE_MODE" \
    --cache-dir /data/cache \
    --vfs-cache-max-age 1h \
    --log-level "$LOG_LEVEL"
