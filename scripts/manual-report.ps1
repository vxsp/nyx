$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'main.py') report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
