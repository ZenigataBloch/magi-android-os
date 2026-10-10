import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


# ---------------------------------------------------------------- palette
BG = QColor("#04060a")
ORANGE = QColor("#ff6a00")
AMBER = QColor("#ffb000")
GREEN = QColor("#3dff8a")


def _alpha(color, a):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(a))))
    return c


def _hexagon(cx, cy, r, rot=30):
    return QPolygonF(
        [
            QPointF(
                cx + r * math.cos(math.radians(rot + 60 * i)),
                cy + r * math.sin(math.radians(rot + 60 * i)),
            )
            for i in range(6)
        ]
    )


class MAGIBoot(QWidget):
    """Schermata di avvio in stile NERV.

    Stessa interfaccia di prima: MAGIBoot(agents), segnale `finished`,
    e la finestra si chiude da sola alla fine. Click o tasto = salta.
    """

    finished = Signal()

    W, H = 900, 560

    # (ms di inizio, messaggio, indice del nodo MAGI che inizia a caricarsi)
    STEPS = [
        (0, "MAGI SYSTEM INITIALIZING...", None),
        (650, "Loading MELCHIOR-01...", 0),
        (1400, "Loading BALTHASAR-02...", 1),
        (2150, "Loading CASPER-03...", 2),
        (2900, "Establishing neural link...", None),
        (3700, "MAGI ARRAY ONLINE", None),
    ]
    NODES = ["MELCHIOR-01", "BALTHASAR-02", "CASPER-03"]

    LOAD_MS = 700        # durata del "LOADING" di ogni nodo
    CHAR_MS = 22         # velocita' della scrittura del log
    PROGRESS_MS = 3900   # tempo per arrivare al 100%
    FADE_IN_MS = 350
    FADE_START = 5100
    FADE_MS = 450

    def __init__(self, agents):
        super().__init__()
        self.agents = agents

        self.setWindowTitle("MAGI-OS INITIALIZING")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setFixedSize(self.W, self.H)
        self.setWindowOpacity(0.0)

        self._clock = QElapsedTimer()
        self._offset = 0
        self._done = False

        self._build_static_layers()

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ helpers
    def _font(self, size, bold=False, spacing=0, serif=False):
        f = QFont()
        if serif:
            f.setFamilies(["Times New Roman", "DejaVu Serif", "serif"])
            f.setStyleHint(QFont.Serif)
        else:
            f.setFamilies(
                ["JetBrains Mono", "Consolas", "DejaVu Sans Mono", "Courier New", "monospace"]
            )
            f.setStyleHint(QFont.Monospace)
        f.setPixelSize(size)
        f.setBold(bold)
        if spacing:
            f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
        return f

    def _t(self):
        return (self._clock.elapsed() + self._offset) if self._clock.isValid() else 0

    def _progress(self, t):
        x = min(1.0, t / self.PROGRESS_MS)
        return x * x * (3 - 2 * x)

    def _build_static_layers(self):
        """Sfondo (griglia esagonale + vignettatura) e scanline: disegnati una volta sola."""
        dpr = self.devicePixelRatioF()
        size = (int(self.W * dpr), int(self.H * dpr))

        # sfondo
        self._bg = QPixmap(*size)
        self._bg.setDevicePixelRatio(dpr)
        self._bg.fill(BG)
        p = QPainter(self._bg)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(_alpha(ORANGE, 26), 1))
        r = 20
        dx, dy = 1.5 * r, math.sqrt(3) * r
        for c in range(int(self.W / dx) + 2):
            for row in range(int(self.H / dy) + 2):
                p.drawPolygon(_hexagon(c * dx, row * dy + (c % 2) * dy / 2, r, 0))
        vignette = QRadialGradient(self.W / 2, self.H / 2, self.W * 0.65)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 210))
        p.fillRect(0, 0, self.W, self.H, QBrush(vignette))
        p.end()

        # scanline
        self._scan = QPixmap(*size)
        self._scan.setDevicePixelRatio(dpr)
        self._scan.fill(Qt.transparent)
        p = QPainter(self._scan)
        p.setPen(QPen(QColor(0, 0, 0, 38), 1))
        for y in range(0, self.H, 3):
            p.drawLine(0, y, self.W, y)
        p.end()

    # ------------------------------------------------------------- events
    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())
        if not self._clock.isValid():
            self._clock.start()
            self.timer.start()

    def mousePressEvent(self, event):
        self._skip()

    def keyPressEvent(self, event):
        self._skip()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def _skip(self):
        t = self._t()
        if t < self.FADE_START:
            self._offset += self.FADE_START - t

    def _end(self):
        if self._done:
            return
        self._done = True
        self.timer.stop()
        self.finished.emit()
        self.close()

    def _tick(self):
        t = self._t()
        if t < self.FADE_IN_MS:
            opacity = t / self.FADE_IN_MS
        elif t < self.FADE_START:
            opacity = 1.0
        else:
            opacity = 1.0 - (t - self.FADE_START) / self.FADE_MS
        self.setWindowOpacity(max(0.0, min(1.0, opacity)))

        if t >= self.FADE_START + self.FADE_MS:
            self._end()
            return
        self.update()

    # ----------------------------------------------------------- painting
    def paintEvent(self, _event):
        t = self._t()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        p.drawPixmap(0, 0, self._bg)
        self._draw_sweep(p, t)
        self._draw_frame(p)
        self._draw_header(p, t)
        self._draw_title(p)
        self._draw_nodes(p, t)
        self._draw_log(p, t)
        self._draw_progress(p, t)
        p.drawPixmap(0, 0, self._scan)
        p.end()

    def _draw_sweep(self, p, t):
        y = (t * 0.22) % (self.H + 140) - 70
        grad = QLinearGradient(0, y - 60, 0, y + 60)
        grad.setColorAt(0.0, _alpha(ORANGE, 0))
        grad.setColorAt(0.5, _alpha(ORANGE, 34))
        grad.setColorAt(1.0, _alpha(ORANGE, 0))
        p.fillRect(QRectF(0, y - 60, self.W, 120), QBrush(grad))

    def _draw_frame(self, p):
        m, c = 18, 24  # margine, taglio dell'angolo
        w, h = self.W, self.H
        outer = QPolygonF(
            [
                QPointF(m + c, m), QPointF(w - m, m), QPointF(w - m, h - m - c),
                QPointF(w - m - c, h - m), QPointF(m, h - m), QPointF(m, m + c),
            ]
        )
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(ORANGE, 2))
        p.drawPolygon(outer)
        p.setPen(QPen(_alpha(ORANGE, 70), 1))
        p.drawRect(QRectF(m + 8, m + 8, w - 2 * m - 16, h - 2 * m - 16))

    def _draw_header(self, p, t):
        p.setFont(self._font(11, spacing=1))
        p.setPen(_alpha(ORANGE, 210))
        for i, line in enumerate(["FILE : MAGI_SYS", "CODE : 473", "PRIORITY : AAA"]):
            p.drawText(QPointF(48, 58 + i * 15), line)

        ready = t >= self.STEPS[-1][0] + 400
        blink = int(t / 350) % 2 == 0
        color = GREEN if ready else AMBER
        label = "SYSTEM READY" if ready else "BOOT SEQUENCE"
        p.setPen(color)
        p.drawText(
            QRectF(self.W - 260, 46, 212, 18), Qt.AlignRight | Qt.AlignVCenter, label
        )
        if ready or blink:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(self.W - 40, 55), 4, 4)

    def _draw_title(self, p):
        title = "MAGI-OS"
        rect = QRectF(0, 96, self.W, 84)
        p.setFont(self._font(68, bold=True, spacing=12, serif=True))
        for off, a in ((4, 25), (2, 45)):  # alone
            p.setPen(_alpha(ORANGE, a))
            p.drawText(rect.translated(0, off), Qt.AlignCenter, title)
            p.drawText(rect.translated(off, 0), Qt.AlignCenter, title)
        p.setPen(ORANGE)
        p.drawText(rect, Qt.AlignCenter, title)

        p.setFont(self._font(14, spacing=6))
        p.setPen(_alpha(AMBER, 210))
        p.drawText(QRectF(0, 182, self.W, 24), Qt.AlignCenter, "NERV DECISION SUPPORT SYSTEM")
        p.setPen(QPen(_alpha(ORANGE, 120), 1))
        p.drawLine(QPointF(self.W / 2 - 190, 218), QPointF(self.W / 2 + 190, 218))

    def _node_state(self, i, t):
        start = next(s for s in self.STEPS if s[2] == i)[0]
        if t < start:
            return "standby"
        if t < start + self.LOAD_MS:
            return "loading"
        return "online"

    def _draw_nodes(self, p, t):
        r, cy = 46, 318
        xs = [self.W * 0.25, self.W * 0.5, self.W * 0.75]
        states = [self._node_state(i, t) for i in range(3)]

        # collegamenti tra i nodi (si accendono con il "neural link")
        linked = t >= self.STEPS[4][0]
        for a, b in ((0, 1), (1, 2)):
            pen = QPen(_alpha(GREEN, 190) if linked else _alpha(ORANGE, 60), 2)
            if linked:
                pen.setStyle(Qt.DashLine)
                pen.setDashOffset(-t / 45.0)
            p.setPen(pen)
            p.drawLine(QPointF(xs[a] + r + 8, cy), QPointF(xs[b] - r - 8, cy))

        for i, (x, state) in enumerate(zip(xs, states)):
            if state == "online":
                color, fill = GREEN, _alpha(GREEN, 38)
                status = "ONLINE"
            elif state == "loading":
                pulse = 0.5 + 0.5 * math.sin(t / 70.0)
                color, fill = _alpha(AMBER, 130 + 125 * pulse), _alpha(AMBER, 14 + 22 * pulse)
                status = "LOADING"
            else:
                color, fill = _alpha(ORANGE, 80), Qt.NoBrush
                status = "STANDBY"

            p.setPen(QPen(color, 2))
            p.setBrush(fill)
            p.drawPolygon(_hexagon(x, cy, r))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(_alpha(color, color.alpha() * 0.5), 1))
            p.drawPolygon(_hexagon(x, cy, r * 0.72))

            p.setFont(self._font(26, bold=True))
            p.setPen(color)
            p.drawText(QRectF(x - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter, f"0{i + 1}")

            p.setFont(self._font(13, bold=True, spacing=3))
            p.setPen(_alpha(ORANGE, 230))
            p.drawText(
                QRectF(x - 100, cy + r + 10, 200, 20), Qt.AlignCenter, self.NODES[i].split("-")[0]
            )
            p.setFont(self._font(11, spacing=2))
            p.setPen(color)
            p.drawText(QRectF(x - 100, cy + r + 30, 200, 18), Qt.AlignCenter, status)

    def _draw_log(self, p, t):
        started = [s for s in self.STEPS if s[0] <= t]
        shown = started[-3:]
        p.setFont(self._font(13))
        y0 = 436
        for k, (ts, msg, _node) in enumerate(shown):
            last = k == len(shown) - 1
            text = msg
            if last:
                text = msg[: max(0, int((t - ts) / self.CHAR_MS))]
                typing = len(text) < len(msg)
                if typing or int(t / 450) % 2 == 0:
                    text += "\u2588"
            age = len(shown) - 1 - k
            base = GREEN if msg == self.STEPS[-1][1] else AMBER
            p.setPen(_alpha(base, 255 - 65 * age))
            p.drawText(QPointF(92, y0 + k * 18), f"> {text}")

    def _draw_progress(self, p, t):
        prog = self._progress(t)
        x, y, w, h = 92, 506, self.W - 184 - 64, 16
        color = GREEN if prog >= 1.0 else ORANGE

        p.setFont(self._font(11, spacing=2))
        p.setPen(_alpha(ORANGE, 200))
        p.drawText(QPointF(x, y - 8), "SYNCHRONIZATION")

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_alpha(color, 160), 1))
        p.drawRect(QRectF(x - 4, y - 4, w + 8, h + 8))

        nseg, gap = 60, 2
        seg_w = (w - (nseg - 1) * gap) / nseg
        filled = int(prog * nseg)
        p.setPen(Qt.NoPen)
        for i in range(nseg):
            on = i < filled
            p.setBrush(color if on else _alpha(ORANGE, 28))
            p.drawRect(QRectF(x + i * (seg_w + gap), y, seg_w, h))

        p.setFont(self._font(14, bold=True))
        p.setPen(color)
        p.drawText(
            QRectF(x + w + 14, y - 4, 70, h + 8), Qt.AlignLeft | Qt.AlignVCenter, f"{int(prog * 100):3d}%"
        )
