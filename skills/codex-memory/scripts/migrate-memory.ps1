param([Parameter(Mandatory=$true)][string]$From, [string]$DataDir, [switch]$Force)
$argsList = @("migrate", "--from", $From)
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
if ($Force) { $argsList += "--force" }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
