import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.memory import load_history
from ui.frame import TitleBlock

ORANGE = "#ff8c00"
AZURE = "#47b4dc"
DIM = "#2b6f8a"

VERDICT_COLORS = {
    "APPROVED": "#3fd17a",
    "DENIED": "#e04040",
    "DEADLOCK": "#ffaa00",
}

VERDICT_CODES = {"APPROVED": "APR", "DENIED": "DNY", "DEADLOCK": "DLK"}

STYLE = f"""
QWidget {{
    background:#000000;
    color:{ORANGE};
    font-family:Consolas;
}}
QListWidget {{
    background:#050505;
    border:1px solid {ORANGE};
    outline:0;
    font-size:13px;
}}
QListWidget::item {{
    padding:6px 8px;
    border-bottom:1px solid #1a1a1a;
}}
QListWidget::item:selected {{
    background:{AZURE};
    color:#000000;
}}
QTextEdit {{
    background:#050505;
    border:1px solid {ORANGE};
    padding:8px;
}}
QLineEdit {{
    background:#050505;
    color:{ORANGE};
    border:1px solid {ORANGE};
    padding:5px 8px;
    selection-background-color:{AZURE};
    selection-color:#000000;
}}
QPushButton {{
    background:#000000;
    color:{AZURE};
    border:2px solid {AZURE};
    padding:6px 16px;
    font-weight:bold;
}}
QPushButton:hover {{
    background:{AZURE};
    color:#000000;
}}
QScrollBar:vertical {{
    background:#000000;
    width:10px;
}}
QScrollBar::handle:vertical {{
    background:{DIM};
    min-height:24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height:0;
}}
"""


def _verdict(entry):
    """Verdetto della voce; per i vecchi record lo ricava dalla scelta."""
    v = str(entry.get("verdict", "")).upper()
    if v in VERDICT_COLORS:
        return v

    choice = str(entry.get("choice", "")).strip().lower()

    if choice in ("", "unknown", "deadlock"):
        return "DEADLOCK"
    if choice == "no":
        return "DENIED"
    return "APPROVED"


