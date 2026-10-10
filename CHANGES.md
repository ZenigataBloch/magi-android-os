# Patch MAGI-OS (10 ott 2026)

File completi da sovrascrivere (stessa struttura del progetto):
  config.py, agents/base.py, core/controller.py,
  providers/_http.py, providers/groq.py, providers/mistral.py, providers/gemini.py
File nuovi:
  providers/openai_compat.py, providers/chain.py

Due modifiche manuali (poche righe):

1) core/options.py  -> l'estrattore passa a Gemini (libera quota Groq)
   -    from providers.groq import GroqProvider
   +    from providers.gemini import GeminiProvider
   -    raw = await GroqProvider().ask(
   +    raw = await GeminiProvider().ask(

2) core/deliberation.py  -> confidenza normalizzata come nel round 1
   in cima:   from agents.base import BANNED, SYSTEM_TEMPLATE, _extract, _match_option, normalize_confidence
   in _revise, sostituire il blocco
        "confidence": max(0.0, min(100.0, float(data.get("confidence", 0)))),
   con
        "confidence": normalize_confidence(data.get("confidence", 0)),

Poi:
 - version.txt -> 2 (altrimenti l'aggiornamento OTA non scatta)
 - keys.env: NVIDIA_API_KEY=... è opzionale (senza, la riserva NVIDIA viene saltata)
 - modelli: tutto in config.py
