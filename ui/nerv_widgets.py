"""Widget in stile NERV per l'interfaccia Android (Kivy puro, senza KivyMD)."""

from kivy.graphics import Color, Line, Quad, Rectangle
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget


ORANGE = [1, 0.416, 0, 1]
GREEN_LINE = [0.18, 0.78, 0.45, 0.9]

SANS = "HelveticaNeueCondensed"
JP = "NotoSerifJP"


def spaced(text):
    """Simula la spaziatura tra le lettere: 'MAGI SYNC' -> 'M A G I   S Y N C'."""
    return "   ".join(" ".join(word) for word in text.split())


class SegBar(Widget):
    """Barra a segmenti (sincronizzazione / consenso)."""

    value = NumericProperty(0.0)  # 0..1
    segments = NumericProperty(30)
    color = ListProperty(ORANGE)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            value=self._redraw,
            segments=self._redraw,
            color=self._redraw,
        )
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        n = max(1, int(self.segments))
        gap, pad = dp(2), dp(3)
        w = self.width - 2 * pad
        h = self.height - 2 * pad
        if w <= 0 or h <= 0:
            return
        seg_w = (w - (n - 1) * gap) / n
        filled = int(max(0.0, min(1.0, self.value)) * n)
        r, g, b = self.color[0], self.color[1], self.color[2]
        with self.canvas:
            Color(r, g, b, 0.6)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
            for i in range(n):
                if i < filled:
                    Color(r, g, b, 1)
                else:
                    Color(1, 0.416, 0, 0.11)
                Rectangle(
                    pos=(self.x + pad + i * (seg_w + gap), self.y + pad),
                    size=(seg_w, h),
                )


class NervPanel(BoxLayout):
    """Pannello nero con bordo arancione."""

    border_color = ListProperty([1, 0.416, 0, 0.55])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.02, 0.015, 0, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            self._bc = Color(*self.border_color)
            self._ln = Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
        self.bind(pos=self._upd, size=self._upd, border_color=self._upd)

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bc.rgba = self.border_color
        self._ln.rectangle = (self.x, self.y, self.width, self.height)


class DiamondTitle(Label):
    """Titolo di sezione con due rombi ai lati."""

    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", SANS)
        kwargs.setdefault("font_size", sp(11))
        kwargs.setdefault("color", ORANGE)
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, texture_size=self._draw)
        self._draw()

    def _draw(self, *_):
        self.canvas.after.clear()
        s = dp(4.5)
        cy = self.center_y
        half = self.texture_size[0] / 2 + dp(14)
        with self.canvas.after:
            Color(*ORANGE)
            for cx in (self.center_x - half, self.center_x + half):
                Quad(points=[cx - s, cy, cx, cy + s, cx + s, cy, cx, cy - s])


class JpTag(Label):
    """Etichetta giapponese con la doppia linea verde sopra e sotto."""

    line_color = ListProperty(GREEN_LINE)

    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", JP)
        kwargs.setdefault("font_size", sp(26))
        kwargs.setdefault("color", ORANGE)
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, line_color=self._draw)
        self._draw()

    def _draw(self, *_):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(*self.line_color)
            for dy in (dp(1), dp(5)):
                Line(points=[self.x, self.top - dy, self.right, self.top - dy], width=1)
                Line(points=[self.x, self.y + dy, self.right, self.y + dy], width=1)


class BoxLabel(Label):
    """Etichetta con sfondo e bordo (il riquadro 情報)."""

    border_color = ListProperty([0.25, 0.72, 0.92, 1])
    bg_color = ListProperty([0.08, 0.25, 0.33, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._fill = Color(*self.bg_color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
            self._bc = Color(*self.border_color)
            self._ln = Line(rectangle=(self.x, self.y, self.width, self.height), width=dp(1.3))
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._ln.rectangle = (self.x, self.y, self.width, self.height)

from kivy.uix.behaviors import ButtonBehavior

class MemoryButton(ButtonBehavior, BoxLabel):
    pass

class VoteBar(BoxLayout):
    """
    Barra voto MAGI.
    Mostra:
    nome scelta
    barra proporzionale
    punteggio
    """

    label = StringProperty("")
    score = NumericProperty(0)
    maximum = NumericProperty(100)
    bar_color = ListProperty(ORANGE)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.orientation = "vertical"
        self.spacing = dp(2)

        self.title = Label(
            font_name=SANS,
            font_size=sp(12),
            color=[0.85, 0.85, 0.85, 1],
            size_hint_y=None,
            height=dp(18)
        )

        self.add_widget(self.title)

        self.bind(
            label=self._refresh,
            score=self._refresh,
            maximum=self._refresh,
            bar_color=self._refresh
        )

        self._refresh()

    def _refresh(self, *_):

        self.clear_widgets()

        title = Label(
            text=f"[b]\u25c6[/b] {self.label.upper()}   {self.score:.1f}",
            markup=True,
            font_name=SANS,
            font_size=sp(12),
            color=self.bar_color,
            halign="left",
            size_hint_y=None,
            height=dp(18),
        )
        title.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))

        self.add_widget(title)

        bar = VoteProgress(
            value=(
                self.score / self.maximum
                if self.maximum
                else 0
            ),
            color=self.bar_color
        )

        bar.size_hint_y = None
        bar.height = dp(10)

        self.add_widget(bar)


class VoteProgress(Widget):
    """
    Barra orizzontale percentuale.
    """

    value = NumericProperty(0)
    color = ListProperty(ORANGE)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind(
            pos=self._draw,
            size=self._draw,
            value=self._draw,
            color=self._draw
        )

        self._draw()

    def _draw(self, *_):

        self.canvas.clear()

        with self.canvas:

            Color(
                0.15,
                0.15,
                0.15,
                1
            )

            Rectangle(
                pos=self.pos,
                size=self.size
            )

            Color(*self.color)

            Rectangle(
                pos=self.pos,
                size=(
                    self.width * max(
                        0,
                        min(
                            1,
                            self.value
                        )
                    ),
                    self.height
                )
            )