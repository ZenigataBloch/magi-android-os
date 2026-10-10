import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QTextEdit,
    QPushButton
)


class MAGIWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "MAGI-OS NERV Decision System"
        )

        self.resize(
            800,
            600
        )


        layout = QVBoxLayout()


        self.title = QLabel(
            "MAGI-OS\nNERV DECISION SUPPORT SYSTEM"
        )


        self.output = QTextEdit()
        self.output.setReadOnly(True)


        self.button = QPushButton(
            "Synchronize MAGI Cores"
        )


        self.button.clicked.connect(
            self.run_test
        )


        layout.addWidget(
            self.title
        )

        layout.addWidget(
            self.output
        )

        layout.addWidget(
            self.button
        )


        self.setLayout(
            layout
        )


    def run_test(self):

        self.output.append(
            """
[SYSTEM]

Synchronizing MAGI cores...

MELCHIOR ONLINE
BALTHASAR ONLINE
CASPER ONLINE

CONSENSUS READY
"""
        )



def start_gui():

    app = QApplication(
        sys.argv
    )

    window = MAGIWindow()

    window.show()

    sys.exit(
        app.exec()
    )