# Änderungen

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
