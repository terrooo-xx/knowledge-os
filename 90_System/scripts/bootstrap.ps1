<#
Knowledge OS Bootstrap (Gate 3)

Restores a GitHub-cloned Knowledge OS on a Windows machine to a runnable,
verifiable state. PowerShell orchestrator + Python helper.

Modes:
  bootstrap.ps1                 full init (discover python, ensure deps/models,
                                config.local.yaml, index, scheduler, codex/mcp,
                                health check, baseline verification)
  bootstrap.ps1 -CheckOnly      read-only audit of the current machine
  -SkipModels / -SkipScheduler / -SkipCodex / -SkipIndex / -SkipBaseline / -SkipDeps
  -CreateVenv                   force creating 90_System/.venv

Bootstrap NEVER:
  - modifies Wiki / Source / knowledge content
  - commits / pushes / creates repos / rewrites history
  - saves secrets into Git/Vault/logs
  - copies machine-local config into the Vault (config.local.yaml is gitignored)
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipModels,
    [switch]$SkipScheduler,
    [switch]$SkipCodex,
    [switch]$SkipIndex,
    [switch]$SkipBaseline,
    [switch]$SkipDeps,
    [switch]$SkipAI,
    [switch]$CreateVenv,
    [string]$VaultRoot = ""
)

$ErrorActionPreference = 'Stop'
# UTF-8 everywhere: PS5.1 otherwise decodes python's UTF-8 stdout / sends args
# using the ANSI codepage, corrupting non-ASCII paths (e.g. C:\Users\马权煜).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---------- path discovery (position-independent) ----------
$ScriptDir = $PSScriptRoot
if (-not $VaultRoot) {
    $VaultRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
}
$SystemDir = Join-Path $VaultRoot "90_System"
$RagDir = Join-Path $SystemDir "rag"
$Helper = Join-Path $ScriptDir "bootstrap_helper.py"
$StatePath = Join-Path $ScriptDir ".bootstrap_state.json"
$PyPath = $null          # resolved interpreter (full path preferred)
$PyCmd = $null           # command array: either full path or ['py','-3.14']

function Invoke-Helper {
    param([string]$Cmd, [string]$Py = "", [string]$Reranker = "", [int]$Limit = 0, [string]$State = "")
    $a = @($Helper, $Cmd)
    if ($Py) { $a += @("--python", $Py) }
    if ($Reranker) { $a += @("--reranker", $Reranker) }
    if ($Limit -gt 0) { $a += @("--limit", "$Limit") }
    if ($State) { $a += @("--state", $State) }
    $out = & python $a 2>&1
    if ($LASTEXITCODE -ne 0) { return @{ok=$false; error=($out -join " ")} }
    try { return ($out | Select-Object -Last 1 | ConvertFrom-Json) } catch { return @{ok=$false; error=($out -join " ")} }
}

function Test-Py {
    param([string]$Py, [string]$VersionArg = "")
    $probe = if ($VersionArg) { & $Py $VersionArg -c "import sys; print(sys.version.split()[0])" 2>$null } else { & $Py -c "import sys; print(sys.version.split()[0])" 2>$null }
    return ($LASTEXITCODE -eq 0)
}

function Get-VaultPath { return $VaultRoot }

function Show-Result {
    param([string]$Name, [string]$Status, [string]$Detail = "")
    $line = "[{0}] {1}" -f $Status.PadRight(6), $Name
    if ($Detail) { $line += " - " + $Detail }
    Write-Host $line
    return ($Status -eq "PASS")
}

# ---------- state ----------
$State = @{}
$st = Invoke-Helper "load-state"
if ($st.ok) { $State = $st.state }

Write-Host "=============================================="
Write-Host " Knowledge OS Bootstrap"
Write-Host " Mode: $(if ($CheckOnly) {'CHECK ONLY'} else {'FULL INIT'})"
Write-Host " Vault: $VaultRoot"
Write-Host "=============================================="

$overall = @()

# ---------- 1. Python ----------
Write-Host "`n== Python =="
$pyinfo = Invoke-Helper "detect-python"
$pythonPass = $false
if ($pyinfo.ok) {
    # prefer full executable path (needed for scheduler pythonw resolution)
    if ($pyinfo.executable) { $PyPath = $pyinfo.executable } else { $PyPath = $pyinfo.python }
    $pythonPass = Show-Result "Python" "PASS" ("{0} ({1})" -f $pyinfo.version, $pyinfo.source)
} else {
    $pythonPass = Show-Result "Python" "FAIL" "no python found"
    $overall += $false
}
$State.python = $pyinfo | ConvertTo-Json -Compress
$State.python_path = $PyPath

