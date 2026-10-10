# Unisce la versione desktop e la repo Android (magi_android_GPT) in un'unica cartella.
# Esegui DALLA cartella desktop (quella che contiene magi_android_GPT).
#
#   Simulazione (non tocca nulla):
#     powershell -ExecutionPolicy Bypass -File .\merge_desktop.ps1
#   Applica davvero (prima fa il backup):
#     powershell -ExecutionPolicy Bypass -File .\merge_desktop.ps1 -Apply
#
# Copia nella repo SOLO i file che li' non esistono: non sovrascrive nulla.

param([switch]$Apply)

$root = (Get-Location).Path
$repo = Join-Path $root "magi_android_GPT"

if (-not (Test-Path $repo)) {
    throw "Non trovo magi_android_GPT in $root. Esegui lo script dalla cartella desktop."
}

$skipDirs = @("magi_android_GPT", "venv", ".venv", "__pycache__", ".git", "data", ".buildozer", "bin")
$skipFiles = @("main.py", "keys.env", ".env", "crash.log", "*.pyc")

if ($Apply) {
    $backup = "$root" + "_backup_" + (Get-Date -Format "yyyyMMdd_HHmm")
    Write-Host "Backup in $backup ..."
    robocopy $root $backup /E /XD venv .venv __pycache__ .buildozer bin /NFL /NDL /NJH /NJS | Out-Null
}

# /XC /XN /XO = salta i file gia' presenti (uguali, piu' nuovi o piu' vecchi): copia solo i nuovi
$flags = @("/E", "/XC", "/XN", "/XO", "/NJH", "/NJS")
if (-not $Apply) { $flags += "/L" ; Write-Host "SIMULAZIONE: elenco di cio' che verrebbe copiato" }

robocopy $root $repo @flags /XD @skipDirs /XF @skipFiles

if (-not $Apply) {
    Write-Host ""
    Write-Host "Se l'elenco e' giusto (ui\gui.py, ui\boot.py, ui\fonts.py, ui\magi_map.py, discord_magi.py, assets...), rilancia con -Apply"
    exit 0
}

# main.py desktop -> run_desktop.py (main.py della repo e' il wrapper OTA)
$deskMain = Join-Path $root "main.py"
$runDesk = Join-Path $repo "run_desktop.py"
if ((Test-Path $deskMain) -and -not (Test-Path $runDesk)) {
    Copy-Item $deskMain $runDesk
    Write-Host "Creato run_desktop.py (copia del main.py desktop)"
} elseif (-not (Test-Path $deskMain)) {
    Write-Host "ATTENZIONE: nessun main.py nella cartella desktop: copia a mano il file di avvio come run_desktop.py"
}

$utf8 = New-Object System.Text.UTF8Encoding $false

# core/memory.py: sul desktop salva sempre nella cartella della repo
$mem = Join-Path $repo "core\memory.py"
if (Test-Path $mem) {
    $s = [IO.File]::ReadAllText($mem)
    $old = 'return Path(private) if private else Path(".")'
    $new = 'return Path(private) if private else Path(__file__).resolve().parent.parent'
    if ($s.Contains($old)) {
        [IO.File]::WriteAllText($mem, $s.Replace($old, $new), $utf8)
        Write-Host "core\memory.py aggiornato"
    } else {
        Write-Host "core\memory.py: riga non trovata, nessuna modifica"
    }
}

# buildozer.spec: niente file desktop nell'APK
$spec = Join-Path $repo "buildozer.spec"
if (Test-Path $spec) {
    $s = [IO.File]::ReadAllText($spec)
    $extra = ",ui/gui.py,ui/boot.py,ui/fonts.py,ui/magi_map.py,ui/nerv.py,discord_magi.py,run_desktop.py"
    if (($s -match "(?m)^source\.exclude_patterns\s*=") -and -not $s.Contains("ui/gui.py")) {
        $s = [regex]::Replace($s, "(?m)^(source\.exclude_patterns\s*=.*?)\s*$", ('$1' + $extra))
        [IO.File]::WriteAllText($spec, $s, $utf8)
        Write-Host "buildozer.spec aggiornato"
    } else {
        Write-Host "buildozer.spec: gia' a posto o riga non trovata"
    }
}

Write-Host ""
Write-Host "Fatto. Prova il desktop:"
Write-Host "  cd $repo"
Write-Host "  pip install requests python-dotenv rich"
Write-Host "  python run_desktop.py"
Write-Host "Ricorda: version.txt a 2 solo quando il desktop funziona. Dati storici: copia a mano data\decisions.json."
