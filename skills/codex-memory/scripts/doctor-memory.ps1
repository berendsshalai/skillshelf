param([string]$DataDir)
$argsList = @("doctor")
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
