import random


class MockProvider:

    async def ask(
        self,
        model,
        system,
        prompt
    ):

        return {
            "decision": random.choice(
                [
                    "APPROVE",
                    "REJECT"
                ]
            ),

            "confidence": round(
                random.uniform(
                    0.60,
                    0.95
                ),
                2
            ),

            "reasoning":
                "Analisi simulata dal sistema MAGI."
        }