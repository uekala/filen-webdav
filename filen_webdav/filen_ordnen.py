#!/usr/bin/env python3
"""Filen ordnen: Übersicht über Ordner und Größen, Ordner und Dateien serverseitig verschieben.

Läuft einmal beim Start der App, wenn `filen_uebersicht` an ist oder `filen_verschieben` Einträge hat.
Verschieben geht in Filen ohne neues Hochladen (rclone DirMove). Ein Ziel, das schon existiert, wird nie
zusammengeführt – der Eintrag wird übersprungen, damit nichts überschrieben wird.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fotosortierer import RC, notify  # noqa: E402

OPTIONS = "/data/options.json"
BERICHT_DIR = "/share/filen_webdav"
NID = "filen_ordnen"


def log(msg):
    print(f"[ordnen] {msg}", flush=True)


def groesse_text(n):
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.0f} MB"
    return f"{n / 1e3:.0f} KB"


def warte_auf_rc(rc):
    for _ in range(120):
        try:
            rc.call("rc/noop")
            return True
        except Exception:
            time.sleep(5)
    return False


def nochmal(fn, *a, versuche=4, pause=20, **k):
    """Filen schließt die Verbindung regelmäßig (HTTP/2 GOAWAY) – einzelne Anfragen wiederholen."""
    for v in range(versuche):
        try:
            return fn(*a, **k)
        except Exception as e:
            if v == versuche - 1:
                raise
            log(f"Filen-Aussetzer ({str(e)[:120]}) – neuer Versuch in {pause} s")
            time.sleep(pause)


def eintrag(rc, pfad):
    """Eigenschaften eines Pfads in Filen oder None, wenn es ihn nicht gibt."""
    try:
        r = rc.call("operations/stat", fs="filen:", remote=pfad)
    except Exception as e:
        if "not found" in str(e).lower() or "404" in str(e):
            return None
        raise
    return r.get("item")


def liste_flach(rc, pfad, ordner):
    """Direkte Unterordner bzw. Dateien eines Ordners (nicht rekursiv, schnell)."""
    opt = {"recurse": False, "noMimeType": True, "noModTime": True, ("dirsOnly" if ordner else "filesOnly"): True}
    r = rc.call("operations/list", fs="filen:", remote=pfad, opt=opt)
    return r.get("list", [])


def sammle(rc, pfad):
    """Alle Dateien unter `pfad` als (relativer Pfad, Größe). Erst rekursiv in einem Rutsch; scheitert das
    (Verbindungsabbruch mitten im Durchlauf), wird der Ordner aufgeteilt und Unterordner einzeln gelesen."""
    for _ in range(2):
        try:
            return [(e["Path"], max(e.get("Size", 0), 0)) for e in rc.list(pfad, recurse=True)]
        except Exception:
            time.sleep(10)
    dateien = [(os.path.basename(e["Path"]), max(e.get("Size", 0), 0))
               for e in nochmal(liste_flach, rc, pfad, False)]
    for d in nochmal(liste_flach, rc, pfad, True):
        name = os.path.basename(d["Path"])
        dateien += [(f"{name}/{p}", s) for p, s in sammle(rc, f"{pfad}/{name}")]
    return dateien


def uebersicht(rc):
    log("Übersicht: lese Filen …")
    oben = sorted(os.path.basename(e["Path"]) for e in nochmal(liste_flach, rc, "", True))
    lose = nochmal(liste_flach, rc, "", False)
    agg = defaultdict(lambda: [0, 0])
    for d in oben:
        tiefe = 3 if d == "OneDrive" else 2
        n = 0
        for p, s in sammle(rc, d):
            teile = p.split("/")[:-1]
            for k in range(0, min(len(teile), tiefe - 1) + 1):
                a = agg["/" + "/".join([d] + teile[:k])]
                a[0] += 1
                a[1] += s
            n += 1
        log(f"… /{d}: {n} Dateien gelesen")

    os.makedirs(BERICHT_DIR, exist_ok=True)
    bericht = os.path.join(BERICHT_DIR, f"filen_uebersicht_{dt.datetime.now():%Y-%m-%d_%H%M}.csv")
    with open(bericht, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ordner", "dateien", "bytes"])
        for k in sorted(agg):
            w.writerow([k, agg[k][0], agg[k][1]])

    log(f"ÜBERSICHT – lose Dateien im Hauptverzeichnis: {len(lose)}")
    gesamt = sum(agg[f"/{d}"][1] for d in oben)
    for k in sorted(agg):
        tiefe = k.count("/")
        n, b = agg[k]
        # Tiefe 3 nur für nennenswerte Ordner, damit das Protokoll lesbar bleibt
        if tiefe == 3 and b < 50e6 and n < 200:
            continue
        log(f"{'  ' * (tiefe - 1)}{k}: {n} Dateien, {groesse_text(b)}")
    klein = sum(1 for k in agg if k.count("/") == 3 and agg[k][1] < 50e6 and agg[k][0] < 200)
    if klein:
        log(f"(+ {klein} kleinere Unterordner unter /OneDrive, vollständig im Bericht)")
    log(f"GESAMT: {groesse_text(gesamt)} · Bericht: {bericht.replace('/share', 'share')}")
    notify("🗂️ Filen-Übersicht fertig",
           "\n".join(f"/{d}: {agg['/' + d][0]} Dateien, {groesse_text(agg['/' + d][1])}" for d in oben)
           + f"\n\nDetails: {bericht.replace('/share', 'share')}", nid=NID)


def verschiebe(rc, zeilen, probelauf):
    erledigt, uebersprungen = 0, 0
    for zeile in zeilen:
        if "->" not in zeile:
            log(f"UNGÜLTIG (Format „/von -> /nach“): {zeile}")
            uebersprungen += 1
            continue
        von, nach = (x.strip().strip("/") for x in zeile.split("->", 1))
        if not von or not nach or von == nach or nach.startswith(von + "/"):
            log(f"UNGÜLTIG: {zeile}")
            uebersprungen += 1
            continue
        quelle = nochmal(eintrag, rc, von)
        if quelle is None:
            log(f"ÜBERSPRUNGEN /{von}: nicht vorhanden (schon verschoben?)")
            continue
        if nochmal(eintrag, rc, nach) is not None:
            log(f"ÜBERSPRUNGEN /{von} -> /{nach}: Ziel existiert schon, wird nicht zusammengeführt")
            uebersprungen += 1
            continue
        if probelauf:
            log(f"PROBELAUF: würde /{von} -> /{nach} verschieben")
            continue
        eltern = nach.rsplit("/", 1)[0] if "/" in nach else ""
        if eltern:
            nochmal(rc.call, "operations/mkdir", fs="filen:", remote=eltern)
        try:
            if quelle.get("IsDir"):
                rc.call_job("sync/move", srcFs=f"filen:{von}", dstFs=f"filen:{nach}", deleteEmptySrcDirs=True)
            else:
                rc.call("operations/movefile", srcFs="filen:", srcRemote=von, dstFs="filen:", dstRemote=nach)
            log(f"VERSCHOBEN /{von} -> /{nach}")
            erledigt += 1
        except Exception as e:
            log(f"FEHLER /{von} -> /{nach}: {e}")
            uebersprungen += 1
    if zeilen and not probelauf:
        notify("🗂️ Filen ordnen", f"{erledigt} verschoben, {uebersprungen} übersprungen oder fehlerhaft", nid=NID)


def main():
    with open(OPTIONS, encoding="utf-8") as fh:
        opt = json.load(fh)
    rc = RC()
    if not warte_auf_rc(rc):
        log("rclone-Fernsteuerung nicht erreichbar – Abbruch")
        return
    zeilen = [z for z in opt.get("filen_verschieben", []) if z and z.strip()]
    if zeilen:
        verschiebe(rc, zeilen, bool(opt.get("filen_probelauf", True)))
    if opt.get("filen_uebersicht"):
        try:
            uebersicht(rc)
        except Exception as e:
            log(f"FEHLER Übersicht: {e}")


if __name__ == "__main__":
    main()
