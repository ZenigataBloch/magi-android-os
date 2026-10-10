import sys
import asyncio

from core.controller import run_magi
from core.voting import decide
from ui.fonts import magi_font, serif_font

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QSizePolicy
)

from PySide6.QtCore import (
    QTimer,
    QThread,
    Signal,
    Qt
)

PANEL_STYLE = """

QWidget {
    border: 1px solid #c46f00;
    background-color: #080808;
    border-radius: 2px;
}

QLabel {
    color: white;
    border: none;
    background: transparent;
}

QProgressBar {
    border: 1px solid #7a4300;
    background: #111111;
    border-radius: 2px;
    height: 16px;
    text-align: center;
}

QProgressBar::chunk {
    background: #ff8c00;
    border-radius: 2px;
}
"""

VERDICT_COLORS = {
    "APPROVED": "#00ff88",
    "DENIED": "#ff3333",
    "DEADLOCK": "#ffaa00",
}

class DecisionPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        layout.setSpacing(2)
        layout.setContentsMargins(10, 8, 10, 8)

        self.setStyleSheet(PANEL_STYLE)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.setMinimumHeight(140)

        # --- TITOLO ---
        self.title = QLabel("◆ FINAL MAGI DECISION ◆")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color:#ff8c00;")
        self.title.setFont(magi_font(18, spacing=3))

        # --- SCELTA ---
        self.choice = QLabel("WAITING...")
        self.choice.setWordWrap(True)
        self.choice.setAlignment(Qt.AlignCenter)
        self.choice.setStyleSheet("color:#00ff88;")
        self.choice.setFont(magi_font(26, spacing=2))

        # --- SOTTOTITOLO ---
        self.subtitle = QLabel("READY")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet("color:#888;")
        self.subtitle.setFont(serif_font(14))

        layout.addWidget(self.title)
        layout.addSpacing(6)
        layout.addWidget(self.choice)
        layout.addSpacing(6)
        layout.addWidget(self.subtitle)
        layout.addStretch()

        self.title.setFixedHeight(28)
        self.choice.setFixedHeight(50)
        self.subtitle.setFixedHeight(26)

        self.setLayout(layout)

    def reset(self):
        self.choice.setText("ANALYZING...")
        self.choice.setStyleSheet("color:#888;")
        self.subtitle.setText("◆ AWAITING VOTES ◆")
        self.subtitle.setStyleSheet("color:#888;")

    def update_result(self, result):

        verdict = result.get("verdict", "APPROVED")
        color = VERDICT_COLORS.get(verdict, "#00ff88")

        self.choice.setText(result["choice"].upper())
        self.choice.setStyleSheet(f"color:{color};")

        tally = result.get("tally", "")
        extra = f" · {tally}" if tally and tally != "-" else ""

        self.subtitle.setText(f"◆ {verdict}{extra} ◆")
        self.subtitle.setStyleSheet(f"color:{color};")

