import asyncio

import config
from core.debug import dbg
from core.deliberation import deliberate
from core.options import extract_options
from core.voting import decide


def _emit(callback, *args):
    if callback:
        try:
            callback(*args)
        except Exception as e:
            dbg("[CALLBACK ERROR]", e)


async def run_magi(
    prompt,
    agents,
    status_callback=None,
    event_callback=None
):

    dbg("[SYSTEM] MAGI Round 1: Independent Analysis")

    # opzioni strutturate
    opts = await extract_options(prompt)
    options = opts["options"]
    _emit(event_callback, "options", opts)

    async def run_agent(agent):

        _emit(status_callback, agent.name, "ANALYZING")

        await asyncio.sleep(1)

        try:
            result = await agent.think(prompt, options)
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

    # ROUND 2: deliberazione
    final_results, extra = results, {}

    if getattr(config, "DELIBERATION", True):
        final_results, extra = await deliberate(
            prompt,
            agents,
            options,
            results,
            status_callback,
            event_callback
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