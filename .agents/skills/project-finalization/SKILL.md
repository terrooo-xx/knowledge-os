---
name: project-finalization
description: 项目收尾与基线验收（Project Finalization）。用于项目/专项/重大 Phase 完成后统一封版：先识别是否已有 Summary/Baseline/Tag，已有则进入只读回顾验证模式（EXISTING_BASELINE_VERIFY）并输出 PASS/DRIFT；没有则按 NEW_FINALIZATION 流程生成项目总结验收报告、Baseline（md+json）、Git commit 与正式 Tag。遵守 KNOWLEDGE_OS.md 第二十八章版本治理规则；只读验证优先，不自动 commit/push/tag，不关闭 Phase。
---

# project-finalization —— 项目收尾与基线验收

## 何时执行

- 项目 / 专项 / 重大 Phase 完成后需要正式封版时。
- 再次接手已有 Summary / Baseline / Tag 的项目时（回顾验证，回归）。
- 幂等：已有正式成果的项目只做回顾验证，不重复创建 Baseline / Tag / Summary / commit。

## 权威依据（执行前必读）

1. `90_System/KNOWLEDGE_OS.md` 第二十八章（Commit / Baseline / Tag / Phase / Summary 唯一权威）。
2. 根 `AGENTS.md`（Git 版本治理规则、安全规则）。
3. `90_System/rag/AGENTS.md`（提交/忽略范围）。
4. `90_System/任务记录/README.md`（记录系统职责边界）。
5. `90_System/templates/项目总结验收报告模板.md`（Summary 模板）。
6. `.gitignore`（运行时/派生文件忽略范围）。

以当前 Vault 文件为准，不依赖旧聊天上下文猜测规则。

## 输入

### 必要
- project / scope（项目名）
- 项目目录
- 当前 Phase（如有）
- 项目完成状态
- 已知验收结果

### 可选
- Baseline ID、Tag、项目总结路径、Git commit
- 额外验收命令、关键文件列表

未提供完整信息时：先读取现有 Knowledge OS 记录（`90_System/任务记录/<项目>/`、`正式基线/`）寻找，不要一开始就询问用户。

## 输出

### 新模式（NEW_FINALIZATION）
- `项目总结验收报告.md`
- `Baseline-<yyyymmdd>.md`、`Baseline-<yyyymmdd>.json`
- 准备：Git commit、必要时 Tag、Phase 状态更新建议

### 已有基线模式（EXISTING_BASELINE_VERIFY）
- baseline_id / status / created_at / git.commit / git.tag
- 当前 HEAD、关键文件 hash、drift status
- 结论：`PASS` / `DRIFT` / `REBASELINE_REQUIRED` / `BASELINE_INTEGRITY_ERROR`
- **不得**生成新 Baseline、**不得**创建新 Tag、**不得** commit。

## 两种模式

### Mode A：NEW_FINALIZATION

适用：还没有正式 Baseline 的已完成项目 / Phase。

```text
项目完成
  ↓
Git 状态检查
  ↓
验收检查
  ↓
项目总结（模板）
  ↓
Baseline（md + json）
  ↓
现场 SHA256
  ↓
Git Commit
  ↓
必要时 Tag
  ↓
人工确认
  ↓
CLOSED（仅人工）
```

### Mode B：EXISTING_BASELINE_VERIFY（回顾验证模式）

适用：项目已存在 Summary / Baseline / Tag，Skill 被再次调用。

```text
发现现有 Summary
  ↓
发现现有 Baseline
  ↓
发现现有 Tag
  ↓
识别其 git commit
  ↓
检查当前 HEAD
  ↓
检查 Baseline hash
  ↓
检查验收记录
  ↓
判断是否漂移
  ↓
输出 PASS / DRIFT / REBASELINE_REQUIRED
```

**不得重复创建 Baseline / Tag / Commit / Summary。**

## 内部流程

```text
1. DISCOVER      定位项目目录与既有记录（任务记录/<项目>/、正式基线/）
2. CLASSIFY      判断 NEW_FINALIZATION 或 EXISTING_BASELINE_VERIFY
3. READ_GOVERNANCE  读取 KNOWLEDGE_OS 第二十八章 + 相关规则
4. CHECK_GIT     git status / HEAD / tag / remote
5. DETECT_EXISTING_BASELINE
   ├── EXISTING → VERIFY（drift check → report）
   └── NONE → FINALIZE（acceptance → summary → baseline → hash → commit → tag → report）
```

## Git 安全策略

提交前必须：
1. `git status`
2. 检查 staged / unstaged
3. 识别 USER_WORK（用户原始资料/未完成工作）
4. 识别 IGNORE（运行时/派生文件）
5. 敏感信息扫描
6. 明确 commit 文件范围
7. `git diff`
8. `git diff --cached`

禁止：`git add -A`、`git commit -am`、`git clean`、`git reset`、`git stash`、`git push`、创建 remote。
不自动 commit；commit 范围必须人工确认。

