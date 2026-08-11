<#
knowledge_os_check.ps1 - 知识库架构漂移检测

扫描实际目录与重要文件，与 KNOWLEDGE_OS.md（90_System/KNOWLEDGE_OS.md）
记录的规范结构比较，输出 PASS / WARNING / ERROR 与汇总。

触发方式：
  powershell -ExecutionPolicy Bypass -File 90_System/scripts/knowledge_os_check.ps1

说明：
  - 本脚本的规范清单必须与 90_System/KNOWLEDGE_OS.md 保持同步。
  - 只读检查，不修改任何文件。
  - 退出码：存在 ERROR 时返回 1，否则返回 0。
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$VaultRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Level, [string]$Message) {
    $Results.Add([PSCustomObject]@{ Level = $Level; Message = $Message })
    Write-Host ("[{0}] {1}" -f $Level.PadRight(7), $Message)
}

# ---------- 规范清单（与 KNOWLEDGE_OS.md 同步） ----------
$ExpectedTopDirs = @('00_Inbox','10_Sources','20_Wiki','30_Projects','40_Outputs','50_Reviews','90_System','.agents','.claudian','.obsidian','.git')
$ExpectedRootFiles = @('AGENTS.md','README.md','HOME.md','CHANGELOG.md','interfaces.md','.gitignore')
$ExpectedSystemFiles = @(
    '90_System/KNOWLEDGE_OS.md',
    '90_System/rag/README.md',
    '90_System/rag/AGENTS.md',
    '90_System/rag/config.yaml',
    '90_System/rag/requirements.txt',
    '90_System/rag/scripts/ingest_rag.py',
    '90_System/rag/scripts/update_index.py',
    '90_System/rag/scripts/hybrid_query.py',
    '90_System/rag/scripts/inbox_processor.py',
    '90_System/rag/scripts/wiki_compile.py',
    '90_System/rag/scripts/wiki_review.py',
    '90_System/rag/scripts/rag_health_check.py',
    '90_System/rag/scripts/wiki_health_check.py',
    '90_System/scripts/update_changelog.ps1',
    '90_System/scripts/knowledge_os_check.ps1',
    '.agents/agents/ingest_agent.md',
    '.agents/agents/retrieval_agent.md',
    '.agents/agents/review_agent.md',
    '.agents/agents/wiki_compile_agent.md'
)

Write-Host '===== Knowledge OS 架构漂移检测 ====='
Write-Host ("Vault: {0}" -f $VaultRoot)
Write-Host ''

$ExpectedSecondDirs = @(
    '00_Inbox/AI聊天记录','00_Inbox/临时笔记','00_Inbox/图片截图','00_Inbox/待处理文件','00_Inbox/待处理文件/个人笔记','00_Inbox/网页剪藏','00_Inbox/行业情报',
    '10_Sources/FreeRTOS','10_Sources/ROS2','10_Sources/STM32','10_Sources/控制理论','10_Sources/数据手册','10_Sources/无人机飞控','10_Sources/移动底盘',
    '20_Wiki/01_计算机基础','20_Wiki/02_嵌入式基础','20_Wiki/03_STM32','20_Wiki/04_FreeRTOS','20_Wiki/05_通信协议','20_Wiki/06_控制理论','20_Wiki/07_无人机飞控','20_Wiki/08_移动机器人','20_Wiki/09_ROS2',
    '30_Projects/无人机飞控','30_Projects/移动底盘控制器',
    '30_Projects/无人机飞控/architecture','30_Projects/无人机飞控/modules','30_Projects/无人机飞控/interfaces','30_Projects/无人机飞控/decisions','30_Projects/无人机飞控/tasks','30_Projects/无人机飞控/problems',
    '30_Projects/移动底盘控制器/architecture','30_Projects/移动底盘控制器/modules','30_Projects/移动底盘控制器/interfaces','30_Projects/移动底盘控制器/decisions','30_Projects/移动底盘控制器/tasks','30_Projects/移动底盘控制器/problems',
    '30_Projects/移动底盘控制器/硬件选型','30_Projects/移动底盘控制器/项目适配',
    '40_Outputs/学习总结','40_Outputs/技术方案','40_Outputs/项目报告','40_Outputs/对外材料',
    '50_Reviews/每周复盘','50_Reviews/知识缺口','50_Reviews/过期内容检查',
    '90_System/archive','90_System/logs','90_System/prompts','90_System/schemas','90_System/scripts','90_System/templates','90_System/任务记录','90_System/rag',
    '90_System/rag/rag_engine','90_System/rag/llm','90_System/rag/scripts','90_System/rag/tests','90_System/rag/database','90_System/rag/cache',
    '.agents/agents','.agents/skills'
)

