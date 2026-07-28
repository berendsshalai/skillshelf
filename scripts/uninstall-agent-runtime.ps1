[CmdletBinding()]
param([switch]$Execute, [string]$InstallRoot)
$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA "SkillShelf\runtime\$Version" }
$Target = Join-Path $InstallRoot "venv"
if (-not $Execute) { Write-Host "Dry run: would remove $Target"; exit 0 }
if (-not (Test-Path -LiteralPath $Target)) { Write-Host "Runtime is already absent."; exit 0 }
$Resolved = (Resolve-Path -LiteralPath $Target).Path
if (-not $Resolved.StartsWith((Resolve-Path -LiteralPath $InstallRoot).Path)) { throw "Unsafe target" }
Remove-Item -LiteralPath $Resolved -Recurse -Force
Write-Host "Removed isolated runtime only; local state and Codex configuration were preserved."
