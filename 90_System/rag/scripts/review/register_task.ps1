<#
register_task.ps1 - register/update the "Knowledge OS Weekly Review" scheduled task (idempotent)

Reads the weekly_review section from 90_System/rag/config.yaml:
  enabled / weekday / time
Default: every Friday 18:00.

Usage: powershell -NoProfile -ExecutionPolicy Bypass -File register_task.ps1
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = $PSScriptRoot
$VaultRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir)))
$ConfigPath = Join-Path $VaultRoot "90_System\rag\config.yaml"

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python not found" }
$pyCode = "import yaml,json,sys; d=yaml.safe_load(open(sys.argv[1],encoding='utf-8')); wr=d.get('weekly_review',{}); print(json.dumps(wr))"
$raw = & $py -c $pyCode $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "config parse failed" }
$wr = $raw | ConvertFrom-Json
if (-not $wr.enabled) {
    Write-Host "weekly_review.enabled = false, skip registration."
    exit 0
}

$validDays = @('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')
$dayName = $wr.weekday.Substring(0,1).ToUpper() + $wr.weekday.Substring(1).ToLower()
if ($validDays -notcontains $dayName) { throw "invalid weekday: $($wr.weekday)" }

$taskName = 'Knowledge OS Weekly Review'
$psExe = (Get-Command powershell -ErrorAction SilentlyContinue).Source
if (-not $psExe) { $psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" }
$wrapper = Join-Path $ScriptDir "run_weekly_review.ps1"
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$wrapper`""

$action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $VaultRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dayName -At ([string]$wr.time)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

$t = Get-ScheduledTask -TaskName $taskName
Write-Host "Registered scheduled task: $taskName"
Write-Host ("  State: " + $t.State)
$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host ("  Next run: " + $info.NextRunTime)