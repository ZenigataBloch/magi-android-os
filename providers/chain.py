"""Catena di provider: prova il primo, se fallisce passa al successivo."""

from core.debug import dbg


class FallbackProvider:

    def __init__(self, *providers):
        self.providers = providers
        self.last_used = None

    async def ask(self, role, system, prompt):
        errors = []

        for p in self.providers:
            label = getattr(p, "label", type(p).__name__)
            try:
                result = await p.ask(role, system, prompt)
                self.last_used = label
                if errors:
                    dbg("[CHAIN] fallback riuscito:", label)
                return result
            except Exception as e:
                dbg("[CHAIN] fallito:", label, "->", e)
                errors.append(str(e))

        # tutti falliti: l'errore vero arriva fino ad Agent._error()
        raise RuntimeError(" | ".join(errors) or "nessun provider")
