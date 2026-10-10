import config
from providers.chain import FallbackProvider
from providers.openai_compat import groq, mistral, nvidia


class MistralProvider(FallbackProvider):
    """Casper: Mistral, poi NVIDIA (se c'è la chiave), poi Qwen su Groq."""

    def __init__(self):
        super().__init__(
            mistral(config.MISTRAL_MODEL),
            nvidia(config.NVIDIA_MODEL),
            groq(config.GROQ_FALLBACK_MODEL),
        )
