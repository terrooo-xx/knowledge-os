<#
run_weekly_review.ps1 - run the weekly review pipeline (called by Task Scheduler)
Position-independent: derives the vault root from this script's own location.
Python resolution (deterministic): $env:KNOWLEDGE_OS_PYTHON -> py -3 launcher -> python on PATH.
Exit codes: 0 success, 1 success_with_warnings, 3 critical failure (propagated).
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = $PSScriptRoot
$VaultRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir)))

$Py = $env:KNOWLEDGE_OS_PYTHON
if (-not $Py) {
    $cand = & py -3 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $cand) { $Py = (($cand | Select-Object -Last 1) -as [string]).Trim() }
}
if (-not $Py) { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $Py) {
    Write-Host "python not found" -ForegroundColor Red
    exit 3
}
Write-Host ("using python: " + $Py)

Push-Location $VaultRoot
try {
    & $Py "90_System\rag\scripts\review\weekly_review.py" --insight
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
