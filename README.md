# MAGI-OS (Android)

Sistema di supporto alle decisioni ispirato ai MAGI di *Neon Genesis Evangelion*, per Android. Fai una domanda o proponi delle opzioni: tre "nuclei" (MELCHIOR, BALTHASAR, CASPER), ognuno con una personalità diversa e un modello linguistico diverso, votano, si sfidano e producono un verdetto.

> **Fan project senza scopo di lucro.** Nomi, estetica e riferimenti a MAGI e NERV appartengono ai rispettivi titolari. Il progetto non è affiliato né approvato da loro.

---

## Come funziona

1. **Opzioni.** Dalla tua richiesta vengono estratte da 2 a 5 opzioni: quelle che hai scritto ("pizza o sushi?"), SI/NO per le domande chiuse, oppure tre candidati proposti dal sistema per le domande aperte.
2. **Round 1.** I tre core votano in modo indipendente, con una confidenza da 0 a 100 e una motivazione.
   - **MELCHIOR**: logico. Criteri misurabili, fattibilità, rischi operativi.
   - **BALTHASAR**: pragmatico. Utilità pratica, impatto sulle persone, compromessi.
   - **CASPER**: critico e intuitivo. Cerca il punto debole dell'opzione più ovvia.
3. **Round 2.** Un core a rotazione fa l'*avvocato del diavolo* contro l'opzione in testa. Poi tutti rivedono il voto: lo confermano o lo cambiano solo se convinti.
4. **Verdetto.** Serve il quorum di almeno due core validi. Il risultato è `APPROVED`, `DENIED` o `DEADLOCK` (parità senza scarto netto di confidenza).

---

## Funzioni

### Presenti
- Tre core su tre provider (Gemini, Groq, Mistral), con ripiego automatico per CASPER
- Estrazione automatica delle opzioni, con rete di sicurezza se il provider non risponde
- Votazione con confidenza, quorum, spareggio e consenso
- Deliberazione in due round con avvocato del diavolo a rotazione
- Interfaccia in stile NERV: mappa dei MAGI, barre di sincronizzazione e consenso, matrice dei voti, log da terminale
- Schermata di avvio animata (si salta con un tocco)
- Archivio **記録** con filtro, elenco e dettaglio di ogni decisione (richiesta, verdetto, tally, obiezione, matrice dei voti)
- Salvataggio dello storico nella cartella privata dell'app
- Aggiornamento del codice al volo da GitHub (vedi [Aggiornamenti](#aggiornamenti))
- Schermata di errore con traceback copiabile

### Appena aggiunte, in fase di prova
- Input bloccato mentre i MAGI analizzano
- **Sessione continua:** i core ricordano i turni precedenti ("non ho le lenticchie, cosa proponete?") fino al pulsante **新規** (nuova sessione)
- Compilazione dell'APK su GitHub Actions

### In programma
- Schermata nell'app per inserire le proprie chiavi API
- Possibilità di usare una sola chiave per tutti e tre i core
- Archivio raggruppato per sessione e indicatore del turno
- Orientamento orizzontale con layout a due colonne (pensato per tablet)
- Modelli e provider configurabili da `config.py`
- Build di release firmata, più adatta alla distribuzione
- Sostituzione dei font non liberi con alternative libere

### Idee
- Versione "sicura" per limitare gli avvisi di Play Protect (firma stabile, permessi minimi, aggiornamenti solo tramite nuovo APK)
- Pubblicazione tramite canali ufficiali

---

## Installazione

1. Dal telefono apri la pagina **Releases** di questo repository e scarica l'APK più recente (`APK più recente`).
2. Aprilo. Android chiederà di consentire l'installazione da questa origine per il browser che hai usato: accetta.
3. Se compare un avviso di Play Protect ("app non verificata"), è perché l'APK è di debug e non passa dal Play Store. Puoi scegliere *Installa comunque*.
4. Inserisci le tue chiavi API (sezione seguente).

L'APK pubblicato qui **non contiene nessuna chiave**.

---

## Chiavi API

Servono tre chiavi, una per servizio. I piani gratuiti bastano per provare l'app, ma i limiti e le condizioni d'uso cambiano: controllali sui rispettivi siti.

| Variabile | Dove crearla |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio (aistudio.google.com/apikey) |
| `GROQ_API_KEY` | Groq Console (console.groq.com/keys) |
| `MISTRAL_API_KEY` | Mistral Console (console.mistral.ai/api-keys) |

Le richieste vengono inviate ai tre servizi, quindi valgono le loro politiche sui dati. Lo storico delle decisioni resta solo sul tuo telefono.

### Dove mettere le chiavi (per ora)

Crea un file `keys.env`:

```
GEMINI_API_KEY=...
GROQ_API_KEY=...
MISTRAL_API_KEY=...
```

Poi, con il debug USB attivo e `adb` sul PC, dopo aver aperto l'app almeno una volta:

```
adb shell mkdir -p /sdcard/Android/data/org.magi.magios/files
adb push keys.env /sdcard/Android/data/org.magi.magios/files/keys.env
```

Chiudi l'app dal multitasking e riaprila. Una schermata dentro l'app per inserirle senza PC è in programma.

**Non pubblicare mai `keys.env`.** È escluso dal repository tramite `.gitignore`.

---

## Aggiornamenti

L'app può scaricare da sola le nuove versioni del codice Python da questo repository:

- all'avvio usa il codice già scaricato e, in background, controlla `version.txt` su GitHub;
- se il numero è più alto, scarica e controlla il nuovo codice, che parte alla **riapertura successiva** (chiudi l'app dal multitasking);
- se il nuovo codice va in errore, viene scartato e si torna a quello dell'APK.

Non si aggiornano così `main.py`, `buildozer.spec`, le librerie, l'icona e il presplash: per quelli serve un nuovo APK.

Per chi sviluppa: dopo ogni modifica porta `version.txt` al numero successivo, poi `git commit` e `git push`.

---

## Sviluppo

### Struttura

```
main.py            avvio, schermata di errore, aggiornamento al volo
app_main.py        punto d'ingresso dell'app
config.py          opzioni (DEBUG, DELIBERATION)
agents/            i tre core e il prompt di base
providers/         client HTTP per Gemini, Groq, Mistral
core/              controller, opzioni, votazione, deliberazione, sessione, archivio
ui/                interfaccia Kivy (mobile, mappa, widget, archivio, avvio)
fonts/             font dell'interfaccia
version.txt        versione del codice (per l'aggiornamento al volo)
buildozer.spec     configurazione della build Android
```

### Prova su PC

```
pip install kivy requests python-dotenv pillow
python main.py
```

Con un file `keys.env` nella cartella del progetto.

### Compilare l'APK

**Su GitHub:** il workflow `.github/workflows/build-apk.yml` compila l'APK quando cambiano `main.py` o `buildozer.spec`, oppure a mano da *Actions → Build APK → Run workflow*, e lo pubblica in *Releases*. Il secret `DEBUG_KEYSTORE_B64` (il keystore di debug in base64) permette di aggiornare l'app senza disinstallarla.

**In locale (Linux):**

```
pip install buildozer cython
buildozer -v android debug
```

L'APK compare in `bin/`.

---

## Limiti noti

- L'APK è di debug: Android e Play Protect possono segnalarlo.
- L'orientamento è solo verticale.
- Il layout è tarato su schermi di circa 800 dp di altezza.
- Se un provider è irraggiungibile o ha esaurito la quota, il core corrispondente risulta in errore. Con meno di due core validi non c'è quorum e il verdetto è `DEADLOCK`.
