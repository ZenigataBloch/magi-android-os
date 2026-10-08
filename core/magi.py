from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.mistral import MistralProvider

from agents.melchior import Melchior
from agents.balthasar import Balthasar
from agents.casper import Casper


def create_magi_agents():
    return [
        Melchior("MELCHIOR", GeminiProvider()),
        Balthasar("BALTHASAR", GroqProvider()),
        Casper("CASPER", MistralProvider()),
    ]