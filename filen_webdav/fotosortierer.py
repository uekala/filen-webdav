#!/usr/bin/env python3
"""Sortiert Fotos und Videos in Filen nach Aufnahmedatum: <ziel>/JJJJ/JJJJ-MM/.

Spricht über die rclone-Fernsteuerung (rclone rcd auf 127.0.0.1) mit Filen,
damit für alle Dateien nur eine Anmeldung nötig ist.

Datumsquelle (in dieser Reihenfolge):
  1. Dateiname (z. B. 20250814_153012.jpg, IMG-20250814-WA0001.jpg, PXL_20250814_...)
  2. Google-Takeout-JSON (photoTakenTime)
  3. EXIF/Metadaten der Datei (exiftool)
Ohne Datum: <ziel>/_Ohne-Datum/
Exakte Duplikate (gleicher Hash, sonst gleiche Größe + gleicher Name): <ziel>/_Duplikate/
Google-JSON-Dateien: nach der Sortierung nach <ziel>/_Google-Metadaten/
"""

import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

MEDIA_EXT = {
    "jpg", "jpeg", "png", "heic", "heif", "gif", "webp", "bmp", "tif", "tiff", "dng",
    "mp4", "mov", "m4v", "3gp", "avi", "mkv", "webm", "mpg", "mpeg",
}
SPECIAL_DIRS = ("_Duplikate", "_Ohne-Datum", "_Google-Metadaten")
DATE_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)")
MIN_YEAR = 1990


def log(msg):
    print(f"[fotosortierer] {msg}", flush=True)


# ---------------------------------------------------------------- rclone rc
class RC:
    def __init__(self, url="http://127.0.0.1:5572", fs="filen:"):
        self.url = url.rstrip("/")
        self.fs = fs

    def call(self, method, **params):
        req = urllib.request.Request(
            f"{self.url}/{method}",
            data=json.dumps(params).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read() or b"{}")

    def list(self, remote):
        try:
            res = self.call("operations/list", fs=self.fs, remote=remote,
                            opt={"recurse": True, "showHash": True, "filesOnly": True, "noMimeType": True})
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        return res.get("list", [])

    def move(self, src, dst):
        self.call("operations/movefile", srcFs=self.fs, srcRemote=src, dstFs=self.fs, dstRemote=dst)

    def download(self, src, local_dir, name):
        self.call("operations/copyfile", srcFs=self.fs, srcRemote=src, dstFs=local_dir, dstRemote=name)
        return os.path.join(local_dir, name)

    def rmdirs(self, remote):
        try:
            self.call("operations/rmdirs", fs=self.fs, remote=remote, leaveRoot=False)
        except Exception as e:  # leere Ordner aufräumen ist optional
            log(f"Leere Ordner unter {remote} nicht entfernt: {e}")


# ---------------------------------------------------------------- Datum
def plausible(d):
    return d is not None and MIN_YEAR <= d.year and d <= dt.datetime.now() + dt.timedelta(days=1)


def date_from_name(name):
    for m in DATE_RE.finditer(name):
        try:
            d = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if plausible(d):
            return d
    return None


def date_from_json(data):
    for key in ("photoTakenTime", "creationTime"):
        ts = (data.get(key) or {}).get("timestamp")
        if ts:
            try:
                d = dt.datetime.fromtimestamp(int(ts))  # lokale Zeit (TZ vom Supervisor)
            except (ValueError, OverflowError, OSError):
                continue
            if plausible(d):
                return d
    return None


def date_from_exif(path):
    try:
        out = subprocess.run(
            ["exiftool", "-j", "-api", "QuickTimeUTC", "-d", "%Y-%m-%d %H:%M:%S",
             "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate", "-TrackCreateDate", path],
            capture_output=True, text=True, timeout=60,
        ).stdout
        data = json.loads(out or "[{}]")[0]
    except Exception:
        return None
    for key in ("DateTimeOriginal", "CreateDate", "MediaCreateDate", "TrackCreateDate"):
        v = data.get(key)
        if isinstance(v, str):
            try:
                d = dt.datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if plausible(d):
                return d
    return None


# ---------------------------------------------------------------- Google-JSON
def json_candidates(media_name):
    """Namen der zugehörigen Takeout-JSON, wie Google sie vergibt (auch gekürzt)."""
    names = [media_name]
    m = re.match(r"^(.*)\((\d+)\)(\.[^.]+)$", media_name)  # Bild(1).jpg -> Bild.jpg(1).json
    if m:
        names.append(f"{m.group(1)}{m.group(3)}({m.group(2)})")
    return names


