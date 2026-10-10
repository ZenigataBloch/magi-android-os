import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "magi.ico"
APP_ID = "magi-os.nerv.decision-support"


def set_taskbar_identity():
    """Windows: dà al processo un'identità propria, così la taskbar usa
    la nostra icona invece di quella di python.exe.
    Va chiamata PRIMA di creare QApplication."""

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def app_icon():
    return QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()