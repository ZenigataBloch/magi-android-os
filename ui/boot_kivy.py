"""Schermata di avvio NERV per Android (Kivy).

Porting di boot.py (PySide6): griglia esagonale, tre nodi MAGI che si
caricano, log scritto a macchina, barra di sincronizzazione a segmenti,
scanline e dissolvenza finale. Un tocco la salta.

Uso (vedi mobile.py): si aggiunge sopra l'interfaccia e si rimuove da sola.
"""

import math
import os
import time

from kivy import kivy_data_dir
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (
    Color,
    Ellipse,
    InstructionGroup,
    Line,
    Mesh,
    Rectangle,
)
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget

BG = (0.016, 0.024, 0.039, 1.0)
ORANGE = (1.0, 0.416, 0.0)
AMBER = (1.0, 0.69, 0.0)
GREEN = (0.239, 1.0, 0.541)

SANS = "HelveticaNeueCondensed"
SERIF = "Times"


def _rgba(color, a):
    return (color[0], color[1], color[2], max(0.0, min(1.0, a)))


def _hex(cx, cy, r, rot=30):
    pts = []
    for i in range(6):
        a = math.radians(rot + 60 * i)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _flat(pts):
    out = []
    for x, y in pts:
        out += [x, y]
    return out


def _fill_hex(group, cx, cy, r):
    """Esagono pieno (ventaglio di triangoli)."""
    verts = [cx, cy, 0, 0]
    for x, y in _hex(cx, cy, r):
        verts += [x, y, 0, 0]
    verts += verts[4:8]  # richiude il ventaglio
    group.add(Mesh(vertices=verts, indices=list(range(8)), mode="triangle_fan"))


def _spaced(text):
    return "   ".join(" ".join(word) for word in text.split())


