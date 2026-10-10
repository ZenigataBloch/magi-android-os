import json
import os
from datetime import datetime
from pathlib import Path


def _base_dir():
    # su Android si usa la cartella privata dell'app, che resta tra un avvio
    # e l'altro; altrove la cartella corrente, come prima
    private = os.environ.get("ANDROID_PRIVATE")
    return Path(private) if private else Path(__file__).resolve().parent.parent


MEMORY_DIR = _base_dir() / "data"
MEMORY_FILE = MEMORY_DIR / "decisions.json"


def _ensure_storage():
    MEMORY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def load_history():
    """
    Carica lo storico MAGI.
    Se il file non esiste o è corrotto,
    restituisce una lista vuota.
    """

    if not MEMORY_FILE.exists():
        return []

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def _next_id(history):
    """
    Genera codice progressivo MAGI.
    """

    return f"MAGI-{len(history) + 1:06d}"


def save_decision(
    prompt,
    decision,
    responses=None
):
    """
    Salva una decisione MAGI completa.

    Compatibile con la vecchia chiamata:
        save_decision(prompt, decision)

    Supporta anche:
        save_decision(prompt, decision, responses)
    """

    _ensure_storage()

    history = load_history()

    entry = {
        "id": _next_id(history),

        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "prompt": prompt,

        "choice": decision.get(
            "choice",
            "UNKNOWN"
        ),

        "verdict": decision.get(
            "verdict",
            ""
        ),

        "consensus": decision.get(
            "consensus",
            0
        ),

        "rounds": decision.get(
            "rounds",
            1
        ),

        "votes": decision.get(
            "votes",
            {}
        ),

        "flips": decision.get(
            "flips",
            []
        ),

        "tally": decision.get("tally", ""),
        "advocate": decision.get("advocate", ""),
        "objection": decision.get("objection", ""),
        "round1": decision.get("round1", {}),

        "agents": {}
    }


    # tollerante: accetta anche l'intero risultato di run_magi (dict)
    if isinstance(responses, dict):
        responses = responses.get("responses", [])

    if responses:
        for response in responses:

            if not isinstance(response, dict):
                continue

            name = response.get(
                "agent",
                "UNKNOWN"
            )

            entry["agents"][name] = {
                "choice": response.get(
                    "choice",
                    "UNKNOWN"
                ),

                "confidence": response.get(
                    "confidence",
                    0
                ),

                "round": response.get(
                    "round",
                    1
                )
            }


    history.append(entry)


    tmp = MEMORY_FILE.with_suffix(".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    os.replace(tmp, MEMORY_FILE)

    return entry


def get_last_decision():
    """
    Restituisce l'ultima decisione MAGI.
    """

    history = load_history()

    if not history:
        return None

    return history[-1]


def get_next_code():
    """
    Restituisce il prossimo CODE NERV.
    """

    history = load_history()

    return f"CODE : {len(history) + 1:06d}"


def get_statistics():
    """
    Statistiche rapide del sistema MAGI.
    """

    history = load_history()

    total = len(history)

    if total == 0:
        return {
            "total": 0,
            "average_consensus": 0
        }


    avg = sum(
        float(
            item.get(
                "consensus",
                0
            )
        )
        for item in history
    ) / total


    return {
        "total": total,
        "average_consensus": round(
            avg,
            2
        )
    }