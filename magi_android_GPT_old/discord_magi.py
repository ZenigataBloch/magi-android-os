"""MAGI su Discord: bot privato, silenzioso, con log degli errori su file.

Comandi (solo per il proprietario):
  /magi richiesta:... [pubblica] [inglese]
                        sottopone una richiesta ai tre core. Con pubblica=Sì, dopo il
                        consenso manda nel canale RICHIESTA e RISULTATO in un unico
                        messaggio; con inglese=Sì li traduce prima di pubblicare
                        (se inglese è No o assente, nessuna traduzione)
  /storico quante:5     ultime decisioni salvate

Avvio silenzioso (Windows):  pythonw discord_magi.py
Errori e avvisi:             logs/magi_discord.log

Variabili nel .env:
  MAGI_DISCORD_TOKEN   token del bot (Developer Portal)
  DISCORD_OWNER_ID     il tuo ID utente Discord
  MAGI_GUILD_ID        (opzionale) ID del tuo server: i comandi compaiono subito
  MAGI_EPHEMERAL       (opzionale) "1" = risposte visibili solo a te (default)
  MAGI_AUTOCLOSE       (opzionale) secondi dopo cui sparisce il messaggio privato una
                       volta pubblicato (default 3; -1 = non chiuderlo mai)
"""

import asyncio
import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # .env e data/decisions.json usano percorsi relativi

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import discord
from discord import app_commands

from agents.base import _extract
from core.controller import run_magi
from core.magi import create_magi_agents
from core.memory import load_history, save_decision
from providers.groq import GroqProvider

# ---------------------------------------------------------------------------
# Log su file (con pythonw non esiste la console)
# ---------------------------------------------------------------------------

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

file_handler = RotatingFileHandler(
    LOG_DIR / "magi_discord.log",
    maxBytes=500_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)

log = logging.getLogger("magi.discord")
log.setLevel(logging.INFO)
log.addHandler(file_handler)

# console: attiva solo con python.exe; con pythonw non c'è e resta il file
if sys.stdout is not None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # niente errori con emoji/accenti

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    log.addHandler(console_handler)


def _excepthook(exc_type, exc, tb):
    log.critical("Eccezione non gestita", exc_info=(exc_type, exc, tb))


def _thread_excepthook(args):
    log.critical(
        "Eccezione non gestita nel thread %s",
        args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


sys.excepthook = _excepthook
threading.excepthook = _thread_excepthook

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

TOKEN = os.getenv("MAGI_DISCORD_TOKEN", "")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "0") or 0)
GUILD_ID = int(os.getenv("MAGI_GUILD_ID", "0") or 0)
EPHEMERAL = os.getenv("MAGI_EPHEMERAL", "1") == "1"
AUTOCLOSE = int(os.getenv("MAGI_AUTOCLOSE", "3") or 3)

TIMEOUT = 300  # secondi massimi per una richiesta

COLORS = {"APPROVED": 0x3FD17A, "DENIED": 0xE04040, "DEADLOCK": 0xFF8C00}


def _cut(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class OwnerTree(app_commands.CommandTree):
    """Albero dei comandi: risponde solo al proprietario."""

    async def interaction_check(self, interaction):
        if interaction.user.id == OWNER_ID:
            return True

        log.warning(
            "Accesso negato a %s (%s)", interaction.user, interaction.user.id
        )
        try:
            await interaction.response.send_message(
                "Non autorizzato.", ephemeral=True
            )
        except discord.HTTPException:
            pass
        return False

    async def on_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            return

        orig = getattr(error, "original", error)
        name = getattr(interaction.command, "name", "?")
        log.error("Errore nel comando /%s", name, exc_info=error)

        text = _cut(f"Errore: {type(orig).__name__}: {orig}", 1500)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            pass


class MagiBot(discord.Client):

    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = OwnerTree(self)
        self.lock = None

    async def setup_hook(self):
        self.lock = asyncio.Lock()

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Comandi sincronizzati sul server %s: %s", GUILD_ID,
                     ", ".join(c.name for c in synced))
        else:
            synced = await self.tree.sync()
            log.info("Comandi sincronizzati (globali): %s",
                     ", ".join(c.name for c in synced))

    async def on_ready(self):
        log.info("MAGI-OS avviato: online come %s (id %s)", self.user, self.user.id)

    async def on_error(self, event_method, *args, **kwargs):
        log.error("Errore in %s", event_method, exc_info=True)
        await self.notify_owner(
            f"Errore interno in `{event_method}`: vedi logs/magi_discord.log"
        )

    async def notify_owner(self, text):
        """Messaggio privato al proprietario (errori fuori dai comandi)."""
        try:
            user = await self.fetch_user(OWNER_ID)
            await user.send(_cut(text, 1900))
        except Exception:
            log.exception("Impossibile avvisare il proprietario")


