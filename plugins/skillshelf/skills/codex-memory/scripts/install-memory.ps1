param([switch]$Execute)
$argsList = @("install")
if ($Execute) { $argsList += "--execute" }
& node (Join-Path $PSScriptRoot "installer.mjs") @argsList
exit $LASTEXITCODE
