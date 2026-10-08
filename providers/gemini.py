import os

from dotenv import load_dotenv

from providers._http import post_json

try:
    load_dotenv()
except Exception:
    # su Android le chiavi le carica già main.py
    pass

MODEL = "gemini-3.1-flash-lite"
URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


class GeminiProvider:

    async def ask(
        self,
        model,
        system,
        prompt
    ):

        try:

            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise RuntimeError("GEMINI_API_KEY mancante nel file .env")

            # la chiave va nell'header, non nell'URL: così non compare
            # mai nei messaggi di errore
            data = await post_json(
                URL,
                {
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                {
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]}
                    ],
                },
            )

            candidates = data.get("candidates") or []

            if not candidates:
                raise RuntimeError(
                    f"risposta vuota ({data.get('promptFeedback', 'nessun dettaglio')})"
                )

            parts = candidates[0].get("content", {}).get("parts", [])

            return "".join(
                p.get("text", "") for p in parts if not p.get("thought")
            )

        except Exception as e:

            return {
                "choice": "UNKNOWN",
                "confidence": 0.0,
                "reasoning":
                    f"MELCHIOR OFFLINE: {str(e)}"
            }