class MAGIBootKivy(Widget):
    """Schermata di avvio. Chiama on_finish() quando ha finito."""

    # (ms di inizio, messaggio, indice del nodo MAGI che inizia a caricarsi)
    STEPS = [
        (0, "MAGI SYSTEM INITIALIZING...", None),
        (650, "Loading MELCHIOR-01...", 0),
        (1400, "Loading BALTHASAR-02...", 1),
        (2150, "Loading CASPER-03...", 2),
        (2900, "Establishing neural link...", None),
        (3700, "MAGI ARRAY ONLINE", None),
    ]
    NODES = ["MELCHIOR", "BALTHASAR", "CASPER"]

    LOAD_MS = 700
    CHAR_MS = 22
    PROGRESS_MS = 3900
    FADE_IN_MS = 350
    FADE_START = 5100
    FADE_MS = 450

    def __init__(self, on_finish=None, inset_top=0, inset_bottom=0, **kwargs):
        super().__init__(**kwargs)
        self.on_finish = on_finish
        self.inset_top = inset_top
        self.inset_bottom = inset_bottom

        self._done = False
        self._offset = 0.0
        self._start = time.monotonic()
        self._cache = {}
        self._mono = self._find_mono_font()

        self._static = InstructionGroup()
        self._dyn = InstructionGroup()
        self._top = InstructionGroup()
        self.canvas.add(self._static)
        self.canvas.add(self._dyn)
        self.canvas.add(self._top)

        self._vignette = self._make_vignette()
        self._sweep_tex = self._make_sweep()
        self._scan_tex = self._make_scan()

        self.bind(pos=self._rebuild, size=self._rebuild)
        self._rebuild()

        self.opacity = 0.0
        self._ev = Clock.schedule_interval(self._tick, 1 / 30.0)

    # ------------------------------------------------------------ risorse
    @staticmethod
    def _find_mono_font():
        path = os.path.join(kivy_data_dir, "fonts", "RobotoMono-Regular.ttf")
        return path if os.path.exists(path) else "Roboto"

    @staticmethod
    def _make_vignette():
        try:
            n = 32
            c = (n - 1) / 2.0
            buf = bytearray()
            for yy in range(n):
                for xx in range(n):
                    d = math.hypot(xx - c, yy - c) / (c * 1.4142)
                    k = max(0.0, min(1.0, (d - 0.30) / 0.70))
                    buf += bytes((0, 0, 0, int(210 * k * k)))
            tex = Texture.create(size=(n, n), colorfmt="rgba")
            tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
            tex.mag_filter = "linear"
            tex.min_filter = "linear"
            return tex
        except Exception:
            return None

    @staticmethod
    def _make_sweep():
        try:
            n = 32
            buf = bytearray()
            for i in range(n):
                a = math.sin(math.pi * i / (n - 1)) ** 2
                buf += bytes((255, 255, 255, int(255 * a)))
            tex = Texture.create(size=(1, n), colorfmt="rgba")
            tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
            tex.mag_filter = "linear"
            tex.min_filter = "linear"
            return tex
        except Exception:
            return None

    @staticmethod
    def _make_scan():
        try:
            data = bytes((0, 0, 0, 40)) + bytes((0, 0, 0, 0)) * 3
            tex = Texture.create(size=(1, 4), colorfmt="rgba")
            tex.blit_buffer(data, colorfmt="rgba", bufferfmt="ubyte")
            tex.mag_filter = "nearest"
            tex.min_filter = "nearest"
            tex.wrap = "repeat"
            return tex
        except Exception:
            return None

    # --------------------------------------------------------------- testo
    def _tex(self, text, size, font):
        key = (text, round(size, 1), font)
        tex = self._cache.get(key)
        if tex is None:
            try:
                lbl = CoreLabel(text=text, font_size=size, font_name=font)
                lbl.refresh()
                tex = lbl.texture
            except Exception:
                tex = None
            self._cache[key] = tex
        return tex

    def _text(self, g, text, x, y, size, color, anchor="center", font=SANS):
        """Disegna testo con il centro verticale in y. Ritorna (x, y, w, h)."""
        if not text:
            return None
        tex = self._tex(text, size, font)
        if tex is None:
            return None
        w, h = tex.size
        if anchor == "center":
            px = x - w / 2.0
        elif anchor == "right":
            px = x - w
        else:
            px = x
        py = y - h / 2.0
        g.add(Color(*color))
        g.add(Rectangle(texture=tex, pos=(px, py), size=(w, h)))
        return (px, py, w, h)

    # ------------------------------------------------------------- statico
    def _rebuild(self, *_):
        x0, y0 = self.pos
        W, H = self.size

        g = self._static
        g.clear()
        g.add(Color(*BG))
        g.add(Rectangle(pos=self.pos, size=self.size))

        # griglia esagonale
        r = dp(16)
        dx, dy = 1.5 * r, math.sqrt(3) * r
        g.add(Color(*_rgba(ORANGE, 0.10)))
        for c in range(int(W / dx) + 2):
            for row in range(int(H / dy) + 2):
                cx = x0 + c * dx
                cy = y0 + row * dy + (c % 2) * dy / 2.0
                g.add(Line(points=_flat(_hex(cx, cy, r, 0)), close=True, width=1))

        if self._vignette is not None:
            g.add(Color(1, 1, 1, 1))
            g.add(Rectangle(texture=self._vignette, pos=self.pos, size=self.size))

        # scanline, sopra a tutto
        t = self._top
        t.clear()
        if self._scan_tex is not None and H > 0:
            n = H / dp(4)
            t.add(Color(1, 1, 1, 1))
            t.add(
                Rectangle(
                    texture=self._scan_tex,
                    pos=self.pos,
                    size=self.size,
                    tex_coords=(0, 0, 1, 0, 1, n, 0, n),
                )
            )

    # -------------------------------------------------------------- tempo
    def _t(self):
        return (time.monotonic() - self._start) * 1000.0 + self._offset

    def _progress(self, t):
        x = min(1.0, t / self.PROGRESS_MS)
        return x * x * (3 - 2 * x)

    def _node_state(self, i, t):
        start = next(s for s in self.STEPS if s[2] == i)[0]
        if t < start:
            return "standby"
        if t < start + self.LOAD_MS:
            return "loading"
        return "online"

    def _tick(self, _dt):
        t = self._t()
        if t < self.FADE_IN_MS:
            op = t / self.FADE_IN_MS
        elif t < self.FADE_START:
            op = 1.0
        else:
            op = 1.0 - (t - self.FADE_START) / self.FADE_MS
        self.opacity = max(0.0, min(1.0, op))

        if t >= self.FADE_START + self.FADE_MS:
            self._end()
            return
        self._paint(t)

    # ------------------------------------------------------------- eventi
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        t = self._t()
        if t < self.FADE_START:
            self._offset += self.FADE_START - t
        return True

    def _end(self):
        if self._done:
            return
        self._done = True
        if self._ev is not None:
            self._ev.cancel()
        if self.parent is not None:
            self.parent.remove_widget(self)
        if self.on_finish:
            try:
                self.on_finish()
            except Exception:
                pass

    # ------------------------------------------------------------ disegno
    def _dashed(self, g, x1, x2, y, phase):
        dash, gap = dp(6), dp(5)
        step = dash + gap
        x = x1 - step + (phase % step)
        while x < x2:
            a, b = max(x, x1), min(x + dash, x2)
            if b > a:
                g.add(Line(points=[a, y, b, y], width=dp(1.5)))
            x += step

    def _paint(self, t):
        g = self._dyn
        g.clear()

        x0, y0 = self.pos
        W, H = self.size
        top = y0 + H - self.inset_top
        bot = y0 + self.inset_bottom
        hh = max(1.0, top - bot)

        def Y(f):  # frazione dall'alto dell'area utile
            return top - hh * f

        cx = x0 + W / 2.0
        m, cut = dp(10), dp(18)
        left, right = x0 + m, x0 + W - m
        tp, bt = top - m, bot + m

        # barra di scansione
        if self._sweep_tex is not None:
            sy = y0 + ((t / 2600.0) % 1.15) * H - 0.1 * H
            band = H * 0.12
            g.add(Color(*_rgba(ORANGE, 0.14)))
            g.add(
                Rectangle(
                    texture=self._sweep_tex,
                    pos=(x0, sy - band),
                    size=(W, 2 * band),
                )
            )

        # cornice con due angoli tagliati
        pts = [
            left + cut, tp,
            right, tp,
            right, bt + cut,
            right - cut, bt,
            left, bt,
            left, tp - cut,
        ]
        g.add(Color(*_rgba(ORANGE, 1.0)))
        g.add(Line(points=pts, close=True, width=dp(1.2)))
        g.add(Color(*_rgba(ORANGE, 0.27)))
        g.add(
            Line(
                rectangle=(
                    left + dp(6),
                    bt + dp(6),
                    right - left - dp(12),
                    tp - bt - dp(12),
                ),
                width=1,
            )
        )

        # intestazione
        small = sp(10)
        for i, line in enumerate(("FILE : MAGI_SYS", "CODE : 473", "PRIORITY : AAA")):
            self._text(
                g, line, left + dp(16), tp - dp(22) - i * dp(14), small,
                _rgba(ORANGE, 0.82), anchor="left", font=self._mono,
            )

        ready = t >= self.STEPS[-1][0] + 400
        blink = int(t / 350) % 2 == 0
        col = GREEN if ready else AMBER
        label = "SYSTEM READY" if ready else "BOOT SEQUENCE"
        self._text(
            g, label, right - dp(30), tp - dp(22), small,
            _rgba(col, 1.0), anchor="right", font=self._mono,
        )
        if ready or blink:
            d = dp(7)
            g.add(Color(*_rgba(col, 1.0)))
            g.add(Ellipse(pos=(right - dp(20) - d / 2, tp - dp(22) - d / 2), size=(d, d)))

        # titolo con alone
        title = " ".join("MAGI-OS")
        ty, tsize = Y(0.16), sp(34)
        for off, a in ((dp(2), 0.10), (dp(1), 0.18)):
            self._text(g, title, cx, ty - off, tsize, _rgba(ORANGE, a), font=SERIF)
            self._text(g, title, cx + off, ty, tsize, _rgba(ORANGE, a), font=SERIF)
        self._text(g, title, cx, ty, tsize, _rgba(ORANGE, 1.0), font=SERIF)

        self._text(
            g, _spaced("NERV DECISION SUPPORT SYSTEM"), cx, Y(0.215), sp(10),
            _rgba(AMBER, 0.82),
        )
        g.add(Color(*_rgba(ORANGE, 0.47)))
        g.add(Line(points=[cx - W * 0.30, Y(0.245), cx + W * 0.30, Y(0.245)], width=1))

        # nodi MAGI
        rr, cy = W * 0.105, Y(0.38)
        xs = [x0 + W * 0.20, x0 + W * 0.50, x0 + W * 0.80]
        states = [self._node_state(i, t) for i in range(3)]

        linked = t >= self.STEPS[4][0]
        for a, b in ((0, 1), (1, 2)):
            x1, x2 = xs[a] + rr + dp(5), xs[b] - rr - dp(5)
            if linked:
                g.add(Color(*_rgba(GREEN, 0.75)))
                self._dashed(g, x1, x2, cy, t * 0.04 * dp(1))
            else:
                g.add(Color(*_rgba(ORANGE, 0.24)))
                g.add(Line(points=[x1, cy, x2, cy], width=dp(1.5)))

        for i, (x, state) in enumerate(zip(xs, states)):
            if state == "online":
                color, a_line, a_fill, status = GREEN, 1.0, 0.15, "ONLINE"
            elif state == "loading":
                pulse = 0.5 + 0.5 * math.sin(t / 70.0)
                color = AMBER
                a_line = (130 + 125 * pulse) / 255.0
                a_fill = (14 + 22 * pulse) / 255.0
                status = "LOADING"
            else:
                color, a_line, a_fill, status = ORANGE, 0.31, 0.0, "STANDBY"

            if a_fill > 0:
                g.add(Color(*_rgba(color, a_fill)))
                _fill_hex(g, x, cy, rr)
            g.add(Color(*_rgba(color, a_line)))
            g.add(Line(points=_flat(_hex(x, cy, rr)), close=True, width=dp(1.5)))
            g.add(Color(*_rgba(color, a_line * 0.5)))
            g.add(Line(points=_flat(_hex(x, cy, rr * 0.72)), close=True, width=1))

            self._text(g, "0%d" % (i + 1), x, cy, sp(18), _rgba(color, a_line))
            self._text(
                g, _spaced(self.NODES[i]), x, cy - rr - dp(20), sp(10),
                _rgba(ORANGE, 0.90),
            )
            self._text(g, status, x, cy - rr - dp(38), sp(9), _rgba(color, a_line))

        # log
        shown = [s for s in self.STEPS if s[0] <= t][-3:]
        for k, (ts, msg, _node) in enumerate(shown):
            last = k == len(shown) - 1
            text = msg
            cursor = False
            if last:
                text = msg[: max(0, int((t - ts) / self.CHAR_MS))]
                typing = len(text) < len(msg)
                cursor = typing or int(t / 450) % 2 == 0
            age = len(shown) - 1 - k
            base = GREEN if msg == self.STEPS[-1][1] else AMBER
            ly = Y(0.575) - k * dp(20)
            rect = self._text(
                g, "> " + text, left + dp(24), ly, sp(11),
                _rgba(base, (255 - 65 * age) / 255.0),
                anchor="left", font=self._mono,
            )
            if last and cursor and rect is not None:
                g.add(Color(*_rgba(base, 1.0)))
                g.add(
                    Rectangle(
                        pos=(rect[0] + rect[2] + dp(2), ly - dp(6)),
                        size=(dp(7), dp(12)),
                    )
                )

        # barra di sincronizzazione
        prog = self._progress(t)
        color = GREEN if prog >= 1.0 else ORANGE
        bx = left + dp(24)
        bw = (right - dp(24)) - bx - dp(60)
        by, bh = Y(0.80), dp(14)

        self._text(
            g, "SYNCHRONIZATION", bx, by + bh + dp(16), sp(10),
            _rgba(ORANGE, 0.78), anchor="left", font=self._mono,
        )
        g.add(Color(*_rgba(color, 0.63)))
        g.add(Line(rectangle=(bx - dp(4), by - dp(4), bw + dp(8), bh + dp(8)), width=1))

        nseg, gap = 40, dp(2)
        seg_w = (bw - (nseg - 1) * gap) / nseg
        filled = int(prog * nseg)
        for i in range(nseg):
            if i < filled:
                g.add(Color(*_rgba(color, 1.0)))
            else:
                g.add(Color(*_rgba(ORANGE, 0.11)))
            g.add(Rectangle(pos=(bx + i * (seg_w + gap), by), size=(seg_w, bh)))

        self._text(
            g, "%3d%%" % int(prog * 100), bx + bw + dp(12), by + bh / 2.0, sp(13),
            _rgba(color, 1.0), anchor="left", font=self._mono,
        )

        self._text(g, "TAP TO SKIP", cx, Y(0.93), sp(9), _rgba(ORANGE, 0.30), font=self._mono)
