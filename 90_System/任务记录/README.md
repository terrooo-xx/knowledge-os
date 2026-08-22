---
type: system
status: draft
domain: 记录系统规范
created: 2026-08-13
updated: 2026-08-22
---

# 任务记录 —— 记录系统职责边界

> 本文只说明**记录系统的职责边界**，不重复 KNOWLEDGE_OS 的架构内容。
> 系统级架构、目录职责、AI 权限、知识生命周期的唯一权威依据是 `90_System/KNOWLEDGE_OS.md`。

## 四个入口的职责

| 位置 | 职责 | 说明 |
|---|---|---|
| `KNOWLEDGE_OS.md` | 当前系统是什么 | 唯一权威架构说明；结构变化必须同步更新 |
| `CHANGELOG.md` | 系统发生过什么变化 | 位于 Vault 根目录，是整个 Knowledge OS 的系统变更时间线；由 `update_changelog.ps1` 自动维护（NO_TOUCH） |
| `任务记录/Phase X/` | 某个阶段为什么做、怎么做、如何验证、最终结论 | 阶段工程记录；Phase 完成后保留原位，不迁移 |
| `任务记录/archive/` | 已废弃、被替代、不再参与当前系统运行的历史资产 | 仅历史追溯，不是普通阶段记录 |

## 任务记录结构

```text
任务记录/
├── Phase 2/            # Phase 工程记录（阶段总结/归档报告等）
├── Phase 3/            # Phase 工程记录（阶段14~22D 治理记录、阶段总结；ACTIVE）
├── 历史阶段/           # 早期阶段报告（阶段06~12C、阶段13），无法映射到 Phase 的正式阶段记录
├── archive/            # 废弃资产归档
│   └── agents/         # 早期 Agent 工作流文档（已废弃）
├── inbox_processor_log.md   # 日常任务日志（追加式）
├── Wiki更新建议_*.md        # 知识更新建议（待人工确认）
└── 本次PDF知识导入分析.md    # 单次任务分析记录
```

## 规则

1. **Phase 是历史边界**：Phase X 完成后保留在 `任务记录/Phase X/`，不再移动到 archive。
2. **历史阶段**：无法准确映射到已有 Phase 的早期阶段记录放入 `历史阶段/`；不得为了整齐强行改名。
3. **archive 只装废弃资产**：被替代、不再参与当前系统运行的文件才进 `任务记录/archive/`。
4. **禁止重复层级**：不创建 `任务记录/stages/`、`任务记录/阶段记录/`、`任务记录/history/` 等新历史层级。
5. **CHANGELOG 不记录实施过程**：完整实施过程属于 `任务记录/Phase X/`；CHANGELOG 只做时间线索引。
6. **移动即改引用**：任何路径调整后必须全 Vault 检查并修复链接（Markdown / Wikilink / 脚本 / Control Center / MCP / Skill / Prompt / README）。
## 版本治理

- 版本治理体系（Commit / Baseline / Tag / Phase / Project Summary）的唯一权威依据是 `90_System/KNOWLEDGE_OS.md` 第二十八章；本文件只引用，不复制。
- Phase 生命周期：`PLANNED → ACTIVE → VALIDATING → BASELINED → CLOSED`；CLOSED 必须人工确认，AI 不擅自关闭 Phase。
- Phase 3 当前状态 ACTIVE，包含阶段14~22D 的历史成果（归属说明见 `Phase 3/阶段总结.md`）。
- 项目/阶段的正式基线位于 `任务记录/<项目或阶段>/正式基线/`，命名 `Baseline-<yyyymmdd>.{md,json}`；对应 Git Tag 用 `baseline/<baseline_id>`。
- 任务记录（阶段报告、阶段总结）属于正式历史，按批次进入 Git；历史内容不重写。