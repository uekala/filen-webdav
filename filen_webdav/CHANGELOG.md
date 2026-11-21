# Änderungen

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
