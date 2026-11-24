#!/usr/bin/env python3
"""Umzug von OneDrive nach Filen über rclone (läuft einmal beim Start der App).

Modi (Option onedrive_modus):
  aus      – nichts tun
  analyse  – OneDrive einlesen, Ordnergrößen, größte Dateien und Altlasten-Kandidaten ins Protokoll
             und als CSV nach /share/filen_webdav schreiben. Kopiert und löscht nichts.
  umzug    – Ordner aus onedrive_kopieren nach <onedrive_ziel>/<Pfad> kopieren und Datei für Datei
             (Name + Größe) prüfen; Fotos aus onedrive_fotos_abgleich nur übernehmen, wenn sie in /Fotos
             noch fehlen. Mit onedrive_probelauf=true wird nur geplant.
Löschen in OneDrive (Papierkorb, nicht endgültig) nur bei onedrive_loeschen=true und nur:
  - Ordner aus onedrive_kopieren / onedrive_fotos_abgleich, deren Prüfung fehlerfrei war
  - Einträge aus onedrive_nur_loeschen (ohne Kopie, ausdrücklich gelistet)
"""

import csv
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fotosortierer import MEDIA_EXT, RC, ext_of, notify  # noqa: E402

OD = "onedrive:"
BERICHT_DIR = "/share/filen_webdav"
ALTLAST_EXT = {"iso", "img", "vmdk", "vhd", "vhdx", "ova", "ovf", "exe", "msi", "dmg", "dlc", "bin", "apk"}
ALTLAST_WORTE = re.compile(r"(backup|sicherung|setup|install|portable|keygen|crack|benchmark|pcmark)", re.I)


def log(msg):
    print(f"[onedrive] {msg}", flush=True)


def gb(n):
    return f"{n / 1e9:.1f} GB"


def norm(name):
    """Vergleichsname: ohne die 8-stellige Kennung, die Microsofts Google-Fotos-Import anhängt
    (IMG_6174_83a5f51f.JPG -> img_6174.jpg). Zähler wie „(1)“ bleiben erhalten (Serienbilder!)."""
    return re.sub(r"_[0-9a-f]{8}(?=\.[^.]+$)", "", name).lower()


TOLERANZ = 0.03  # Google entfernt beim Export über die API Metadaten – Größe weicht dann leicht ab


def vorhanden(index, f):
    """Vorhanden, wenn ein Foto mit gleichem Namen (inkl. Zähler „(1)“) existiert und die Größe gleich ist
    oder höchstens 3 % abweicht. Größere Abweichung = anderes Foto, wird kopiert."""
    size = f.get("Size") or 0
    for s in index.get(norm(f["Name"]), ()):
        if s == size or (s and size and abs(s - size) <= TOLERANZ * max(s, size)):
            return True
    return False


def od_list(rc, path, modtime=False):
    return RC(fs=OD).list(path.strip("/"), modtime=modtime)


# ------------------------------------------------------------------ Analyse
def groesse(rc, path, filt=None):
    """Anzahl und Bytes eines Ordners, ohne die Dateiliste in den Speicher zu holen."""
    fs = OD if path == ROOT else f"{OD}{path.strip('/')}"
    extra = {"_filter": filt} if filt else {}
    r = rc.call_job("operations/size", fs=fs, **extra)
    return r.get("count", 0), r.get("bytes", 0)


