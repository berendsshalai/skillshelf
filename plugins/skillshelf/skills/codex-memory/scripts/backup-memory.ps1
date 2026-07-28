param([string]$DataDir, [string]$Output, [switch]$IncludeVector)
$argsList = @("backup")
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
if ($Output) { $argsList += @("--output", $Output) }
if ($IncludeVector) { $argsList += "--include-vector" }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
