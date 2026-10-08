import asyncio
import random

from agents.base import BANNED, SYSTEM_TEMPLATE, _extract, _match_option
from core.debug import dbg
from core.voting import decide

_state = {"i": None}


def pick_advocate(agents):
    """Rotazione: a ogni richiesta tocca a un core diverso."""
    if _state["i"] is None:
        _state["i"] = random.randrange(len(agents))

    agent = agents[_state["i"] % len(agents)]
    _state["i"] += 1
    return agent


def _emit(callback, *args):
    if callback:
        try:
            callback(*args)
        except Exception as e:
            dbg("[CALLBACK ERROR]", e)


def _line(r):
    if not r or not r.get("valid", True):
        return f"- {r['agent'] if r else '?'}: nessun voto valido"

    return (
        f"- {r['agent']}: {r['choice']}) {r['label']} "
        f"(confidenza {r['confidence']:.0f}%) — {r['reasoning']}"
    )


def _leading(round1):
    """Opzione in testa dopo il round 1 (voti, poi confidenza)."""
    counts, conf = {}, {}

    for r in round1:
        if not r.get("valid", True):
            continue
        k = r["choice"]
        counts[k] = counts.get(k, 0) + 1
        conf[k] = conf.get(k, 0) + r["confidence"]

    if not counts:
        return None

    return max(counts, key=lambda k: (counts[k], conf[k]))


def _system_prompt(agent, options):
    lista = "\n".join(f"{o['id']}) {o['label']}" for o in options)

    return SYSTEM_TEMPLATE.format(
        name=agent.name,
        role=agent.role.strip(),
        options_block=f"\nOPZIONI (scegline UNA)\n{lista}\n",
        choice_format="SOLO l'ID di una opzione (per esempio A). Nient'altro.",
    )


CHALLENGE_SYSTEM = """Sei {name}, uno dei tre nuclei decisionali del sistema MAGI di NERV.

In questa deliberazione hai il ruolo di AVVOCATO DEL DIAVOLO.

Il tuo compito NON è dire cosa preferisci: è mettere alla prova l'opzione in
testa, trovando l'argomento più forte contro di essa. Il tuo angolo di
attacco, coerente con la tua personalità:
{role}

REGOLE
- Attacca l'opzione indicata anche se concordi con essa.
- Sii concreto: rischi, assunzioni deboli, costi nascosti, aspetti ignorati
  dagli altri nuclei.
- Non inventare dati o statistiche.
- 2-4 frasi in italiano, riferite alla richiesta.

Rispondi SOLO con JSON valido, senza altro testo:
{{"objection": "..."}}
"""


async def _challenge(advocate, prompt, options, round1, leading):

    label = next(o["label"] for o in options if o["id"] == leading)

    system = CHALLENGE_SYSTEM.format(
        name=advocate.name,
        role=advocate.role.strip()
    )

    user = (
        f"RICHIESTA ORIGINALE\n{prompt}\n\n"
        f"OPZIONE IN TESTA DOPO IL ROUND 1: {leading}) {label}\n\n"
        "VOTI DEL ROUND 1\n"
        + "\n".join(_line(r) for r in round1)
        + f"\n\nCOMPITO\nTrova l'argomento più forte contro {leading}) {label}."
    )

    for attempt in range(2):
        try:
            raw = await advocate.provider.ask(advocate.role, system, user)
            text = str(_extract(raw).get("objection", "")).strip()
            if text:
                return text
        except Exception as e:
            dbg("[DELIBERATION] obiezione fallita:", e)

    return None


