import asyncio
import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.utils import platform

import os
from kivy import kivy_data_dir
from kivy.utils import escape_markup

from core.controller import run_magi
from core.debug import dbg
from core.magi import create_magi_agents
from ui.boot_kivy import MAGIBootKivy
from ui.magi_map_kivy import MagiMapKivy  # noqa: F401  (registra il widget per il KV)
from ui.nerv_widgets import (  # noqa: F401  (registrano i widget per il KV)
    BoxLabel,
    DiamondTitle,
    JpTag,
    NervPanel,
    SegBar,
    MemoryButton,
    VoteBar
)

from ui.memory_kivy import MemoryPopup

from core.memory import (
    get_next_code,
    save_decision,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FONTS = BASE_DIR / "fonts"

LabelBase.register(
    name="HelveticaNeueCondensed",
    fn_regular=str(FONTS / "HelveticaNeueCondensed.ttf"),
)

LabelBase.register(
    name="Times",
    fn_regular=str(FONTS / "times.ttf"),
)

# font giapponese ridotto ai soli caratteri usati (vedi pyftsubset)
_JP = FONTS / "NotoSerifJP-Bold-sub.otf"
if _JP.exists():
    LabelBase.register(name="NotoSerifJP", fn_regular=str(_JP))
else:
    # senza il file l'app non deve crashare: i kanji appariranno come quadratini
    dbg("FONT GIAPPONESE MANCANTE:", _JP)
    LabelBase.register(
        name="NotoSerifJP",
        fn_regular=str(FONTS / "HelveticaNeueCondensed.ttf"),
    )

dbg("FONT REGISTERED")


KV = """
#:import spaced ui.nerv_widgets.spaced
#:set ORANGE (1, 0.416, 0, 1)
#:set AMBER (1, 0.69, 0, 1)
#:set GREEN (0.24, 1, 0.54, 1)

<Label>:
    font_name: "HelveticaNeueCondensed"

<NervButton@Button>:
    background_normal: ""
    background_down: ""
    background_color: (1, 0.416, 0, 0.35) if self.state == "down" else (1, 0.416, 0, 0.10)
    color: ORANGE
    font_size: sp(16)
    canvas.after:
        Color:
            rgba: 1, 0.416, 0, 0.9
        Line:
            rectangle: self.x, self.y, self.width, self.height
            width: 1

<NervInput@TextInput>:
    background_normal: ""
    background_active: ""
    background_color: 0.02, 0.014, 0, 1
    foreground_color: 1, 0.75, 0.3, 1
    hint_text_color: 1, 0.416, 0, 0.45
    cursor_color: 1, 0.416, 0, 1
    selection_color: 1, 0.416, 0, 0.3
    font_name: "HelveticaNeueCondensed"
    input_type: "text"
    keyboard_suggestions: True
    font_size: sp(16)
    multiline: False
    write_tab: False
    padding: [dp(10), dp(14), dp(10), dp(14)]
    canvas.after:
        Color:
            rgba: 1, 0.416, 0, 0.55
        Line:
            rectangle: self.x, self.y, self.width, self.height
            width: 1

FloatLayout:
    canvas.before:
        Color:
            rgba: 0, 0, 0, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "vertical"
        padding: [dp(10), app.inset_top + dp(6), dp(10), app.inset_bottom + dp(8)]
        spacing: dp(6)

        # ---- intestazione ----
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            spacing: dp(6)

            JpTag:
                text: "質問"
                font_name: "NotoSerifJP"
                size_hint_x: None
                width: dp(74)

            BoxLayout:
                orientation: "vertical"
                padding: [dp(2), dp(2)]

                Label:
                    text: app.system_code
                    font_size: sp(17)
                    color: ORANGE
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    size_hint_y: 0.4

                Label:
                    text: "FILE:MAGI_SYS\\nEX_MODE:ON\\nPRIORITY:AAA"
                    font_size: sp(8)
                    color: 1, 0.416, 0, 0.85
                    halign: "left"
                    valign: "top"
                    text_size: self.size
                    size_hint_y: 0.6

            JpTag:
                text: "解決"
                font_name: "NotoSerifJP"
                size_hint_x: None
                width: dp(74)

            BoxLayout:
                orientation: "vertical"
                size_hint_x: None
                width: dp(52)
                spacing: dp(4)

                MemoryButton:
                    text: "情報"
                    font_name: "NotoSerifJP"
                    font_size: sp(14)
                    color: 0.35, 0.78, 0.95, 1
                    on_release: app.open_memory()

                NervButton:
                    text: "消去"
                    font_name: "NotoSerifJP"
                    font_size: sp(12)
                    on_release: app.clear_session()

        # ---- mappa ----
        MagiMapKivy:
            id: magi_map
            size_hint_y: None
            height: self.width * 0.5

        # ---- sincronizzazione e consenso ----
        BoxLayout:
            size_hint_y: None
            height: dp(58)
            spacing: dp(10)

            BoxLayout:
                orientation: "vertical"
                spacing: dp(3)
                DiamondTitle:
                    text: spaced("MAGI SYNCHRONIZATION")
                    font_size: sp(9)
                    size_hint_y: None
                    height: dp(16)
                SegBar:
                    size_hint_y: None
                    height: dp(18)
                    value: app.sync_value
                Label:
                    text: app.sync_text
                    font_size: sp(10)
                    color: 1, 0.416, 0, 0.85

            BoxLayout:
                orientation: "vertical"
                spacing: dp(3)
                DiamondTitle:
                    text: spaced("MAGI CONSENSUS MONITOR")
                    font_size: sp(9)
                    size_hint_y: None
                    height: dp(16)
                SegBar:
                    size_hint_y: None
                    height: dp(18)
                    value: app.consensus_value
                Label:
                    text: app.consensus_text
                    font_size: sp(10)
                    color: 0.9, 0.9, 0.9, 1

        # ---- decisione finale ----
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: dp(60)

            DiamondTitle:
                text: spaced("FINAL MAGI DECISION")
                size_hint_y: None
                height: dp(16)

            Label:
                text: app.final_text
                font_size: sp(22)
                color: app.final_color
                halign: "center"
                shorten: True
                shorten_from: "right"
                text_size: self.width, None

            Label:
                text: app.final_sub
                font_name: "Times"
                font_size: sp(11)
                color: app.final_color
                size_hint_y: None
                height: dp(14)

        # ---- matrice dei voti ----
        DiamondTitle:
            text: spaced("MAGI VOTING MATRIX")
            size_hint_y: None
            height: dp(16)

        NervPanel:
            size_hint_y: None
            height: dp(92)
            padding: dp(8)

            ScrollView:
                do_scroll_x: False
                bar_width: dp(3)

                BoxLayout:
                    id: vote_box
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(4)

        # ---- log terminale ----
        NervPanel:
            padding: dp(6)

            ScrollView:
                id: log_scroll
                do_scroll_x: False
                bar_width: dp(4)
                bar_color: 1, 0.416, 0, 0.8
                bar_inactive_color: 1, 0.416, 0, 0.3
                scroll_type: ["bars", "content"]

                Label:
                    text: app.nerv_log
                    markup: True
                    font_name: app.mono_font
                    font_size: sp(10)
                    color: 1, 0.55, 0, 1
                    size_hint_y: None
                    height: self.texture_size[1]
                    text_size: self.width, None
                    halign: "left"
                    valign: "top"

        # ---- input ----
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(6)

            NervInput:
                id: prompt
                hint_text: "Inserisci richiesta MAGI..."
                on_text_validate: app.analyze(self.text)

            NervButton:
                text: "ANALYZE"
                size_hint_x: None
                width: dp(98)
                on_release: app.analyze(prompt.text)
"""


def _vote_text(payload, revised=False):
    """Testo del voto per la mappa, come nella GUI desktop."""

    label = payload.get("label", "")
    conf = payload["confidence"]

    if revised and payload.get("changed"):
        return (
            f"{payload['previous']} > {payload['choice']} "
            f"\u00b7 {label} \u00b7 {conf:.0f}%"
        )

    return f"{payload['choice']} \u00b7 {label} \u00b7 {conf:.0f}%"

def _system_insets():
    """(alto, basso) in pixel delle barre di sistema di Android.

    Ritorna (0, 0) fuori da Android e None se Android non e' ancora pronto.
    """

    if platform != "android":
        return 0, 0

    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        insets = activity.getWindow().getDecorView().getRootWindowInsets()

        if insets is None:
            return None

        sdk = autoclass("android.os.Build$VERSION").SDK_INT

        if sdk >= 30:
            kind = autoclass("android.view.WindowInsets$Type")
            bars = insets.getInsets(kind.systemBars() | kind.displayCutout())
            return int(bars.top), int(bars.bottom)

        return (
            int(insets.getSystemWindowInsetTop()),
            int(insets.getSystemWindowInsetBottom()),
        )

    except Exception as e:
        dbg("INSETS ERROR:", e)
        return None

GREEN = [0.24, 1, 0.54, 1]
RED = [1, 0.2, 0.2, 1]
AMBER = [1, 0.69, 0, 1]

class MAGIMobile(App):

    result = StringProperty("")
    nerv_log = StringProperty("")

    mono_font = StringProperty("Roboto")
    
    def add_nerv_log(self, line):
        self.nerv_log = (self.nerv_log + "\n" + line) if self.nerv_log else line
        # scorre in fondo
        Clock.schedule_once(
            lambda dt: setattr(self.root.ids.log_scroll, "scroll_y", 0), 0.05
        )
    def _on_status(self, name, status):
        name = name.upper()
        self.root.ids.magi_map.set_status(name, status)
        if status in ("ANALYZING", "COMPLETE", "ERROR"):
            self.add_nerv_log(f"[{name}] {status}")


    system_code = StringProperty(
        "CODE : 000000"
    )

    nerv_log = StringProperty(
        ""
    )

    # barre di sistema (px) e indicatori
    inset_top = NumericProperty(0)
    inset_bottom = NumericProperty(0)

    sync_value = NumericProperty(0)
    sync_target = 0
    sync_event = None
    sync_text = StringProperty("SYNCHRONIZATION RATE: 0%")
    consensus_value = NumericProperty(0)
    consensus_text = StringProperty("WAITING FOR DECISION...")
    final_text = StringProperty("WAITING...")
    final_sub = StringProperty("READY")
    final_color = ListProperty(GREEN)
 
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_lines = []
        self.busy = False
        self._answered = set()
        self._boot = None
        self._inset_tries = 0

    def build(self):
        self.title = "MAGI-OS | NERV Decision Support System"
        Window.clearcolor = (0, 0, 0, 1)

        try:
            # la tastiera spinge su l'interfaccia invece di coprire il campo
            Window.softinput_mode = "below_target"
        except Exception:
            pass

        mono = os.path.join(kivy_data_dir, "fonts", "RobotoMono-Regular.ttf")
        if os.path.exists(mono):
            self.mono_font = mono

        return Builder.load_string(KV)

    def on_start(self):
        self.system_code = get_next_code()
        self._refresh_insets()

        # la schermata di avvio sta sopra l'interfaccia e si toglie da sola
        try:
            self._boot = MAGIBootKivy(
                inset_top=self.inset_top,
                inset_bottom=self.inset_bottom,
                size_hint=(1, 1),
                on_finish=self._boot_finished,
            )
            self.root.add_widget(self._boot)
        except Exception as e:
            dbg("BOOT ERROR:", e)
            self._boot = None

    def _boot_finished(self):
        if not self.root:
            return

        magi_map = self.root.ids.magi_map

        magi_map.set_status(
            "MELCHIOR",
            "ONLINE"
        )

        magi_map.set_status(
            "BALTHASAR",
            "ONLINE"
        )

        magi_map.set_status(
            "CASPER",
            "ONLINE"
        )

    def on_pause(self):
        # evita che Android chiuda l'app mentre i core stanno rispondendo
        return True
  
   
    # ---------- barre di sistema ----------

    def _refresh_insets(self, *_):
        self._inset_tries += 1
        found = _system_insets()

        if found is None:
            if self._inset_tries < 12:
                Clock.schedule_once(self._refresh_insets, 0.3)
            else:
                self._apply_insets(dp(28), dp(44))
            return

        self._apply_insets(*found)

    def _apply_insets(self, top, bottom):
        self.inset_top = top
        self.inset_bottom = bottom

        if self._boot is not None:
            self._boot.inset_top = top
            self._boot.inset_bottom = bottom

        dbg("INSETS:", top, bottom)

    def start_sync_animation(self):
        self.sync_value = 0

        if self.sync_event:
            self.sync_event.cancel()

        self.sync_event = Clock.schedule_interval(
            self._increase_sync,
            0.1
        )

    def _increase_sync(self, dt):
        if self.sync_value < 0.90:
            self.sync_value += 0.02
        else:
            self.sync_value = min(self.sync_value + 0.005, 0.95)
        self.sync_text = f"SYNCHRONIZATION RATE: {self.sync_value * 100:.0f}%"

    # ---------- eventi dal controller (thread) -> interfaccia ----------

    def handle_event(self, kind, payload):
        """Chiamato sul thread di Kivy."""

        magi_map = self.root.ids.magi_map

        if kind == "options":
            magi_map.set_caption("ROUND 1")
            self.add_nerv_log(
                "[SYSTEM]\n"
                "OPTIONS GENERATED\n"
            )

        elif kind == "agent_result":
            if payload.get("valid", True):
                magi_map.set_vote(payload["agent"], _vote_text(payload))
                self.add_nerv_log(
                    f"[{payload['agent']}] VOTE: {payload['choice']} · "
                    f"{escape_markup(str(payload.get('label')))} · "
                    f"{payload.get('confidence', 0):.0f}%"
                )
            else:
                magi_map.set_vote(payload["agent"], "ERROR")

            self._answered.add(payload.get("agent"))

        elif kind == "round":
            self.add_nerv_log(f"[SYSTEM] ROUND {payload['n']} · ADVOCATE: {payload['advocate']}")
            magi_map.set_caption(f"ROUND {payload['n']}", f"ADV: {payload['advocate']}")
            self.consensus_text = f"ROUND {payload['n']} IN PROGRESS..."

        elif kind == "objection":
            self.add_nerv_log(
                f"[{payload.get('agent')}] OBJECTION:\n"
                f"{escape_markup(str(payload.get('text')))}\n"
            )

        elif kind == "revision":
            if not payload.get("carried"):
                magi_map.set_vote(payload["agent"], _vote_text(payload, revised=True))
                self.add_nerv_log(
                    f"[{payload['agent']}] CONFIRMED: "
                    f"{escape_markup(_vote_text(payload, revised=True))}"
                )

    # ---------- risultato finale ----------

    def update_vote_matrix(self, votes):
        box = self.root.ids.vote_box
        box.clear_widgets()
        maximum = max(votes.values(), default=1)

        for choice, score in sorted(votes.items(), key=lambda x: x[1], reverse=True):
            bar = VoteBar()
            bar.label = str(choice)
            bar.score = float(score)
            bar.maximum = float(maximum)
            bar.bar_color = GREEN if score == maximum else [1, 0.416, 0, 1]
            bar.size_hint_y = None
            bar.height = dp(34)
            box.add_widget(bar)
 
    def show_result(self, result):
        if self.sync_event:
            self.sync_event.cancel()
            self.sync_event = None
        
        self.busy = False

        if not isinstance(result, dict):
            self.result = str(result)
            self.final_text = "DONE"
            return

        responses = result.get("responses", [])
        decision = result.get("decision", {})

        try:
            save_decision(
                result.get("prompt", ""),
                decision,
                result.get("responses", [])
            )

        except Exception as e:
            dbg(
                "[MEMORY SAVE ERROR]",
                e
            )

        votes = decision.get("votes", {})
        winner = decision.get("choice", "UNKNOWN")
        consensus = decision.get("consensus", 0)
        verdict = decision.get("verdict", "")

        self.root.ids.magi_map.set_caption(verdict)

        # indicatori
        try:
            self.consensus_value = max(0.0, min(1.0, float(consensus) / 100.0))
        except (TypeError, ValueError):
            self.consensus_value = 0
        self.final_text = str(winner).upper()

        self.sync_value = self.consensus_value
        self.sync_text = f"SYNCHRONIZATION RATE: {consensus}%"
        
        if verdict == "APPROVED":
            self.final_color = GREEN

        elif verdict == "DENIED":
            self.final_color = RED
        else:
            self.final_color = AMBER
        
        tally = decision.get("tally", "")
        self.root.ids.magi_map.set_caption(verdict, tally)
        self.consensus_text = f"CONSENSUS LEVEL: {consensus}%"
        self.final_sub = f"{verdict} · {tally}"

        for r in responses:
            self.add_nerv_log(
                f"\n[{r.get('agent','?').upper()}] "
                f"{escape_markup(str(r.get('label') or r.get('choice')))} · "
                f"{r.get('confidence', 0):.0f}%\n"
                f"{escape_markup(str(r.get('reasoning', '')))}"
            )

        sep = "=" * 28
        self.add_nerv_log(f"\n{sep}\n[SYSTEM] MAGI SYNCHRONIZATION COMPLETE")
        self.add_nerv_log(f"[SYSTEM] VERDICT: {verdict}  ({tally})")
        if decision.get("rounds") == 2:
            r1 = decision.get("round1", {})
            self.add_nerv_log(
                f"[SYSTEM] ROUND 1: {r1.get('verdict')} ({r1.get('tally')})"
                f"  >  ROUND 2: {verdict} ({tally})"
            )
        self.add_nerv_log(f"[SYSTEM] DECISION: {str(winner).upper()}")
        if decision.get("dissent"):
            self.add_nerv_log("[SYSTEM] DISSENT: " + ", ".join(decision["dissent"]))
        self.add_nerv_log(sep)

        self.update_vote_matrix(votes)

    def show_error(self, message):

        self.busy = False
        self.final_text = "ERROR"
        self.final_sub = str(message)[:80]
        self.final_color = RED
        self.consensus_text = "NO DECISION"
        self.add_nerv_log(f"[SYSTEM] ERROR: {escape_markup(str(message))}")

    # ---------- avvio richiesta ----------

    def clear_session(self):
        if self.busy:
            return

        self.result = ""
        self.nerv_log = ""

        self.sync_value = 0
        self.sync_text = "SYNCHRONIZATION RATE: 0%"

        self.consensus_value = 0
        self.consensus_text = "WAITING FOR DECISION..."

        self.final_text = "WAITING..."
        self.final_sub = "READY"
        self.final_color = GREEN

        self._answered.clear()

        if self.root and "magi_map" in self.root.ids:
            self.root.ids.magi_map.reset()
            
        self.root.ids.vote_box.clear_widgets()

        self.system_code = get_next_code()

    def open_memory(self):

        dbg("[MEMORY] ARCHIVE OPEN")

        popup = MemoryPopup()
        popup.open()

    def analyze(self, prompt):

            prompt = prompt.strip()

            if self.busy:
                return

            self.add_nerv_log("[SYSTEM] Inserisci una richiesta")

            self.busy = True
            
            self.nerv_log = ""; self.add_nerv_log("[SYSTEM] MAGI ANALYZING...")
            self.root.ids.vote_box.clear_widgets()

            # svuota il campo: la richiesta e' gia' stata copiata in `prompt`
            self.root.ids.prompt.text = ""           

            # azzera gli indicatori
            self._answered = set()
            self.sync_value = 0
            self.sync_text = "SYNCHRONIZATION RATE: 0%"
            self.consensus_value = 0
            self.consensus_text = "ANALYZING..."
            self.final_text = "ANALYZING..."
            self.final_sub = "PLEASE WAIT"
            self.final_color = GREEN
            self.start_sync_animation()

            magi_map = self.root.ids.magi_map
            magi_map.reset()

            def worker():
             
                agents = create_magi_agents()

                def status_update(name, status):
                    Clock.schedule_once(
                        lambda dt: magi_map.set_status(name.upper(), status)
                    )

                def on_event(kind, payload):
                    Clock.schedule_once(
                        lambda dt: self.handle_event(kind, payload)
                    )

                try:
                    result = asyncio.run(
                    run_magi(
                        prompt,
                        agents,
                        status_callback=status_update,
                        event_callback=on_event
                    )
                )
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.show_error(str(e)))
                    return

                Clock.schedule_once(lambda dt: self.show_result(result))

            threading.Thread(target=worker, daemon=True).start()
