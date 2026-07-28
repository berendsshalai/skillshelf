param([string]$InputFile, [string]$BackupDir, [string]$DataDir, [switch]$Force)
$argsList = @("recover")
if ($InputFile) { $argsList += @("--input", $InputFile) }
if ($BackupDir) { $argsList += @("--backup-dir", $BackupDir) }
if ($DataDir) { $argsList += @("--data-dir", $DataDir) }
if ($Force) { $argsList += "--force" }
& node (Join-Path $PSScriptRoot "memory-admin.mjs") @argsList
exit $LASTEXITCODE
