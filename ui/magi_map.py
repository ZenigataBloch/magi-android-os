"""Mappa MAGI in stile Evangelion: tre core poligonali con stati colorati.

Uso: copia in ui/magi_map.py. Per l'anteprima, dalla radice del progetto:
    python -m ui.magi_map
"""

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.fonts import magi_font, serif_font

ORANGE = QColor("#ff8c00")
AZURE = QColor("#47b4dc")
AZURE_DIM = QColor("#2b6f8a")
GREEN = QColor("#3fd17a")
RED = QColor("#e04040")
GREY = QColor("#4a4a4a")
AMBER = QColor("#ffaa00")
BLACK = QColor("#000000")

# colore del verdetto mostrato nel canale centrale
VERDICT_COLORS = {"APPROVED": GREEN, "DENIED": RED, "DEADLOCK": AMBER}

# trattino spento durante il lampeggio dei collegamenti
LINK_DIM = QColor("#7a4400")

# area di riferimento, in coordinate dello screenshot originale (800x459)
REF = QRectF(20, 22, 760, 380)

SHAPES = {
    "BALTHASAR": [(279, 33), (523, 33), (523, 215), (465, 254), (340, 254), (279, 215)],
    "CASPER": [(33, 211), (232, 211), (340, 287), (340, 388), (33, 388)],
    "MELCHIOR": [(570, 211), (768, 211), (768, 388), (463, 388), (463, 287)],
}

LABELS = {
    "BALTHASAR": "BALTHASAR \u2022 2",
    "CASPER": "CASPER \u2022 3",
    "MELCHIOR": "MELCHIOR \u2022 1",
}

# centro del nome e larghezza massima del testo del voto
ANCHORS = {
    "BALTHASAR": (401, 130, 232),
    "CASPER": (186, 290, 290),
    "MELCHIOR": (616, 290, 290),
}

KANJI = {"ok": "\u627f\u8a8d", "no": "\u5426\u6c7a"}  # 承認 / 否決


def _tone_of(text):
    """Deduce il tono dal testo del voto, es. 'A · SI · 80%' o 'A → B · NO · 70%'."""
    if not text:
        return None

    if text.strip().upper().startswith("ERROR"):
        return "err"

    parts = [p.strip() for p in text.replace("\u2713", "").split("\u00b7")]
    label = parts[1].lower() if len(parts) > 1 else ""

    if label in ("si", "s\u00ec", "yes"):
        return "ok"
    if label == "no":
        return "no"
    return None


def kanji_font(px):
    f = QFont()
    f.setFamilies([
        "Noto Serif JP", "Yu Mincho", "MS Mincho",
        "Hiragino Mincho ProN", "Noto Serif CJK JP",
    ])
    f.setPixelSize(px)
    f.setBold(True)
    return f


class CoreHandle:
    """Stessa interfaccia di AgentPanel: set_status() e set_vote()."""

    def __init__(self, view, key):
        self._view = view
        self._key = key

    def set_status(self, text):
        self._view.set_status(self._key, text)

    def set_vote(self, text):
        self._view.set_vote(self._key, text)


