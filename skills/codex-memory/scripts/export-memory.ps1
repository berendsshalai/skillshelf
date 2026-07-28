param([string]$DataDir, [Parameter(Mandatory=$true)][string]$Output)
$argsList = @("export", "--output", $Output)
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
