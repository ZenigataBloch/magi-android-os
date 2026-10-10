"""Intestazione in stile MAGI: 質問 / blocco info / 解決 / badge 情報."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.magi_map import kanji_font

ORANGE = "#ff8c00"
AZURE = "#47b4dc"
LINE_GREEN = QColor("#2e9b63")


class DoubleLine(QWidget):
    """Doppia linea sottile verde, come nella schermata originale."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(9)
        self.setMinimumWidth(60)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setPen(QPen(LINE_GREEN, 1))
        w = self.width()
        p.drawLine(0, 1, w, 1)
        p.drawLine(0, 5, w, 5)
        p.end()


class TitleBlock(QWidget):

    def __init__(self, text, width=190):
        super().__init__()

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        label = QLabel(text)
        font = kanji_font(44)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        label.setFont(font)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color:{ORANGE};")

        col.addWidget(DoubleLine())
        col.addWidget(label)
        col.addWidget(DoubleLine())

        self.setFixedWidth(width)


class HeaderBar(QWidget):

    def __init__(self):
        super().__init__()

        self._info = {
            "code": 473,
            "file": "MAGI_SYS",
            "ex_mode": "OFF",
            "priority": "AAA",
        }

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(20)

        row.addWidget(TitleBlock("質問"))

        self.info = QLabel()
        self.info.setTextFormat(Qt.RichText)
        self.info.setStyleSheet(
            f"color:{ORANGE}; font-family:Consolas; font-size:12px;"
        )
        row.addWidget(self.info)

        row.addStretch(1)

        row.addWidget(TitleBlock("解決"))

        # il badge apre la finestra della memoria
        self.memory_button = QPushButton("情報")
        self.memory_button.setFont(kanji_font(26))
        self.memory_button.setFixedSize(84, 48)
        self.memory_button.setStyleSheet(
            f"""
            QPushButton {{
                color:{AZURE};
                border:2px solid {AZURE};
                background:#04202a;
                padding:0;
            }}
            QPushButton:hover {{
                background:{AZURE};
                color:#000000;
            }}
            QPushButton:disabled {{
                color:#2b6f8a;
                border-color:#2b6f8a;
                background:#02101a;
            }}
            """
        )
        row.addWidget(self.memory_button, 0, Qt.AlignTop)

        self._refresh()

    def _refresh(self):
        i = self._info
        self.info.setText(
            f"<span style='font-size:22px;'>CODE:{i['code']}</span><br>"
            f"FILE:{i['file']}<br>"
            f"EX_MODE:{i['ex_mode']}<br>"
            f"PRIORITY:{i['priority']}"
        )

    def set_info(self, ex_mode=None, priority=None):
        if ex_mode is not None:
            self._info["ex_mode"] = ex_mode
        if priority is not None:
            self._info["priority"] = priority
        self._refresh()

    def next_code(self):
        """Nuovo codice a ogni richiesta; la priorità torna al valore base."""
        self._info["code"] += 1
        self._info["priority"] = "AAA"
        self._refresh()
