import asyncio

from PySide6.QtCore import QThread, Signal

from core.controller import run_magi


class MAGIWorker(QThread):

    finished = Signal(dict)
    status_update = Signal(str, str)
    magi_event = Signal(str, object)

    def __init__(self, prompt, agents):
        super().__init__()
        self.prompt = prompt
        self.agents = agents

    def run(self):
        result = asyncio.run(
            run_magi(
                self.prompt,
                self.agents,
                status_callback=self.status_update.emit,
                event_callback=self.magi_event.emit
            )
        )
        self.finished.emit(result)