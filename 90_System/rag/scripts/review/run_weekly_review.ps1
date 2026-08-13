<#
run_weekly_review.ps1 - run the weekly review generator (called by Task Scheduler)
Position-independent: derives the vault root from this script's own location.
Exit code: 0 on success, non-zero on failure.
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = $PSScriptRoot
$VaultRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir)))
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) {
    Write-Host "python not found" -ForegroundColor Red
    exit 1
}
Push-Location $VaultRoot
try {
    & $Py "90_System\rag\scripts\review\weekly_review.py"
    exit $LASTEXITCODE
} finally {
    Pop-Location
}