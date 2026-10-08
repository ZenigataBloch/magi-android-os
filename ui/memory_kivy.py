import os

from kivy import kivy_data_dir
from kivy.app import App
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup, get_color_from_hex as hexc

from core.memory import load_history
from ui.nerv_widgets import JpTag, NervPanel, VoteBar

MONO = os.path.join(kivy_data_dir, "fonts", "RobotoMono-Regular.ttf")
if not os.path.exists(MONO):
    MONO = "Roboto"

ORANGE = "#ff6a00"
AMBER = "#ff8c00"
AZURE = "#3f8fb5"
GREEN = "#3fd17a"
RED = "#e04040"

# verdetto -> (sigla, colore)
VERDICTS = {
    "APPROVED": ("APR", GREEN),
    "DENIED": ("DNY", RED),
    "DEADLOCK": ("DLK", AMBER),
}

BAR_COLOR = [1, 0.416, 0, 0.8]
BAR_DIM = [1, 0.416, 0, 0.3]


def _wrapped(markup, size=12, color=(1, 1, 1, 1), font=None):
    """Label a tutta larghezza, che va a capo e cresce in altezza."""
    lbl = Label(
        text=markup,
        markup=True,
        font_size=sp(size),
        color=color,
        halign="left",
        valign="top",
        size_hint_y=None,
    )
    if font:
        lbl.font_name = font
    lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
    return lbl


def _scroll():
    return ScrollView(
        do_scroll_x=False,
        bar_width=dp(4),
        bar_color=BAR_COLOR,
        bar_inactive_color=BAR_DIM,
        scroll_type=["bars", "content"],
    )


def _number(entry):
    return str(entry.get("id", "")).split("-")[-1].lstrip("0") or "0"


