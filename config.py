DEBUG = False
DELIBERATION = True

# Salta il round 2 se i core sono tutti d'accordo e tutti sicuri
# (risparmia ~4 chiamate e quota gratuita sui casi facili)
SKIP_ROUND2_IF_UNANIMOUS = True
UNANIMOUS_MIN_CONFIDENCE = 85

# ---------------------------------------------------------------
# MODELLI: cambiare modello = cambiare una riga qui.
# Verifica sempre gli ID: i free tier cambiano spesso.
# ---------------------------------------------------------------
GEMINI_MODEL = "gemini-3.1-flash-lite"   # prova anche gemini-3.5-flash se è free per te

GROQ_MODEL = "openai/gpt-oss-120b"       # Balthasar
GROQ_REASONING = "low"                   # low | medium | high (solo gpt-oss). "low" risparmia TPM
GROQ_FALLBACK_MODEL = "qwen/qwen3.8-27b"

MISTRAL_MODEL = "mistral-medium-latest"  # Casper (o mistral-large-latest)

# Riserva opzionale: serve NVIDIA_API_KEY in keys.env, altrimenti viene saltata
NVIDIA_MODEL = "openai/gpt-oss-20b"      # controlla l'ID su build.nvidia.com

# Non impostata per Gemini 3: Google consiglia il valore di default
TEMPERATURE = 0.3
