$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path '.venv\Scripts\python.exe')) { py -3 -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if (-not (Test-Path 'config\.env')) { Copy-Item 'config\.env.example' 'config\.env'; Write-Host 'Next: edit config\.env with your Navidrome login.' }
