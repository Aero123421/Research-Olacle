[CmdletBinding()]
param(
    [switch]$Initialize,
    [string]$Answers,
    [switch]$WithData,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

function Find-Python {
    $candidates = @(
        @{ Command = 'py'; Args = @('-3.13') },
        @{ Command = 'py'; Args = @('-3.12') },
        @{ Command = 'py'; Args = @('-3.11') },
        @{ Command = 'python'; Args = @() },
        @{ Command = 'python3'; Args = @() }
    )
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
            try {
                $version = & $candidate.Command @($candidate.Args) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                $parts = $version.Trim().Split('.')
                if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11)) {
                    return $candidate
                }
            } catch { }
        }
    }
    throw 'Python 3.11 or later was not found. Install it from python.org and rerun this script.'
}

$Python = Find-Python
$Venv = Join-Path $Root '.venv'
if (-not (Test-Path $Venv)) {
    Write-Host 'Creating local Python environment...' -ForegroundColor Cyan
    & $Python.Command @($Python.Args) -m venv $Venv
}

$VenvPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment Python not found at $VenvPython"
}

Write-Host 'Installing Codex Research Harness locally...' -ForegroundColor Cyan
& $VenvPython -m pip install --disable-pip-version-check -e .
if ($WithData) {
    Write-Host 'Installing optional data-science dependencies...' -ForegroundColor Cyan
    & $VenvPython -m pip install -e '.[data]'
}

$ResearchCtl = Join-Path $Venv 'Scripts\researchctl.exe'
if (-not (Test-Path $ResearchCtl)) {
    throw 'researchctl entry point was not created.'
}

if ($Initialize) {
    $initArgs = @('init')
    if ($Answers) { $initArgs += @('--answers', $Answers) }
    & $ResearchCtl @initArgs
}

Write-Host 'Running quick readiness checks...' -ForegroundColor Cyan
& $ResearchCtl doctor --profile quick
$DoctorExit = $LASTEXITCODE
if ($DoctorExit -eq 2) {
    Write-Warning 'Quick Doctor found blocking setup issues. Read the readiness path printed above.'
}

if (-not $SkipTests) {
    Write-Host 'Running structural tests...' -ForegroundColor Cyan
    & $VenvPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $ResearchCtl self-test
    if ($LASTEXITCODE -ne 0) { throw 'researchctl self-test failed.' }
}

Write-Host ''
Write-Host 'Codex Research Harness is installed.' -ForegroundColor Green
Write-Host "Open this folder in Codex: $Root"
Write-Host 'Then ask Codex to follow AGENTS.md and BOOTSTRAP.md.'
exit $DoctorExit
