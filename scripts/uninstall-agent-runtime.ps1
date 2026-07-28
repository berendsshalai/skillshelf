[CmdletBinding()]
param([switch]$Execute)
$Root = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $Root "sdk/python/.venv"
if (-not $Execute) { Write-Host "Dry run: would remove $Target"; exit 0 }
$Resolved = (Resolve-Path -LiteralPath $Target).Path
if (-not $Resolved.StartsWith((Resolve-Path -LiteralPath $Root).Path)) { throw "Unsafe target" }
Remove-Item -LiteralPath $Resolved -Recurse -Force
Write-Host "Removed isolated runtime only; local state and Codex configuration were preserved."