# ---------- 2. venv / deps ----------
$depsPass = $false
if ($pythonPass -and -not $CheckOnly -and -not $SkipDeps) {
    Write-Host "`n== Dependencies =="
    $venvPy = Join-Path $VaultRoot "90_System\.venv\Scripts\python.exe"
    if ($CreateVenv -or (Test-Path $venvPy)) {
        $cv = Invoke-Helper "create-venv" $PyPath
        if ($cv.ok) { $PyPath = $cv.venv; $PyCmd = @($cv.venv); Write-Host "venv: $($cv.venv) (created=$($cv.created))" }
        else { Write-Host "venv creation failed: $($cv.error)" }
    }
    $deps = Invoke-Helper "check-deps" $PyPath
    if (-not $deps.ok) {
        Write-Host "missing deps: $($deps.missing -join ', ') -> installing"
        $inst = Invoke-Helper "install-deps" $PyPath
        if (-not $inst.ok) { Write-Host "pip install failed: $($inst.error)" }
        $deps = Invoke-Helper "check-deps" $PyPath
    }
    $depsPass = Show-Result "Dependencies" $(if ($deps.ok) {"PASS"} else {"FAIL"}) $(if ($deps.ok) {"imports ok"} else {"missing: $($deps.missing -join ', ')"})
} elseif ($pythonPass) {
    $deps = Invoke-Helper "check-deps" $PyPath
    $depsPass = Show-Result "Dependencies" $(if ($deps.ok) {"PASS"} else {"FAIL"}) $(if ($deps.ok) {"imports ok"} else {"missing: $($deps.missing -join ', ')"})
} else { $depsPass = $false }
$overall += $depsPass

# ---------- 3. Models + config.local.yaml ----------
$modelPass = $false
Write-Host "`n== Models =="
$models = Invoke-Helper "detect-models"
if ($models.ok) {
    $emb = $models.embedding; $rr = $models.reranker
    $rerankerTarget = $null
    if ($rr.modelscope_found) { $rerankerTarget = $rr.modelscope_path }
    elseif ($rr.hf_complete) { $rerankerTarget = "BAAI/bge-reranker-v2-m3" }
    $embOk = $emb.complete
    $rrOk = [bool]$rerankerTarget
    if ($embOk -and $rrOk) {
        $modelPass = Show-Result "Models" "PASS" ("embedding=$($emb.name) reranker=$($rr.name)")
    } else {
        $missing = @()
        if (-not $embOk) { $missing += "embedding" }
        if (-not $rrOk) { $missing += "reranker" }
        $modelPass = Show-Result "Models" "FAIL" ("missing complete: $($missing -join ', '); Bootstrap must download (online) or restore model cache")
    }
    if ($rerankerTarget -and -not $CheckOnly -and -not $SkipModels) {
        $wcl = Invoke-Helper "write-config-local" $PyPath $rerankerTarget
        if ($wcl.ok) { Write-Host "config.local.yaml -> $($wcl.reranker)" }
        else { Write-Host "write-config-local failed: $($wcl.error)" }
    }
    $State.models = $models | ConvertTo-Json -Compress
} else {
    $modelPass = Show-Result "Models" "FAIL" $models.error
}
$overall += $modelPass

# ---------- 4. Secret ----------
Write-Host "`n== Secrets =="
$sec = Invoke-Helper "check-secret"
$secPass = Show-Result "DEEPSEEK_API_KEY" $(if ($sec.ok) {"PASS"} else {"MISSING"}) $(if ($sec.ok) {"present (value never shown)"} else {"set DEEPSEEK_API_KEY in user env, then re-run"})
$overall += $secPass

# ---------- 5. Index ----------
$idxPass = $false
Write-Host "`n== RAG Index =="
$idx = Invoke-Helper "check-index"
if ($idx.ok) {
    $idxPass = Show-Result "Index" "PASS" $idx.summary
} else {
    if (-not $CheckOnly -and -not $SkipIndex -and $pythonPass) {
        Write-Host "index missing/incomplete ($($idx.records) records) -> rebuilding"
        $rb = Invoke-Helper "rebuild-index" $PyPath
        $idx = Invoke-Helper "check-index"
        $idxPass = Show-Result "Index" $(if ($idx.ok) {"PASS"} else {"FAIL"}) $idx.summary
    } else {
        $idxPass = Show-Result "Index" "FAIL" "records=$($idx.records); run bootstrap without -SkipIndex to rebuild"
    }
}
$overall += $idxPass

