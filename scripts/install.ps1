[CmdletBinding(SupportsShouldProcess)]
param(
  [ValidateSet('Project','User')][string]$Scope = 'Project',
  [string]$TargetRoot
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$names = @('find-skills-codex','superpowers-codex','codex-memory','codex-design-intelligence','codex-skill-governor')
if (-not $TargetRoot) {
  $TargetRoot = if ($Scope -eq 'User') { Join-Path $env:USERPROFILE '.agents\skills' } else { Join-Path (Get-Location) '.agents\skills' }
}
$target = [IO.Path]::GetFullPath($TargetRoot)
New-Item -ItemType Directory -Path $target -Force | Out-Null
$backupRoot = Join-Path $target ('.skillshelf-backup-' + (Get-Date -Format 'yyyyMMddHHmmss'))
foreach ($name in $names) {
  $source = Join-Path $repo "skills\$name"
  $dest = Join-Path $target $name
  if (Test-Path -LiteralPath $dest) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Copy-Item -LiteralPath $dest -Destination (Join-Path $backupRoot $name) -Recurse -Force
  }
  if ($PSCmdlet.ShouldProcess($dest, "Install SkillShelf skill")) {
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
    Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
  }
}
Write-Output "Installed five SkillShelf skills in $target"
if (Test-Path -LiteralPath $backupRoot) { Write-Output "Backup: $backupRoot" }
