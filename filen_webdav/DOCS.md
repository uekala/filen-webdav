# Filen WebDAV

Das Add-on startet einen WebDAV-Server (rclone), der einen Ordner in deinem Filen-Laufwerk bereitstellt.
Die eingebaute WebDAV-Integration von Home Assistant nutzt ihn als Speicherort für Backups.

```
HA-Backup ──WebDAV──▶ Filen WebDAV (rclone) ──Ende-zu-Ende-verschlüsselt──▶ Filen
```

## 1. API-Schlüssel erzeugen (einmalig, wegen 2FA)

rclone meldet sich mit E-Mail, Passwort **und** einem API-Schlüssel an. Dadurch ist beim Start keine 2FA-Eingabe nötig.

1. Filen-CLI auf dem PC installieren:
   - Windows: `filen-cli` von <https://github.com/FilenCloudDienste/filen-cli-releases/releases/latest>
   - Linux/macOS: `curl -sL https://raw.githubusercontent.com/FilenCloudDienste/filen-rs/refs/heads/main/filen-cli/install.sh | bash`
2. `filen export-api-key` ausführen, mit E-Mail, Passwort und 2FA-Code anmelden.
3. Den ausgegebenen Schlüssel in die Option **Filen-API-Schlüssel** kopieren.

## 2. Add-on konfigurieren

| Option | Bedeutung |
|---|---|
| Filen-E-Mail / -Passwort | Zugangsdaten des Filen-Kontos |
| Filen-API-Schlüssel | aus Schritt 1 |
| Ordner in Filen | nur dieser Ordner ist per WebDAV erreichbar (Standard `/Home Assistant`) |
| WebDAV-Benutzer / -Passwort | eigene Zugangsdaten nur für den WebDAV-Server |
| Zwischenspeicher | `off` (empfohlen): Upload geht direkt zu Filen, ein Fehler landet sofort im Backup-Ergebnis |

Add-on starten und im Protokoll auf `WebDAV-Server startet auf Port 8080` warten.

## 3. WebDAV-Integration in Home Assistant

*Einstellungen → Geräte & Dienste → Integration hinzufügen → WebDAV*

| Feld | Wert |
|---|---|
| URL | `http://fd35518d-filen-webdav:8080` (interner Hostname des Add-ons, steht auch auf der Info-Seite) |
| Benutzername / Passwort | WebDAV-Benutzer / -Passwort aus dem Add-on |
| Backup-Pfad | `/backups` |
| SSL prüfen | aus (Verbindung bleibt im internen Netz von Home Assistant) |

Danach unter *Einstellungen → System → Backups → Backup-Einstellungen* den neuen Speicherort **WebDAV** anhaken.

## 4. Fotosortierung (optional)

Ordnet Fotos und Videos in Filen nach Aufnahmedatum:

```
/Fotos/2025/2025-08/20250814_153012.jpg
/Fotos/_Duplikate/…        exakte Duplikate (gleicher Inhalt) – nach Kontrolle selbst löschen
/Fotos/_Ohne-Datum/…       kein Datum gefunden
/Fotos/_Google-Metadaten/… JSON-Dateien aus Google Takeout
```

Datum: zuerst aus dem Dateinamen, dann aus der Google-JSON, zuletzt aus den EXIF-Daten der Datei
(dafür wird die Datei kurz heruntergeladen). Gleichnamige Dateien werden durchnummeriert, nie überschrieben.

1. **Fotosortierung aktiv** einschalten, **Nur Probelauf** anlassen, Quellordner prüfen, App neu starten.
2. Nach dem Lauf kommt eine Benachrichtigung; der Bericht liegt in `share/filen_webdav/fotosortierung_…_probelauf.csv`.
3. Passt der Bericht: **Nur Probelauf** ausschalten, App neu starten.
4. Danach läuft die Sortierung täglich zur eingestellten Uhrzeit für neue Dateien in den Quellordnern.

Kamera-Upload vom Handy: Die Filen-App kann neue Uploads selbst nach Datum ordnen. Den Kamera-Upload-Ordner nur
als Quelle eintragen, wenn sicher ist, dass die App verschobene Fotos nicht erneut hochlädt.

## Hinweise

- Backups mit Verschlüsselung in Home Assistant lassen; Filen verschlüsselt zusätzlich Ende-zu-Ende.
- Die Add-on-Optionen (inkl. Filen-Zugangsdaten) sind Teil der HA-Backups. Die Backups sind mit dem
  Backup-Schlüssel verschlüsselt.
- Port 8080 bleibt standardmäßig geschlossen. Nur öffnen, wenn andere Geräte zugreifen sollen, und nie am Router freigeben.
