# Filen WebDAV für Home Assistant

Home-Assistant-Add-on, das einen Ordner in [Filen.io](https://filen.io) per WebDAV bereitstellt.
Zusammen mit der eingebauten WebDAV-Integration landen Home-Assistant-Backups Ende-zu-Ende-verschlüsselt in Filen.

## Installation

1. *Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories*
2. `https://github.com/uekala/filen-webdav` hinzufügen
3. **Filen WebDAV** installieren und nach [DOCS.md](filen_webdav/DOCS.md) einrichten

Unterstützt: `aarch64` (z. B. Home Assistant Green), `amd64`.

Grundlage ist [rclone](https://rclone.org/filen/) mit dem Filen-Backend.
