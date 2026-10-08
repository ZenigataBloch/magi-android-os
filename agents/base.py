import json
import re

from config import DEBUG
from core.session import context_block

BANNED = ("non disponibil", "trend di mercato")

SYSTEM_TEMPLATE = """Sei {name}, uno dei tre nuclei decisionali del sistema MAGI di NERV.

RUOLO
{role}

REGOLE
- Devi SEMPRE scegliere. Non esiste astensione e non esiste "dipende".
- Se la richiesta è soggettiva (gusti, arte, giochi, manga, film), definisci
  2-3 criteri e scegli l'opzione che li soddisfa meglio.
- Se mancano informazioni, assumi l'ipotesi più ragionevole, dichiarala in
  mezza frase e decidi comunque.
- Non citare dati, statistiche o trend che non ti sono stati forniti.
  Non scrivere mai che i dati non sono disponibili.
- Non giudicare se la richiesta sia valida o permessa.
- Resta nella tua personalità: il sistema ha senso solo se i tre nuclei
  guardano il problema da angoli diversi.
{options_block}
FORMATO
- "choice": {choice_format}
- "confidence": intero da 0 a 100. 50 = indeciso, 90+ solo se la scelta è netta.
- "reasoning": 2-4 frasi in italiano, concrete e riferite alla richiesta.

Rispondi SOLO con JSON valido, senza altro testo:
{{"choice": "...", "confidence": 0, "reasoning": "..."}}
"""


def _extract(result):
    if isinstance(result, dict):
        return result

    text = re.sub(r"```(?:json)?", "", str(result))
    start, end = text.find("{"), text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("nessun JSON nella risposta")

    raw = (
        text[start:end + 1]
        .replace("\u202f", " ")
        .replace("\u00a0", " ")
    )
    return json.loads(raw, strict=False)


def _match_option(choice, options):
    """Accetta 'A', 'A)', 'a' oppure il testo esatto dell'opzione."""
    c = str(choice).strip().upper().rstrip(").:")

    for o in options:
        if c == o["id"]:
            return o["id"]

    for o in options:
        if str(choice).strip().upper() == o["label"].strip().upper():
            return o["id"]

    return None


class Agent:

    role = ""

    def __init__(self, name, provider, role=None):
        self.name = name
        self.provider = provider
        if role:
            self.role = role

    def _error(self, msg):
        return {
            "agent": self.name,
            "choice": "ERROR",
            "label": "ERROR",
            "confidence": 0,
            "reasoning": f"Core non disponibile: {msg}",
            "valid": False,
        }

    async def think(self, prompt, options=None, history=None):

        if options:
            lista = "\n".join(
                f"{o['id']}) {o['label']}" for o in options
            )
            options_block = f"\nOPZIONI (scegline UNA)\n{lista}\n"
            choice_format = "SOLO l'ID di una opzione (per esempio A). Nient'altro."
        else:
            options_block = ""
            choice_format = "1-4 parole in MAIUSCOLO."

        system_prompt = SYSTEM_TEMPLATE.format(
            name=self.name,
            role=self.role.strip(),
            options_block=options_block,
            choice_format=choice_format
        )

        # sessione in corso: i turni precedenti vengono prima della richiesta
        context = context_block(history)
        user_prompt = (
            f"{context}\n\nNUOVA RICHIESTA\n{prompt}" if context else prompt
        )

        last_error = "risposta non valida"

        for attempt in range(2):
            try:
                result = await self.provider.ask(
                    self.role, system_prompt, user_prompt
                )

                if DEBUG:
                    print("\n--- RAW", self.name, attempt, "---")
                    print(result)

                data = _extract(result)

                choice = str(data.get("choice", "")).strip().upper()
                reasoning = str(data.get("reasoning", "")).strip()
                confidence = max(
                    0.0,
                    min(100.0, float(data.get("confidence", 0)))
                )

                bad = (
                    not choice
                    or choice in ("UNKNOWN", "ABSTAIN")
                    or any(b in reasoning.lower() for b in BANNED)
                )

                if bad:
                    last_error = "risposta di ripiego"
                    continue

                label = choice

                if options:
                    oid = _match_option(choice, options)

                    if not oid:
                        last_error = f"opzione non valida: {choice}"
                        continue

                    choice = oid
                    label = next(
                        o["label"] for o in options if o["id"] == oid
                    )

                return {
                    "agent": self.name,
                    "choice": choice,
                    "label": label,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "valid": True,
                }

            except Exception as e:
                last_error = str(e)

        return self._error(last_error)
