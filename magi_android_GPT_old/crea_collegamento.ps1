$root = "C:\Users\aless\Documents\Bots\MAGI-OS"
$pyw  = "C:\Users\aless\Documents\Bots\MAGI-OS\venv\scripts\pythonw.exe"   # senza venv: output di "where pythonw"
$icon = "$root\magi.ico"
$dir  = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

$ws = New-Object -ComObject WScript.Shell
$s  = $ws.CreateShortcut("$dir\MAGI-OS.lnk")
$s.TargetPath       = $pyw
$s.Arguments        = "main.py"
$s.WorkingDirectory = $root
$s.IconLocation     = $icon
$s.Description      = "MAGI-OS"
$s.Save()