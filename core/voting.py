from config import DEBUG
from core.debug import dbg

TIEBREAK_MARGIN = 15   # punti di confidenza necessari per rompere una parità


def normalize_choice(choice):

    choice = str(choice).lower().strip()

    # rimuove punteggiatura finale
    choice = choice.rstrip(".!?")

    # rimuove articoli iniziali comuni
    articles = [
        "the ",
        "a ",
        "an "
    ]

    for article in articles:
        if choice.startswith(article):
            choice = choice[len(article):]
            break

    # normalizza spazi multipli
    choice = " ".join(
        choice.split()
    )

    return choice


def decide(results, options=None, weights=None):

    labels = {o["id"]: o["label"] for o in (options or [])}
    weights = weights or {}

    votes, counts, breakdown = {}, {}, {}

    for r in results:

        dbg("VOTING:", r)

        agent = r.get("agent", "?")
        raw = str(r.get("choice", "")).strip()

        if (
            not r.get("valid", True)
            or not raw
            or raw.upper() in ("UNKNOWN", "ERROR", "ABSTAIN")
        ):
            breakdown[agent] = {"id": None, "label": "ERROR", "confidence": 0}
            continue

        key = raw.upper() if labels else normalize_choice(raw)

        try:
            confidence = float(r.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0

        if 0 < confidence <= 1:
            confidence *= 100

        votes[key] = votes.get(key, 0) + confidence * weights.get(agent, 1.0)
        counts[key] = counts.get(key, 0) + 1

        breakdown[agent] = {
            "id": key,
            "label": labels.get(key, key),
            "confidence": round(confidence, 1),
        }

    valid = sum(counts.values())

    result = {
        "choice": "DEADLOCK",
        "choice_id": None,
        "verdict": "DEADLOCK",
        "confidence": 0,
        "consensus": 0,
        "votes": {labels.get(k, k): round(v, 1) for k, v in votes.items()},
        "tally": "-".join(
            str(c) for c in sorted(counts.values(), reverse=True)
        ) or "-",
        "dissent": [],
        "errors": [a for a, b in breakdown.items() if b["id"] is None],
        "tiebreak": False,
        "breakdown": breakdown,
        "reasoning": "\n\n".join(r.get("reasoning", "") for r in results),
        "note": "",
    }

    # serve il quorum: almeno 2 core validi
    if valid < 2:
        result["note"] = "Quorum non raggiunto: servono almeno 2 core validi"
        return result

    ranked = sorted(
        counts,
        key=lambda k: (counts[k], votes[k]),
        reverse=True
    )
    top = ranked[0]

    # parità sul numero di voti: la confidenza decide solo se lo scarto è netto
    tied = [k for k in ranked if counts[k] == counts[top]]

    if len(tied) > 1:
        gap = votes[tied[0]] - votes[tied[1]]

        if gap < TIEBREAK_MARGIN:
            result["note"] = (
                f"Parità {result['tally']}: confidenza troppo vicina "
                f"(scarto {gap:.0f} punti)"
            )
            return result

        result["tiebreak"] = True
        result["note"] = f"Parità risolta dalla confidenza (scarto {gap:.0f} punti)"

    total = sum(votes.values())
    consensus = (
        votes[top] / total * 100 if total > 0
        else counts[top] / valid * 100
    )

    label = labels.get(top, top)
    verdict = "DENIED" if normalize_choice(label) == "no" else "APPROVED"

    result.update({
        "choice": str(label).upper(),
        "choice_id": top,
        "verdict": verdict,
        "confidence": round(consensus, 1),
        "consensus": round(consensus, 1),
        "dissent": [
            a for a, b in breakdown.items()
            if b["id"] not in (None, top)
        ],
    })

    return result