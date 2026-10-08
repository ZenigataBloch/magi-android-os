"""Chiamate HTTP ai provider LLM con `requests` (funziona anche su Android).

Sostituisce gli SDK groq / mistralai / google-genai, che dipendono da
pydantic e httpx e non si possono includere nell'APK.
"""

import asyncio

import requests

TIMEOUT = 60


def _post(url, headers, payload):
    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)

    if not r.ok:
        # il corpo della risposta non contiene mai la chiave API
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

    return r.json()


async def post_json(url, headers, payload):
    """POST in un thread: non blocca l'event loop (né la GUI)."""
    return await asyncio.to_thread(_post, url, headers, payload)


async def openai_chat(url, key, model, system, prompt, **extra):
    """Chat completion nel formato OpenAI (usato da Groq e Mistral)."""

    if not key:
        raise RuntimeError("chiave API mancante")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        **extra,
    }

    data = await post_json(
        url,
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        payload,
    )

    return data["choices"][0]["message"]["content"]
