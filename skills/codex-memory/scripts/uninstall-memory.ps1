param([switch]$Execute)
$argsList = @("uninstall")
if ($Execute) { $argsList += "--execute" }
& node (Join-Path $PSScriptRoot "installer.mjs") @argsList
exit $LASTEXITCODE
