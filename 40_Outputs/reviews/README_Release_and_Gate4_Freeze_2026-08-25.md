# Knowledge OS README New Machine Setup 发布 + Gate 4 启动前最终冻结

- 日期：2026-08-25
- 两阶段：Phase A（README 发布）+ Phase B（Gate 4 最终冻结，不执行）

## Phase A：README New Machine Setup 正式发布

```
========================================
Knowledge OS
README NEW MACHINE SETUP RELEASE
========================================
README:   PUBLISHED（commit 5669fa7，远程 14991B，gh api 确认）
GitHub:   PASS（master=fc8e8cd）
Profile:  CURRENT
Working Tree: CLEAN（仅 2 个 DEFER Source）
Secret:   0
========================================
```

- Commit：`5669fa7` docs: improve new machine setup guide（README +146/-4，仅此文件 + CHANGELOG 自动条目）+ `fc8e8cd` docs: sync system profile to current head
- Push 经历网络抖动（多 IP 交替后经 140.82.112.3 成功；未写永久配置）
- 提交前：README 14 项真实性复核全 PASS（含 Node=Codex npm 前置依赖、CC Switch 非自动安装、Python 不自动装、402=上游余额、routing 不强制）

## Phase B：Gate 4 启动前最终冻结（未执行 Gate 4）

```
========================================
Knowledge OS
GATE 4 PREFLIGHT
========================================
New Machine Environment: FROZEN
README Flow:             FROZEN
Bootstrap:               READY
Gate 4:                  READY TO START
NO GATE 4 EXECUTION
========================================
```

### Gate 4 唯一目标
一台符合冻结条件的新 Windows 电脑，**仅通过 GitHub clone + 当前 README + 当前 Bootstrap** 恢复完整 Knowledge OS（三者一起验证）。

### 新电脑最低前置（冻结）
- 必须预装：Windows 10/11、PowerShell 5.1+、Git、Internet、GitHub Private Repository 认证、**Python 3.14.x**、**Node.js**（Codex 缺失时 Bootstrap 用 npm 装 `@openai/codex`，Node 为该链路前置）
- 不应提前存在：Knowledge OS / venv / deps / RAG database / BGE model / Reranker / Knowledge OS config / Codex user config / MCP / Scheduler / Control Center / 旧 runtime
- 禁止从当前电脑复制：~/.codex、~/.cc-connect、模型缓存、RAG index、旧配置

### 用户允许提供
GitHub 私库认证、DeepSeek API Key（仅用户→Bootstrap，绝不进 Git/Vault/README/日志/Chat）、CC Switch 官方安装器（若缺失，Bootstrap 提示→用户提供→安装→重跑）。

### Gate 4 标准流程（冻结，严格按 README）
```text
1. 新 Windows 环境准备 → 2. GitHub auth → 3. 阅读 README → 4. git clone → 5. cd knowledge-os
→ 6. bootstrap.ps1 -CheckOnly → 7. 补齐缺失前置 → 8. bootstrap.ps1 → 9. 提供 DeepSeek Key
→ 10. 必要时 CC Switch installer → 11. BOOTSTRAP READY → 12. Health Check → 13. Baseline Verification
→ 14. Codex→DeepSeek → 15. Codex→knowledge_search → 16. cwd≠Vault → 17. Gate 4
```

### Gate 4 验收要求
- README 可执行性：逐 README 步骤记录 PASS/FAIL（Prerequisites/GitHub Login/Clone/CheckOnly/Bootstrap/DeepSeek/CC Switch/Verification）；步骤无法执行时记录 finding，不直接改 README
- Bootstrap 验证：Python/Deps/Models/Reranker/RAG Index/MCP/Approval/Scheduler/CC/Codex/DeepSeek 全达标 → BOOTSTRAP READY
- Baseline：按项目规则 REAL_REGRESSION=0（JUDGE_VARIANCE 不阻塞）
- 隔离：测试机不与当前机器共享配置；README 本身是 Gate 4 验证对象（能照 README 恢复成功 = 流程闭环）

## 变更报告

- **已提交+推送**：README.md（5669fa7）+ system_profile sync（fc8e8cd）；远程 master=fc8e8cd
- **未跟踪（预期）**：2 个 DEFER Source
- 未创建/移动 Tag、未改 Baseline/Bootstrap/Wiki/Source；未开始 Gate 4；未输出任何凭据值
