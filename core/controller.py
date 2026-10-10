import asyncio

import config
from core.debug import dbg
from core.deliberation import deliberate
from core.options import extract_options
from core.session import context_block
from core.voting import decide


def _emit(callback, *args):
    if callback:
        try:
            callback(*args)
        except Exception as e:
            dbg("[CALLBACK ERROR]", e)


def _unanimous(results):
    """True se tutti i core hanno votato valido, uguale e con confidenza alta."""
    if not results or not all(r.get("valid", True) for r in results):
        return False

    if len({r["choice"] for r in results}) != 1:
        return False

    floor = getattr(config, "UNANIMOUS_MIN_CONFIDENCE", 85)
    return min(r.get("confidence", 0) for r in results) >= floor


async def run_magi(
    prompt,
    agents,
    status_callback=None,
    event_callback=None,
    history=None
):
    """history: lista di turni di sessione (vedi core/session.py), opzionale.

    Senza history (desktop) si comporta come prima.
    """

    dbg("[SYSTEM] MAGI Round 1: Independent Analysis")

    # opzioni strutturate (l'estrattore legge da solo la history)
    opts = await extract_options(prompt, history)
    options = opts["options"]
    _emit(event_callback, "options", opts)

    # i core ricevono i turni precedenti davanti al nuovo messaggio
    context = context_block(history)
    agent_prompt = (
        f"{context}\n\nNUOVO MESSAGGIO\n{prompt}" if context else prompt
    )

    async def run_agent(agent):

        _emit(status_callback, agent.name, "ANALYZING")

        await asyncio.sleep(1)

        try:
            result = await agent.think(agent_prompt, options)
        except Exception as e:
            result = agent._error(str(e))

        _emit(
            status_callback,
            agent.name,
            "COMPLETE" if result.get("valid", True) else "ERROR"
        )

        return result

    # ROUND 1: i risultati arrivano uno alla volta
    tasks = [asyncio.create_task(run_agent(a)) for a in agents]
    results = []

    for finished in asyncio.as_completed(tasks):
        result = await finished
        results.append(result)
        _emit(event_callback, "agent_result", result)

    order = {a.name: i for i, a in enumerate(agents)}
    results.sort(key=lambda r: order.get(r["agent"], 99))

    # ROUND 2: deliberazione (saltata se c'è unanimità netta)
    final_results, extra = results, {}

    skip = (
        getattr(config, "SKIP_ROUND2_IF_UNANIMOUS", False)
        and _unanimous(results)
    )

    if skip:
        dbg("[SYSTEM] Unanimità netta: round 2 saltato")

    if getattr(config, "DELIBERATION", True) and not skip:
        # deliberate() aggiunge da sola il contesto: qui va il prompt "puro"
        final_results, extra = await deliberate(
            prompt,
            agents,
            options,
            results,
            status_callback,
            event_callback,
            history
        )

    decision = decide(final_results, options=options)
    decision.update(extra)

    return {
        "prompt": prompt,
        "options": options,
        "responses": final_results,
        "round1": results,
        "decision": decision
    }