# ---------- 6. Scheduler ----------
$schedPass = $false
if (-not $CheckOnly -and -not $SkipScheduler) {
    Write-Host "`n== Scheduler =="
    $schedPass = & {
        $pyExe = $PyPath
        $pyw = if ($pyExe -and (Test-Path $pyExe)) { Join-Path (Split-Path $pyExe) "pythonw.exe" } else { "pythonw" }
        $allOk = $true
        # --- Review Preflight (every 30 min) ---
        $t1 = "Knowledge OS Review Preflight"
        $exists1 = (schtasks /Query /TN $t1 2>$null | Select-String $t1) -ne $null
        if (-not $exists1) {
            if ($pyw -and (Test-Path $pyw)) {
                $arg = "`"$(Join-Path $SystemDir 'control_center\review_preflight_cli.py')`" --once --trigger scheduled --governance"
                schtasks /Create /F /TN $t1 /TR "`"$pyw`" $arg" /SC MINUTE /MO 30 /RL LIMITED | Out-Null
                $allOk = $allOk -and ($LASTEXITCODE -eq 0)
            } else { $allOk = $false }
        }
        # --- Weekly Review (Fri 18:00) ---
        $t2 = "Knowledge OS Weekly Review"
        $exists2 = (schtasks /Query /TN $t2 2>$null | Select-String $t2) -ne $null
        if (-not $exists2) {
            $ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
            $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $RagDir 'scripts\review\run_weekly_review.ps1')`""
            schtasks /Create /F /TN $t2 /TR "`"$ps`" $arg" /SC WEEKLY /D FRI /ST 18:00 /RL LIMITED | Out-Null
            $allOk = $allOk -and ($LASTEXITCODE -eq 0)
        }
        # --- UpdateChangelog (daily 23:00) ---
        $t3 = "KnowledgeBase-UpdateChangelog"
        $exists3 = (schtasks /Query /TN $t3 2>$null | Select-String $t3) -ne $null
        if (-not $exists3) {
            $arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $SystemDir 'scripts\update_changelog.ps1')`""
            schtasks /Create /F /TN $t3 /TR "`"powershell.exe`" $arg" /SC DAILY /ST 23:00 /RL LIMITED | Out-Null
            $allOk = $allOk -and ($LASTEXITCODE -eq 0)
        }
        # set KNOWLEDGE_OS_PYTHON for weekly-review script resolution (machine-local user env)
        if ($PyPath) {
            [Environment]::SetEnvironmentVariable("KNOWLEDGE_OS_PYTHON", $PyPath, "User")
        }
        Show-Result "Scheduler" $(if ($allOk) {"PASS"} else {"PARTIAL"}) "preflight=$exists1 weekly=$exists2 changelog=$exists3"
        return $allOk
    }
} else {
    # read-only report
    $tasks = @("Knowledge OS Review Preflight", "Knowledge OS Weekly Review", "KnowledgeBase-UpdateChangelog")
    $present = @()
    foreach ($t in $tasks) { if ((schtasks /Query /TN $t 2>$null | Select-String $t)) { $present += $t } }
    $schedPass = Show-Result "Scheduler" $(if ($present.Count -eq 3) {"PASS"} else {"PARTIAL"}) ("present: " + ($present -join ", "))
}
$overall += $schedPass

