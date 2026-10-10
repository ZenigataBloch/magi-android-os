from dotenv import load_dotenv

load_dotenv()

import asyncio

from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.mistral import MistralProvider

from agents.melchior import Melchior
from agents.balthasar import Balthasar
from agents.casper import Casper

from core.controller import run_magi
from core.voting import decide

from ui.nerv import header, show_result, console
from rich.panel import Panel

from ui.gui import MAGIWindow
from PySide6.QtWidgets import QApplication

from ui.boot import MAGIBoot

from core.magi import create_magi_agents

from config import DEBUG
from ui.icon import set_taskbar_identity, app_icon

def display_agents(results):

    console.print(
        "\n━━━━━━━━━━━━━━━━━━━━━━"
    )

    for r in results:
        console.print(
            f"""
{r['agent']}

CHOICE:
{r['choice']}

CONFIDENCE:
{r['confidence']:.1f}%

━━━━━━━━━━━━━━━━━━━━━━
"""
        )

def display_magi_result(result):

    votes_text = "\n".join(
        [
            f"◈ {choice:<15} {score:.1f}"
            for choice, score in result["votes"].items()
        ]
    )

    console.print(
        Panel(
            f"""
CHOICE:

{result['choice']}


CONSENSUS:

{result['consensus']:.1f}%


MAGI CORES:

3 ANALYZED


VOTES:

{votes_text}

""",
            title="FINAL MAGI DECISION"
        )
    )

def main():

    agents = create_magi_agents()

    set_taskbar_identity()          # NUOVO: prima di QApplication

    app = QApplication([])
    app.setWindowIcon(app_icon())   # NUOVO

    boot = MAGIBoot(
        agents
    )


    def open_gui():

        window = MAGIWindow(
            agents
        )

        window.show()

        boot.main_window = window


    boot.finished.connect(
        open_gui
    )


    boot.show()

    app.exec()


if __name__ == "__main__":
    main()