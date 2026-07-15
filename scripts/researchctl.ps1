[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Exe = Join-Path $Root '.venv\Scripts\researchctl.exe'
if (-not (Test-Path $Exe)) {
    throw 'researchctl is not installed. Run scripts\bootstrap.ps1 first.'
}
& $Exe @Arguments
exit $LASTEXITCODE