def analyse(rc):
    log("Analyse: ermittle Ordnergrößen (speicherschonend) …")
    odrc = RC(fs=OD)
    ordner = {}
    total_n = total_b = 0
    for d in odrc.list("", recurse=False, dirs=True):
        n, b = groesse(rc, d["Name"])
        ordner[d["Name"]] = b
        total_n += n
        total_b += b
        if b >= 2e9:
            for d2 in odrc.list(d["Name"], recurse=False, dirs=True):
                ordner[f"{d['Name']}/{d2['Name']}"] = groesse(rc, f"{d['Name']}/{d2['Name']}")[1]
    lose = odrc.list("", recurse=False)
    total_n += len(lose)
    total_b += sum(f.get("Size", 0) for f in lose)
    for f in lose:
        if f.get("Size", 0) >= 500e6:
            ordner[f["Name"]] = f["Size"]
    log(f"OneDrive: {total_n} Dateien, {gb(total_b)}")

    log("Suche große Dateien (ab 50 MB) …")
    gross = odrc.list("", modtime=True, filt={"MinSize": "50M"})
    jahr_grenze = dt.datetime.now().year - 5
    altlast = []
    for f in gross:
        jahr = int((f.get("ModTime") or "0000")[:4] or 0)
        ext = ext_of(f["Name"])
        if (ext in ALTLAST_EXT or ALTLAST_WORTE.search(f["Path"])
                or (jahr and jahr < jahr_grenze and ext in {"zip", "7z", "rar", "tar", "gz"})):
            altlast.append((f["Size"], f["Path"], jahr))
    altlast.sort(reverse=True)

    os.makedirs(BERICHT_DIR, exist_ok=True)
    with open(os.path.join(BERICHT_DIR, "onedrive_ordner.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ordner", "bytes", "gb"])
        for k, v in sorted(ordner.items()):
            w.writerow([k, v, round(v / 1e9, 2)])
    with open(os.path.join(BERICHT_DIR, "onedrive_grosse_dateien.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["pfad", "bytes", "geaendert"])
        for f in sorted(gross, key=lambda x: -x.get("Size", 0)):
            w.writerow([f["Path"], f.get("Size", 0), (f.get("ModTime") or "")[:10]])

    for k, v in sorted(ordner.items(), key=lambda x: -x[1]):
        log(f"{'ORDNER2' if '/' in k else 'ORDNER1'} {gb(v):>9} | {k}")
    log(f"=== Altlasten-Kandidaten: {len(altlast)} Dateien, {gb(sum(a[0] for a in altlast))} ===")
    for size, path, jahr in altlast[:150]:
        log(f"ALTLAST {gb(size):>9} | {jahr} | {path}")
    notify("☁️ OneDrive-Analyse fertig",
           f"{total_n} Dateien, {gb(total_b)}\nAltlasten-Kandidaten: {len(altlast)} ({gb(sum(a[0] for a in altlast))})\n"
           f"Details: share/filen_webdav/onedrive_*.csv", nid="filen_onedrive")


# ------------------------------------------------------------------ Umzug
ROOT = "."  # Eintrag für die losen Dateien im Hauptverzeichnis von OneDrive
TRESOR = ("Persönlicher Tresor", "Personal Vault")


def glob_escape(text):
    return re.sub(r"([\\\[\]{}*?])", r"\\\1", text)


def ausschluesse(eintrag, alle_pfade):
    """rclone-Filter: alle anderen gelisteten Pfade unterhalb von `eintrag` auslassen."""
    e = "" if eintrag == ROOT else eintrag.strip("/")
    regeln = []
    for p in alle_pfade:
        p = p.strip("/")
        if p == e or p == ROOT:
            continue
        if e == "":
            rel = p
        elif p.startswith(e + "/"):
            rel = p[len(e) + 1:]
        else:
            continue
        rel = glob_escape(rel)
        regeln += [f"/{rel}", f"/{rel}/**"]
    if e == "":
        # Persönlicher Tresor ist gesperrt und für rclone nicht lesbar
        regeln += [f"/{t}" for t in TRESOR] + [f"/{t}/**" for t in TRESOR]
    filt = {"ExcludeRule": regeln} if regeln else {}
    if eintrag == ROOT:
        filt["MaxDepth"] = 1
    return filt


def fs_von(eintrag):
    return OD if eintrag == ROOT else f"{OD}{eintrag.strip('/')}"

def warte_job(rc, jobid, titel):
    letzte = 0
    while True:
        st = rc.call("job/status", jobid=jobid)
        if st.get("finished"):
            if not st.get("success"):
                raise RuntimeError(f"{titel}: {st.get('error')}")
            return
        if time.time() - letzte > 300:
            s = rc.call("core/stats", group=f"job/{jobid}")
            log(f"{titel}: {gb(s.get('bytes', 0))} übertragen, {s.get('transfers', 0)} Dateien, "
                f"{s.get('errors', 0)} Fehler, {s.get('speed', 0) / 1e6:.1f} MB/s")
            letzte = time.time()
        time.sleep(20)


def pruefe(rc, src, dst, filt=None):
    """Liefert die Dateien, die im Ziel vorhanden und gleich groß sind (OneDrive und Filen haben keinen
    gemeinsamen Hash, rclone vergleicht dann die Größe). Nur positiv bestätigte Dateien zählen: Kann rclone
    ein Verzeichnis nicht lesen, tauchen dessen Dateien hier nicht auf und gelten weiter als offen."""
    extra = {"_filter": filt} if filt else {}
    r = rc.call_job("operations/check", srcFs=fs_von(src), dstFs=f"filen:{dst}", oneWay=True,
                    match=True, missingOnDst=True, differ=True, error=True, **extra)
    return {unicodedata.normalize("NFC", x) for x in (r.get("match") or [])}


def quellliste(src, filt, anzahl):
    """Unabhängige Liste aller Quelldateien (relativ zu `src`). Muss mindestens so viele Dateien enthalten
    wie die Größenabfrage gezählt hat, sonst gilt sie als unvollständig."""
    for versuch in range(3):
        if versuch:
            time.sleep(60)
        try:
            liste = {unicodedata.normalize("NFC", e["Path"]) for e in RC(fs=fs_von(src)).list("", filt=filt or None)}
        except Exception as e:
            log(f"Quellliste {src} nicht lesbar: {e}")
            continue
        if len(liste) >= anzahl:
            return liste
        log(f"Quellliste {src} unvollständig: {len(liste)} von {anzahl} Dateien")
    return None


def kopiere_ordner(rc, path, ziel_root, probelauf, alle_pfade):
    src = ROOT if path.strip() in (ROOT, "/") else path.strip("/")
    dst = ziel_root.strip("/") if src == ROOT else f"{ziel_root.strip('/')}/{src}"
    filt = ausschluesse(src, alle_pfade)
    anzahl, bytes_ = groesse(rc, src, filt)
    aus = len(filt.get("ExcludeRule", [])) // 2
    log(f"KOPIEREN {src}: {anzahl} Dateien, {gb(bytes_)} -> /{dst}" + (f" (ohne {aus} gelistete Unterpfade)" if aus else ""))
    if probelauf or not anzahl:
        return {"pfad": src, "dateien": anzahl, "bytes": bytes_, "fehlend": None if probelauf else []}
    extra = {"_filter": filt} if filt else {}
    quelle = quellliste(src, filt, anzahl)
    if quelle is None:
        log(f"GEPRÜFT {src}: Quellliste nicht vollständig lesbar – gilt als nicht geprüft")
        return {"pfad": src, "dateien": anzahl, "bytes": bytes_, "fehlend": ["Quellliste nicht lesbar"]}
    # Filen schließt die Verbindung regelmäßig (HTTP/2 GOAWAY nach 2000 Anfragen). Ein Verzeichnis, das dabei
    # nicht gelesen werden konnte, ist in diesem Durchgang unbestätigt. Bis zu drei Durchgänge (kopieren +
    # prüfen); eine Datei gilt als vorhanden, sobald ein Durchgang sie bestätigt hat.
    bestaetigt = set()
    fehlend = sorted(quelle)
    for versuch in range(3):
        if versuch:
            log(f"NACHPRÜFUNG {src}: {len(fehlend)} unbestätigt – Durchgang {versuch + 1} von 3 in 60 s")
            time.sleep(60)
        try:
            job = rc.call("sync/copy", srcFs=fs_von(src), dstFs=f"filen:{dst}", _async=True, **extra)
            warte_job(rc, job["jobid"], f"Kopie {src}")
        except Exception as e:
            log(f"Kopie {src} mit Fehlern beendet: {e} – die Prüfung entscheidet")
        try:
            bestaetigt |= pruefe(rc, src, dst, filt)
        except Exception as e:
            log(f"Prüfung {src} fehlgeschlagen: {e}")
        fehlend = sorted(quelle - bestaetigt)
        if not fehlend:
            break
    log(f"GEPRÜFT {src}: {len(quelle) - len(fehlend)}/{len(quelle)} bestätigt" + (f", offen u. a. {fehlend[:3]}" if fehlend else ""))
    return {"pfad": src, "dateien": anzahl, "bytes": bytes_, "fehlend": fehlend}


def foto_abgleich(rc, path, foto_namen, probelauf, alle_pfade):
    src = path.strip("/")
    filt = ausschluesse(src, alle_pfade)
    # Filter gelten relativ zur Wurzel des Remotes – deshalb direkt auf den Quellordner wurzeln
    alle = RC(fs=fs_von(src)).list("", filt=filt or None)
    dateien = [f for f in alle if ext_of(f["Name"]) in MEDIA_EXT]
    # Andere Dateien (außer Google-JSON/HTML) werden immer mitgenommen, damit beim Löschen nichts verloren geht
    sonstige = [f for f in alle if ext_of(f["Name"]) not in MEDIA_EXT | {"json", "html"}]
    fehlen = [f for f in dateien if not vorhanden(foto_namen, f)] + sonstige
    nur_name = sum(1 for f in dateien if not vorhanden(foto_namen, f) and norm(f["Name"]) in foto_namen)
    if nur_name:
        log(f"HINWEIS {src}: {nur_name} Dateien mit gleichem Namen, aber anderer Größe – werden sicherheitshalber übernommen")
    log(f"FOTOABGLEICH {src}: {len(dateien)} Fotos/Videos, davon schon in Filen: {len(dateien) - len(fehlen) + len(sonstige)}, "
        f"zu übernehmen: {len(fehlen) - len(sonstige)} Fotos/Videos + {len(sonstige)} andere Dateien "
        f"({gb(sum(f.get('Size', 0) for f in fehlen))})")
    for f in fehlen[:20]:
        log(f"FEHLT {f['Path']}")
    if probelauf:
        return {"pfad": src, "dateien": len(dateien), "fehlen": len(fehlen), "fehlend": None,
                "bytes": sum(f.get("Size", 0) for f in fehlen)}
    fehler = []
    for f in fehlen:
        dst = f"Fotos/_Aus-OneDrive/{src}/{f['Path']}"
        for versuch in range(3):
            try:
                rc.call("operations/copyfile", srcFs=OD, srcRemote=f"{src}/{f['Path']}", dstFs="filen:", dstRemote=dst)
                foto_namen.setdefault(norm(f["Name"]), set()).add(f.get("Size"))
                break
            except Exception as e:
                if versuch == 2:
                    fehler.append(f["Path"])
                    log(f"FEHLER {src}/{f['Path']}: {e}")
                else:
                    time.sleep(30)
    return {"pfad": src, "dateien": len(dateien), "fehlen": len(fehlen), "fehlend": fehler,
            "bytes": sum(f.get("Size", 0) for f in fehlen)}


def loesche(rc, path):
    p = path.strip("/")
    if p == ROOT:
        # nur die losen Dateien im Hauptverzeichnis (keine Ordner)
        rc.call_job("operations/delete", fs=OD, _filter=ausschluesse(ROOT, []))
        log("GELÖSCHT (OneDrive-Papierkorb): lose Dateien im Hauptverzeichnis")
        return
    if not p:
        raise RuntimeError("Wurzel von OneDrive wird nie gelöscht")
    try:
        rc.call("operations/purge", fs=OD, remote=p)  # Ordner -> OneDrive-Papierkorb
    except Exception:
        rc.call("operations/deletefile", fs=OD, remote=p)  # einzelne Datei
    log(f"GELÖSCHT (OneDrive-Papierkorb): {p}")


def umzug(rc, opt):
    probelauf = bool(opt.get("onedrive_probelauf", True))
    loeschen = bool(opt.get("onedrive_loeschen", False)) and not probelauf
    ziel_root = opt.get("onedrive_ziel", "/OneDrive")
    ergebnis = []
    kopieren = [p for p in opt.get("onedrive_kopieren", []) if p.strip()]
    nur_loeschen = [p for p in opt.get("onedrive_nur_loeschen", []) if p.strip()]
    foto_quellen = [p for p in opt.get("onedrive_fotos_abgleich", []) if p.strip()]
    alle_pfade = kopieren + nur_loeschen + foto_quellen
    if foto_quellen:
        log("Lese vorhandene Fotos in Filen /Fotos …")
        foto_namen = {}
        for f in RC().list("Fotos"):
            foto_namen.setdefault(norm(f["Name"]), set()).add(f.get("Size"))
        log(f"In Filen /Fotos: {len(foto_namen)} verschiedene Dateinamen")
        for p in foto_quellen:
            r = foto_abgleich(rc, p, foto_namen, probelauf, alle_pfade)
            ergebnis.append(("fotoabgleich", r))

    for p in kopieren:
        try:
            ergebnis.append(("kopie", kopiere_ordner(rc, p, ziel_root, probelauf, alle_pfade)))
        except Exception as e:
            log(f"FEHLER bei {p}: {e}")
            ergebnis.append(("kopie", {"pfad": p, "fehlend": ["Abbruch"]}))

    geloescht = []
    alles_ok = all(r.get("fehlend") == [] for _, r in ergebnis)
    if loeschen and not alles_ok:
        for _, r in ergebnis:
            if r.get("fehlend") != []:
                log(f"NICHT sauber: {r['pfad']} – deshalb wird in OneDrive NICHTS gelöscht")
    elif loeschen:
        ziele = [r["pfad"] for _, r in ergebnis] + nur_loeschen
        ziele = [p.strip("/") for p in ziele]
        # Unterpfade weglassen, wenn ein übergeordneter Ordner ohnehin gelöscht wird
        minimal = [p for p in ziele if p == ROOT or not any(q != ROOT and q != p and p.startswith(q + "/") for q in ziele)]
        # Lose Dateien im Hauptverzeichnis zuletzt (sie enthalten ggf. auch einzeln gelistete Dateien)
        reihenfolge = [p for p in dict.fromkeys(minimal) if p != ROOT] + ([ROOT] if ROOT in minimal else [])
        for p in reihenfolge:
            try:
                loesche(rc, p)
                geloescht.append(p)
            except Exception as e:
                log(f"FEHLER beim Löschen {p}: {e}")
    elif not probelauf:
        log("Löschen ist aus (onedrive_loeschen=false) – OneDrive bleibt unverändert.")

    gesamt = sum(r.get("bytes", 0) for _, r in ergebnis)
    log(f"SUMME nach Filen: {gb(gesamt)}")
    try:
        about = RC().call_job("operations/about", fs="filen:")
        if about.get("free") is not None:
            log(f"Filen frei: {gb(about['free'])} (belegt {gb(about.get('used', 0))} von {gb(about.get('total', 0))})")
    except Exception:
        pass

    zeilen = []
    for art, r in ergebnis:
        if art == "kopie":
            status = "geplant" if r.get("fehlend") is None else ("ok" if not r["fehlend"] else f"{len(r['fehlend'])} fehlen")
            zeilen.append(f"📁 {r['pfad']}: {r.get('dateien', '?')} Dateien, {gb(r.get('bytes', 0))} – {status}")
        else:
            status = "geplant" if r.get("fehlend") is None else ("ok" if not r["fehlend"] else f"{len(r['fehlend'])} Fehler")
            zeilen.append(f"📸 {r['pfad']}: {r['fehlen']} Dateien ({gb(r.get('bytes', 0))}) fehlten in Filen, "
                          f"{r['dateien']} Fotos/Videos geprüft – {status}")
    zeilen.append(f"Σ nach Filen: {gb(gesamt)}")
    if probelauf and nur_loeschen:
        zeilen.append(f"🗑️ würde gelöscht (ohne Kopie): {len(nur_loeschen)} Pfade")
    if geloescht:
        zeilen.append("🗑️ in OneDrive gelöscht (Papierkorb): " + ", ".join(geloescht))
    text = ("Probelauf – nichts kopiert/gelöscht\n" if probelauf else "") + "\n".join(zeilen)
    log("ERGEBNIS | " + text.replace("\n", " | "))
    notify("☁️ OneDrive → Filen", text or "nichts zu tun", nid="filen_onedrive")


def schreibe_config(opt):
    """Legt den rclone-Eintrag [onedrive] in /data/rclone.conf an, wenn sich das Token geändert hat.
    rclone erneuert das Token selbst und schreibt es in dieselbe Datei zurück."""
    import hashlib
    token = (opt.get("onedrive_token") or "").strip()
    drive_id = (opt.get("onedrive_drive_id") or "").strip()
    if not token or not drive_id:
        print("[onedrive] FEHLER: onedrive_token und onedrive_drive_id müssen gesetzt sein", flush=True)
        return 1
    json.loads(token)  # Format prüfen
    conf, marker = "/data/rclone.conf", "/data/onedrive_token.sha256"
    h = hashlib.sha256((token + drive_id).encode()).hexdigest()
    if os.path.exists(marker) and open(marker).read().strip() == h and "[onedrive]" in open(conf).read():
        return 0
    alt = open(conf).read() if os.path.exists(conf) else ""
    alt = re.sub(r"\[onedrive\][^\[]*", "", alt)
    with open(conf, "w") as fh:
        fh.write(alt.strip() + ("\n\n" if alt.strip() else "") +
                 f"[onedrive]\ntype = onedrive\ntoken = {token}\ndrive_id = {drive_id}\n"
                 "drive_type = personal\ndelta = true\n")
    os.chmod(conf, 0o600)
    with open(marker, "w") as fh:
        fh.write(h)
    print("[onedrive] rclone-Konfiguration für OneDrive geschrieben", flush=True)
    return 0


def main():
    with open("/data/options.json", encoding="utf-8") as fh:
        opt = json.load(fh)
    if "--config" in sys.argv:
        return schreibe_config(opt)
    modus = opt.get("onedrive_modus", "aus")
    if modus == "aus":
        return
    rc = RC(fs=OD)
    for _ in range(30):
        try:
            rc.call("rc/noop")
            break
        except Exception:
            time.sleep(2)
    try:
        if modus == "analyse":
            analyse(rc)
        elif modus == "umzug":
            umzug(rc, opt)
    except Exception as e:
        log(f"FEHLER: {e}")
        notify("☁️ OneDrive → Filen fehlgeschlagen", str(e), nid="filen_onedrive")


if __name__ == "__main__":
    sys.exit(main())
