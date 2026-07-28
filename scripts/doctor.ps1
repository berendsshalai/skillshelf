param([ValidateSet('Project','User')][string]$Scope = 'Project',[string]$TargetRoot)
$ErrorActionPreference = 'Stop'
if (-not $TargetRoot) { $TargetRoot = if ($Scope -eq 'User') { Join-Path $env:USERPROFILE '.agents\skills' } else { Join-Path (Get-Location) '.agents\skills' } }
$names = @('find-skills-codex','superpowers-codex','codex-memory','codex-design-intelligence','codex-skill-governor')
$missing = @($names | Where-Object { -not (Test-Path -LiteralPath (Join-Path $TargetRoot "$_\SKILL.md")) })
if ($missing.Count) { Write-Error ("Missing SkillShelf skills: " + ($missing -join ', ')); exit 1 }
Write-Output "Doctor passed: exactly five expected SkillShelf skills are present at $TargetRoot"
