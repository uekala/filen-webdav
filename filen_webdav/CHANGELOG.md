# Änderungen

## 0.5.0

- Neu: **eigenständiger Betrieb** als Docker-Container ohne Home Assistant OS, z. B. auf Unraid. Fertiges Image
  für amd64 und arm64 unter `ghcr.io/uekala/filen-webdav`, Anleitung im Repository unter `deploy/standalone`.
  Als HA-App bleibt alles wie bisher.
- Benachrichtigungen gehen im eigenständigen Betrieb über `HA_URL` und `HA_TOKEN` an Home Assistant.
- Die Speichergrenze der rclone-Fernsteuerung (400 MiB) lässt sich mit `RCD_MEMLIMIT` ändern.
- Fehlt `/data/options.json` oder ist sie kein gültiges JSON, steht das jetzt klar im Protokoll.

## 0.4.3

- Aufräumen: neue Regel `einmal: /A` – innerhalb von A bleibt von inhaltsgleichen Dateien (BLAKE3-Hash) nur eine.
  Behalten wird die Datei außerhalb von `_Duplikate`/`_Ohne-Datum`/„Neuer Ordner“, ohne Kopie-Endung
  (`_2`, `(1)`, `-Kopie`, `-TABLET`), mit dem längeren Dateinamen und dem kürzeren Pfad.

## 0.4.2

- Neu: **Filen: aufräumen** – Regeln `doppelt: /A => /B` (Dateien unter A in den Papierkorb, die es unter B
  inhaltsgleich gibt, geprüft per BLAKE3-Hash) und `weg: /Pfad`. Mit Probelauf.
- Doppel-Suche zeigt zusätzlich die 30 größten Doppel-Gruppen mit Pfaden.

## 0.4.1

- Neu: **Filen: Doppel suchen** – findet doppelte Dateien in Filen und zeigt, welche Ordner sich überschneiden
  (Protokoll und CSV-Bericht). Nur lesend.

## 0.4.0

- Neu: **Filen ordnen** – Übersicht über alle Ordner in Filen mit Anzahl und Größe, und Ordner oder Dateien
  per Liste „/von -> /nach“ serverseitig verschieben (ohne neues Hochladen, Ziele werden nie zusammengeführt).
- OneDrive-Umzug: Der Eintrag „.“ umfasst jetzt wirklich nur die losen Dateien im Hauptverzeichnis. Die
  Begrenzung auf eine Ebene (MaxDepth) kennt der rclone-Filter nicht; sie wurde ignoriert, sodass „.“ auch
  nicht gelistete Unterordner kopiert und am Ende gelöscht hat (nach vollständiger Prüfung).

- Foto-Abgleich: Ausnahmen (andere gelistete Unterordner, z. B. `Bilder/Creative Cloud Files` oder Löschkandidaten)
  griffen nicht, weil der Filter relativ zur OneDrive-Wurzel ausgewertet wurde. Dadurch landeten auch
  Nicht-Foto-Dateien dieser Unterordner in `/Fotos/_Aus-OneDrive`.

## 0.3.9

- OneDrive-Umzug prüft jetzt positiv: Eine Datei gilt erst als vorhanden, wenn rclone sie im Ziel gefunden und
  die Größe verglichen hat. Grundlage ist eine eigene, vollständige Liste der Quelldateien. Bisher konnten
  Dateien in einem Quellverzeichnis, das rclone nicht lesen konnte, unbemerkt durchrutschen.
- Bis zu drei Durchgänge aus Kopie und Prüfung; was ein Durchgang bestätigt hat, bleibt bestätigt. Filen schließt
  die Verbindung nach 2000 Anfragen (HTTP/2 GOAWAY), dadurch scheiterte bisher fast jede Prüfung großer Ordner.

## 0.3.8

- OneDrive-Umzug: Meldet die Prüfung eines Ordners Abweichungen, wird bis zu zweimal erneut kopiert und geprüft.
  Filen bricht gelegentlich Verbindungen ab; dann galten Dateien als fehlend, die längst da waren, und das Löschen
  unterblieb. Gezählt wird nur die letzte Prüfung.
- Foto-Abgleich: Scheitert das Kopieren eines Fotos, wird es nach 30 s bis zu zweimal erneut versucht.

## 0.3.7

- Die rclone-Fernsteuerung loggt nur noch Hinweise und Fehler (bei Protokollstufe DEBUG weiterhin alles).
  Große Kopien verdrängen die Ergebnisse von Fotosortierung und OneDrive-Umzug nicht mehr aus dem Log.
- Fotosortierung und OneDrive-Umzug haben getrennte Benachrichtigungen und überschreiben sich nicht mehr.
- Ist Home Assistant beim Senden einer Benachrichtigung gerade nicht erreichbar, wird es bis zu 5 Minuten lang
  erneut versucht.

## 0.3.6

- Persönlicher Tresor von OneDrive wird ausgelassen (gesperrt, rclone meldete „ObjectHandle is Invalid“).
- Foto-Abgleich: gleicher Name (inkl. Zähler) und höchstens 3 % Größenunterschied gilt als vorhanden – Google
  entfernt beim Export über die API Metadaten (Microsofts Google-Fotos-Import).

