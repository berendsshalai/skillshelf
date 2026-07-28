param([Parameter(Mandatory=$true)][string]$InputFile, [string]$DataDir, [switch]$Force)
$argsList = @("import", "--input", $InputFile)
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
if ($Force) { $argsList += "--force" }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
