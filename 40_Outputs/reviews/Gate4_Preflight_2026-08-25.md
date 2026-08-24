# Knowledge OS Gate 4 前置检查（正式冻结）

- 日期：2026-08-25
- 范围：README + 治理报告正式发布后的 Gate 4 启动前最终检查（**不执行 Gate 4**）
- 依据：system_profile.md（freshness CURRENT）+ bootstrap.ps1/helper 当前代码 + 已验证事实

## 1. Phase A 发布确认

```
========================================
README + GOVERNANCE RELEASE = PASS
========================================
README                         GitHub ✅（8803B）
Bootstrap Upgrade Report       GitHub ✅（4907B）
Gate3 Implementation Report    GitHub ✅（6021B）
Governance + README Report     GitHub ✅（3655B）
Secret                         0 ✅
Profile Freshness              CURRENT ✅
Remote                         PASS ✅（master=220a17c）
Working Tree                   CLEAN ✅（仅 2 个 DEFER Source 未跟踪）
DEFER / 私人 / machine-local   未纳入 ✅
========================================
```

- Commits：`0400f30`（docs: publish readme and governance reports）+ `220a17c`（docs: sync system profile to current head）已 push。

## 2. Gate 4 新电脑正式初始环境（冻结）

| 项 | 要求 |
|---|---|
| Windows | **必须预装**（10/11，已验证 Windows 11） |
| PowerShell | **必须预装**（5.1+ / PS7） |
| Git | **必须预装** |
| Internet | **必须可用** |
| GitHub Private Repository 认证 | **必须预装**（gh 或 credential，能 clone terrooo-xx/knowledge-os） |
| Python 3.14.x | **必须预装**（Bootstrap 只自动发现 py -3.14 / python，不安装；缺失则 FAIL） |
| 其余（Knowledge OS / venv / deps / RAG database / BGE model / Reranker / Codex config / MCP / Scheduler / Control Center） | **不应预装**，由 Bootstrap 恢复 |

## 3. Bootstrap 行为（冻结）

- **自动安装**：Codex（`npm install -g @openai/codex`，需 Node.js）
- **自动配置**：venv（90_System/.venv）、依赖（requirements-lock）、BGE embedding + reranker（检测+config.local.yaml）、RAG index、Codex config、DeepSeek provider（读/验）、MCP（knowledge.config.toml + bridge）、approval=approve、Scheduler（3 任务）、Control Center
- **用户提供**：DeepSeek API Key（machine-local，CC Switch provider 安全存储）；CC Switch **缺失时需用户提供官方安装器**（Bootstrap 不硬编码下载 URL）
- 幂等：重复执行 = VERIFY/REPAIR

## 4. Gate 4 测试条件（冻结）

在另一台真实 Windows 电脑，按序执行：

```text
1. git clone https://github.com/terrooo-xx/knowledge-os.git
2. powershell -ExecutionPolicy Bypass -File 90_System/scripts/bootstrap.ps1
3. Health Check（knowledge_os_check.ps1 / rag_health_check.py / wiki_health_check.py）
4. Baseline Verification（evaluate_benchmark.py，REAL_REGRESSION=0 为门禁）
5. Codex → DeepSeek（最小无副作用请求）
6. Codex → knowledge_search（cwd ≠ Vault，如 C:\Temp\... 独立目录）
7. 最终：BOOTSTRAP HEALTH CHECK → BOOTSTRAP READY
```

## 5. 验收标准（冻结）

- bootstrap.ps1 完整运行 → **BOOTSTRAP READY**（Python/Deps/Models/Secrets/Index/Scheduler/Codex-MCP/AI Runtime/CC/Baseline 全 PASS）
- Health Check = 运行时健康（区别于 Baseline Verification = 行为复现）
- Baseline：与官方 bl-eval-20260817T162956 对比，REAL_REGRESSION=0（JUDGE_VARIANCE 不阻塞）
- MCP：knowledge_search → answerable + judge relevant，cwd≠Vault
- DeepSeek 账户需有余额（曾出现瞬时 HTTP 402 环境因素）
- 隔离要求：测试机与当前机器互不干扰；不使用当前机器配置

## 6. 结论

```
========================================
Knowledge OS
GATE 4 PREFLIGHT
========================================
New Machine Environment:  FROZEN
Test Conditions:          FROZEN
Bootstrap:                READY
Gate 4:                   READY TO START
NO GATE 4 EXECUTION YET
========================================
```

## 7. 边界遵守

- ✅ 未执行 Gate 4 / 未在第二台电脑操作
- ✅ 未创建/移动 Tag、未改 Baseline、未改 Git 历史、未改 Bootstrap
- ✅ 未纳入 DEFER / 私人 / runtime / machine-local / Secret
- ✅ 未输出任何凭据值