## 0.3.5

- Foto-Abgleich strenger: Ein Foto gilt nur als vorhanden, wenn Name (inkl. Zähler wie „(1)“) **und** Größe
  übereinstimmen. Serienbilder (0)/(1)/(2) werden nicht mehr zusammengeworfen; im Zweifel wird kopiert.

## 0.3.4

- Foto-Abgleich erkennt Dateien aus Microsofts Google-Fotos-Import (Kennung wie `_83a5f51f` vor der Endung).

## 0.3.3

- OneDrive-Umzug: Pfade, die an anderer Stelle gelistet sind (z. B. „Ohne Kopie löschen“ oder ein eigener
  Foto-Abgleich), werden beim Kopieren des übergeordneten Ordners automatisch ausgelassen.
- Eintrag `.` in „Ordner/Dateien kopieren“ übernimmt die losen Dateien im Hauptverzeichnis von OneDrive.
- Gelöscht wird nur, wenn **alle** Kopien und Abgleiche fehlerfrei waren; übergeordnete Ordner werden in einem Schritt
  gelöscht, lose Dateien im Hauptverzeichnis zuletzt.
- Summe der Übertragung und freier Platz in Filen im Protokoll.

## 0.3.2

- Speicher: Die OneDrive-Analyse hat alle 361.000 Dateien auf einmal eingelesen; rclone brauchte 1,4 GB und wurde
  vom System beendet. Jetzt: Ordnergrößen über `operations/size`, große Dateien über einen Größenfilter (ab 50 MB),
  Prüfung nach dem Kopieren über `operations/check` (liefert nur Abweichungen).
- rclone-Fernsteuerung mit Speichergrenze (GOMEMLIMIT 400 MiB, `--use-mmap`) und automatischem Neustart.

## 0.3.1

- Große Auflistungen (z. B. OneDrive mit mehreren 100 GB) laufen als Hintergrund-Auftrag von rclone;
  vorher brach die OneDrive-Analyse nach 10 Minuten mit „timed out“ ab.

## 0.3.0

- Neu: Umzug von OneDrive nach Filen über rclone.
  - `analyse`: liest OneDrive ein, schreibt Ordnergrößen, größte Dateien und Altlasten-Kandidaten (ISOs, VM-Images,
    Installer, alte Sicherungen) ins Protokoll und als CSV nach `share/filen_webdav`. Kopiert und löscht nichts.
  - `umzug`: kopiert gelistete Ordner nach `<Ziel>/<Pfad>` und prüft jede Datei (Name + Größe). Foto-Ordner werden
    gegen `/Fotos` abgeglichen; nur Fehlendes kommt nach `/Fotos/_Aus-OneDrive`.
  - Löschen in OneDrive nur mit `onedrive_loeschen`, nur nach fehlerfreier Prüfung und nur in den OneDrive-Papierkorb.
- Probelauf ist Standard.

## 0.2.2

- Fotosortierung: Pfade aus der rclone-Fernsteuerung wurden doppelt zusammengesetzt (Quellordner zweimal);
  dadurch waren Google-JSON und EXIF nicht lesbar und Dateien landeten fälschlich bei „Ohne Datum“.

## 0.2.1

- Fotosortierung deutlich schneller: keine Hash-Abfrage pro Datei mehr (Filen braucht dafür je Datei eine
  Extra-Anfrage). Duplikat = gleicher Name (ohne „(1)“) und gleiche Größe in Byte.
- Im Ziel werden nur noch die Jahres- und Sonderordner eingelesen, nicht die Quellordner ein zweites Mal.
- Fortschritt im Protokoll alle 1000 Dateien.

## 0.2.0

- Neu: Fotosortierung. Ordnet Fotos und Videos aus frei wählbaren Filen-Ordnern nach Aufnahmedatum in
  `<Ziel>/JJJJ/JJJJ-MM/`. Datum aus Dateiname, Google-Takeout-JSON oder EXIF (exiftool), sonst `_Ohne-Datum`.
  Exakte Duplikate (gleicher Hash) wandern nach `_Duplikate`, Google-JSON nach `_Google-Metadaten`.
  Gleichnamige Dateien werden nie überschrieben, sondern durchnummeriert.
- Probelauf (Standard): nichts wird verschoben, nur Bericht als CSV in `share/filen_webdav` und Benachrichtigung.
- Läuft beim Start und täglich zur eingestellten Uhrzeit; Zugriff auf Filen über eine nur lokal erreichbare
  rclone-Fernsteuerung, damit nur eine Anmeldung nötig ist.

## 0.1.0

- Erste Version: WebDAV-Server mit rclone 1.76.0 für einen Ordner im Filen-Laufwerk, Anmeldung per API-Schlüssel
  (keine 2FA-Eingabe beim Start), Prüfung der Anmeldung beim Start, Ordner wird bei Bedarf angelegt.