async def _revise(agent, prompt, options, own, round1, objection, advocate_name):

    peers = [r for r in round1 if r["agent"] != agent.name]

    parts = [
        f"RICHIESTA ORIGINALE\n{prompt}",
        "ROUND 1 — IL TUO VOTO\n"
        + (_line(own) if own else "nessun voto valido"),
        "ROUND 1 — GLI ALTRI NUCLEI\n"
        + "\n".join(_line(r) for r in peers),
    ]

    if objection:
        if advocate_name == agent.name:
            head = (
                "OBIEZIONE (l'hai scritta tu come avvocato del diavolo: "
                "era un ruolo recitato, il tuo voto deve riflettere ciò che "
                "pensi davvero)"
            )
        else:
            head = (
                f"OBIEZIONE DELL'AVVOCATO DEL DIAVOLO ({advocate_name}) — "
                "è uno stress-test: valutala nel merito"
            )
        parts.append(f"{head}\n{objection}")

    parts.append(
        "COMPITO\n"
        "Rivedi il tuo voto alla luce di quanto sopra. Puoi confermarlo o "
        "cambiarlo, ma cambia solo se un argomento ti ha davvero convinto: "
        "non allinearti agli altri solo perché sono in maggioranza. "
        'In "reasoning" (1-3 frasi) spiega cosa ti ha fatto cambiare idea '
        "oppure perché resti della tua posizione."
    )

    user = "\n\n".join(parts)
    system = _system_prompt(agent, options)

    for attempt in range(2):
        try:
            raw = await agent.provider.ask(agent.role, system, user)
            data = _extract(raw)

            oid = _match_option(data.get("choice", ""), options)
            reasoning = str(data.get("reasoning", "")).strip()

            if not oid or any(b in reasoning.lower() for b in BANNED):
                continue

            return {
                "agent": agent.name,
                "choice": oid,
                "label": next(o["label"] for o in options if o["id"] == oid),
                "confidence": max(
                    0.0, min(100.0, float(data.get("confidence", 0)))
                ),
                "reasoning": reasoning,
                "valid": True,
                "round": 2,
            }

        except Exception as e:
            dbg("[DELIBERATION] revisione fallita:", agent.name, e)

    return None


async def deliberate(
    prompt,
    agents,
    options,
    round1,
    status_callback=None,
    event_callback=None
):
    """Round 2. Restituisce (risultati_finali, info_extra)."""

    leading = _leading(round1)

    if not leading or len(agents) < 2:
        return round1, {}

    by_name = {r["agent"]: r for r in round1}
    advocate = pick_advocate(agents)

    _emit(event_callback, "round", {"n": 2, "advocate": advocate.name})

    # Fase A: l'avvocato del diavolo scrive l'obiezione
    _emit(status_callback, advocate.name, "ANALYZING")

    objection = await _challenge(
        advocate, prompt, options, round1, leading
    )

    if objection:
        _emit(
            event_callback,
            "objection",
            {"agent": advocate.name, "text": objection}
        )

    # Fase B: tutti rivedono il voto
    async def revise_one(agent):

        own = by_name.get(agent.name)
        own_ok = bool(own and own.get("valid", True))

        if agent is not advocate:
            _emit(status_callback, agent.name, "ANALYZING")

        try:
            r2 = await _revise(
                agent, prompt, options, own, round1,
                objection, advocate.name
            )
        except Exception as e:
            dbg("[DELIBERATION] errore:", agent.name, e)
            r2 = None

        _emit(
            status_callback,
            agent.name,
            "COMPLETE" if (r2 or own_ok) else "ERROR"
        )

        if r2:
            prev = own["choice"] if own_ok else None
            r2["previous"] = prev
            r2["changed"] = prev is not None and prev != r2["choice"]

        _emit(
            event_callback,
            "revision",
            r2 or {"agent": agent.name, "carried": True}
        )

        return agent.name, r2

    tasks = [asyncio.create_task(revise_one(a)) for a in agents]
    revisions = {}

    for finished in asyncio.as_completed(tasks):
        name, r2 = await finished
        if r2:
            revisions[name] = r2

    # se una revisione manca, vale il voto del round 1
    final = []
    for r in round1:
        r2 = revisions.get(r["agent"])
        final.append(
            r2 if r2 else {**r, "round": 1, "carried": True, "changed": False}
        )

    d1 = decide(round1, options=options)

    extra = {
        "rounds": 2,
        "advocate": advocate.name,
        "objection": objection,
        "flips": [r["agent"] for r in final if r.get("changed")],
        "round1": {
            "verdict": d1["verdict"],
            "choice": d1["choice"],
            "tally": d1["tally"],
        },
    }

    return final, extra