bot = MagiBot()

# ---------------------------------------------------------------------------
# Avanzamento in diretta
# ---------------------------------------------------------------------------

class Progress:
    """Stato mostrato mentre i core lavorano (aggiornato sul thread del bot)."""

    def __init__(self):
        self.caption = "RICEZIONE"
        self.header = ""
        self.status = {}
        self.votes = {}
        self.dirty = True

    def set_status(self, name, status):
        self.status[name] = status
        self.dirty = True

    def on_event(self, kind, p):
        if kind == "options":
            self.caption = "ROUND 1"

        elif kind == "round":
            self.caption = f"ROUND {p['n']} \u00b7 avvocato: {p['advocate']}"

        elif kind in ("agent_result", "revision"):
            if p.get("carried"):
                return

            if not p.get("valid", True):
                self.votes[p["agent"]] = "ERRORE"
            elif p.get("changed"):
                self.votes[p["agent"]] = (
                    f"{p['previous']}\u2192{p['choice']}) {p['label']} "
                    f"{p['confidence']:.0f}%"
                )
            else:
                self.votes[p["agent"]] = (
                    f"{p['choice']}) {p['label']} {p['confidence']:.0f}%"
                )

        self.dirty = True

    def render(self):
        lines = [self.header] if self.header else []
        lines.append(f"**MAGI** \u00b7 {self.caption}")

        for name in ("MELCHIOR", "BALTHASAR", "CASPER"):
            line = f"`{name:<9}` {self.status.get(name, 'IN ATTESA')}"
            if name in self.votes:
                line += f" \u2192 {self.votes[name]}"
            lines.append(line)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

def build_embed(richiesta, result):
    d = result["decision"]
    verdict = d.get("verdict", "DEADLOCK")
    head = "DEADLOCK" if verdict == "DEADLOCK" else d.get("choice", "?")

    lines = [
        f"**{verdict}** \u00b7 voti {d.get('tally', '-')} "
        f"\u00b7 consenso {d.get('consensus', 0)}%"
    ]

    if d.get("rounds") == 2:
        r1 = d.get("round1", {})
        lines.append(
            f"Round 1: {r1.get('verdict')} ({r1.get('tally')}) \u2192 "
            f"Round 2: {verdict} ({d.get('tally')})"
        )
        if d.get("flips"):
            lines.append("Hanno cambiato voto: " + ", ".join(d["flips"]))

    if d.get("note"):
        lines.append(f"_{d['note']}_")

    embed = discord.Embed(
        title=_cut(f"MAGI \u00b7 {head}", 250),
        description="\n".join(lines),
        color=COLORS.get(verdict, 0xFF8C00),
    )
    embed.set_author(name=_cut(richiesta, 250))

    if d.get("objection"):
        embed.add_field(
            name=_cut(f"Obiezione \u00b7 {d.get('advocate', '?')}", 250),
            value=_cut(d["objection"], 1000),
            inline=False,
        )

    for r in result.get("responses", []):
        if r.get("valid", True):
            tag = " (voto round 1)" if r.get("carried") else ""
            name = (
                f"{r['agent']} \u00b7 {r['choice']}) {r['label']} "
                f"\u00b7 {r['confidence']:.0f}%{tag}"
            )
        else:
            name = f"{r['agent']} \u00b7 ERRORE"

        embed.add_field(
            name=_cut(name, 250),
            value=_cut(r.get("reasoning") or "\u2014", 1000),
            inline=False,
        )

    return embed


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------