## Dirty Worktree 处理

存在用户未提交修改 / USER_WORK / NEEDS_DECISION / 未验收内容时：

```text
STOP
  ↓
列出冲突文件
  ↓
说明原因
  ↓
保持 Git 状态不变
  ↓
等待人工决定
```

不得擅自提交。

## 敏感信息安全

扫描：API Key / Token / Password / Private Key / `.env` / `.key` / `.pem` / `secrets/`。
禁止把 secret 写入 Summary / Baseline / JSON / Git / 最终报告。
只允许输出 `present=true/false`，不输出 secret 值。

## Baseline 生成规则（仅 NEW_FINALIZATION）

1. 验收通过
2. 生成 Markdown
3. 生成 JSON
4. 现场计算 SHA256
5. 记录 Git commit
6. 记录 Git tag（如创建）
7. 回读验证
8. 确认无 secret
9. 进入 Git

Schema（与 KNOWLEDGE_OS 第二十八章一致）：

```yaml
baseline_id:
status:
created_at:
purpose:
scope:
external_state:
git:
  commit:
  tag:
validation:
files:
known_limitations:
security:
```

- 位置：`90_System/任务记录/<项目或阶段>/正式基线/Baseline-<yyyymmdd>.{md,json}`
- 外部文件（Vault 外）：`external_state: machine-local`，不得表述为跨机器可复现。

## Baseline Drift 规则

- **情况 A**：`HEAD == baseline.git.commit` 且关键文件 hash 全部一致 → `PASS`
- **情况 B**：`HEAD > baseline.git.commit`（后续发生新 commit）→ `BASELINE_STALE`
  - 说明：当前系统已超出该 Baseline；判断是否有新的已验收变更；**不自动覆盖旧 Baseline**。
- **情况 C**：关键文件 hash ≠ Baseline hash → `DRIFT`
  - 找出差异 → 判断是否属于已记录变更 → **不覆盖旧 Baseline** → 如需新稳定状态走 NEW_FINALIZATION / REBASELINE。
- **情况 D**：Baseline 文件 / Tag / Git commit 关系断裂（Tag 不存在、Tag 指向错误 commit、`baseline.git.commit` 与 Tag 不一致）→ `BASELINE_INTEGRITY_ERROR`，**不得自动修复**。
- **外部 machine-local 漂移**：`external_state: machine-local` 的外部文件 hash 变化，识别为"已知外部漂移"，**不是 Baseline corruption**；Baseline 原始 hash 保持不动。

## Tag 规则

- 格式：`baseline/<baseline_id>`
- 仅在：正式稳定里程碑 + Baseline 已完成 + Git commit 已稳定 + 验收通过 时创建。
- 已有项目验证模式：**绝对不创建重复 Tag**。

## Project Summary 规则

- 使用 `90_System/templates/项目总结验收报告模板.md`。
- 至少记录：项目背景 / 目标 / 最终架构 / 实施阶段 / 关键问题与根因 / 修复方案 / 关键文件与配置 / 安全边界 / 验收矩阵 / 已知限制 / 外部依赖 / Git / Baseline / Tag / AI 回顾规则 / 后续维护说明。
- 已有正式总结：**不得重复生成**，验证即可。

## Phase 规则

- 读取当前 Phase 状态，只允许 `PLANNED / ACTIVE / VALIDATING / BASELINED / CLOSED`。
- 不允许自动 `CLOSED`，只有人工确认后才能 CLOSED。
- 新项目验收完成可建议 `VALIDATING → BASELINED`；`BASELINED → CLOSED` 必须人工决定。

## 目录兼容

- 优先 `90_System/任务记录/<项目>/` 及项目已有目录。
- 新项目 Baseline：`<项目>/正式基线/`；项目总结：`<项目>/项目总结验收报告.md`。
- 项目已有专门任务目录时使用现有目录，不新建重复体系。

## Skill 不承担

不自动：修改项目代码、修复项目 bug、决定 Wiki 是否 stable、决定验收是否通过、关闭 Phase、push、创建 Git remote、解决历史记录冲突、移动历史文件、修改用户原始资料、清理 Git 工作树、覆盖 Baseline。

## 最终报告格式

```text
# Project Finalization Report

## Mode
NEW_FINALIZATION / EXISTING_BASELINE_VERIFY

## Project
...

## Phase
...

## Git
HEAD:
working_tree:
baseline_commit:
tag:

## Baseline
baseline_id:
status:
created_at:

## Validation
...

## Drift
...

## Actions
created:
modified:
committed:
tagged:

## Safety
secret_scan:
user_work:
ignored_files:
push:

## Result
PASS / DRIFT / BLOCKED / REBASELINE_REQUIRED
```

## 执行原则

> 把"已经完成的工作"安全、规范、可追溯地封版；先识别已有基线并只读验证，绝不重复创建。
