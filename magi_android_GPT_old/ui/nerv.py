from rich.console import Console
from rich.panel import Panel


console = Console()


def header():

    console.print(
        Panel(
"""
        MAGI-OS

 NERV DECISION SUPPORT SYSTEM

        MELCHIOR
        BALTHASAR
        CASPER

"""
        )
    )


def show_result(result):

    confidence = float(
        result.get("confidence", 0)
    )

    # Se arriva normalizzata 0-1, trasformala in 0-100
    if confidence <= 1:
        confidence *= 100


    console.print(
f"""
━━━━━━━━━━━━━━━━━━━━━━

{result.get("agent", "MAGI CORE")}

CHOICE:

{result.get("choice", result.get("decision", "UNKNOWN"))}

CONFIDENCE:

{confidence:.1f}%

{result.get("reasoning", "No reasoning")}

━━━━━━━━━━━━━━━━━━━━━━
"""
)