import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # su Android le chiavi le carica già main.py
    pass

import config
from providers._http import post_json
from providers.chain import FallbackProvider
from providers.openai_compat import nvidia

BASE = "https://generativelanguage.googleapis.com/v1beta/models/"


class _GeminiRaw:

    name = "gemini"

    @property
    def label(self):
        return f"gemini:{config.GEMINI_MODEL}"

    async def ask(self, role, system, prompt):
        try:
            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise RuntimeError("GEMINI_API_KEY mancante")

            # la chiave va nell'header, non nell'URL: così non compare
            # mai nei messaggi di errore
            data = await post_json(
                f"{BASE}{config.GEMINI_MODEL}:generateContent",
                {
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                {
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    # niente temperature: per Gemini 3 si lascia il default
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )

            candidates = data.get("candidates") or []

            if not candidates:
                raise RuntimeError(
                    f"risposta vuota ({data.get('promptFeedback', 'nessun dettaglio')})"
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(
                p.get("text", "") for p in parts if not p.get("thought")
            )

            if not text.strip():
                reason = candidates[0].get("finishReason", "?")
                raise RuntimeError(f"testo vuoto (finishReason={reason})")

            return text

        except Exception as e:
            raise RuntimeError(f"{self.label}: {e}") from None


class GeminiProvider(FallbackProvider):
    """Melchior (e estrattore di opzioni): Gemini, poi NVIDIA se c'è la chiave."""

    def __init__(self):
        super().__init__(_GeminiRaw(), nvidia(config.NVIDIA_MODEL))
