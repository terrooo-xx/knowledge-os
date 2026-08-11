<#
update_changelog.ps1 - 自动更新 CHANGELOG.md

检测自上次运行以来的 Git 变更（新提交 + 未提交工作区变更），
按日期分节合并进 CHANGELOG.md，并把该文件 git add 进暂存区。

触发方式：
  - 手动：powershell -ExecutionPolicy Bypass -File 90_System/scripts/update_changelog.ps1
  - 自动：.git/hooks/pre-commit（每次 commit 前自动执行）

参数：
  -DryRun  只输出将要写入的条目，不修改任何文件

说明：
  - 状态记录在 90_System/scripts/.changelog_state.json
  - 首次运行只建立基线，不写 changelog
  - .obsidian/、.claudian/、90_System/scripts/ 下的变更不记录
#>
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
# git 输出为 UTF-8，强制控制台解码为 UTF-8（Windows PowerShell 5.1 默认按 GBK 解码会导致中文路径乱码）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    $VaultRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $ScriptDir = $PSScriptRoot
    $Changelog = Join-Path $VaultRoot 'CHANGELOG.md'
    $StatePath = Join-Path $ScriptDir '.changelog_state.json'

    $ExcludePrefixes = @('.obsidian/', '.claudian/', '90_System/scripts/')

    function Get-GitHead {
        $h = & git -C $VaultRoot rev-parse HEAD 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return $h.Trim()
    }

    function Test-Excluded([string]$Path) {
        foreach ($p in $ExcludePrefixes) {
            if ($Path -like "$p*") { return $true }
        }
        return $false
    }

    # ---------- 读取状态 ----------
    $state = @{ lastHead = $null; baseline = @() }
    if (Test-Path $StatePath) {
        $state = Get-Content $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    $head = Get-GitHead

    # ---------- 解析工作区变更 ----------
    $workChanges = New-Object System.Collections.Generic.List[object]
    $statusLines = @(& git -C $VaultRoot -c core.quotepath=false status --porcelain 2>$null)
    foreach ($line in $statusLines) {
        if ($line.Length -lt 4) { continue }
        $xy   = $line.Substring(0, 2)
        $path = $line.Substring(3).Trim('"')
        if ($path -match ' -> ') { $path = ($path -split ' -> ')[-1] }
        if ($path -eq 'CHANGELOG.md') { continue }
        if (Test-Excluded $path) { continue }
        $type = '修改'
        if ($xy -match 'D') { $type = '删除' }
        elseif ($xy -match '\?\?|A') { $type = '新增' }
        $workChanges.Add([PSCustomObject]@{ Type = $type; Path = $path })
    }

    # ---------- 生成新条目 ----------
    $entries = @{}
    function Add-Entry([string]$Date, [string]$Type, [string]$Text) {
        if (-not $entries.ContainsKey($Date)) { $entries[$Date] = @{} }
        if (-not $entries[$Date].ContainsKey($Type)) {
            $entries[$Date][$Type] = New-Object System.Collections.Generic.List[string]
        }
        $entries[$Date][$Type].Add($Text)
    }

    $hasNew = $false

    # 新提交（自上次记录的 HEAD 以来）
    if ($state.lastHead -and $head -and $state.lastHead -ne $head) {
        $logs = @(& git -C $VaultRoot log --format='%H|%ad|%s' --date=format:'%Y-%m-%d' "$($state.lastHead)..HEAD" 2>$null)
        foreach ($l in $logs) {
            $parts = $l -split '\|', 3
            if ($parts.Count -lt 3) { continue }
            $short = $parts[0].Substring(0, [Math]::Min(7, $parts[0].Length))
            Add-Entry $parts[1] '提交' "- 提交 $short：$($parts[2])"
            $hasNew = $true
        }
    }

    # 未提交变更（相对基线的新增）——仅当已初始化过（存在 lastHead）
    if ($state.lastHead) {
        $baselineKeys = @{}
        foreach ($b in @($state.baseline)) { $baselineKeys["$($b.Type)|$($b.Path)"] = $true }
        $today = Get-Date -Format 'yyyy-MM-dd'
        foreach ($c in $workChanges) {
            $key = "$($c.Type)|$($c.Path)"
            if ($baselineKeys.ContainsKey($key)) { continue }
            Add-Entry $today $c.Type "- $($c.Path)"
            $hasNew = $true
        }
    }

    if ($DryRun) {
        Write-Host 'DryRun：将写入以下条目（不修改文件）'
        Write-Host '------------------------------'
        foreach ($date in ($entries.Keys | Sort-Object -Descending)) {
            Write-Host "## $date"
            foreach ($type in @('新增','修改','删除','提交')) {
                if ($entries[$date].ContainsKey($type)) {
                    Write-Host "### $type"
                    foreach ($t in $entries[$date][$type]) { Write-Host "  $t" }
                }
            }
        }
        Write-Host '------------------------------'
        exit 0
    }

    # ---------- 保存新状态 ----------
    $newState = @{
        lastHead = $head
        baseline = @($workChanges | ForEach-Object { [PSCustomObject]@{ Type = $_.Type; Path = $_.Path } })
    }
    $newState | ConvertTo-Json -Depth 4 | Set-Content -Path $StatePath -Encoding UTF8

    if (-not $hasNew) { exit 0 }

    # ---------- 合并进 CHANGELOG.md ----------
    $lines = @(Get-Content $Changelog -Encoding UTF8)

    # 解析现有分节
    $sections = New-Object System.Collections.Generic.List[object]
    $title = $null
    $types = $null
    $curType = $null
    foreach ($line in $lines) {
        $t = $line.TrimEnd()
        if ($t -match '^## (.+)$') {
            if ($title) { $sections.Add([PSCustomObject]@{ Title = $title; Types = $types }) }
            $title = $Matches[1].Trim()
            $types = @{}
            $curType = $null
        }
        elseif ($t -match '^### (.+)$' -and $title) {
            $curType = $Matches[1].Trim()
            if (-not $types.ContainsKey($curType)) { $types[$curType] = New-Object System.Collections.Generic.List[string] }
        }
        elseif ($t -match '^- (.+)$' -and $title -and $curType -and $types.ContainsKey($curType)) {
            $types[$curType].Add($t)
        }
    }
    if ($title) { $sections.Add([PSCustomObject]@{ Title = $title; Types = $types }) }

    # 合并新条目到分节
    foreach ($date in ($entries.Keys | Sort-Object)) {
        $sec = $null
        foreach ($s in $sections) {
            if ($s.Title -eq $date) { $sec = $s; break }
        }
        if ($sec) {
            foreach ($type in $entries[$date].Keys) {
                if (-not $sec.Types.ContainsKey($type)) {
                    $sec.Types[$type] = New-Object System.Collections.Generic.List[string]
                }
                foreach ($item in $entries[$date][$type]) {
                    if (-not $sec.Types[$type].Contains($item)) { $sec.Types[$type].Add($item) }
                }
            }
        }
        else {
            $newTypes = @{}
            foreach ($type in $entries[$date].Keys) { $newTypes[$type] = $entries[$date][$type] }
            $sections.Add([PSCustomObject]@{ Title = $date; Types = $newTypes })
        }
    }

    # 序列化（按日期倒序）
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine('# 知识库变更记录')
    foreach ($s in ($sections | Sort-Object { $_.Title } -Descending)) {
        [void]$sb.AppendLine('')
        [void]$sb.AppendLine("## $($s.Title)")
        foreach ($type in @('新增','修改','删除','提交')) {
            if ($s.Types.ContainsKey($type) -and $s.Types[$type].Count -gt 0) {
                [void]$sb.AppendLine('')
                [void]$sb.AppendLine("### $type")
                foreach ($item in $s.Types[$type]) { [void]$sb.AppendLine($item) }
            }
        }
    }
    $newContent = $sb.ToString().TrimEnd() + "`r`n"

    [System.IO.File]::WriteAllText($Changelog, $newContent, (New-Object System.Text.UTF8Encoding $false))
    & git -C $VaultRoot add CHANGELOG.md
    Write-Host 'CHANGELOG.md 已更新并加入暂存区。'
    exit 0
}
catch {
    Write-Error "update_changelog.ps1 失败：$($_.Exception.Message)"
    exit 1
}