def find_json(media_path, jsons_in_dir):
    name = os.path.basename(media_path)
    for base in json_candidates(name):
        for j in jsons_in_dir:
            jn = os.path.basename(j)
            if jn == base + ".json" or (jn.startswith(base + ".") and jn.endswith(".json")):
                return j
    # Google kürzt lange Namen (ohne .json) auf 46/51 Zeichen
    stem = name
    for j in jsons_in_dir:
        jn = os.path.basename(j)[:-5]
        core = jn.split(".supplemental")[0]
        if len(core) >= 30 and stem.startswith(core):
            return j
    return None


# ---------------------------------------------------------------- Planung
def ext_of(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def is_year_dir(top):
    return bool(re.fullmatch(r"(19|20)\d{2}", top))


def dup_key(entry):
    hashes = entry.get("Hashes") or {}
    for h in sorted(hashes):
        if hashes[h]:
            return ("hash", h, hashes[h])
    return ("size+name", entry.get("Size"), entry.get("Name", "").lower())


def unique_target(target, taken):
    """Freier Zielname; `taken` enthält Pfade in Kleinschreibung (Filen unterscheidet nicht)."""
    if target.lower() not in taken:
        return target
    base, dot, ext = target.rpartition(".")
    if not dot:
        base, ext = target, ""
    for i in range(1, 10000):
        cand = f"{base}_{i}.{ext}" if ext else f"{base}_{i}"
        if cand.lower() not in taken:
            return cand
    raise RuntimeError(f"kein freier Name für {target}")


def plan(rc, ziel, quellen, tmp):
    ziel = ziel.strip("/")
    # Bereits sortierter Bestand im Ziel (nur Jahresordner) als Duplikat- und Namensbasis
    taken, seen = set(), {}
    for e in rc.list(ziel):
        top = e["Path"].split("/", 1)[0]
        p = f"{ziel}/{e['Path']}"
        if is_year_dir(top) or top in ("_Ohne-Datum",):
            taken.add(p.lower())
            seen.setdefault(dup_key(e), p)
        elif top in SPECIAL_DIRS:
            taken.add(p.lower())  # nie überschreiben, aber nicht als Original zählen
    log(f"Im Ziel schon sortiert: {len(taken)} Dateien")

    actions = []  # (aktion, quelle, ziel, datumsquelle)
    stats = {"sortiert": 0, "duplikat": 0, "ohne_datum": 0, "json": 0, "sonstige": 0}
    json_cache = {}
    for q in quellen:
        q = q.strip("/")
        entries = rc.list(q)
        log(f"Quelle /{q}: {len(entries)} Dateien")
        by_dir = {}
        for e in entries:
            by_dir.setdefault(os.path.dirname(e["Path"]), []).append(e)
        for d, files in sorted(by_dir.items()):
            jsons = [f"{q}/{f['Path']}" for f in files if f["Name"].lower().endswith(".json")]
            for e in sorted(files, key=lambda x: x["Path"]):
                src = f"{q}/{e['Path']}"
                name = e["Name"]
                ext = ext_of(name)
                if ext == "json":
                    continue
                if ext not in MEDIA_EXT:
                    stats["sonstige"] += 1
                    continue
                key = dup_key(e)
                if key in seen:
                    rel = src[len(q) + 1:]
                    actions.append(("duplikat", src, f"{ziel}/_Duplikate/{os.path.basename(q)}/{rel}", f"wie {seen[key]}"))
                    stats["duplikat"] += 1
                    continue
                datum, quelle = date_from_name(name), "dateiname"
                if datum is None:
                    j = find_json(src, jsons)
                    if j:
                        if j not in json_cache:
                            try:
                                with open(rc.download(j, tmp, "meta.json"), encoding="utf-8") as fh:
                                    json_cache[j] = date_from_json(json.load(fh))
                            except Exception as ex:
                                log(f"JSON {j} nicht lesbar: {ex}")
                                json_cache[j] = None
                        datum, quelle = json_cache[j], "google-json"
                if datum is None:
                    try:
                        local = rc.download(src, tmp, "datei." + ext)
                        datum, quelle = date_from_exif(local), "exif"
                        os.remove(local)
                    except Exception as ex:
                        log(f"{src} nicht lesbar: {ex}")
                if datum is None:
                    target = unique_target(f"{ziel}/_Ohne-Datum/{name}", taken)
                    actions.append(("ohne_datum", src, target, "-"))
                    stats["ohne_datum"] += 1
                else:
                    target = unique_target(f"{ziel}/{datum:%Y}/{datum:%Y-%m}/{name}", taken)
                    actions.append(("sortiert", src, target, f"{quelle} {datum:%Y-%m-%d}"))
                    stats["sortiert"] += 1
                taken.add(target.lower())
                seen[key] = target
            for j in jsons:
                rel = j[len(q) + 1:]
                actions.append(("json", j, f"{ziel}/_Google-Metadaten/{os.path.basename(q)}/{rel}", "-"))
                stats["json"] += 1
    return actions, stats


# ---------------------------------------------------------------- Ablauf
def notify(title, message):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    req = urllib.request.Request(
        "http://supervisor/core/api/services/persistent_notification/create",
        data=json.dumps({"title": title, "message": message, "notification_id": "filen_fotosortierer"}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"Benachrichtigung fehlgeschlagen: {e}")


def run(rc, ziel, quellen, probelauf, bericht_dir):
    start = time.time()
    tmp = tempfile.mkdtemp(prefix="fotos-", dir="/data" if os.path.isdir("/data") else None)
    try:
        actions, stats = plan(rc, ziel, quellen, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fehler = 0
    if not probelauf:
        for i, (art, src, dst, _) in enumerate(actions, 1):
            try:
                rc.move(src, dst)
            except Exception as e:
                fehler += 1
                log(f"FEHLER beim Verschieben {src} -> {dst}: {e}")
            if i % 500 == 0:
                log(f"{i}/{len(actions)} verschoben")
        for q in quellen:
            rc.rmdirs(q.strip("/"))

    os.makedirs(bericht_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    bericht = os.path.join(bericht_dir, f"fotosortierung_{stamp}{'_probelauf' if probelauf else ''}.csv")
    with open(bericht, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["aktion", "von", "nach", "datum/grund"])
        w.writerows(actions)

    dauer = int(time.time() - start)
    modus = "Probelauf – nichts verschoben" if probelauf else f"verschoben, {fehler} Fehler"
    text = (f"{modus}\n\n"
            f"📅 Sortiert: {stats['sortiert']}\n"
            f"♻️ Duplikate: {stats['duplikat']}\n"
            f"❓ Ohne Datum: {stats['ohne_datum']}\n"
            f"🧾 Google-JSON: {stats['json']}\n"
            f"📄 Andere Dateien (bleiben liegen): {stats['sonstige']}\n\n"
            f"Bericht: {bericht.replace('/share', 'share')} · Dauer {dauer // 60} min")
    log(text.replace("\n", " | "))
    if actions or not probelauf:
        notify("📸 Filen-Fotosortierung", text)
    return stats, fehler


def einmal(opt):
    quellen = [q for q in opt.get("foto_quellen", []) if q.strip()]
    if not quellen:
        log("Keine Quellordner eingetragen – nichts zu tun.")
        return
    try:
        run(RC(), opt.get("foto_ziel", "/Fotos"), quellen,
            bool(opt.get("foto_probelauf", True)), "/share/filen_webdav")
    except Exception as e:
        log(f"FEHLER: {e}")
        notify("📸 Filen-Fotosortierung fehlgeschlagen", str(e))


def warte_bis(uhrzeit):
    h, m = (int(x) for x in uhrzeit.split(":"))
    jetzt = dt.datetime.now()
    ziel = jetzt.replace(hour=h, minute=m, second=0, microsecond=0)
    if ziel <= jetzt:
        ziel += dt.timedelta(days=1)
    log(f"Nächster Lauf: {ziel:%d.%m. %H:%M}")
    time.sleep((ziel - jetzt).total_seconds())


def main():
    with open("/data/options.json", encoding="utf-8") as fh:
        opt = json.load(fh)
    if "--dienst" not in sys.argv:
        einmal(opt)
        return
    # Kurz warten, bis rclone rcd bereit ist
    for _ in range(30):
        try:
            RC().call("rc/noop")
            break
        except Exception:
            time.sleep(2)
    if opt.get("foto_beim_start", True):
        einmal(opt)
    while True:
        warte_bis(opt.get("foto_uhrzeit", "03:30"))
        einmal(opt)


if __name__ == "__main__":
    sys.exit(main())