class AgentPanel(QWidget):

    def apply_state_style(self, color):

        self.setStyleSheet(
            f"""
            QWidget {{
                border:2px solid {color};
                background:#101010;
                border-radius: 2px;
            }}
            QLabel {{
                color:white;
            }}
            """
        )

    def animate_status(self):

        self.flash = not self.flash

        border = "#ffaa00" if self.flash else "#553300"
        width = 3 if self.flash else 2

        self.setStyleSheet(
            f"""
            QWidget {{
                border:{width}px solid {border};
                background:#101010;
                border-radius: 2px;
            }}
            QLabel {{
                color:white;
            }}
            """
        )

    def __init__(self, name, provider):

        super().__init__()
        
        self.setStyleSheet(
            """
            QWidget {
                border: 2px solid #c46f00;
                background-color: #101010;
                border-radius: 2px;
                padding: 8px;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        self.name = QLabel(name)
        self.provider = QLabel(provider)

        self.blink_timer = QTimer()

        self.blink_timer.timeout.connect(
            self.blink_status
        )
        self.blink_state = False

        self.status = QLabel("WAITING")

        self.vote = QLabel("")
        self.vote.setFont(magi_font(15, spacing=2))
        self.vote.setStyleSheet("color:#00ff88;")

        self.name.setFont(magi_font(20, spacing=3))
        self.provider.setFont(serif_font(13))

        self.status.setStyleSheet(
            """
            color:gray;
            """
        )

        self.flash = False

        self.flash_timer = QTimer()

        self.flash_timer.timeout.connect(
            self.animate_status
        )

        layout.addWidget(self.name)
        layout.addWidget(self.provider)
        layout.addWidget(self.status)
        layout.addWidget(self.vote)

        for label in (
            self.name,
            self.provider,
            self.status,
            self.vote
        ):
            label.setAlignment(Qt.AlignCenter)

        self.setLayout(layout)
        self.setMinimumHeight(150)

    def set_vote(self, text):
        self.vote.setText(text)


    def blink_status(self):

        self.blink_state = not self.blink_state

        if self.blink_state:
            self.status.setStyleSheet(
                """
                color: orange;
                font-weight: bold;
                """
            )
        else:
            self.status.setStyleSheet(
                """
                color: #555;
                font-weight: bold;
                """
            )

    def set_status(self, text):

        self.status.setText(text)


        if text == "WAITING":
            self.flash_timer.stop()
            self.apply_state_style("#555555")

        elif text == "ONLINE":
            self.flash_timer.stop()
            self.apply_state_style("#00aa44")

        elif text == "ANALYZING":
            self.flash_timer.start(500)
            self.apply_state_style("#ffaa00")


        elif text == "COMPLETE":
            self.flash_timer.stop()
            self.apply_state_style("#00aaff")

        elif text == "ERROR":
            self.flash_timer.stop()
            self.apply_state_style("#ff0000")

class ConsensusPanel(QWidget):

    def __init__(self):

        super().__init__()

        layout = QVBoxLayout()

        self.setStyleSheet(PANEL_STYLE)

        VERDICT_COLORS = {
            "APPROVED": "#00ff88",
            "DENIED": "#ff3333",
            "DEADLOCK": "#ffaa00",
        }

        self.setMinimumHeight(120)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.title = QLabel(
            "◆ MAGI CONSENSUS MONITOR ◆"
        )


        self.bar = QProgressBar()

        self.bar.setRange(
            0,
            100
        )


        self.status = QLabel(
            "WAITING FOR DECISION..."
        )


        self.title.setStyleSheet("color:#ff8c00;")
        self.title.setFont(magi_font(18, spacing=3))


        layout.addWidget(
            self.title
        )

        layout.addWidget(
            self.bar
        )

        layout.addWidget(
            self.status
        )

        self.title.setAlignment(Qt.AlignCenter)
        self.status.setAlignment(Qt.AlignCenter)

        self.setLayout(
            layout
        )
        self.setLayout(layout)


    def update_consensus(
        self,
        value
    ):

        self.bar.setValue(
            int(value)
        )

        self.status.setText(
            f"CONSENSUS LEVEL: {value:.1f}%"
        )

class VotingPanel(QWidget):

    def __init__(self):
        super().__init__()

        self.setStyleSheet(PANEL_STYLE)

        self.setMinimumHeight(120)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )


        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)


        self.title = QLabel(
            "◆ MAGI VOTING MATRIX ◆"
        )

        self.title.setAlignment(
            Qt.AlignCenter
        )

        self.title.setStyleSheet("color:#ff8c00;")
        self.title.setFont(magi_font(18, spacing=3))


        self.layout.addWidget(
            self.title
        )


        self.setLayout(
            self.layout
        )


    def update_votes(self, votes):

        while self.layout.count() > 1:

            item = self.layout.takeAt(1)

            if item.widget():
                item.widget().deleteLater()


        if not votes:
            return


        max_vote = max(
            votes.values()
        )


        for choice, score in sorted(
            votes.items(),
            key=lambda x: x[1],
            reverse=True
        ):


            label = QLabel(
                f"◈ {choice.upper()}   {score:.1f}"
            )


            label.setStyleSheet(
                """
                color:#00ff88;
                font-weight:bold;
                """
            )


            bar = QProgressBar()

            bar.setRange(
                0,
                int(max_vote)
            )

            bar.setValue(
                int(score)
            )


            self.layout.addWidget(
                label
            )

            self.layout.addWidget(
                bar
            )

class SyncPanel(QWidget):
    
    def __init__(self):

        super().__init__()

        layout = QVBoxLayout()

        self.title = QLabel(
            "◆ MAGI SYNCHRONIZATION ◆"
        )

        self.title.setFont(magi_font(16, spacing=3))

        self.setStyleSheet(PANEL_STYLE)

        self.setMinimumHeight(120)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )


        self.bar = QProgressBar()

        self.bar.setRange(
            0,
            100
        )


        self.value = QLabel(
            "SYNCHRONIZATION RATE: 0%"
        )


        layout.addWidget(
            self.title
        )

        layout.addWidget(
            self.bar
        )

        layout.addWidget(
            self.value
        )

        self.title.setAlignment(Qt.AlignCenter)
        self.value.setAlignment(Qt.AlignCenter)


        self.setLayout(
            layout
        )


        self.setStyleSheet(
            """
            QWidget {
                border:1px solid #c46f00;
                background:#080808;
                padding:8px;
            }

            QLabel { border:none; background:transparent; padding:0; }

            QProgressBar {
                border:1px solid #7a4300;
                background:#111;
                height:12px;
            }

            QProgressBar::chunk {
                background:#ff8c00;
            }
            """
        )


    def update_sync(self, value):

        self.bar.setValue(
            int(value)
        )

        self.value.setText(
            f"SYNCHRONIZATION RATE: {value:.0f}%"
        )