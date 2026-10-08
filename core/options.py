import re

from agents.base import _extract
from core.debug import dbg
from core.session import context_block
from providers.groq import GroqProvider

LETTERS = "ABCDE"

EXTRACT_PROMPT = """Estrai le opzioni tra cui l'utente deve scegliere.

REGOLE
- Se la richiesta elenca già le opzioni (es. "A o B", "X vs Y"), usa quelle.
- Se è una domanda sì/no (es. "devo comprare X?"), le opzioni sono "SI" e "NO".
- Se è una domanda aperta senza opzioni, proponi 3 candidati plausibili e concreti.
- Da 2 a 5 opzioni, etichette brevi (1-4 parole), nella lingua della richiesta.
- Se è presente una CONVERSAZIONE FINORA, il NUOVO MESSAGGIO la continua: ricava
  le opzioni dalla nuova richiesta tenendo conto del contesto. Non riproporre
  ciò che l'utente ha scartato o che non può fare (per esempio un ingrediente
  che non ha).

Rispondi SOLO con JSON valido:
{"options": ["...", "..."], "generated": false}

"generated" è true solo se le opzioni le hai proposte tu.
"""


def _build(labels, generated=False):
    clean, seen = [], set()

    for label in labels:
        label = " ".join(str(label).split())[:60]
        if label and label.lower() not in seen:
            seen.add(label.lower())
            clean.append(label)

    clean = clean[:len(LETTERS)]

    if len(clean) < 2:
        return None

    return {
        "options": [
            {"id": LETTERS[i], "label": label}
            for i, label in enumerate(clean)
        ],
        "generated": generated,
    }


def _heuristic(prompt):
    """Rete di sicurezza se il provider non risponde: 'A o B', 'A vs B'."""
    text = prompt.strip().rstrip("?!. ")
    text = re.sub(r"^\W*(è\s+)?(meglio|preferisci|scegli)\s+", "", text, flags=re.I)

    parts = [
        p.strip()
        for p in re.split(
            r"\s*(?:,|;|\bvs\.?|\bcontro\b|\boppure\b|\bo\b)\s*",
            text,
            flags=re.I
        )
        if p and p.strip()
    ]

    if (
        len(text) <= 80
        and 2 <= len(parts) <= 5
        and all(len(p.split()) <= 4 for p in parts)
    ):
        return _build(parts)

    return None


async def extract_options(prompt, history=None):
    """Restituisce {"options": [{"id": "A", "label": "..."}], "generated": bool}."""

    context = context_block(history)
    message = f"{context}\n\nNUOVO MESSAGGIO\n{prompt}" if context else prompt

    try:
        raw = await GroqProvider().ask(
            "Estrattore di opzioni",
            EXTRACT_PROMPT,
            message
        )
        data = _extract(raw)
        built = _build(
            data.get("options", []),
            bool(data.get("generated"))
        )
        if built:
            return built

    except Exception as e:
        dbg("[OPTIONS] estrazione fallita:", e)

    return (
        _heuristic(prompt)
        or _build(["SI", "NO"])
    )