class MagiMap(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cores = {
            key: {"status": "ONLINE", "vote": "", "tone": None}
            for key in SHAPES
        }
        self._flash = False
        self._caption = []

        self._timer = QTimer(self)
        self._timer.setInterval(450)
        self._timer.timeout.connect(self._tick)

        self.setMinimumSize(520, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ---------- API ----------

    def handle(self, key):
        return CoreHandle(self, key)

    def set_status(self, key, status):
        if key not in self.cores:
            return

        self.cores[key]["status"] = status

        if any(c["status"] == "ANALYZING" for c in self.cores.values()):
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._flash = False

        self.update()

    def set_caption(self, *lines):
        """Righe di testo sotto la barra centrale (es. round e avvocato)."""
        self._caption = [str(l) for l in lines if l]
        self.update()

    def set_vote(self, key, text):
        if key not in self.cores:
            return

        self.cores[key]["vote"] = text or ""
        self.cores[key]["tone"] = _tone_of(text)
        self.update()

    # ---------- interni ----------

    def _tick(self):
        self._flash = not self._flash
        self.update()

    def _fill(self, core):
        status, tone = core["status"], core["tone"]

        if status == "ANALYZING":
            return ORANGE if self._flash else AZURE_DIM
        if status == "ERROR" or tone == "err":
            return GREY
        if tone == "ok":
            return GREEN
        if tone == "no":
            return RED
        if status == "WAITING":
            return AZURE_DIM
        return AZURE

    @staticmethod
    def _text(p, cx, cy, w, h, text, font, color):
        # se il testo non sta nella larghezza, rimpicciolisce il font
        # (minimo 11 px); i puntini compaiono solo come ultima risorsa
        font = QFont(font)
        while (
            font.pixelSize() > 11
            and QFontMetrics(font).horizontalAdvance(text) > w
        ):
            font.setPixelSize(font.pixelSize() - 1)

        p.setFont(font)
        p.setPen(color)
        text = QFontMetrics(font).elidedText(text, Qt.ElideRight, int(w))
        p.drawText(QRectF(cx - w / 2, cy - h / 2, w, h), Qt.AlignCenter, text)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        p.fillRect(self.rect(), BLACK)

        # adatta l'area di riferimento al widget mantenendo le proporzioni
        s = min(self.width() / REF.width(), self.height() / REF.height())
        ox = (self.width() - REF.width() * s) / 2 - REF.x() * s
        oy = (self.height() - REF.height() * s) / 2 - REF.y() * s
        p.translate(ox, oy)
        p.scale(s, s)

        # poligoni dei core
        for key, pts in SHAPES.items():
            path = QPainterPath()
            path.moveTo(*pts[0])
            for pt in pts[1:]:
                path.lineTo(*pt)
            path.closeSubpath()

            p.setPen(QPen(ORANGE, 1.5))
            p.setBrush(self._fill(self.cores[key]))
            p.drawPath(path)

        # trattini di collegamento: pulsano mentre i core analizzano
        analyzing = any(
            c["status"] == "ANALYZING" for c in self.cores.values()
        )
        link = ORANGE if (not analyzing or self._flash) else LINK_DIM

        p.setPen(QPen(link, 5, Qt.SolidLine, Qt.FlatCap))
        # i due diagonali attraversano la fascia nera restando al suo interno
        p.drawLine(296, 252, 306, 237)
        p.drawLine(505, 253, 495, 238)
        p.drawLine(343, 321, 460, 321)

        # scritta centrale
        center_font = serif_font(36)
        center_font.setBold(True)
        center_font.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        self._text(p, 401, 276, 122, 44, "MAGI", center_font, ORANGE)

        # didascalia sotto la barra centrale
        for i, line in enumerate(self._caption[:2]):
            is_verdict = line in VERDICT_COLORS

            self._text(
                p, 401, 345 + i * 21, 126, 22, line,
                magi_font(19 if is_verdict else 15, bold=is_verdict),
                VERDICT_COLORS.get(line, ORANGE)
            )

        # nomi, kanji e voti
        for key, (cx, cy, max_w) in ANCHORS.items():
            core = self.cores[key]

            self._text(p, cx, cy, 300, 44, LABELS[key],
                       magi_font(32), BLACK)

            kanji = KANJI.get(core["tone"])
            if kanji:
                self._text(p, cx, cy - 58, 160, 40, kanji,
                           kanji_font(30), BLACK)

            if core["vote"]:
                self._text(p, cx, cy + 38, max_w, 28, core["vote"],
                           magi_font(18), BLACK)

        p.end()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    from ui.fonts import load_fonts

    app = QApplication(sys.argv)
    load_fonts()

    w = MagiMap()
    w.resize(900, 480)
    w.show()

    for k in SHAPES:
        w.set_status(k, "ANALYZING")

    def done(k, vote):
        w.set_status(k, "COMPLETE")
        w.set_vote(k, vote)

    QTimer.singleShot(2000, lambda: done("MELCHIOR", "A \u00b7 SI \u00b7 80%"))
    QTimer.singleShot(2800, lambda: done("BALTHASAR", "B \u2192 A \u00b7 SI \u00b7 70%"))
    QTimer.singleShot(3600, lambda: done("CASPER", "B \u00b7 NO \u00b7 90%"))

    sys.exit(app.exec())
