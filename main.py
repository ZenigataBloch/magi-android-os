"""Wrapper di diagnostica + aggiornamento OTA.

Avvia l'app originale (rinominata app_main.py). Se crasha, mostra a schermo:
  - l'ultima riga del traceback (l'errore vero) in evidenza
  - un pulsante COPIA per copiare tutto il traceback negli appunti
  - i percorsi dove e' stato salvato crash.log
Sistema anche load_dotenv() su Android (trova keys.env nella cartella dell'app).

Aggiornamento OTA: all'avvio usa il codice gia' scaricato (se piu' recente di
quello dell'APK) e in background controlla version.txt su GitHub. Il nuovo
codice parte alla riapertura successiva dell'app. Se il codice scaricato
crasha, viene scartato e si torna a quello dell'APK.
"""

import io
import os
import runpy
import shutil
import sys
import threading
import traceback
import zipfile

# ---------------------------------------------------------------- OTA
OTA_REPO = "ZenigataBloch/magi-android-os"
OTA_BRANCH = "main"
OTA_SKIP = {"main.py", "keys.env", "buildozer.spec"}
OTA_REQUIRED = (
    "app_main.py",
    "version.txt",
    os.path.join("ui", "mobile.py"),
    os.path.join("core", "controller.py"),
)

_ota = {"active": False, "version": 0}
_HERE = os.path.dirname(os.path.abspath(__file__))


def _external_dir():
    """Cartella esterna specifica dell'app (Android/data/<pacchetto>/files)."""
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        return activity.getExternalFilesDir(None).getAbsolutePath()
    except Exception:
        return None


