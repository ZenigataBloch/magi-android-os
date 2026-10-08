"""Wrapper di diagnostica.

Avvia l'app originale (rinominata app_main.py). Se crasha, mostra a schermo:
  - l'ultima riga del traceback (l'errore vero) in evidenza
  - un pulsante COPIA per copiare tutto il traceback negli appunti
  - i percorsi dove e' stato salvato crash.log
Sistema anche load_dotenv() su Android (trova keys.env nella cartella dell'app).
"""

import os
import runpy
import sys
import traceback

OTA_REPO = "ZenigataBloch/magi-android-os"

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


_patch_dotenv()

try:
    runpy.run_module("app_main", run_name="__main__")
except SystemExit:
    raise
except BaseException:
    _show(traceback.format_exc())
