"""Chiamate HTTP ai provider LLM con `requests` (funziona anche su Android).

Sostituisce gli SDK groq / mistralai / google-genai, che dipendono da
pydantic e httpx e non si possono includere nell'APK.

Novità: retry con attesa breve su 429/5xx/errori di rete. Se il provider
chiede un'attesa lunga (quota giornaliera finita) non si insiste: si passa
subito al fallback.
"""

import asyncio
import time

import requests

TIMEOUT = 60
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 2
MAX_WAIT = 8  # secondi


def _wait_time(r, attempt):
    """Secondi da attendere, oppure None se l'attesa è troppo lunga."""
    try:
        wait = float(r.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0 * (attempt + 1)
    return wait if wait <= MAX_WAIT else None


def _post(url, headers, payload):
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        except requests.RequestException as e:
            if attempt < MAX_RETRIES:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise RuntimeError(f"rete: {e}")

        if r.ok:
            return r.json()

        if r.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
            wait = _wait_time(r, attempt)
            if wait is not None:
                time.sleep(wait)
                continue

        # il corpo della risposta non contiene mai la chiave API
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")


async def post_json(url, headers, payload):
    """POST in un thread: non blocca l'event loop (né la GUI)."""
    return await asyncio.to_thread(_post, url, headers, payload)


async def openai_chat(url, key, model, system, prompt, **extra):
    """Chat completion nel formato OpenAI (Groq, Mistral, NVIDIA, OpenRouter)."""

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

    content = data["choices"][0]["message"].get("content")

    if not content or not str(content).strip():
        raise RuntimeError("risposta vuota")

    return content