_background = set()


def _spawn(coro):
    """Avvia una coroutine in background tenendone un riferimento."""
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _close_later(interaction, delay):
    """Elimina il messaggio privato (visibile solo all'utente) dopo qualche secondo."""
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        log.warning("Chiusura del messaggio privato non riuscita", exc_info=True)


async def consult(interaction, prompt, header=""):
    """Consulta i MAGI mostrando l'avanzamento sul messaggio originale.

    Da chiamare dopo defer() e con il lock preso. Restituisce il risultato,
    oppure None se c'è stato un errore (già comunicato all'utente).
    """
    log.info("Richiesta: %s", _cut(prompt, 300))

    loop = asyncio.get_running_loop()
    prog = Progress()
    prog.header = header

    # run_magi gira in un thread con un suo event loop: così le chiamate
    # bloccanti dei provider non fermano il bot. I callback tornano sul
    # loop del bot in modo sicuro.
    def on_status(name, status):
        loop.call_soon_threadsafe(prog.set_status, name, status)

    def on_event(kind, payload):
        loop.call_soon_threadsafe(prog.on_event, kind, payload)

    def worker():
        return asyncio.run(
            run_magi(
                prompt,
                create_magi_agents(),
                status_callback=on_status,
                event_callback=on_event,
            )
        )

    async def updater():
        while True:
            await asyncio.sleep(2)
            if prog.dirty:
                prog.dirty = False
                try:
                    await interaction.edit_original_response(
                        content=prog.render()
                    )
                except discord.HTTPException:
                    log.warning("Aggiornamento avanzamento non riuscito")

    task = asyncio.create_task(updater())

    try:
        result = await asyncio.wait_for(asyncio.to_thread(worker), TIMEOUT)

    except asyncio.TimeoutError:
        log.error("Timeout (%ss) su: %s", TIMEOUT, _cut(prompt, 300))
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await interaction.edit_original_response(
            content="Timeout: i core non hanno risposto in tempo."
        )
        return None

    except Exception:
        log.exception("Richiesta fallita: %s", _cut(prompt, 300))
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await interaction.edit_original_response(
            content="Errore durante l'analisi. Dettagli in logs/magi_discord.log."
        )
        return None

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    decision = result["decision"]

    # core in errore: finiscono nel log anche se il verdetto è valido
    for r in result.get("responses", []):
        if not r.get("valid", True):
            log.warning("%s offline: %s", r.get("agent"), r.get("reasoning"))

    try:
        save_decision(prompt, decision)
    except Exception:
        log.exception("Salvataggio della decisione non riuscito")

    log.info(
        "Verdetto: %s (%s) su: %s",
        decision.get("verdict"), decision.get("tally"), _cut(prompt, 300),
    )

    return result


@bot.tree.command(name="magi", description="Sottopone una richiesta ai tre core MAGI")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(
    richiesta="Domanda o opzioni, per esempio 'pizza o sushi'",
    pubblica="Dopo il consenso, pubblica nel canale richiesta e risultato in un unico messaggio",
    inglese="Con pubblica: traduce richiesta e risultato in inglese prima di pubblicare",
)
async def magi_cmd(
    interaction: discord.Interaction,
    richiesta: str,
    pubblica: bool = False,
    inglese: bool = False,
):

    if bot.lock.locked():
        await interaction.response.send_message(
            "MAGI è già al lavoro su un'altra richiesta.", ephemeral=True
        )
        return

    async with bot.lock:
        # con pubblica=True l'avanzamento resta privato: nel canale va
        # solo il risultato
        await interaction.response.defer(
            ephemeral=EPHEMERAL or pubblica, thinking=True
        )

        result = await consult(interaction, richiesta)
        if result is None:
            return

        decision = result["decision"]
        private_embed = build_embed(richiesta, result)

        if not pubblica:
            await interaction.edit_original_response(
                content=None, embed=private_embed
            )
            return

        # si pubblica solo con un consenso: mai in caso di deadlock
 #       if decision.get("verdict") == "DEADLOCK" or not decision.get("choice_id"):
 #           await interaction.edit_original_response(
 #               content="Nessun consenso (deadlock): nulla è stato pubblicato.",
