"""Versione in esecuzione e controllo aggiornamenti (OTA e APK).

Senza dipendenze da Kivy: l'interfaccia chiama check() in un thread e
mostra il risultato.

- OTA: confronta version.txt su GitHub con quello del codice in esecuzione.
- APK: confronta il numero di build dell'APK installato (build_id.txt,
  scritto dal workflow) con quello della release "apk-latest".
  Se l'APK e' stato compilato a mano (niente build_id.txt) l'avviso APK
  resta spento, perche' non si puo' sapere se e' vecchio.
"""

import os
import re
import sys
from pathlib import Path

import requests

# gli stessi valori di main.py (OTA_REPO / OTA_BRANCH)
REPO = "ZenigataBloch/magi-android-os"
BRANCH = "main"
APK_TAG = "apk-latest"

CODE_DIR = Path(__file__).resolve().parent.parent
TIMEOUT = 10


def _read_int(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _norm(path):
    return os.path.realpath(str(path))


def _ota_root():
    private = os.environ.get("ANDROID_PRIVATE")
    return os.path.join(private, "ota") if private else None


def running_version():
    return _read_int(CODE_DIR / "version.txt")


def running_source():
    """'OTA' se il codice viene dalla cartella degli aggiornamenti,
    'APK' se e' quello incluso nell'APK, 'DEV' fuori da Android."""
    root = _ota_root()
    if not root:
        return "DEV"
    if _norm(CODE_DIR).startswith(_norm(root) + os.sep):
        return "OTA"
    return "APK"


def installed_build():
    """Numero di build dell'APK installato, oppure None se non compilato da GitHub."""
    candidates = [
        os.environ.get("ANDROID_ARGUMENT"),
        os.environ.get("ANDROID_APP_PATH"),
        *sys.path,
    ]
    for d in candidates:
        if not d or "/ota/" in d.replace("\\", "/") + "/":
            continue
        path = os.path.join(d, "build_id.txt")
        if os.path.exists(path):
            n = _read_int(path)
            if n:
                return n
    return None


def build_info():
    """Testo breve per l'interfaccia, es. 'v2 OTA #7'."""
    text = f"v{running_version()} {running_source()}"
    build = installed_build()
    if build:
        text += f" #{build}"
    return text


def pending_ota():
    """Versione gia' scaricata e pronta alla prossima apertura, o None."""
    root = _ota_root()
    if not root:
        return None
    v = _read_int(os.path.join(root, "current", "version.txt"))
    return v if v > running_version() else None


def _bad_ota():
    root = _ota_root()
    return _read_int(os.path.join(root, "bad.txt")) if root else 0


def remote_version():
    r = requests.get(
        f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.txt",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return int(r.text.strip())


def latest_apk():
    """(numero_build, url_download) della release apk-latest, o (None, None)."""
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/releases/tags/{APK_TAG}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "magi-os",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    m = re.search(r"build\s+(\d+)", str(data.get("name", "")), re.I)
    build = int(m.group(1)) if m else None

    url = next(
        (
            a.get("browser_download_url")
            for a in data.get("assets", [])
            if str(a.get("name", "")).endswith(".apk")
        ),
        None,
    )
    return (build, url) if build and url else (None, None)


def check():
    """Ritorna {"ota": None | ("ready"|"downloading", versione),
                "apk": None | (build, url)}."""
    out = {"ota": None, "apk": None}

    run = running_version()
    pending = pending_ota()

    if pending:
        out["ota"] = ("ready", pending)
    else:
        try:
            remote = remote_version()
            if remote > run and remote != _bad_ota():
                out["ota"] = ("downloading", remote)
        except Exception:
            pass

    installed = installed_build()
    if installed is not None:
        try:
            build, url = latest_apk()
            if build and build > installed:
                out["apk"] = (build, url)
        except Exception:
            pass

    return out


def open_url(url):
    """Apre il link nel browser (Android: Intent; altrove: webbrowser)."""
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    except Exception:
        import webbrowser

        webbrowser.open(url)