def _save(tb):
    """Scrive crash.log in tutte le cartelle disponibili. Ritorna i percorsi."""
    saved = []
    for base in (os.environ.get("ANDROID_PRIVATE"), _external_dir(), os.getcwd()):
        if not base:
            continue
        try:
            path = os.path.join(base, "crash.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write(tb)
            saved.append(path)
        except Exception:
            continue
    return saved


def _last_line(tb):
    lines = [line for line in tb.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "errore sconosciuto"


def _prepare_crash_screen():
    """I widget dell'app morta restano agganciati alla finestra: al primo
    tocco il loro gestore hover rilancia l'errore e uccide anche la schermata
    di crash. Li stacchiamo e facciamo ignorare a Kivy le eccezioni residue."""

    try:
        from kivy.base import ExceptionHandler, ExceptionManager

        class _Ignore(ExceptionHandler):
            def handle_exception(self, inst):
                return ExceptionManager.PASS

        ExceptionManager.add_handler(_Ignore())
    except Exception:
        traceback.print_exc()

    try:
        import gc

        from kivy.core.window import Window
        from kivymd.uix.behaviors.hover_behavior import HoverBehavior

        for obj in gc.get_objects():
            try:
                if isinstance(obj, HoverBehavior):
                    Window.unbind(mouse_pos=obj.on_mouse_update)
            except Exception:
                pass
    except Exception:
        pass

    try:
        from kivy.core.window import Window

        for child in list(Window.children):
            Window.remove_widget(child)
    except Exception:
        pass


def _show(tb):
    print(tb, file=sys.stderr)  # finisce anche in logcat
    saved = _save(tb)
    _prepare_crash_screen()

    try:
        from kivy.app import App
        from kivy.core.clipboard import Clipboard
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView

        def wrapped_label(text, font_size, color, bold=False):
            label = Label(
                text=text,
                size_hint_y=None,
                halign="left",
                valign="top",
                font_size=font_size,
                color=color,
                bold=bold,
            )
            label.bind(width=lambda w, v: setattr(w, "text_size", (v - 20, None)))
            label.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
            return label

        class CrashApp(App):
            def build(self):
                root = BoxLayout(orientation="vertical", padding=6, spacing=6)

                # errore finale in evidenza, in alto (scrollabile se lungo)
                head = ScrollView(size_hint_y=0.28)
                head.add_widget(
                    wrapped_label(
                        _last_line(tb), "15sp", (1, 0.3, 0.3, 1), bold=True
                    )
                )
                root.add_widget(head)

                button = Button(
                    text="COPIA TRACEBACK",
                    size_hint_y=None,
                    height="56dp",
                )

                def copy(_btn):
                    try:
                        Clipboard.copy(tb)
                        button.text = "COPIATO"
                    except Exception:
                        button.text = "COPIA NON RIUSCITA"

                button.bind(on_release=copy)
                root.add_widget(button)

                where = "crash.log salvato in:\n" + (
                    "\n".join(saved) if saved else "(nessun percorso scrivibile)"
                )
                body = ScrollView()
                body.add_widget(
                    wrapped_label(
                        where + "\n\n" + tb, "11sp", (1, 0.55, 0, 1)
                    )
                )
                root.add_widget(body)
                return root

        CrashApp().run()

    except Exception:
        traceback.print_exc()


def _patch_dotenv():
    """Su Android i .py sono solo .pyc: find_dotenv() cercherebbe nello stack
    un file che non esiste e va in errore. Gli diciamo noi dov'è il file."""

    try:
        import dotenv
        import dotenv.main

        base = os.path.dirname(os.path.abspath(__file__))

        def find_dotenv(*args, **kwargs):
            for name in ("keys.env", ".env"):
                path = os.path.join(base, name)
                if os.path.exists(path):
                    return path
            return ""

        dotenv.main.find_dotenv = find_dotenv
        dotenv.find_dotenv = find_dotenv

    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------- OTA
def _ota_root():
    # su Android: cartella privata dell'app; su PC solo se imposti MAGI_OTA_DIR
    base = os.environ.get("ANDROID_PRIVATE") or os.environ.get("MAGI_OTA_DIR")
    return os.path.join(base, "ota") if base else None


def _read_int(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _complete(folder):
    return all(os.path.exists(os.path.join(folder, p)) for p in OTA_REQUIRED)


def _ota_activate():
    """Mette il codice scaricato davanti a quello dell'APK."""
    root = _ota_root()
    if not root:
        return

    cur = os.path.join(root, "current")
    if not os.path.isdir(cur):
        return

    bundled = _read_int(os.path.join(_HERE, "version.txt"))
    version = _read_int(os.path.join(cur, "version.txt"))

    if version <= bundled or not _complete(cur):
        # APK più recente oppure aggiornamento incompleto
        shutil.rmtree(cur, ignore_errors=True)
        return

    sys.path.insert(0, cur)
    _ota.update(active=True, version=version)
    print("OTA attivo: versione", version, file=sys.stderr)


def _ota_discard():
    """Aggiornamento che crasha: lo scarta e non lo riscarica."""
    root = _ota_root()
    if not root:
        return
    try:
        with open(os.path.join(root, "bad.txt"), "w", encoding="utf-8") as f:
            f.write(str(_ota["version"]))
    except Exception:
        pass
    shutil.rmtree(os.path.join(root, "current"), ignore_errors=True)


def _ota_check():
    """Thread in background: scarica un eventuale aggiornamento."""
    root = _ota_root()
    new = os.path.join(root, "new")

    try:
        import requests

        os.makedirs(root, exist_ok=True)

        have = max(
            _read_int(os.path.join(_HERE, "version.txt")),
            _read_int(os.path.join(root, "current", "version.txt")),
        )
        bad = _read_int(os.path.join(root, "bad.txt"))

        r = requests.get(
            f"https://raw.githubusercontent.com/{OTA_REPO}/{OTA_BRANCH}/version.txt",
            timeout=15,
        )
        r.raise_for_status()
        remote = int(r.text.strip())

        if remote <= have or remote == bad:
            return

        r = requests.get(
            f"https://github.com/{OTA_REPO}/archive/refs/heads/{OTA_BRANCH}.zip",
            timeout=90,
        )
        r.raise_for_status()

        shutil.rmtree(new, ignore_errors=True)
        os.makedirs(new)
        new_abs = os.path.abspath(new)

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                parts = info.filename.split("/")[1:]  # toglie la cartella radice
                if not parts or not parts[-1]:
                    continue
                rel = os.path.join(*parts)
                if rel in OTA_SKIP:
                    continue
                dest = os.path.abspath(os.path.join(new, rel))
                if not dest.startswith(new_abs + os.sep):
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)

        if not _complete(new):
            raise RuntimeError("zip incompleto")

        if _read_int(os.path.join(new, "version.txt")) <= have:
            raise RuntimeError("version.txt non aumentata")

        # niente errori di sintassi: li scopriresti solo al prossimo avvio
        for folder, _dirs, files in os.walk(new):
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as f:
                        compile(f.read(), path, "exec")

        cur = os.path.join(root, "current")
        shutil.rmtree(cur, ignore_errors=True)
        os.replace(new, cur)
        print("OTA scaricato, attivo alla prossima apertura", file=sys.stderr)

    except Exception as e:
        shutil.rmtree(new, ignore_errors=True)
        print("OTA check fallito:", e, file=sys.stderr)


def _ota_start():
    if _ota_root():
        threading.Thread(target=_ota_check, daemon=True).start()


# ---------------------------------------------------------------- avvio
_patch_dotenv()
_ota_activate()
_ota_start()

try:
    runpy.run_module("app_main", run_name="__main__")
except SystemExit:
    raise
except BaseException:
    tb = traceback.format_exc()
    if _ota["active"]:
        _ota_discard()
        tb = (
            f"AGGIORNAMENTO OTA RIMOSSO (versione {_ota['version']}): "
            "riapri l'app.\n\n" + tb
        )
    _show(tb)
