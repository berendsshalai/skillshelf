[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Sdk = Join-Path $Root "sdk/python"
$Venv = Join-Path $Sdk ".venv"
$Python = Get-Command python -ErrorAction Stop
if (-not (Test-Path -LiteralPath $Venv)) { & $Python.Source -m venv $Venv }
$RuntimePython = Join-Path $Venv "Scripts/python.exe"
& $RuntimePython -m pip install --disable-pip-version-check -r (Join-Path $Sdk "requirements.lock")
& $RuntimePython -m pip install --disable-pip-version-check --no-deps -e $Sdk
& $RuntimePython (Join-Path $Root "scripts/generate-agents.py")
& $RuntimePython (Join-Path $Root "scripts/validate-agents.py")
& $RuntimePython (Join-Path $Root "scripts/run-agent-smoke-tests.py")
Write-Host "Installed without model calls, API-token use, reviews, or engagement actions."
Write-Host "& '$($Venv)\Scripts\skillshelf.exe' doctor"
