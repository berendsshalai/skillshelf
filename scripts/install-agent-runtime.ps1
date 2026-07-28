[CmdletBinding()]
param([string]$InstallRoot)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Sdk = Join-Path $Root "sdk/python"
$Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA "SkillShelf\runtime\$Version" }
$Venv = Join-Path $InstallRoot "venv"
$Python = Get-Command python -ErrorAction Stop
& $Python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)"
if ($LASTEXITCODE -ne 0) { throw "SkillShelf requires Python 3.11 or newer" }
$Expected = ((Get-Content -LiteralPath (Join-Path $Sdk "requirements.lock.sha256") -Raw).Split()[0]).ToLowerInvariant()
$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Sdk "requirements.lock")).Hash.ToLowerInvariant()
if ($Expected -ne $Actual) { throw "Dependency lock integrity verification failed" }
if (-not (Test-Path -LiteralPath $Venv)) { & $Python.Source -m venv $Venv }
$RuntimePython = Join-Path $Venv "Scripts/python.exe"
& $RuntimePython -m pip install --disable-pip-version-check -r (Join-Path $Sdk "requirements.lock")
$WheelRoot = Join-Path ([System.IO.Path]::GetTempPath()) "skillshelf-wheel-$PID"
New-Item -ItemType Directory -Path $WheelRoot -Force | Out-Null
try {
    & $RuntimePython -m pip wheel --disable-pip-version-check --no-deps --wheel-dir $WheelRoot $Sdk
    $Wheel = Get-ChildItem -LiteralPath $WheelRoot -Filter "skillshelf_agents-$Version-*.whl" | Select-Object -First 1
    if (-not $Wheel) { throw "SkillShelf wheel build failed" }
    & $RuntimePython -m pip install --disable-pip-version-check --no-deps --force-reinstall $Wheel.FullName
} finally {
    if ((Resolve-Path -LiteralPath $WheelRoot).Path.StartsWith([System.IO.Path]::GetTempPath())) {
        Remove-Item -LiteralPath $WheelRoot -Recurse -Force
    }
}
& $RuntimePython (Join-Path $Root "scripts/generate-agents.py") --profile runtime
& $RuntimePython (Join-Path $Root "scripts/validate-agents.py")
& $RuntimePython (Join-Path $Root "scripts/run-agent-smoke-tests.py")
& (Join-Path $Venv "Scripts/skillshelf.exe") doctor --deep
Write-Host "Installed without model calls, API-token use, reviews, or engagement actions."
Write-Host "& '$($Venv)\Scripts\skillshelf.exe' doctor"
