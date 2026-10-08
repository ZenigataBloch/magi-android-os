"""Mappa MAGI in stile Evangelion per Kivy (porting di ui/magi_map.py).

Si disegna tutto sul canvas: tre poligoni, trattini, testo. Le coordinate sono
quelle dello screenshot originale (800x459); il widget le stira per riempire
lo spazio, così su un telefono in verticale la mappa resta alta e leggibile
(il testo non viene deformato: la sua dimensione dipende solo dalla larghezza).

Font opzionali, da mettere in fonts/ :
  - HelveticaNeueCondensed (registrato in mobile.py) per i nomi
  - Times (registrato in mobile.py) per la scritta MAGI
  - NotoSerifJP-Bold.ttf per 承認 / 否決 (se manca, i kanji non si disegnano)
"""

from pathlib import Path

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Mesh, Rectangle
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hexc
from kivy.animation import Animation

BASE_DIR = Path(__file__).resolve().parent.parent
KANJI_FONT = BASE_DIR / "fonts" / "NotoSerifJP-Bold.ttf"

NAME_FONT = "HelveticaNeueCondensed"
SERIF_FONT = "Times"

ORANGE = hexc("#ff8c00")
AZURE = hexc("#47b4dc")
AZURE_DIM = hexc("#2b6f8a")
GREEN = hexc("#3fd17a")
RED = hexc("#e04040")
GREY = hexc("#4a4a4a")
BLACK = (0, 0, 0, 1)

# area di riferimento (coordinate dello screenshot, y verso il basso)
REF_X, REF_Y, REF_W, REF_H = 20, 22, 760, 380

SHAPES = {
    "BALTHASAR": [(279, 33), (523, 33), (523, 215), (465, 254), (340, 254), (279, 215)],
    "CASPER": [(33, 211), (232, 211), (340, 287), (340, 388), (33, 388)],
    "MELCHIOR": [(570, 211), (768, 211), (768, 388), (463, 388), (463, 287)],
}

CONNECTORS = [
    ((297, 251), (306, 238)),
    ((496, 238), (505, 251)),
    ((344, 321), (459, 321)),
]

LABELS = {
    "BALTHASAR": "BALTHASAR \u2022 2",
    "CASPER": "CASPER \u2022 3",
    "MELCHIOR": "MELCHIOR \u2022 1",
}

KANJI_FONT = BASE_DIR / "fonts" / "NotoSerifJP-Bold-sub.otf"

# centro del nome (x, y) e larghezza massima del testo, in unità di riferimento
ANCHORS = {
    "BALTHASAR": (401, 130, 232),
    "CASPER": (186, 290, 290),
    "MELCHIOR": (616, 290, 290),
}

KANJI = {"ok": "\u627f\u8a8d", "no": "\u5426\u6c7a"}  # 承認 / 否決


def _clean(text):
    # ✓ e → non sono nel font di default di Kivy
    return str(text).replace("\u2713", "").replace("\u2192", ">").strip()


def _tone_of(text):
    """Tono dal testo del voto, es. 'A · SI · 80%' o 'A > B · NO · 70%'."""
    if not text:
        return None

    if text.strip().upper().startswith("ERROR"):
        return "err"

    parts = [p.strip() for p in _clean(text).split("\u00b7")]
    label = parts[1].lower() if len(parts) > 1 else ""

    if label in ("si", "s\u00ec", "yes"):
        return "ok"
    if label == "no":
        return "no"
    return None


def _split_vote(text):
    """'A · Michael Myers · 90%' -> ('Michael Myers', 'A · 90%')."""
    parts = [p.strip() for p in _clean(text).split("\u00b7")]
    if len(parts) == 3:
        return parts[1], f"{parts[0]} \u00b7 {parts[2]}"
    return _clean(text), ""


