"""Memoria di sessione: i turni precedenti diventano il contesto dei core.

Una sessione e' una lista di turni. Dopo ogni decisione si aggiunge un turno
(make_turn); a ogni nuova richiesta la lista viene trasformata in testo
(context_block) e messa davanti al messaggio. Si azzera col pulsante NEW SESSION.
"""

MAX_TURNS = 5      # quanti turni precedenti mandare ai core
MAX_REASON = 240   # caratteri di ragionamento tenuti per ogni core


def make_turn(result):
    """Riassume il risultato di run_magi in un turno di sessione."""

    decision = result.get("decision", {})
    options = result.get("options", [])
    verdict = decision.get("verdict", "")

    if verdict == "DEADLOCK":
        choice = "nessuna decisione (parità)"
    else:
        labels = {o["id"]: o["label"] for o in options}
        choice = labels.get(decision.get("choice_id"), decision.get("choice", ""))

    reasons = []
    for r in result.get("responses", []):
        if not r.get("valid", True):
            continue

        text = " ".join(str(r.get("reasoning", "")).split())
        if len(text) > MAX_REASON:
            text = text[:MAX_REASON].rstrip() + "..."

        reasons.append({
            "agent": r.get("agent", "?"),
            "choice": r.get("label") or r.get("choice", ""),
            "reasoning": text,
        })

    return {
        "prompt": result.get("prompt", ""),
        "options": [o["label"] for o in options],
        "choice": choice,
        "verdict": verdict,
        "reasons": reasons,
    }


def context_block(history):
    """Testo da mettere davanti alla nuova richiesta. Vuoto se non c'e' storia."""

    if not history:
        return ""

    lines = ["CONVERSAZIONE FINORA (turni precedenti della stessa sessione)"]

    for i, turn in enumerate(history[-MAX_TURNS:], 1):
        lines.append(f"{i}. Richiesta: {turn.get('prompt', '')}")

        if turn.get("options"):
            lines.append(f"   Opzioni: {', '.join(turn['options'])}")

        lines.append(f"   Decisione MAGI: {turn.get('choice', '')}")

        for r in turn.get("reasons", []):
            lines.append(f"   - {r['agent']}: {r['choice']} - {r['reasoning']}")

    lines.append("")
    lines.append(
        "Il messaggio che segue continua questa conversazione: "
        "interpretalo alla luce dei turni precedenti."
    )

    return "\n".join(lines)
