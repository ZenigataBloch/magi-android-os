import os

from providers._http import openai_chat

URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:

    async def ask(
        self,
        model,
        system,
        prompt
    ):

        try:

            content = await openai_chat(
                URL,
                os.getenv("GROQ_API_KEY"),
                "openai/gpt-oss-20b",
                system,
                prompt,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            print("BALTHASAR RAW:")
            print(content)

            return content

        except Exception as e:

            return {
                "decision": "ABSTAIN",
                "confidence": 0,
                "reasoning":
                    f"BALTHASAR OFFLINE: {str(e)}"
            }
