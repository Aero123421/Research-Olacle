[CmdletBinding()]
param(
    [switch]$FullDoctor,
    [switch]$SkipLint
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$ResearchCtl = Join-Path $Root '.venv\Scripts\researchctl.exe'

if (-not (Test-Path $Python) -or -not (Test-Path $ResearchCtl)) {
    throw 'The local environment is missing. Run scripts\bootstrap.ps1 first.'
}

Push-Location $Root
try {
    Write-Host 'Compiling Python sources...' -ForegroundColor Cyan
    & $Python -m compileall -q src tests
    if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed.' }

    Write-Host 'Running unit and integration tests...' -ForegroundColor Cyan
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

    Write-Host 'Running structural repository checks...' -ForegroundColor Cyan
    & $ResearchCtl self-test
    if ($LASTEXITCODE -ne 0) { throw 'Structural self-test failed.' }

    if (-not $SkipLint) {
        $Ruff = Join-Path $Root '.venv\Scripts\ruff.exe'
        if (Test-Path $Ruff) {
            Write-Host 'Running Ruff...' -ForegroundColor Cyan
            & $Ruff check .
            if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed.' }
            & $Ruff format --check .
            if ($LASTEXITCODE -ne 0) { throw 'Ruff format check failed.' }
        } else {
            Write-Warning 'Ruff is not installed. Install .[dev] or rerun with -SkipLint.'
        }
    }

    $Profile = if ($FullDoctor) { 'full' } else { 'quick' }
    Write-Host "Running $Profile Doctor..." -ForegroundColor Cyan
    & $ResearchCtl doctor --profile $Profile
    $DoctorExit = $LASTEXITCODE
    if ($DoctorExit -eq 2) {
        throw 'Doctor found blocking readiness failures. Read research\setup\READINESS.md.'
    }

    Write-Host 'Verification completed successfully.' -ForegroundColor Green
    exit $DoctorExit
}
finally {
    Pop-Location
}