# ---------- 1. 一级目录 ----------
$actualTopDirs = Get-ChildItem -LiteralPath $VaultRoot -Force -Directory | Select-Object -ExpandProperty Name
foreach ($d in $ExpectedTopDirs) {
    if ($d -eq '个人笔记') { continue }
    if ($actualTopDirs -contains $d) {
        Add-Result 'PASS' "一级目录存在：$d"
    } else {
        Add-Result 'ERROR' "一级目录缺失：$d（见 KNOWLEDGE_OS.md 第五章）"
    }
}
$extraDirs = $actualTopDirs | Where-Object { $ExpectedTopDirs -notcontains $_ }
foreach ($d in $extraDirs) {
    Add-Result 'WARNING' "未记录的一级目录：$d（如为正式目录请登记到 KNOWLEDGE_OS.md）"
}

# ---------- 2. 根目录重要文件 ----------
foreach ($f in $ExpectedRootFiles) {
    if (Test-Path -LiteralPath (Join-Path $VaultRoot $f)) {
        Add-Result 'PASS' "根文件存在：$f"
    } else {
        Add-Result 'ERROR' "根文件缺失：$f"
    }
}

# ---------- 3. 系统关键文件 ----------
foreach ($f in $ExpectedSystemFiles) {
    if (Test-Path -LiteralPath (Join-Path $VaultRoot $f)) {
        Add-Result 'PASS' "系统文件存在：$f"
    } else {
        Add-Result 'ERROR' "系统文件缺失：$f（见 KNOWLEDGE_OS.md 第七章）"
    }
}

# ---------- 3b. 重要二级目录存在性（KNOWLEDGE_OS.md 第五章声明） ----------
foreach ($d in $ExpectedSecondDirs) {
    if (Test-Path -LiteralPath (Join-Path $VaultRoot $d)) {
        Add-Result 'PASS' "二级目录存在：$d"
    } else {
        Add-Result 'ERROR' "声明但缺失的二级目录：$d（见 KNOWLEDGE_OS.md 第五章）"
    }
}

# ---------- 4. 空占位文件 ----------
$interfaces = Join-Path $VaultRoot 'interfaces.md'
if (Test-Path -LiteralPath $interfaces) {
    $len = (Get-Item -LiteralPath $interfaces).Length
    if ($len -le 3) { Add-Result 'WARNING' 'interfaces.md 为空（已知占位，待补充）' }
}

# ---------- 5. Inbox 待处理 ----------
$inboxFiles = Get-ChildItem -LiteralPath (Join-Path $VaultRoot '00_Inbox') -Recurse -File |
    Where-Object { $_.Name -ne '.gitkeep' }
if ($inboxFiles.Count -gt 0) {
    Add-Result 'WARNING' ("00_Inbox 有 {0} 个待处理/待确认文件（正常状态，处理后保留原文）" -f $inboxFiles.Count)
} else {
    Add-Result 'PASS' '00_Inbox 无待处理文件'
}

