<#
register_review_preflight_task.ps1 - register/update the "Knowledge OS Review Preflight" scheduled task (idempotent)

Reads the review_preflight section from 90_System/rag/config.yaml:
  enabled / schedule_minutes
Default: every 30 minutes.

The scheduled task runs the standalone Review Preflight CLI so the LLM Review
Judge completes outside the Control Center page-load path.

Usage: powershell -NoProfile -ExecutionPolicy Bypass -File register_review_preflight_task.ps1
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = $PSScriptRoot
$VaultRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ConfigPath = Join-Path $VaultRoot "90_System\rag\config.yaml"

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python not found" }
$pyCode = "import yaml,json,sys; d=yaml.safe_load(open(sys.argv[1],encoding='utf-8')); print(json.dumps(d.get('review_preflight',{})))"
$raw = & $py -c $pyCode $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "config parse failed" }
$rp = $raw | ConvertFrom-Json
if (-not $rp.enabled) {
    Write-Host "review_preflight.enabled = false, skip registration."
    exit 0
}
$intervalMin = if ($rp.schedule_minutes) { [int]$rp.schedule_minutes } else { 30 }
if ($intervalMin -lt 1) { $intervalMin = 1 }

$taskName = 'Knowledge OS Review Preflight'
$cli = Join-Path $ScriptDir "review_preflight_cli.py"
$pyw = Join-Path (Split-Path -Parent $py) "pythonw.exe"
if (-not (Test-Path $pyw)) { throw "pythonw not found: $pyw" }
$arg = "`"$cli`" --once --trigger scheduled --governance"

$action = New-ScheduledTaskAction -Execute $pyw -Argument $arg -WorkingDirectory $VaultRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $intervalMin)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

$t = Get-ScheduledTask -TaskName $taskName
Write-Host "Registered scheduled task: $taskName (every $intervalMin min)"
Write-Host ("  State: " + $t.State)
$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host ("  Next run: " + $info.NextRunTime)


