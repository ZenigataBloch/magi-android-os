import config
from providers.chain import FallbackProvider
from providers.openai_compat import groq, nvidia


class GroqProvider(FallbackProvider):
    """Balthasar: gpt-oss-120b su Groq, poi NVIDIA (se c'è la chiave), poi Qwen."""

    def __init__(self):
        super().__init__(
            groq(config.GROQ_MODEL),
            nvidia(config.NVIDIA_MODEL),
            groq(config.GROQ_FALLBACK_MODEL),
        )
