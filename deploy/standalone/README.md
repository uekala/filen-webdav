# Eigenständiger Betrieb mit Docker (z. B. Unraid)

Filen WebDAV läuft auch ohne Home Assistant OS als gewöhnlicher Container. Home Assistant erreicht den
WebDAV-Server dann über das Heimnetz und nutzt ihn wie bisher als Speicherort für Backups. Fotosortierung,
OneDrive-Umzug und „Filen ordnen“ arbeiten wie in der HA-App.

Image: `ghcr.io/uekala/filen-webdav` (amd64 und arm64), Tags `latest` und die Versionsnummer.

## Was anders ist als in der HA-App

| | HA-App | Eigenständig |
|---|---|---|
| Einstellungen | Seite „Konfiguration“ der App | Datei `data/options.json` |
| Benachrichtigungen | automatisch | nur mit `HA_URL` und `HA_TOKEN` |
| Berichte | `share/filen_webdav` | Ordner `berichte` |
| Zeitzone | von Home Assistant | Variable `TZ` |
| Neustart | Watchdog von Home Assistant | `restart: unless-stopped` (nach einem Absturz) |
| Sicherung der Einstellungen | Teil der HA-Backups | selbst sichern (Ordner `data`) |

## Einrichten

1. Einen Ordner anlegen und `docker-compose.yml` sowie `options.beispiel.json` aus diesem Verzeichnis hineinlegen.
2. Einstellungen anlegen und schützen (die Datei enthält die Filen-Zugangsdaten im Klartext):

   ```bash
   mkdir -p data berichte
   cp options.beispiel.json data/options.json
   chmod 600 data/options.json
   ```

3. `data/options.json` ausfüllen. Die Schlüssel sind die Optionen der HA-App: Was sie bewirken, steht in
   [DOCS.md](../../filen_webdav/DOCS.md), die Beschreibung je Schlüssel in
   [translations/de.yaml](../../filen_webdav/translations/de.yaml). Pflicht sind `email`, `password`, `api_key`
   und `webdav_password`.
4. Starten und das Protokoll prüfen:

   ```bash
   docker compose up -d
   docker compose logs -f     # erwartet: „WebDAV-Server startet auf Port 8080“
   ```

Nach jeder Änderung an `data/options.json` den Container neu starten (`docker compose restart`).

**Unraid:** entweder mit dem Plugin „Docker Compose Manager“ wie oben, oder als einzelner Container mit dem
Repository `ghcr.io/uekala/filen-webdav`, den Pfaden `/data` und `/share/filen_webdav` (z. B. unter
`/mnt/user/appdata/filen-webdav/`), Port 8080 und den Variablen unten.

## Umgebungsvariablen

| Variable | Bedeutung | Standard |
|---|---|---|
| `TZ` | Zeitzone für die Uhrzeit der Fotosortierung und die Namen der Berichte | `Europe/Berlin` (in der Compose-Datei) |
| `HA_URL` | Adresse von Home Assistant, z. B. `http://192.168.1.20:8123`. Die IP eintragen, `.local`-Namen werden im Container oft nicht aufgelöst | leer |
| `HA_TOKEN` | langlebiges Zugriffstoken (Home Assistant → Profil → Sicherheit) | leer |
| `RCD_MEMLIMIT` | Speichergrenze der rclone-Fernsteuerung, z. B. `1GiB` | `400MiB` |

`HA_URL` und `HA_TOKEN` gehören zusammen. Fehlt einer der beiden Werte, läuft alles wie gewohnt, nur ohne
Benachrichtigung; die Ergebnisse stehen dann im Protokoll und in den Berichten. Beide Werte am besten in eine
Datei `.env` neben der Compose-Datei schreiben (`chmod 600 .env`).

## In Home Assistant einbinden

*Einstellungen → Geräte & Dienste → Integration hinzufügen → WebDAV*

| Feld | Wert |
|---|---|
| URL | `http://<IP des Servers>:8080` |
| Benutzername / Passwort | `webdav_user` / `webdav_password` aus `data/options.json` |
| Backup-Pfad | `/backups` |
| SSL prüfen | aus |

Danach unter *Einstellungen → System → Backups → Backup-Einstellungen* den Speicherort **WebDAV** anhaken.

## Umzug von der HA-App

1. In Home Assistant die Seite „Konfiguration“ der App öffnen, über ⋮ die YAML-Ansicht wählen und die Werte nach
   `data/options.json` übertragen. Bleibt `root_folder` gleich, sieht Home Assistant danach dieselben Backups.
2. Die HA-App stoppen. Beide dürfen nicht gleichzeitig sortieren oder aufräumen.
3. Den Container starten und das Protokoll prüfen.
4. In Home Assistant die bisherige WebDAV-Integration löschen und mit der neuen Adresse neu anlegen (die Adresse
   eines bestehenden Eintrags lässt sich nicht ändern). In den Backup-Einstellungen den Speicherort wieder anhaken.
5. Ein Backup von Hand auslösen und prüfen, dass es in Filen ankommt.
6. Erst danach die HA-App deinstallieren.

## Sicherheit

- `data/options.json` und `data/rclone.conf` enthalten Zugangsdaten. Den Ordner nur für den Besitzer lesbar halten
  und nicht über eine Netzwerkfreigabe anbieten.
- Der WebDAV-Server spricht unverschlüsseltes HTTP mit Benutzername und Passwort. Port 8080 deshalb nur im Heimnetz
  nutzen und nie am Router freigeben; von unterwegs über ein VPN zugreifen.
- Die Backups selbst bleiben mit dem Backup-Schlüssel von Home Assistant verschlüsselt, und Filen verschlüsselt
  zusätzlich Ende-zu-Ende.
