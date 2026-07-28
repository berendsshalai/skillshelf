param([Parameter(Mandatory=$true)][string]$InputFile, [Parameter(Mandatory=$true)][string]$Output)
& node (Join-Path $PSScriptRoot "memory-admin.mjs") redact --input $InputFile --output $Output
exit $LASTEXITCODE
