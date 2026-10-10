"""Provider generico per le API in formato OpenAI + costruttori pronti."""

import os

import config
from providers._http import openai_chat

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


class OpenAICompatProvider:

    def __init__(self, name, url, key_env, model, **extra):
        self.name = name
        self.url = url
        self.key_env = key_env
        self.model = model
        self.extra = extra

    @property
    def label(self):
        return f"{self.name}:{self.model}"

    async def ask(self, role, system, prompt):
        try:
            return await openai_chat(
                self.url,
                os.getenv(self.key_env),
                self.model,
                system,
                prompt,
                **self.extra,
            )
        except Exception as e:
            raise RuntimeError(f"{self.label}: {e}") from None


def groq(model):
    extra = {
        "temperature": config.TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model and getattr(config, "GROQ_REASONING", None):
        extra["reasoning_effort"] = config.GROQ_REASONING
    return OpenAICompatProvider("groq", GROQ_URL, "GROQ_API_KEY", model, **extra)


def mistral(model):
    return OpenAICompatProvider(
        "mistral", MISTRAL_URL, "MISTRAL_API_KEY", model,
        temperature=config.TEMPERATURE,
        response_format={"type": "json_object"},
    )


def nvidia(model):
    # niente response_format: non tutti i modelli NIM lo supportano
    return OpenAICompatProvider(
        "nvidia", NVIDIA_URL, "NVIDIA_API_KEY", model,
        temperature=config.TEMPERATURE,
    )
