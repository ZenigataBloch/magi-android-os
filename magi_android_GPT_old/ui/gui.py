import config

from core.debug import dbg
from core.memory import save_decision

from ui.fonts import load_fonts
from ui.frame import HeaderBar
from ui.magi_map import MagiMap
from ui.memory_window import MemoryWindow
from ui.panels import (
    ConsensusPanel,
    DecisionPanel,
    SyncPanel,
    VotingPanel
)
from ui.theme import MAGI_STYLE
from ui.worker import MAGIWorker

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget
)


def _priority(final):
    """Priorità mostrata nell'header, ricavata dalla confidenza del verdetto."""

    if final.get("verdict") == "DEADLOCK":
        return "---"

    conf = final.get("confidence", 0)

    if conf >= 80:
        return "AAA"
    if conf >= 60:
        return "AA"
    return "A"


class MAGIWindow(QWidget):

    def on_event(self, kind, payload):

        if kind == "options":

            note = " (PROPOSTE DAI MAGI)" if payload["generated"] else ""
            self.log(f"[SYSTEM] OPTIONS DETECTED{note}")

            for o in payload["options"]:
                self.log(f"      {o['id']}) {o['label']}")

            self.log("")
            self.log("[SYSTEM] ROUND 1 — INDEPENDENT ANALYSIS")
            self.magi_map.set_caption("ROUND 1")

        elif kind == "agent_result":

            agent = payload["agent"]
            panel = self.panels.get(agent)

            if payload.get("valid", True):
                text = (
                    f"{payload['choice']} · "
                    f"{payload.get('label', '')} · "
                    f"{payload['confidence']:.0f}%"
                )
                if panel:
                    panel.set_vote(text)

                self.log("")
                self.log(f"[{agent}] VOTE: {text}")
                self.log(payload["reasoning"])

            else:
                if panel:
                    panel.set_vote("ERROR")
                self.log(f"[{agent}] ERROR: {payload['reasoning']}")

        elif kind == "round":

            self.log("")
            self.log("────────────────────────────")
            self.log(
                f"[SYSTEM] ROUND {payload['n']} — "
                f"DEVIL'S ADVOCATE: {payload['advocate']}"
            )
            self.magi_map.set_caption(
                f"ROUND {payload['n']}",
                f"ADV: {payload['advocate']}"
            )

        elif kind == "objection":

            self.log("")
            self.log(f"[{payload['agent']}] OBJECTION:")
            self.log(payload["text"])

        elif kind == "revision":

            agent = payload["agent"]
            panel = self.panels.get(agent)

            if payload.get("carried"):
                self.log("")
                self.log(f"[{agent}] REVISION UNAVAILABLE - ROUND 1 VOTE KEPT")
                return

            label = payload.get("label", "")
            conf = payload["confidence"]

            if payload.get("changed"):
                text = f"{payload['previous']} → {payload['choice']} · {label} · {conf:.0f}%"
                tag = "CHANGED"
            else:
                text = f"{payload['choice']} · {label} · {conf:.0f}% ✓"
                tag = "CONFIRMED"

            if panel:
                panel.set_vote(text)

            self.log("")
            self.log(f"[{agent}] {tag}: {text}")
            self.log(payload["reasoning"])

    def log_verdict(self, final):

        self.log("")
        self.log("════════════════════════════")
        self.log("[SYSTEM] MAGI SYNCHRONIZATION COMPLETE")
        self.log(f"[SYSTEM] VERDICT: {final['verdict']}  ({final['tally']})")

        if final.get("rounds") == 2:
            r1 = final["round1"]
            self.log(
                f"[SYSTEM] ROUND 1: {r1['verdict']} ({r1['tally']})"
                f"  →  ROUND 2: {final['verdict']} ({final['tally']})"
            )
            if final.get("flips"):
                self.log("[SYSTEM] CHANGED VOTE: " + ", ".join(final["flips"]))

        if final["verdict"] != "DEADLOCK":
            self.log(f"[SYSTEM] DECISION: {final['choice']}")

        if final.get("dissent"):
            self.log("[SYSTEM] DISSENT: " + ", ".join(final["dissent"]))

        if final.get("errors"):
            self.log("[SYSTEM] CORES OFFLINE: " + ", ".join(final["errors"]))

        if final.get("note"):
            self.log("[SYSTEM] " + final["note"])

        self.log("════════════════════════════")

    def open_memory(self):

        self.memory_window = MemoryWindow()
        self.memory_window.show()

    def log(self, message):

        dbg("LOG:", message)
        self.output_box.append(message)

    def update_sync_text(self):

        if self.sync_index < len(self.sync_messages):

            self.log("[SYSTEM] " + self.sync_messages[self.sync_index])
            self.sync_index += 1

    def show_decision(self, final):

        self.progress.hide()
        self.timer.stop()

        for panel in self.panels.values():
            panel.set_status("COMPLETE")

        self.decision_panel.update_result(final)

    def _set_clear_enabled(self, enabled):
        """消去 è attivo solo quando c'è un risultato da cancellare."""

        self.clear_button.setEnabled(enabled)
        self.clear_button.setCursor(
            Qt.PointingHandCursor if enabled else Qt.ArrowCursor
        )
        self.clear_button.setToolTip(
            "Azzera l'interfaccia (voti, log, decisione)" if enabled else ""
        )

    def _snapshot_idle(self, *panels):
        """Fotografa testi e stili iniziali dei pannelli (stato 'in attesa')."""

        state = []

        for panel in panels:
            for w in panel.findChildren(QLabel):
                state.append((w, w.text(), w.styleSheet()))
            for b in panel.findChildren(QProgressBar):
                state.append((b, b.value(), None))

        return state

    def _restore_idle(self):

        for w, value, style in self._idle_state:
            if isinstance(w, QLabel):
                w.setText(value)
                w.setStyleSheet(style)
            else:
                w.setValue(value)

    def clear_ui(self):
        """Pulsante 消去: riporta l'interfaccia allo stato iniziale."""

        self.output_box.clear()

        for p in self.panels.values():
            p.set_vote("")

        self.magi_map.set_caption("")
        self.reset_results()
        self.decision_panel.reset()
        self.sync_panel.update_sync(0)

        # i pannelli tornano esattamente com'erano all'avvio
        self._restore_idle()

        # niente più da cancellare
        self._set_clear_enabled(False)

    def _place_clear_button(self):
        """Mette il pulsante 消去 sotto il pulsante della memoria (情報)."""

        if not hasattr(self, "clear_button"):
            return

        mb = self.memory_button
        pos = mb.mapTo(self, QPoint(0, 0))

        self.clear_button.setFixedSize(mb.width(), max(28, mb.height() * 3 // 4))
        self.clear_button.move(pos.x(), pos.y() + mb.height() + 6)
        self.clear_button.raise_()

    def resizeEvent(self, event):

        super().resizeEvent(event)
        self._place_clear_button()

    def showEvent(self, event):

        super().showEvent(event)
        QTimer.singleShot(0, self._place_clear_button)

    def reset_results(self):
        """Azzera i risultati della richiesta precedente (voti, consenso, priorità)."""

        self.header.set_info(priority="---")

        for panel, fallback in (
            (self.voting_panel, lambda: self.voting_panel.update_votes({})),
            (self.consensus_panel, lambda: self.consensus_panel.update_consensus(0)),
        ):
            try:
                if callable(getattr(panel, "reset", None)):
                    panel.reset()
                else:
                    fallback()
            except Exception as e:
                dbg("RESET non riuscito:", panel.__class__.__name__, e)

    def ask_magi(self):

        prompt = self.input_box.text()
        self.current_prompt = prompt

        if not prompt:
            return

        self.input_box.clear()

        self.analyze_button.setEnabled(False)
        self.input_box.setEnabled(False)
        self.memory_button.setEnabled(False)
        self._set_clear_enabled(False)

        self.progress.show()

        self.sync_index = 0
        self.timer.start(3000)

        self.sync_value = 0
        self.sync_panel.update_sync(0)
        self.sync_timer.start(100)

        # pulizia log solo all'inizio di una nuova richiesta
        self.output_box.clear()

        for p in self.panels.values():
            p.set_vote("")

        self.magi_map.set_caption("")
        self.header.next_code()
        self.decision_panel.reset()
        self.reset_results()

        self.log("[SYSTEM] MAGI REQUEST RECEIVED")
        self.log("[SYSTEM] Awaiting MAGI responses...")

        # 1. si crea il worker, 2. si collegano i segnali, 3. si avvia
        self.worker = MAGIWorker(prompt, self.agents)

        self.worker.finished.connect(self.process_result)
        self.worker.status_update.connect(self.update_agent_status)
        self.worker.magi_event.connect(self.on_event)

        self.worker.start()

    def process_result(self, results):

        self.analyze_button.setEnabled(True)
        self.input_box.setEnabled(True)
        self.memory_button.setEnabled(True)
        self._set_clear_enabled(True)

        self.timer.stop()
        self.sync_timer.stop()

        final = results["decision"]

        save_decision(self.current_prompt, final, results)

        self.sync_panel.update_sync(final["consensus"])

        self.progress.hide()

        self.log_verdict(final)

        self.header.set_info(priority=_priority(final))
        self.magi_map.set_caption(
            final["verdict"],
            final["tally"] if final["tally"] != "-" else ""
        )

        self.decision_panel.update_result(final)
        self.consensus_panel.update_consensus(final["consensus"])

        dbg("DECISION DEBUG:", final)

        self.voting_panel.update_votes(final["votes"])

    def update_agent_status(self, agent, status):

        dbg("STATUS RECEIVED:", agent, status)

        self.log(f"[{agent}] {status}")

        panel = self.panels.get(agent)

        if panel:
            panel.set_status(status)

    def animate_sync(self):

        if self.sync_value < 100:

            self.sync_value += 2
            self.sync_panel.update_sync(self.sync_value)

    def closeEvent(self, event):

        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def __init__(self, agents):
        super().__init__()
        load_fonts()

        self.current_prompt = None
        self.agents = agents

        self.settings = QSettings("MAGI-OS", "MAGI")

        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        self.setStyleSheet(MAGI_STYLE)
        self.setWindowTitle("MAGI-OS | NERV Decision Support System")
        self.setMinimumSize(1100, 700)

        self.sync_messages = [
            "Synchronizing MAGI cores...",
            "Establishing neural link...",
            "Awaiting MAGI consensus...",
            "Decision matrix processing...",
        ]
        self.sync_index = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_sync_text)

        self.sync_value = 0

        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.animate_sync)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        # =========================
        # HEADER
        # =========================

        self.header = HeaderBar()
        self.header.set_info(
            ex_mode="ON" if getattr(config, "DELIBERATION", True) else "OFF"
        )

        # il badge 情報 è il pulsante della memoria
        self.memory_button = self.header.memory_button
        self.memory_button.clicked.connect(self.open_memory)

        # pulsante 消去 (cancella): sovrapposto, sotto il pulsante della memoria
        self.clear_button = QPushButton("消去", self)
        self.clear_button.setFont(self.memory_button.font())
        self.clear_button.setToolTip("Azzera l'interfaccia (voti, log, decisione)")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setStyleSheet(
            "QPushButton { color:#ff8c00; background:#0a0500;"
            " border:1px solid #ff8c00; }"
            "QPushButton:hover { background:#2a1600; }"
            "QPushButton:disabled { color:transparent; background:transparent;"
            " border:1px solid transparent; }"
        )
        self.clear_button.clicked.connect(self.clear_ui)
        self._set_clear_enabled(False)

        layout.addWidget(self.header)

        # =========================
        # MAPPA DEI CORE
        # =========================

        self.magi_map = MagiMap()
        layout.addWidget(self.magi_map, 5)

        self.melchior_panel = self.magi_map.handle("MELCHIOR")
        self.balthasar_panel = self.magi_map.handle("BALTHASAR")
        self.casper_panel = self.magi_map.handle("CASPER")

        self.panels = {
            "MELCHIOR": self.melchior_panel,
            "BALTHASAR": self.balthasar_panel,
            "CASPER": self.casper_panel,
        }

        # =========================
        # STATO: SYNC / CONSENSUS / DECISIONE
        # =========================

        self.sync_panel = SyncPanel()
        self.consensus_panel = ConsensusPanel()
        self.decision_panel = DecisionPanel()

        for panel in (
            self.sync_panel,
            self.consensus_panel,
            self.decision_panel
        ):
            panel.setFixedHeight(140)

        self.sync_panel.setMinimumWidth(240)
        self.consensus_panel.setMinimumWidth(240)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        status_row.addWidget(self.sync_panel, 1)
        status_row.addWidget(self.consensus_panel, 1)
        status_row.addWidget(self.decision_panel, 2)

        layout.addLayout(status_row)

        # =========================
        # VOTI + LOG
        # =========================

        self.voting_panel = VotingPanel()
        self.voting_panel.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        self.voting_panel.setMinimumHeight(150)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        self.output_box.setMinimumHeight(150)

        lower_row = QHBoxLayout()
        lower_row.setSpacing(10)
        lower_row.addWidget(self.voting_panel, 1)
        lower_row.addWidget(self.output_box, 2)

        layout.addLayout(lower_row, 3)

        # =========================
        # INPUT
        # =========================

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Inserisci richiesta MAGI...")
        self.input_box.returnPressed.connect(self.ask_magi)

        self.analyze_button = QPushButton("ANALYZE")
        self.analyze_button.clicked.connect(self.ask_magi)

        question_label = QLabel("question:")
        question_label.setStyleSheet(
            "color:#ff8c00; font-family:Consolas; font-size:12px;"
        )

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.addWidget(question_label)
        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.analyze_button)

        layout.addLayout(input_row)

        # =========================
        # PROGRESS
        # =========================

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()

        layout.addWidget(self.progress)

        self.setLayout(layout)

        # stato iniziale dei pannelli, per il pulsante 消去
        self._idle_state = self._snapshot_idle(
            self.sync_panel,
            self.consensus_panel,
            self.decision_panel,
        )