class MagiMapKivy(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.animations = {}

        self._ox = self._oy = 0.0

        self.cores = {
            key: {
                "status": "OFFLINE",
                "vote": "",
                "tone": None
            }
            for key in SHAPES
        }
        self._caption = []
        self._flash = False
        self._tick_ev = None
        self._cache = {}
        self._sx = self._sy = 1.0

        self.bind(pos=self._redraw, size=self._redraw)

    # ---------- API ----------

    def boot_core(self, key):
        """
        Attiva un core durante la sequenza di boot.
        """

        if key not in self.cores:
            return

        self.cores[key]["status"] = "ONLINE"
        self._redraw()

    def set_status(self, key, status):
        if key not in self.cores:
            return

        self.cores[key]["status"] = status

        analyzing = any(
            c["status"] == "ANALYZING" for c in self.cores.values()
        )

        if analyzing and self._tick_ev is None:
            self._tick_ev = Clock.schedule_interval(self._tick, 0.45)
        elif not analyzing and self._tick_ev is not None:
            self._tick_ev.cancel()
            self._tick_ev = None
            self._flash = False

        self._redraw()

    def set_vote(self, key, text):
        if key not in self.cores:
            return

        self.cores[key]["vote"] = text or ""
        self.cores[key]["tone"] = _tone_of(text)
        self._redraw()

    def set_caption(self, *lines):
        self._caption = [str(l) for l in lines if l]
        self._redraw()

    def reset(self):
        """
        Nuova richiesta:
        pulisce voti e prepara i core.
        """

        for c in self.cores.values():
            c.update(
                status="ONLINE",
                vote="",
                tone=None
            )

        self._caption = []
        self._redraw()

    def update_core(self, agent, status):
        agent = agent.upper().strip()

        # normalizza MELCHIOR-01 -> MELCHIOR
        agent = agent.split("-")[0]

        if agent not in self.cores:
            return

        self.set_status(agent, status)

    # ---------- interni ----------

    def _tick(self, _dt):
        self._flash = not self._flash
        self._redraw()

    def _fill(self, core):
        status, tone = core["status"], core["tone"]

        if status == "OFFLINE":
            return GREY
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

    def _pt(self, x, y):
        return (
            self._ox + (x - REF_X) * self._sx,
            self._oy + REF_H * self._sy - (y - REF_Y) * self._sy,
        )

    def _texture(self, text, font, px):
        key = (text, font, int(px))

        if key not in self._cache:
            if len(self._cache) > 300:
                self._cache.clear()

            label = CoreLabel(text=text, font_size=int(px), font_name=font)
            label.refresh()
            self._cache[key] = label.texture

        return self._cache[key]

    def _text(self, cx, cy, max_w, text, font, size, color, dy=0, min_px=9):
        """Testo centrato su (cx, cy) in coordinate di riferimento.

        size e max_w sono in unità di riferimento; se il testo non sta,
        il font si rimpicciolisce (fino a min_px) invece di essere troncato.
        """
        if not text:
            return

        px = max(min_px, size * self._sx)
        limit = max_w * self._sx

        tex = self._texture(text, font, px)
        while tex.width > limit and px > min_px:
            px -= 1
            tex = self._texture(text, font, px)

        x, y = self._pt(cx, cy)
        Color(*color)
        Rectangle(
            texture=tex,
            size=tex.size,
            pos=(x - tex.width / 2, y - tex.height / 2 + dy),
        )

    def _redraw(self, *_):
        if self.width <= 1 or self.height <= 1:
            return

        s = min(self.width / REF_W, self.height / REF_H)
        self._sx = self._sy = s
        self._ox = self.x + (self.width - REF_W * s) / 2
        self._oy = self.y + (self.height - REF_H * s) / 2

        self.canvas.clear()

        with self.canvas:
            Color(*BLACK)
            Rectangle(pos=self.pos, size=self.size)

            # poligoni (convessi: bastano i triangle_fan)
            for key, pts in SHAPES.items():
                coords = [self._pt(x, y) for x, y in pts]

                Color(*self._fill(self.cores[key]))
                verts = []
                for px, py in coords:
                    verts += [px, py, 0, 0]
                Mesh(
                    vertices=verts,
                    indices=list(range(len(coords))),
                    mode="triangle_fan",
                )

                Color(*ORANGE)
                Line(
                    points=[c for pt in coords for c in pt],
                    width=dp(1),
                    close=True,
                )

            # PUNTO 2: trattini di collegamento (sostituisce il vecchio blocco)
            Color(*ORANGE)
            width = max(dp(2), 4 * self._sx)
            for a, b in CONNECTORS:
                Line(points=[*self._pt(*a), *self._pt(*b)], width=width, cap="none")

            # PUNTO 3: scritta centrale (sostituisce la vecchia riga con "MAGI")
            for off in (-0.8, 0.8):
                self._text(401 + off, 275, 120, "MAGI", SERIF_FONT, 40, ORANGE)

            # didascalia (round, avvocato, verdetto)
            for i, line in enumerate(self._caption[:2]):
                self._text(
                    401, 346, 124, line, NAME_FONT, 22, ORANGE,
                    dy=-i * 22 * self._sx * 1.15, min_px=8,
                )

            # nomi, kanji e voti
            kanji_ok = KANJI_FONT.exists()

            for key, (cx, cy, max_w) in ANCHORS.items():
                core = self.cores[key]

                self._text(cx, cy, 250, LABELS[key], NAME_FONT, 40, BLACK)

                kanji = KANJI.get(core["tone"])
                if kanji and kanji_ok:
                    self._text(cx, cy - 58, 160, kanji, str(KANJI_FONT),
                               36, BLACK)

                if core["vote"]:
                    line1, line2 = _split_vote(core["vote"])
                    size = 28
                    self._text(cx, cy + 36, max_w, line1, NAME_FONT, size,
                               BLACK)
                    self._text(cx, cy + 36, max_w, line2, NAME_FONT, size,
                               BLACK, dy=-size * self._sx * 1.15)