class MemoryPopup(ModalView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.size_hint = (1, 1)
        self.auto_dismiss = False
        self.background = ""
        self.background_color = (0, 0, 0, 1)

        app = App.get_running_app()
        top = getattr(app, "inset_top", 0)
        bottom = getattr(app, "inset_bottom", 0)

        self.history = list(reversed(load_history()))

        self.frame = BoxLayout(
            orientation="vertical",
            padding=[dp(10), top + dp(6), dp(10), bottom + dp(8)],
            spacing=dp(6),
        )
        self.add_widget(self.frame)

        self._build_header()

        self.body = BoxLayout(orientation="vertical", spacing=dp(6))
        self.frame.add_widget(self.body)

        self.show_list()

    # ---------- intestazione ----------

    def _build_header(self):
        counts = {"APPROVED": 0, "DENIED": 0, "DEADLOCK": 0}
        for e in self.history:
            if e.get("verdict") in counts:
                counts[e["verdict"]] += 1

        head = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        head.add_widget(JpTag(text="記録", size_hint_x=None, width=dp(74)))

        info = Label(
            text=(
                f"[size=17sp]RECORDS:{len(self.history)}[/size]\n"
                f"[size=9sp]APPROVED:{counts['APPROVED']}\n"
                f"DENIED:{counts['DENIED']}\n"
                f"DEADLOCK:{counts['DEADLOCK']}[/size]"
            ),
            markup=True,
            color=hexc(ORANGE),
            halign="left",
            valign="middle",
        )
        info.bind(size=lambda w, s: setattr(w, "text_size", s))
        head.add_widget(info)

        self.frame.add_widget(head)

    # ---------- schermata 1: lista ----------

    def show_list(self, *_):
        self.body.clear_widgets()

        self.search = Factory.NervInput(
            hint_text="filtra per richiesta o decisione...",
            size_hint_y=None,
            height=dp(44),
        )
        self.search.bind(text=self._fill_list)
        self.body.add_widget(self.search)

        panel = NervPanel(padding=dp(2))
        scroll = _scroll()
        self.rows = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2)
        )
        self.rows.bind(minimum_height=self.rows.setter("height"))
        scroll.add_widget(self.rows)
        panel.add_widget(scroll)
        self.body.add_widget(panel)

        close = Factory.NervButton(
            text="CLOSE ARCHIVE", size_hint_y=None, height=dp(46)
        )
        close.bind(on_release=lambda *_: self.dismiss())
        self.body.add_widget(close)

        self._fill_list()

    def _fill_list(self, *_):
        query = self.search.text.strip().lower()
        self.rows.clear_widgets()

        shown = 0
        for e in self.history:
            prompt = str(e.get("prompt", ""))
            if (
                query
                and query not in prompt.lower()
                and query not in str(e.get("choice", "")).lower()
            ):
                continue

            tag, color = VERDICTS.get(e.get("verdict"), ("---", AMBER))

            row = Button(
                text=f"{_number(e):>3}  {tag}  {prompt}",
                font_name=MONO,
                font_size=sp(11),
                color=hexc(color),
                background_normal="",
                background_down="",
                background_color=(1, 0.416, 0, 0.07),
                size_hint_y=None,
                height=dp(44),
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            row.bind(
                size=lambda w, s: setattr(w, "text_size", (s[0] - dp(16), s[1]))
            )
            row.bind(on_release=lambda _b, entry=e: self.show_detail(entry))
            self.rows.add_widget(row)
            shown += 1

        if not shown:
            self.rows.add_widget(
                _wrapped(
                    "[color=#777777]NO STORED DECISIONS[/color]", 12, font=MONO
                )
            )

    # ---------- schermata 2: dettaglio ----------

    def show_detail(self, e):
        self.body.clear_widgets()

        verdict = str(e.get("verdict") or "UNKNOWN")
        color = VERDICTS.get(verdict, ("", AMBER))[1]

        panel = NervPanel(padding=dp(8))
        scroll = _scroll()
        box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4)
        )
        box.bind(minimum_height=box.setter("height"))

        def add(markup, size=12, font=MONO, color_=(1, 1, 1, 1)):
            box.add_widget(_wrapped(markup, size, color_, font))

        def section(title, markup, size=12):
            add(f"[color={AZURE}]{title}[/color]", 10)
            add(markup, size)

        add(
            f"[color={AZURE}]No.{_number(e).zfill(3)}  \u00b7  "
            f"{e.get('timestamp', '')}[/color]",
            10,
        )

        section("REQUEST", escape_markup(str(e.get("prompt", ""))))

        add(f"[color={AZURE}]VERDICT[/color]", 10)
        add(f"[b][color={color}]{verdict}[/color][/b]", 22, font=None)

        tally = e.get("tally") or "-"
        add(
            f"[color={AMBER}]TALLY {tally}  |  "
            f"CONSENSUS {e.get('consensus', 0)}%[/color]",
            12,
        )

        if e.get("rounds") == 2:
            r1 = e.get("round1") or {}
            add(
                f"[color={AMBER}]ROUND 1: {r1.get('verdict', '-')} "
                f"({r1.get('tally', '-')})  >  "
                f"ROUND 2: {verdict} ({tally})[/color]",
                11,
            )
            if e.get("flips"):
                add(
                    f"[color={AMBER}]CHANGED VOTE: "
                    f"{', '.join(e['flips'])}[/color]",
                    11,
                )

        if e.get("advocate"):
            add(f"[color={AZURE}]DEVIL'S ADVOCATE: {e['advocate']}[/color]", 11)

        if e.get("objection"):
            section("OBJECTION", escape_markup(str(e["objection"])), 11)

        votes = e.get("votes") or {}
        if votes:
            add(f"[color={AZURE}]VOTING MATRIX[/color]", 10)
            maximum = max(votes.values(), default=1)
            for choice, score in sorted(
                votes.items(), key=lambda x: x[1], reverse=True
            ):
                bar = VoteBar()
                bar.label = str(choice)
                bar.score = float(score)
                bar.maximum = float(maximum)
                bar.bar_color = (
                    [0.28, 0.71, 0.86, 1]
                    if score == maximum
                    else [1, 0.416, 0, 1]
                )
                bar.size_hint_y = None
                bar.height = dp(34)
                box.add_widget(bar)

        scroll.add_widget(box)
        panel.add_widget(scroll)
        self.body.add_widget(panel)

        back = Factory.NervButton(
            text="BACK TO LIST", size_hint_y=None, height=dp(46)
        )
        back.bind(on_release=self.show_list)
        self.body.add_widget(back)