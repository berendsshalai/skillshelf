[CmdletBinding(SupportsShouldProcess)]
param([ValidateSet('Project','User')][string]$Scope = 'Project',[string]$TargetRoot)
$ErrorActionPreference = 'Stop'
$names = @('find-skills-codex','superpowers-codex','codex-memory','codex-design-intelligence','codex-skill-governor')
if (-not $TargetRoot) { $TargetRoot = if ($Scope -eq 'User') { Join-Path $env:USERPROFILE '.agents\skills' } else { Join-Path (Get-Location) '.agents\skills' } }
$target = [IO.Path]::GetFullPath($TargetRoot)
foreach ($name in $names) {
  $dest = Join-Path $target $name
  if ((Test-Path -LiteralPath $dest) -and $PSCmdlet.ShouldProcess($dest, "Remove SkillShelf-owned skill")) {
    Remove-Item -LiteralPath $dest -Recurse -Force
  }
}
Write-Output "Removed SkillShelf-owned skills from $target; unrelated skills were preserved."
