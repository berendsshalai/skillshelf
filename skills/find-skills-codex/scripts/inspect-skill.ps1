param(
  [Parameter(Mandatory)][string]$Path,
  [Parameter(Mandatory)][string]$Repository,
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit
)
$ErrorActionPreference = 'Stop'
python (Join-Path $PSScriptRoot 'inspect_skill.py') $Path --repository $Repository --commit $Commit
