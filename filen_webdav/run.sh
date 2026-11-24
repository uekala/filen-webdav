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
FOTO_SORTIERUNG=$(jq -r '.foto_sortierung // false' "$OPTIONS")
ONEDRIVE_MODUS=$(jq -r '.onedrive_modus // "aus"' "$OPTIONS")
FILEN_UEBERSICHT=$(jq -r '.filen_uebersicht // false' "$OPTIONS")
FILEN_VERSCHIEBEN=$(jq -r '[.filen_verschieben[]? | select(. != null and . != "")] | length' "$OPTIONS")
FILEN_ORDNEN=false
if [ "$FILEN_UEBERSICHT" = "true" ] || [ "$FILEN_VERSCHIEBEN" -gt 0 ]; then
    FILEN_ORDNEN=true
fi

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

if [ "$ONEDRIVE_MODUS" != "aus" ]; then
    python3 /onedrive.py --config || ONEDRIVE_MODUS=aus
fi

if [ "$FOTO_SORTIERUNG" = "true" ] || [ "$ONEDRIVE_MODUS" != "aus" ] || [ "$FILEN_ORDNEN" = "true" ]; then
    echo "[filen-webdav] Starte rclone-Fernsteuerung (nur lokal)"
    # Speichergrenze für Go: rclone räumt früher auf, statt den Green an den Rand zu bringen
    # Wird rclone beendet (z. B. Speicher), startet es nach 10 s neu.
    # Die Fernsteuerung loggt nur Hinweise und Fehler, nicht jede kopierte Datei –
    # sonst verdrängen große Kopien die Ergebnisse von Sortierer und Umzug aus dem Log.
    RCD_LEVEL=NOTICE
    [ "$LOG_LEVEL" = "DEBUG" ] && RCD_LEVEL=DEBUG
    (
        while true; do
            GOMEMLIMIT=400MiB rclone rcd --rc-addr 127.0.0.1:5572 --rc-no-auth --use-mmap --log-level "$RCD_LEVEL"
            echo "[filen-webdav] rclone-Fernsteuerung beendet (Code $?) – Neustart in 10 s"
            sleep 10
        done
    ) &
fi
if [ "$FOTO_SORTIERUNG" = "true" ]; then
    echo "[filen-webdav] Fotosortierung aktiv"
    python3 /fotosortierer.py --dienst &
fi
if [ "$ONEDRIVE_MODUS" != "aus" ]; then
    echo "[filen-webdav] OneDrive-Modus: $ONEDRIVE_MODUS"
    python3 /onedrive.py &
fi
if [ "$FILEN_ORDNEN" = "true" ]; then
    echo "[filen-webdav] Filen ordnen: Übersicht=$FILEN_UEBERSICHT, $FILEN_VERSCHIEBEN Verschiebung(en)"
    python3 /filen_ordnen.py &
fi

echo "[filen-webdav] WebDAV-Server startet auf Port 8080, Ordner '$ROOT', Zwischenspeicher: $CACHE_MODE"
exec rclone serve webdav "filen:$ROOT" \
    --addr :8080 \
    --user "$DAV_USER" \
    --pass "$DAV_PASS" \
    --vfs-cache-mode "$CACHE_MODE" \
    --cache-dir /data/cache \
    --vfs-cache-max-age 1h \
    --log-level "$LOG_LEVEL"
