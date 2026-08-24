# Knowledge OS System Profile + AGENTS.md 治理报告

- 日期：2026-08-25
- 范围：系统认知层治理（System Profile + AGENTS.md 全面更新）
- 原则：先只读审阅真实状态，再修改；不虚构；以当前源码/运行/Git 为准
- Git 状态：**未 commit / 未 push**（本任务未授权 commit/push）

## 1. 结论

```
========================================
Knowledge OS
SYSTEM COGNITION GOVERNANCE
========================================
System Profile:  READY
Freshness Check: CURRENT (source_commit = HEAD)
AGENTS.md:       READY (7 new protocols)
AI Context Entry:
  AGENTS.md → KNOWLEDGE_OS.md → system_profile.md
README Optimization:
  READY TO START
========================================
```

## 2. 审阅依据（当前真实状态）

- Git：HEAD=82e7383，master，remote=origin（terrooo-xx/knowledge-os，PRIVATE），Tag=baseline/rc-codex-wecom-20260820→f9a1130
- Wiki：25 篇（13 reviewed / 9 draft / 3 stable）；RAG Baseline bl-eval-20260817T162956（89.3% STABLE）；Governance=passed
- 测试：412/412；rag_health ERROR=0 PASS=8；Bootstrap 状态 BOOTSTRAP READY
- Phase 3 ACTIVE；Gaps 5 pending / 1 resolved
- 治理报告：Gate 0~3、Bootstrap Upgrade、Bootstrap Upgrade Release 已读取（仅作历史证据，以当前状态为准）

## 3. 交付物

| 文件 | 说明 |
|---|---|
| 90_System/system_profile.md（新建） | 当前系统全貌快照：23 章 + 版本绑定 frontmatter（source_commit/tag/rag_baseline/freshness_policy） |
| 90_System/scripts/system_profile_generator.py（新建） | 轻量机制：`--check`（STALE/CURRENT）+ `--update`（刷新元数据 + 动态区块） |
| AGENTS.md（修改） | 修正过时"无 remote"声明 + 新增 7 个协议章节 |

## 4. system_profile.md 设计

- 定位：**现在是什么**（KNOWLEDGE_OS.md=应是什么；AGENTS.md=AI 如何操作）
- 版本绑定：frontmatter `source_commit` = 82e7383，`source_tag`、`rag_baseline`、`generated_at`
- 静态/动态分离：稳定描述（架构/目录/生命周期/组件）人工维护；动态字段（HEAD/baseline/bootstrap/health/wiki 计数）由 generator 刷新到 `<!-- DYNAMIC -->` 区块
- 23 章覆盖：System Identity / Version / Git / Phase / Architecture / Directory / Lifecycle / RAG / Evidence / Gaps / Control Center / Weekly Review+Scheduler / MCP-Codex / AI Runtime / Bootstrap / New Machine Env / Git Governance / Baseline / External / Machine-local / Limitations / Health / Sources
- 安全：未记录任何 API Key / token / 真实用户路径细节（machine-local 只写类型/用途/是否自动恢复）

## 5. Freshness 机制

- `system_profile_generator.py --check`：对比 `source_commit` 与 `git HEAD` → CURRENT（相同）/ STALE（不同）
- `--update`：刷新 frontmatter + 动态区块（git/baseline/bootstrap/health/wiki）
- 当前验证：--check = CURRENT；--update 后动态字段正确（rag_baseline 89.3% STABLE / bootstrap READY / rag_health PASS 8 / wiki 25）

## 6. AGENTS.md 更新

新增 7 个协议章节 + 修正 1 处：
1. **AI Context Loading Protocol**：AGENTS.md → KNOWLEDGE_OS.md → system_profile.md → freshness 检查 → 任务深度审阅
2. **Source of Truth Hierarchy**：源码/运行 > 配置 > KNOWLEDGE_OS > system_profile > 审计报告 > 任务记录 > README > 旧资料
3. **System Profile 更新规则**：何时必须更新（架构/RAG/CC/MCP/AI Runtime/Bootstrap/Baseline/Git boundary 等）
4. **Change Impact Rules**：修改 → 应更新文档矩阵
5. **Verification Protocol**：Local / Component / System 三级验证
6. **Machine-local / Secret Boundary**：Git assets ≠ Runtime ≠ Machine-local ≠ Secrets ≠ Private data
7. **Bootstrap 规则**：恢复运行环境；不负责知识内容/Git push/Secret/私人资料
8. **任务完成定义**：必报新建/修改/移动/跳过/问题/待确认
9. **修正**：Git 版本治理规则中"无 remote，不创建"→ 当前已有 origin remote（PRIVATE），commit/push 仅任务明确授权时执行

## 7. 边界遵守

- ✅ 先只读审阅，后修改；全部结论来自当前仓库真实状态
- ✅ 未 commit / 未 push（未授权）
- ✅ 未虚构内容；无法确认项不猜测
- ✅ system_profile 未包含 Secret / 敏感路径 / 临时日志 / 历史 Warning
- ✅ README 优化留待下一任务

## 8. 后续建议

- README 优化（下一任务）：以 system_profile 为认知基础，补齐 Control Center / MCP / Bootstrap / GitHub 发布现状
- 每次涉及系统变化并提交前，运行 `system_profile_generator.py --update`
