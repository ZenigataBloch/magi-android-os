from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from core.debug import dbg

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

MAGI_FONT = "Helvetica"     # fallback se il caricamento fallisce
SERIF_FONT = "Times New Roman"


def load_fonts():
    """Da chiamare una volta, dopo la creazione di QApplication."""
    global MAGI_FONT, SERIF_FONT

    fid = QFontDatabase.addApplicationFont(
        str(FONTS_DIR / "HelveticaNeueCondensed.ttf")
    )
    if fid != -1:
        MAGI_FONT = QFontDatabase.applicationFontFamilies(fid)[0]

    tid = QFontDatabase.addApplicationFont(
        str(FONTS_DIR / "times.ttf")
    )
    if tid != -1:
        SERIF_FONT = QFontDatabase.applicationFontFamilies(tid)[0]

    dbg("FONT:", MAGI_FONT, "|", SERIF_FONT)

    app_font = QFont(MAGI_FONT)
    app_font.setPointSize(11)
    QApplication.setFont(app_font)


def magi_font(size=12, bold=True, spacing=0):
    """Font condensed in stile Evangelion, con spaziatura tra le lettere."""
    f = QFont(MAGI_FONT)
    f.setPixelSize(size)
    f.setBold(bold)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def serif_font(size=12):
    f = QFont(SERIF_FONT)
    f.setPixelSize(size)
    return f