# ---------- 6. Wiki 状态 ----------
$wikiFiles = Get-ChildItem -LiteralPath (Join-Path $VaultRoot '20_Wiki') -Recurse -Filter *.md
$statusCounts = @{}
$noStatus = 0
foreach ($f in $wikiFiles) {
    $head = Get-Content -LiteralPath $f.FullName -Encoding UTF8 -TotalCount 12
    $s = ($head | Select-String '^status:\s*(\S+)' | Select-Object -First 1)
    if ($s -and $s.Matches[0].Groups[1].Value) {
        $v = $s.Matches[0].Groups[1].Value
        $statusCounts[$v] = 1 + $(if ($statusCounts.ContainsKey($v)) { $statusCounts[$v] } else { 0 })
    } else {
        $noStatus++
    }
}
if ($statusCounts.Count -eq 0 -and $noStatus -eq 0) {
    Add-Result 'PASS' '20_Wiki 暂无可统计笔记'
} else {
    foreach ($k in ($statusCounts.Keys | Sort-Object)) {
        Add-Result 'INFO' "Wiki 状态 $k = $($statusCounts[$k]) 篇"
    }
    if ($noStatus -gt 0) { Add-Result 'ERROR' "有 $noStatus 篇 Wiki 缺少 status frontmatter" }
}

# ---------- 7. 派生数据存在性 ----------
foreach ($d in @('90_System/rag/database','90_System/rag/cache')) {
    if (Test-Path -LiteralPath (Join-Path $VaultRoot $d)) {
        Add-Result 'INFO' "派生数据目录存在（可重建，gitignored）：$d"
    } else {
        Add-Result 'INFO' "派生数据目录不存在（尚未索引或已清理）：$d"
    }
}

# ---------- 8. Git 状态 ----------
$statusLines = @(& git -C $VaultRoot status --porcelain 2>$null)
if ($LASTEXITCODE -eq 0 -and $statusLines.Count -gt 0) {
    Add-Result 'WARNING' ("Git 工作区有 {0} 处未提交变更（本检查只读，不处理）" -f $statusLines.Count)
} elseif ($LASTEXITCODE -eq 0) {
    Add-Result 'PASS' 'Git 工作区干净'
} else {
    Add-Result 'WARNING' '无法读取 Git 状态'
}

# ---------- 9. RAG Health（调用只读 Python 检查并汇总） ----------
$oldIoEncoding = $env:PYTHONIOENCODING
$env:PYTHONIOENCODING = 'utf-8'
try {
    $ragOut = & python (Join-Path $VaultRoot '90_System/rag/scripts/rag_health_check.py') 2>&1 | Out-String
    $ragLine = @($ragOut -split "`r?`n" | Where-Object { $_ -match '^RAG_HEALTH_SUMMARY ' })[0]
    if ($ragLine) {
        if ($ragLine -match 'ERROR=(\d+)') {
            $ragErr = [int]$Matches[1]
            if ($ragErr -gt 0) {
                Add-Result 'ERROR' "RAG Health Check 发现 $ragErr 个 ERROR（$ragLine）"
            } else {
                Add-Result 'INFO' "RAG Health Check 汇总：$ragLine"
            }
        } else {
            Add-Result 'WARNING' 'RAG Health Check 输出无法解析'
        }
    } else {
        Add-Result 'WARNING' 'RAG Health Check 无输出（python 可能不可用）'
    }
} catch {
    Add-Result 'WARNING' 'RAG Health Check 无法运行（仅汇总，不影响本检查其余部分）'
} finally {
    if ($null -eq $oldIoEncoding) { Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue } else { $env:PYTHONIOENCODING = $oldIoEncoding }
}

# ---------- 汇总 ----------
Write-Host ''
$errorCount = @($Results | Where-Object { $_.Level -eq 'ERROR' }).Count
$warnCount  = @($Results | Where-Object { $_.Level -eq 'WARNING' }).Count
$passCount  = @($Results | Where-Object { $_.Level -eq 'PASS' }).Count
Write-Host ("汇总：PASS={0}  WARNING={1}  ERROR={2}" -f $passCount, $warnCount, $errorCount)
if ($errorCount -gt 0) { Write-Host '结论：ERROR（存在必须修复的问题）'; exit 1 }
if ($warnCount -gt 0) { Write-Host '结论：WARNING（存在需关注或登记的事项）'; exit 0 }
Write-Host '结论：PASS'; exit 0