def _when(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    return str(ts or "")[:16].replace("T", " ")


def _esc(value):
    return html.escape(str(value))


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render(number, e):
    """HTML del pannello di dettaglio."""

    verdict = _verdict(e)
    color = VERDICT_COLORS[verdict]

    if verdict == "DEADLOCK":
        head = verdict
    else:
        head = (
            f"{verdict} &nbsp;·&nbsp; "
            f"{_esc(str(e.get('choice', '')).upper())}"
        )

    def title(text):
        return (
            f"<p style='color:{AZURE}; font-size:12px; "
            f"margin-bottom:0;'>{text}</p>"
        )

    out = [
        f"<p style='color:{DIM}; font-size:12px;'>"
        f"No.{number:03d} &nbsp;·&nbsp; {_esc(_when(e.get('timestamp')))}</p>",

        title("REQUEST"),
        f"<p style='color:#ffffff; font-size:15px; margin-top:2px;'>"
        f"{_esc(e.get('prompt', ''))}</p>",

        title("VERDICT"),
        f"<p style='color:{color}; font-size:24px; font-weight:bold; "
        f"margin-top:2px;'>{head}</p>",
    ]

    bits = []
    if e.get("tally"):
        bits.append(f"TALLY {_esc(e['tally'])}")
    if e.get("consensus") is not None:
        bits.append(f"CONSENSUS {_esc(e['consensus'])}%")
    if bits:
        out.append(
            f"<p style='color:{ORANGE};'>{' &nbsp;|&nbsp; '.join(bits)}</p>"
        )

    # info sulla deliberazione (se salvate)
    r1 = e.get("round1")
    if e.get("rounds") == 2 and isinstance(r1, dict):
        out.append(
            f"<p style='color:{ORANGE};'>"
            f"ROUND 1: {_esc(r1.get('verdict', '?'))} "
            f"({_esc(r1.get('tally', '-'))})"
            f" &nbsp;→&nbsp; "
            f"ROUND 2: {_esc(verdict)} ({_esc(e.get('tally', '-'))})</p>"
        )
        if e.get("advocate"):
            out.append(
                f"<p style='color:{DIM};'>"
                f"DEVIL'S ADVOCATE: {_esc(e['advocate'])}</p>"
            )
        if e.get("flips"):
            out.append(
                f"<p style='color:{DIM};'>"
                f"CHANGED VOTE: {_esc(', '.join(e['flips']))}</p>"
            )

    if e.get("objection"):
        out.append(
            title("OBJECTION")
            + f"<p style='color:#9fb4bd;'>{_esc(e['objection'])}</p>"
        )

    # matrice dei voti
    votes = e.get("votes")
    if isinstance(votes, dict) and votes:
        top = max(_num(v) for v in votes.values()) or 1.0
        rows = ""

        for name, score in sorted(
            votes.items(), key=lambda kv: _num(kv[1]), reverse=True
        ):
            bar = "█" * max(1, round(_num(score) / top * 24))
            rows += (
                f"<tr>"
                f"<td style='color:#ffffff;'>{_esc(str(name).upper())}"
                f"&nbsp;&nbsp;</td>"
                f"<td style='color:{AZURE};'>{bar}&nbsp;&nbsp;</td>"
                f"<td style='color:{ORANGE};'>{_num(score):.1f}</td>"
                f"</tr>"
            )

        out.append(
            title("VOTING MATRIX")
            + f"<table cellspacing='4'>{rows}</table>"
        )

    # analisi dei core
    cores = e.get("cores")

    if isinstance(cores, list) and cores:
        out.append(title("CORE ANALYSIS"))

        for c in cores:
            if c.get("valid", True):
                vote = (
                    f"{_esc(c.get('choice', '?'))} · "
                    f"{_esc(c.get('label', ''))} · "
                    f"{_num(c.get('confidence')):.0f}%"
                )
                if c.get("changed"):
                    vote = f"{_esc(c.get('previous'))} → " + vote
            else:
                vote = "ERROR"

            text = _esc(c.get("reasoning", "")).replace(chr(10), "<br>")

            out.append(
                f"<p style='color:{ORANGE}; margin-bottom:0;'>"
                f"<b>{_esc(c.get('agent', '?'))}</b> &nbsp;"
                f"<span style='color:{AZURE};'>{vote}</span></p>"
                f"<p style='color:#9fb4bd; margin-top:2px;'>{text}</p>"
            )

    else:
        # vecchi record: testo unico
        reasoning = str(e.get("reasoning", "")).strip()
        if reasoning:
            body = _esc(reasoning).replace(chr(10), "<br>")
            out.append(
                title("ANALYSIS")
                + f"<p style='color:#9fb4bd;'>{body}</p>"
            )

    return "<div style='font-family:Consolas;'>" + "".join(out) + "</div>"


class MemoryWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("MAGI-OS | Memory Archive")
        self.resize(1000, 640)
        self.setStyleSheet(STYLE)

        self.entries = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # ---- header ----
        head = QHBoxLayout()
        head.setSpacing(20)

        head.addWidget(TitleBlock("記録"))

        self.info = QLabel()
        self.info.setTextFormat(Qt.RichText)
        self.info.setStyleSheet(f"color:{ORANGE}; font-size:12px;")
        head.addWidget(self.info)

        head.addStretch(1)
        root.addLayout(head)

        # ---- lista + dettaglio ----
        body = QHBoxLayout()
        body.setSpacing(10)

        self.list = QListWidget()
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)

        self.list.currentItemChanged.connect(self._show_entry)

        body.addWidget(self.list, 2)
        body.addWidget(self.detail, 3)
        root.addLayout(body, 1)

        # ---- ricerca + refresh ----
        foot = QHBoxLayout()
        foot.setSpacing(8)

        label = QLabel("search:")

        self.search = QLineEdit()
        self.search.setPlaceholderText("filtra per richiesta o decisione...")
        self.search.textChanged.connect(self._fill_list)

        refresh = QPushButton("REFRESH DATABASE")
        refresh.clicked.connect(self.load_memory)

        foot.addWidget(label)
        foot.addWidget(self.search, 1)
        foot.addWidget(refresh)
        root.addLayout(foot)

        self.load_memory()

    # ---------- dati ----------

    def load_memory(self):
        self.entries = load_history() or []
        self._update_info()
        self._fill_list()

    def _update_info(self):
        counts = {"APPROVED": 0, "DENIED": 0, "DEADLOCK": 0}

        for e in self.entries:
            counts[_verdict(e)] += 1

        self.info.setText(
            f"<span style='font-size:22px;'>RECORDS:{len(self.entries)}</span><br>"
            f"APPROVED:{counts['APPROVED']}<br>"
            f"DENIED:{counts['DENIED']}<br>"
            f"DEADLOCK:{counts['DEADLOCK']}"
        )

    def _fill_list(self, *_):
        needle = self.search.text().strip().lower()

        self.list.clear()

        # dalla più recente
        for idx in range(len(self.entries) - 1, -1, -1):
            e = self.entries[idx]
            prompt = str(e.get("prompt", ""))
            choice = str(e.get("choice", ""))

            if needle and needle not in f"{prompt} {choice}".lower():
                continue

            verdict = _verdict(e)

            item = QListWidgetItem(
                f"{idx + 1:03d}  {VERDICT_CODES[verdict]}  {prompt[:38]}"
            )
            item.setForeground(QColor(VERDICT_COLORS[verdict]))
            item.setData(Qt.UserRole, idx)
            self.list.addItem(item)

        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.detail.setHtml(
                f"<p align='center' style='color:{ORANGE}; font-size:16px;'>"
                "NO MAGI DECISIONS RECORDED</p>"
            )

    def _show_entry(self, current, _previous=None):
        if current is None:
            return

        idx = current.data(Qt.UserRole)
        self.detail.setHtml(_render(idx + 1, self.entries[idx]))