#                embed=private_embed,
#            )
#            return

        tr = None

        if inglese:
            await interaction.edit_original_response(
                content="Consenso raggiunto: traduco in inglese...",
                embed=None,
            )
            try:
                tr = await asyncio.to_thread(_translate_result_sync, richiesta, result)
            except Exception:
                log.exception("Traduzione del risultato non riuscita")

            if not tr:
                await interaction.edit_original_response(
                    content=(
                        "Consenso raggiunto, ma la traduzione non è riuscita: "
                        "nulla è stato pubblicato."
                    ),
                    embed=private_embed,
                )
                return
        else:
            await interaction.edit_original_response(
                content="Consenso raggiunto: pubblico nel canale...", embed=None
            )

        # il messaggio originale è già stato modificato: il followup è un
        # messaggio nuovo, visibile a tutti nel canale
        published = False

        try:
            await interaction.followup.send(
                embed=build_public_embed(richiesta, result, tr),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            published = True
            status = "Consenso raggiunto: richiesta e risultato pubblicati nel canale."
        except discord.HTTPException:
            log.exception("Pubblicazione nel canale non riuscita")
            status = (
                "Consenso raggiunto, ma non sono riuscito a pubblicare nel "
                "canale. Dettagli in logs/magi_discord.log."
            )

        if published and AUTOCLOSE >= 0:
            # tutto è già nel messaggio pubblico: il privato si chiude da solo
            await interaction.edit_original_response(content=status, embed=None)
            _spawn(_close_later(interaction, AUTOCLOSE))
        else:
            # errori e deadlock: il messaggio privato resta, serve per leggerli
            await interaction.edit_original_response(
                content=status, embed=private_embed
            )


# ---------------------------------------------------------------------------
# Pubblicazione: richiesta + risultato in un unico messaggio, tradotti prima
# ---------------------------------------------------------------------------

TRANSLATE_PROMPT = """Traduci in inglese naturale tutti i valori testuali del JSON che ricevi.

REGOLE
- Mantieni invariate le chiavi e i nomi dei core (MELCHIOR, BALTHASAR, CASPER).
- Non aggiungere né togliere informazioni e non spiegare nulla.
- Lascia invariati numeri, emoji, URL, menzioni e nomi propri.

Rispondi SOLO con JSON valido, con la stessa struttura di quello ricevuto.
"""

TEXTS = {
    "en": {
        "question": "Question", "votes": "votes", "consensus": "consensus",
        "round1": "Round 1", "round2": "Round 2",
        "flips": "Changed their vote", "objection": "Objection",
        "r1vote": " (round 1 vote)",
    },
    "it": {
        "question": "Richiesta", "votes": "voti", "consensus": "consenso",
        "round1": "Round 1", "round2": "Round 2",
        "flips": "Hanno cambiato voto", "objection": "Obiezione",
        "r1vote": " (voto round 1)",
    },
}


def _payload(prompt, result):
    d = result["decision"]
    return {
        "prompt": prompt,
        "choice": d.get("choice", ""),
        "cores": {
            r["agent"]: {
                "label": r.get("label", ""),
                "reasoning": r.get("reasoning", ""),
            }
            for r in result.get("responses", [])
            if r.get("valid", True)
        },
        "objection": d.get("objection") or "",
    }


async def _translate_result(prompt, result):
    """Traduce in inglese richiesta e risultato. None se non riesce."""
    payload = json.dumps(_payload(prompt, result), ensure_ascii=False)

    for _ in range(2):
        try:
            raw = await GroqProvider().ask("Traduttore", TRANSLATE_PROMPT, payload)
            data = _extract(raw)

            if (
                data.get("prompt")
                and data.get("choice")
                and isinstance(data.get("cores"), dict)
            ):
                return data

        except Exception:
            log.warning("Traduzione fallita", exc_info=True)

    return None


def _translate_result_sync(prompt, result):
    # in un thread a parte: le chiamate bloccanti non fermano il bot
    return asyncio.run(_translate_result(prompt, result))


def build_public_embed(prompt, result, tr=None):
    """Messaggio da pubblicare: richiesta e risultato insieme, in un solo embed."""
    t = TEXTS["en" if tr else "it"]
    d = result["decision"]
    verdict = d.get("verdict", "APPROVED")
    cores_tr = (tr or {}).get("cores", {})
    choice = (tr or {}).get("choice") or d.get("choice", "?")
    shown_prompt = (tr or {}).get("prompt") or prompt

    quoted = "> " + _cut(shown_prompt, 800).replace("\n", "\n> ")

    lines = [
        f"**{t['question']}**",
        quoted,
        "",
        f"**{verdict}** \u00b7 {t['votes']} {d.get('tally', '-')} "
        f"\u00b7 {t['consensus']} {d.get('consensus', 0)}%",
    ]

    if d.get("rounds") == 2:
        r1 = d.get("round1", {})
        lines.append(
            f"{t['round1']}: {r1.get('verdict')} ({r1.get('tally')}) \u2192 "
            f"{t['round2']}: {verdict} ({d.get('tally')})"
        )
        if d.get("flips"):
            lines.append(f"{t['flips']}: " + ", ".join(d["flips"]))

    embed = discord.Embed(
        title=_cut(f"MAGI \u00b7 {str(choice).upper()}", 250),
        description="\n".join(lines),
        color=COLORS.get(verdict, 0xFF8C00),
    )

    objection = (tr or {}).get("objection") or d.get("objection")
    if objection:
        embed.add_field(
            name=_cut(f"{t['objection']} \u00b7 {d.get('advocate', '?')}", 250),
            value=_cut(objection, 700),
            inline=False,
        )

    for r in result.get("responses", []):
        if not r.get("valid", True):
            continue

        ct = cores_tr.get(r["agent"], {})
        label = ct.get("label") or r["label"]
        reasoning = ct.get("reasoning") or r.get("reasoning") or "\u2014"
        tag = t["r1vote"] if r.get("carried") else ""

        embed.add_field(
            name=_cut(
                f"{r['agent']} \u00b7 {r['choice']}) {label} "
                f"\u00b7 {r['confidence']:.0f}%{tag}",
                250,
            ),
            value=_cut(reasoning, 700),
            inline=False,
        )

    return embed


@bot.tree.command(name="storico", description="Ultime decisioni dei MAGI")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(quante="Quante mostrarne (1-10)")
async def storico_cmd(
    interaction: discord.Interaction,
    quante: app_commands.Range[int, 1, 10] = 5,
):
    try:
        history = load_history()[-quante:]
    except Exception:
        log.exception("Lettura dello storico non riuscita")
        await interaction.response.send_message(
            "Impossibile leggere lo storico.", ephemeral=True
        )
        return

    if not history:
        await interaction.response.send_message(
            "Nessuna decisione salvata.", ephemeral=True
        )
        return

    lines = [
        f"`{h.get('timestamp', '?')}` **{h.get('choice', '?')}** "
        f"({h.get('consensus', 0)}%) \u2014 {_cut(h.get('prompt', ''), 80)}"
        for h in reversed(history)
    ]

    await interaction.response.send_message(
        _cut("\n".join(lines), 1900), ephemeral=True
    )


# ---------------------------------------------------------------------------

if __name__ == "__main__":

    if not TOKEN or not OWNER_ID:
        log.error(
            "Mancano MAGI_DISCORD_TOKEN o DISCORD_OWNER_ID nel .env: uscita"
        )
        sys.exit(1)

    log.info("Avvio del bot MAGI-OS in corso...")

    # con pythonw non c'è stderr: i log di discord.py vanno sul file
    bot.run(TOKEN, log_handler=file_handler, log_level=logging.INFO)