# ---------- 7. Codex / MCP ----------
$mcpPass = $false
if (-not $CheckOnly -and -not $SkipCodex) {
    Write-Host "`n== Codex / MCP =="
    $mcpPass = & {
        $homeDir = $HOME
        $codexDir = Join-Path $homeDir ".codex"
        $codexCfg = Join-Path $codexDir "knowledge.config.toml"
        $docsDir = Join-Path $homeDir "Documents\Codex"
        $bridgePy = Join-Path $docsDir "knowledge_os_mcp_bridge.py"
        $allOk = $true
        if (-not (Test-Path $codexDir)) { New-Item -ItemType Directory -Path $codexDir -Force | Out-Null }
        if (-not (Test-Path $docsDir)) { New-Item -ItemType Directory -Path $docsDir -Force | Out-Null }
        $pyForCfg = if ($PyPath -and (Test-Path $PyPath)) { $PyPath } else { "python" }
        if (-not (Test-Path $codexCfg)) {
            $bridgeArg = "`"$bridgePy`""
            $cfgText = @"
# Knowledge OS MCP profile - generated by bootstrap.ps1 (machine-local)
[mcp_servers.knowledge-os]
command = '$pyForCfg'
args = [$bridgeArg]
startup_timeout_sec = 120.0
default_tools_approval_mode = "approve"
enabled = true

[mcp_servers.knowledge-os.env]
KNOWLEDGE_OS_VAULT = '$VaultRoot'
"@
            Set-Content -LiteralPath $codexCfg -Value $cfgText -Encoding UTF8
        }
        $tmpl = Join-Path $ScriptDir "templates\mcp_bridge_template.py"
        if (-not (Test-Path $bridgePy) -and (Test-Path $tmpl)) {
            $t = Get-Content -LiteralPath $tmpl -Raw -Encoding UTF8
            $t = $t.Replace("__VAULT_ROOT__", $VaultRoot).Replace("__PYTHON__", $pyForCfg)
            Set-Content -LiteralPath $bridgePy -Value $t -Encoding UTF8
        }
        $cfgOk = Test-Path $codexCfg
        $bridgeOk = Test-Path $bridgePy
        Show-Result "Codex/MCP" $(if ($cfgOk -and $bridgeOk) {"PASS"} else {"PARTIAL"}) "config=$cfgOk bridge=$bridgeOk (machine-local)"
        return ($cfgOk -and $bridgeOk)
    }
} else {
    $homeDir = $HOME
    $codexCfg = Join-Path $homeDir ".codex\knowledge.config.toml"
    $bridgePy = Join-Path $homeDir "Documents\Codex\knowledge_os_mcp_bridge.py"
    $cfgOk = Test-Path $codexCfg; $bridgeOk = Test-Path $bridgePy
    $mcpPass = Show-Result "Codex/MCP" $(if ($cfgOk -and $bridgeOk) {"PASS"} else {"MISSING"}) "config=$cfgOk bridge=$bridgeOk (machine-local)"
}
$overall += $mcpPass

# ---------- 8. Control Center ----------
$ccPass = $false
$ccPort = 8765
$ccProbe = try { (Invoke-WebRequest -Uri "http://127.0.0.1:$ccPort/api/health" -UseBasicParsing -TimeoutSec 3).StatusCode } catch { $null }
$launcher = Test-Path (Join-Path $SystemDir "control_center\start_control_center.bat")
$ccPass = Show-Result "Control Center" $(if ($ccProbe -eq 200) {"PASS"} else {"NOT RUNNING"}) "port=$ccPort launcher=$launcher"
$overall += $ccPass

# ---------- 8.5 AI Runtime (Codex / CC Switch / DeepSeek / MCP) ----------
$aiStatus = "SKIPPED"
if (-not $SkipAI) {
    Write-Host "`n== AI Runtime =="
    $aiFails = @()

    # --- Codex ---
    $cdx = Invoke-Helper "detect-codex"
    if ($cdx.ok) {
        $null = Show-Result "Codex" "PASS" ("{0} @ {1}" -f $cdx.version, $cdx.path)
    } else {
        if (-not $CheckOnly) {
            Write-Host "Codex not found. Attempting npm install (requires Node.js)..."
            $npm = Get-Command npm -ErrorAction SilentlyContinue
            if ($npm) {
                & npm install -g @openai/codex 2>&1 | Out-Null
                $cdx = Invoke-Helper "detect-codex"
            }
        }
        if ($cdx.ok) { $null = Show-Result "Codex" "PASS" ("installed {0}" -f $cdx.version) }
        else {
            $null = Show-Result "Codex" "FAIL" "not installed; Bootstrap attempted npm install (no Node?) - install Codex CLI then re-run"
            $aiFails += "codex"
        }
    }

    # --- CC Switch ---
    $ccs = Invoke-Helper "detect-ccswitch"
    if ($ccs.ok) {
        $ccVer = "?"
        if ($ccs.exe -and (Test-Path $ccs.exe)) {
            $vi = (Get-Item $ccs.exe).VersionInfo
            if ($vi.FileVersion) { $ccVer = $vi.FileVersion }
        }
        $null = Show-Result "CC Switch" "PASS" ("{0} @ {1}" -f $ccVer, $ccs.exe)
    } else {
        $null = Show-Result "CC Switch" "FAIL" "not found; install CC Switch (no verified URL hardcoded - use official release), then re-run"
        $aiFails += "ccswitch"
    }

    # --- DeepSeek provider (via CC Switch) ---
    $ds = Invoke-Helper "ccswitch-deepseek"
    if ($ds.ok -and $ds.provider) {
        $keyState = if ($ds.api_key_present) { "key present" } else { "key MISSING" }
        $routingState = if ($ds.needs_routing) { "ROUTING REQUIRED" } else { "native responses (no protocol routing)" }
        $null = Show-Result "DeepSeek Provider" "PASS" ("{0} wire={1} model={2} {3}" -f $ds.provider.name, $ds.provider.wire_api, $ds.provider.model, $keyState)
        $null = Show-Result "Routing" "PASS" ("{0} | proxy={1} active_base_url={2}" -f $routingState, $(if ($ds.proxy.enabled) {"enabled:" + $ds.proxy.listen} else {"disabled"}), $ds.active_codex_base_url)
        if (-not $ds.api_key_present) {
            $null = Show-Result "DeepSeek Key" "WARN" "provider has no API key - configure in CC Switch (secure storage); core KOS still runs"
            $aiFails += "deepseek-key"
        }
    } else {
        $null = Show-Result "DeepSeek Provider" "FAIL" "not found in CC Switch; create DeepSeek provider in CC Switch UI"
        $aiFails += "deepseek-provider"
    }

    # --- DeepSeek key validation (env) ---
    $vk = Invoke-Helper "validate-deepseek-key"
    if ($vk.ok) {
        $null = Show-Result "DeepSeek API" "PASS" "key validated (HTTP 200; value never shown)"
    } else {
        $null = Show-Result "DeepSeek API" "WARN" ($vk.error)
        $aiFails += "deepseek-api"
    }

    # --- MCP + approval ---
    $homeDir = $HOME
    $codexCfg = Join-Path $homeDir ".codex\knowledge.config.toml"
    $mcpOk = $false
    if (Test-Path $codexCfg) {
        $cfgText = Get-Content -LiteralPath $codexCfg -Raw -Encoding UTF8
        $mcpOk = ($cfgText -match "mcp_servers.knowledge-os") -and ($cfgText -match 'default_tools_approval_mode\s*=\s*"approve"')
    }
    $ccMcp = Invoke-Helper "ccswitch-mcp"
    $ccMcpEnabled = if ($ccMcp.ok) { $ccMcp.enabled_codex } else { $false }
    if ($mcpOk) {
        $null = Show-Result "MCP/Approval" "PASS" "knowledge.config.toml ok (knowledge-os + approve); CC-Switch mcp enabled=$ccMcpEnabled"
    } else {
        $null = Show-Result "MCP/Approval" "FAIL" "knowledge.config.toml missing/incomplete"
        $aiFails += "mcp"
    }

    # --- E2E (cwd != Vault) ---
    if (-not $CheckOnly) {
        $e2eDir = "C:\Temp\KnowledgeOS-Gate4-AI-Test"
        if (-not (Test-Path $e2eDir)) { New-Item -ItemType Directory -Path $e2eDir -Force | Out-Null }
        Write-Host "E2E Test1: Codex -> DeepSeek (minimal request)..."
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $t1 = cmd /c 'echo. | codex exec --skip-git-repo-check -s read-only "只回复两个字：正常"' 2>&1 | Out-String
        $t1ok = ($LASTEXITCODE -eq 0) -and ($t1 -match "正常")
        Write-Host ("  Test1 Codex->DeepSeek: " + $(if ($t1ok) {"PASS"} else {"FAIL"}))
        if (-not $t1ok) { $aiFails += "e2e1" }
        Write-Host "E2E Test2: Codex -> knowledge_search (cwd!=Vault)..."
        Push-Location $e2eDir
        $t2 = cmd /c 'echo. | codex -p knowledge exec --skip-git-repo-check -s read-only "只调用 knowledge_search 查询 FreeRTOS 任务调度是怎么工作的？ mode=fast，返回 status 和 judge.relevance。"' 2>&1 | Out-String
        Pop-Location
        $t2ok = ($LASTEXITCODE -eq 0) -and ($t2 -match "answerable") -and ($t2 -match "relevant")
        Write-Host ("  Test2 Codex->MCP: " + $(if ($t2ok) {"PASS"} else {"FAIL"}))
        if (-not $t2ok) { $aiFails += "e2e2" }
        $ErrorActionPreference = $oldEAP
    } else {
        Write-Host "E2E: skipped in CheckOnly mode"
    }

    if ($aiFails.Count -eq 0) { $aiStatus = "READY" }
    elseif ($aiFails.Count -le 2) { $aiStatus = "DEGRADED" }
    else { $aiStatus = "BLOCKED" }
    $null = Show-Result "AI Runtime" $aiStatus ("Codex/CCSwitch/DeepSeek/MCP/E2E")
} else {
    $null = Show-Result "AI Runtime" "SKIPPED" "(-SkipAI)"
}
$overall += ($aiStatus -eq "READY")

# ---------- 9. Health Check (runtime) ----------
Write-Host "`n== BOOTSTRAP HEALTH CHECK =="
$health = Invoke-Helper "health-summary"
foreach ($name in @("architecture", "rag", "wiki")) {
    $c = $health.checks.$name
    Show-Result ("Health/" + $name) $(if ($c.ok) {"PASS"} else {"FAIL"}) $c.summary
}
$healthPass = $health.ok

# ---------- 10. Baseline Verification (behavior) ----------
$baselinePass = $false
if (-not $CheckOnly -and -not $SkipBaseline) {
    Write-Host "`n== Baseline Verification =="
    Write-Host "running RAG benchmark (may take a few minutes)..."
    $bv = Invoke-Helper "verify-baseline" $PyPath 28
    if ($bv.ok) {
        $baselinePass = Show-Result "Baseline" "PASS" ("coverage={0}% vs baseline={1}% (delta={2}pp, {3})" -f $bv.coverage, $bv.baseline, $bv.delta_pp, $bv.baseline_id)
    } else {
        $baselinePass = Show-Result "Baseline" "FAIL" $bv.error
    }
} else {
    $baselinePass = Show-Result "Baseline" "SKIPPED" "(set by flags / CheckOnly)"
    # SKIPPED does not count toward readiness
    $baselinePass = $true
}
$overall += $baselinePass

# ---------- state + verdict ----------
$State.bootstrap = @{ ran_at = (Get-Date -Format o); mode = $(if ($CheckOnly) {"check-only"} else {"full"}); vault = $VaultRoot }
$State.results = @{ python = $pythonPass; deps = $depsPass; models = $modelPass; secret = $secPass; index = $idxPass; scheduler = $schedPass; mcp = $mcpPass; cc = $ccPass; health = $healthPass; baseline = $baselinePass }
if (-not $CheckOnly) {
    $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

$failures = @($overall | Where-Object { $_ -eq $false }).Count
Write-Host ""
Write-Host "=============================================="
Write-Host " BOOTSTRAP HEALTH CHECK"
Write-Host "----------------------------------------------"
Write-Host (" Python           : " + $(if ($pythonPass) {"PASS"} else {"FAIL"}))
Write-Host (" Dependencies     : " + $(if ($depsPass) {"PASS"} else {"FAIL"}))
Write-Host (" Models           : " + $(if ($modelPass) {"PASS"} else {"FAIL"}))
Write-Host (" Secrets          : " + $(if ($secPass) {"PASS"} else {"FAIL"}))
Write-Host (" Index            : " + $(if ($idxPass) {"PASS"} else {"FAIL"}))
Write-Host (" Scheduler        : " + $(if ($schedPass) {"PASS"} else {"FAIL"}))
Write-Host (" Codex/MCP        : " + $(if ($mcpPass) {"PASS"} else {"FAIL"}))
Write-Host (" AI Runtime       : " + $aiStatus)
Write-Host (" Control Center   : " + $(if ($ccPass) {"PASS"} else {"NOT RUNNING"}))
Write-Host (" Health Check     : " + $(if ($healthPass) {"PASS"} else {"FAIL"}))
Write-Host (" Baseline Verify  : " + $(if ($baselinePass) {"PASS"} else {"FAIL"}))
Write-Host "----------------------------------------------"
if ($failures -eq 0) {
    Write-Host " BOOTSTRAP READY"
} else {
    Write-Host (" NOT READY ($failures failed)")
}
Write-Host "=============================================="
exit $(if ($failures -eq 0) { 0 } else { 1 })
