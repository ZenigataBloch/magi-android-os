import os

from providers._http import openai_chat

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class MistralProvider:

    async def ask(
        self,
        model,
        system,
        prompt
    ):

        # Prima prova: Mistral
        try:

            return await openai_chat(
                MISTRAL_URL,
                os.getenv("MISTRAL_API_KEY"),
                "mistral-small-latest",
                system,
                prompt,
            )

        except Exception:

            # FALLBACK CASPER
            try:

                return await openai_chat(
                    GROQ_URL,
                    os.getenv("GROQ_API_KEY"),
                    "qwen/qwen3.8-27b",
                    system,
                    prompt,
                )

            except Exception as e:

                return {
                    "decision": "ABSTAIN",
                    "confidence": 0.0,
                    "reasoning":
                        f"CASPER OFFLINE: {e}"
                }
