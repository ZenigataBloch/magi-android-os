MAGI_STYLE = """

QWidget {
    background-color: #000000;
    color: #ff8c00;
}


QFrame,
QTextEdit,
QLineEdit,
QPushButton,
QProgressBar {
    border-radius: 2px;
}


QLineEdit {
    border: 1px solid #ff8c00;
    background: #0a0600;
    padding: 6px 8px;
    color: #ffb347;
    font-family: Consolas;
    font-size: 14px;
    selection-background-color: #ff8c00;
    selection-color: #000000;
}


QPushButton {
    border: 1px solid #ff8c00;
    background: #1a0f00;
    color: #ff8c00;
    padding: 6px 16px;
    font-weight: bold;
}


QPushButton:hover {
    background: #ff8c00;
    color: #000000;
}


QPushButton:disabled {
    border-color: #5a3000;
    color: #5a3000;
    background: #0a0600;
}


QTextEdit {
    border: 1px solid #7a4300;
    background: #050300;
    color: #ff9a1f;
    font-family: Consolas;
    font-size: 12px;
    padding: 8px;
}


QProgressBar {
    border: 1px solid #7a4300;
    background: #0a0600;
    text-align: center;
}


QProgressBar::chunk {
    background: #ff8c00;
}

"""
