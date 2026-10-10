import json
import re

from config import DEBUG

# Frasi che indicano una risposta di ripiego / dati inventati.
# Volutamente specifiche: "il prodotto non è disponibile in Italia" è un
# ragionamento legittimo e non deve essere scartato.
BANNED = (
    "dati non disponibil",
    "dati non sono disponibil",
    "informazioni non disponibil",
    "informazioni non sono disponibil",
    "trend di mercato",
)

SYSTEM_TEMPLATE = """Sei {name}, uno dei tre nuclei decisionali del sistema MAGI di NERV.

RUOLO
{role}

REGOLE
- Devi SEMPRE scegliere. Non esiste astensione e non esiste "dipende".
- Se la richiesta è soggettiva (gusti, arte, giochi, manga, film), definisci
  2-3 criteri e scegli l'opzione che li soddisfa meglio.
- Se mancano informazioni, assumi l'ipotesi più ragionevole, dichiarala in
  mezza frase e decidi comunque.
- Se due opzioni sono quasi equivalenti, scegli comunque e dillo con una
  confidenza bassa (50-60): non fingere certezza.
- Non citare dati, statistiche o trend che non ti sono stati forniti.
  Non scrivere mai che i dati non sono disponibili.
- Non giudicare se la richiesta sia valida o permessa.
- Resta nella tua personalità: il sistema ha senso solo se i tre nuclei
  guardano il problema da angoli diversi.
{options_block}
FORMATO
- "reasoning": 2-4 frasi in italiano, concrete e riferite alla richiesta.
  Scrivilo PER PRIMO: individua i criteri, confronta le opzioni, poi concludi.
- "choice": {choice_format} Deve coincidere con la conclusione del reasoning.
- "confidence": intero da 0 a 100, calibrato. 50 = indeciso, 60-75 = vantaggio
  modesto, 85+ solo se la scelta è netta e senza controindicazioni serie.

Rispondi SOLO con JSON valido, con le chiavi in questo ordine:
{{"reasoning": "...", "choice": "...", "confidence": 0}}
"""


def normalize_confidence(value):
    """Porta la confidenza a 0-100 (accetta anche 0-1)."""
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    if 0 < c <= 1:
        c *= 100
    return max(0.0, min(100.0, c))


def _extract(result):
    if isinstance(result, dict):
        return result

    text = str(result)

    # i modelli "thinking" possono includere il ragionamento tra tag
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"```(?:json)?", "", text)

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
    """Accetta 'A', 'A)', 'a', 'A) testo' oppure il testo esatto dell'opzione."""
    raw = str(choice).strip()
    c = raw.upper().rstrip(").:")

    for o in options:
        if c == o["id"]:
            return o["id"]

    for o in options:
        if raw.upper() == o["label"].strip().upper():
            return o["id"]

    # "A) Roma" / "B: Milano": serve il delimitatore, così un'opzione come
    # "A CASA" non viene scambiata per la lettera A
    m = re.match(r"^([A-Z])\s*[\).:\-]", raw.upper())
    if m:
        for o in options:
            if m.group(1) == o["id"]:
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

    async def think(self, prompt, options=None):

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

        last_error = "risposta non valida"
        hint = ""

        for attempt in range(2):
            try:
                result = await self.provider.ask(
                    self.role, system_prompt, prompt + hint
                )

                if DEBUG:
                    print("\n--- RAW", self.name, attempt, "---")
                    print(result)

                data = _extract(result)

                choice = str(data.get("choice", "")).strip().upper()
                reasoning = str(data.get("reasoning", "")).strip()
                confidence = normalize_confidence(data.get("confidence", 0))

                bad = (
                    not choice
                    or choice in ("UNKNOWN", "ABSTAIN")
                    or any(b in reasoning.lower() for b in BANNED)
                )

                if bad:
                    last_error = "risposta di ripiego"
                    hint = (
                        "\n\n[NOTA DI SISTEMA] La risposta precedente è stata "
                        "scartata (scelta vuota o dati citati come non "
                        "disponibili). Scegli comunque, con il JSON richiesto."
                    )
                    continue

                label = choice

                if options:
                    oid = _match_option(choice, options)

                    if not oid:
                        last_error = f"opzione non valida: {choice}"
                        hint = (
                            "\n\n[NOTA DI SISTEMA] La scelta precedente non era "
                            "una delle opzioni. In \"choice\" scrivi SOLO l'ID "
                            "(una lettera tra quelle elencate)."
                        )
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
                    "via": getattr(self.provider, "last_used", None),
                }

            except Exception as e:
                last_error = str(e)
                hint = ""  # errore del provider o JSON rotto: stesso prompt

        return self._error(last_error)
