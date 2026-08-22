# Knowledge OS Gate 1：GitHub 上线前全仓库审计

## 1. 结论

```
GATE 1 = PASS (WITH WARNINGS)
READY FOR GITHUB PRIVATE REPOSITORY
```

- BLOCKER：0
- 真实 Secret：0（当前树 + 全 Git 历史 + 不可达对象 均 0）
- 严重私人资料：0（跟踪内容无电话/身份证/个人邮箱）
- 大文件无 GitHub 阻塞（最大可达 blob = 3.3MB main.js；可达历史 blob 合计 ~5.7MB）
- Git 历史无敏感泄露、无严重垃圾
- 可发布内容完全可控（push 只会携带 301 个跟踪文件 + 17 个 commit）
- 未创建 remote / 未 push / 未修改任何仓库内容

## 2. Git Repository 基础

| 项目 | 值 |
|---|---|
| HEAD | 86b25ae02bec3a0075d9460e06d91a7b4c3a16ff |
| 分支 | master（唯一） |
| commit 数 | 17（线性历史） |
| remote | 无（预期状态，不判错） |
| Tag | baseline/rc-codex-wecom-20260820 → 242f619 |
| RAG Baseline | bl-eval-20260817T162956（89.3%，STABLE） |
| working tree | 无 staged / modified / deleted；8 个未跟踪目录项（详见 §4） |

Tag 与 HEAD 关系：HEAD（86b25ae）是 Tag 提交（242f619）之后的 4 个 commit（242f619 → f9a1130 → 2fc85ed → 8fc7ef0 → 86b25ae），属于“Tag 为历史正式基线、HEAD 在其后继续演进”的合法情况。

## 3. 三边界定义

| 边界 | 内容 | 是否进 Git |
|---|---|---|
| A. Git 正式资产 | 20_Wiki / 30_Projects / 90_System（源码+配置+任务记录+模板）/ .agents/skills / 40_Outputs 正式审计证据 / 根文档 / .obsidian 配置 | 是 |
| B. 本地运行产物 | 向量库（database/）、模型缓存（cache/）、eval runs/baselines/diff、activity_log/review_records/.changelog_state、__pycache__、.pytest_cache、launcher.log、workspace.json/graph.json、.claudian | 否（已 gitignore） |
| C. 外部/machine-local/私人 | ~/.codex、~/.cc-connect、C:\cc-connect-mcp、Windows 用户环境变量（DEEPSEEK_API_KEY）、本机 BGE 模型路径、00_Inbox 私人 PDF | 否（不在 Vault 或未跟踪） |

## 4. 全仓库文件分类（磁盘 567 个文件，排除 .git）

| 状态 | 数量 | 说明 |
|---|---|---|
| Tracked | 301 | 见分类明细 |
| Untracked（未忽略） | 48 | 见 §5 |
| Ignored | 218 | 全部为运行产物/缓存/machine-local（见 §6） |

Tracked 分类明细（301）：
- 90_System：197（RAG 引擎源码+测试+配置、Control Center、任务记录、模板、prompts、scripts、interface）
- 20_Wiki：34（25 篇知识 + 9 .gitkeep）
- 30_Projects：21
- 40_Outputs：18（RAG Evaluation audit/governance/wiki_compilation 正式证据 11 + reviews 与四类输出 .gitkeep 7）
- 00_Inbox：8（2 个已处理 md 源 + 6 .gitkeep）
- 10_Sources：7（全部 .gitkeep，**没有任何真实 Source 文件被跟踪**）
- .agents/skills：3（knowledge-compiler / project-doc-maintainer / weekly-review）
- .obsidian：8（app/appearance/community-plugins/core-plugins.json + realclaudian 插件 4 文件）
- 根目录：5（AGENTS.md / README.md / HOME.md / CHANGELOG.md / .gitignore）

## 5. Untracked 且未忽略（48 个，不会被 push）

| 目录 | 数量 | 大小 | 内容与建议 |
|---|---|---|---|
| 00_Inbox | 33 | 39.4 MB | 个人笔记 PDF（含 29MB stm32笔记.note.pdf）。属私人原始资料 → **不进入 Git**，建议后续显式 gitignore |
| 10_Sources | 7 | 3.65 MB | FreeRTOS Reference Manual PDF(1.7MB)、FreeRTOS_Task_Notifications.html(1.2MB)、STM32 AN4776 PDF(712KB)、工具链 4 个文本/网页（≤64KB）。详见 §8 策略 |
| 40_Outputs | 7 | 0.07 MB | 每周复盘 2026/W33+W34（weekly-review.md/snapshot.json/insight.json 共 6 个）+ Gate 0 审计报告 → **建议纳入 Git**（正式复盘证据） |
| .agents | 1 | 8 KB | project-finalization/SKILL.md → **建议纳入 Git**（正式 Skill，Gate 0 已验收） |

## 6. .gitignore 审计

当前覆盖：.DS_Store/Thumbs.db/desktop.ini、.obsidian/workspace.json+mobile+cache+graph.json、.trash、*.tmp/*.temp/*.bak、.env/.env.*/*.key/*.pem/secrets/、.claudian/、90_System/rag/database/、cache/、*.bin、*.index、__pycache__、*.pyc、launcher.log、control_center/runtime/、activity_log.jsonl、review_records.json、.changelog_state.json、RAG Evaluation runs/baselines/diff/judge_variance/baseline.json/md/evaluation_state.json/latest*.json。

判定：
- 覆盖完整，所有不应进入 Git 的 runtime/cache/machine-local 均已忽略。
- `.pytest_cache/` 当前靠 pytest 自动生成的内层 `.gitignore`（内容 `*`）自忽略，实际生效（`git status --ignored` 可见）；建议在仓库 `.gitignore` 显式补一行 `.pytest_cache/` 使策略自文档化（WARNING，非阻塞）。
- `.obsidian/plugins/realclaudian/main.js`（3.3MB 第三方插件打包）已被跟踪，ignore 不影响已跟踪文件 → 见 §9 大文件。
- 未发现 `.gitignore` 排除任何核心资产（排除项全部为可重建/派生/运行时数据）。

## 7. 运行产物审计（40_Outputs/RAG Evaluation）

| 子目录 | 状态 | 性质 |
|---|---|---|
| audit/ | tracked | 正式审计证据（保留） |
| governance/ | tracked | 正式治理审计（保留） |
| wiki_compilation/ | tracked | 正式编译审计（保留） |
| runs/ | ignored | 运行产物（每次 benchmark 重新生成，可复现） |
| baselines/ | ignored | RAG eval 基线运行产物（bl-eval-* 可由 benchmark 复现） |
| diff/ judge_variance/ | ignored | 运行产物 |
| baseline.json/md、evaluation_state.json、latest*.json | ignored | 机器状态指针 |

判定：正式长期证据已纳管、运行产物已忽略——边界正确，未“整个目录全 ignore”。

## 8. Source 纳管策略（10_Sources）

现状：10_Sources 跟踪了 7 个 .gitkeep，**零真实 Source**；7 个未跟踪真实 Source 被 Wiki 的“资料来源”引用（如 `10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf`）。clone 后这些引用会失效。

建议规则（待人工确认，本次未自动纳入）：
- 小型文本/网页（≤100KB）：Obsidian-Git_GettingStarted.md(8KB)、README.md(8KB)、GettingStarted.html(2KB)、Microsoft_Install_WSL.html(64KB) → **建议纳入**（正式 Source 证据，体积小）
- 中型官方 PDF（<2MB）：FreeRTOS Reference Manual(1.7MB)、STM32 AN4776(712KB) → **可纳入**（GitHub 单文件上限 100MB，远低于；作为 Wiki 来源证据合理）或外部存储
- 大型/可重新获取：FreeRTOS_Task_Notifications.html(1.2MB，网页快照) → 可纳入或仅保留 URL
- 结论：总增量约 3.65MB，纳入不构成 GitHub 负担；是否纳入由你决定。

## 9. 大文件 / GitHub 可维护性

- 当前跟踪树：301 文件 ≈ 5.0 MB
- 可达历史全部 blob 合计：≈ 5.7 MB（357 个 blob）
- 最大可达 blob：`.obsidian/plugins/realclaudian/main.js` 3.3MB（第三方 vendored 插件，可接受；WARNING：可考虑从 Git 移除，由 Obsidian 社区插件市场重装）
- 其余可达 blob 均 ≤150KB
- 本地 .git 中有 ~67MB loose 不可达对象：来源是曾暂存/提交后移除的 00_Inbox 大 PDF（29MB stm32笔记等）。**不可达对象不会被 push**，仅为本机存储膨胀（WARNING：可 `git gc --prune=now` 清理，本次不做）
- 结论：**无 GitHub 阻塞**（远低于 GitHub 100MB/文件、1GB push 限制）

## 10. Git 历史垃圾 / 敏感内容审计

- 历史删除过的文件（`git log --diff-filter=D`）：仅 `.obsidian/graph.json`、`activity_log.jsonl`、`.changelog_state.json`、`.claudian/claudian-settings.json`、旧 .gitkeep/接口文档 —— 均为运行时/机器配置清理，非垃圾。
- 曾提交后移除的大 PDF（stm32笔记 29MB 等）**不在任何可达 commit 中**（`git log --all -- <path>` 为空），不会被 push。
- 无临时文件、无测试残留、无调试导出进入历史。

## 11. Secrets / Credentials 审计（Gate 1 最高优先级）

- **当前树扫描**（301 跟踪文件，含 12 类模式）：6 个命中，全部误报（vendored 插件 OAuth 通用代码、`os.environ.get("DEEPSEEK_API_KEY")` 读取语句）。真实 Secret = 0。
- **Git 历史扫描**（`git rev-list --objects --all` 全可达 blob 537 对象）：命中 0。
- **不可达对象扫描**（fsck 59 个 unreachable blob，含 29MB 大文件）：命中 0。
- **个人资料扫描**：7 个命中，全部误报（代码数值常量、`git@github.com` 格式示例）。无电话/身份证/个人邮箱。
- **env 文件/密钥文件**：Vault 内无 `.env` / `*.key` / `*.pem` / secrets 目录（gitignore 已覆盖，且磁盘扫描无此文件）。
- 结论：**Git 当前与历史均无真实 Secret 泄露**。

## 12. 90_System 完整性

- 核心源码/配置/测试/模板/任务记录全部 tracked；runtime（database/cache/activity_log 等）已忽略。
- 绝对路径引用 35 处，分类：
  - `config.yaml:57` reranker 模型路径 `C:/Users/陶权煜/.cache/modelscope/...` —— **machine-local 依赖写入核心配置**，另一台机器需 Bootstrap 调整（WARNING，Restore Matrix 项）
  - Baseline-20260820.json/md + 项目总结验收报告 —— machine-local 审计记录，已明确标注 external_state=machine-local，属“记录机器状态”而非“Git 资产依赖”，表达正确
  - static/index.html —— UI 文案示例路径（展示用，低风险）
  - 其余为插件/测试配置
- 文档未错误要求 Git 恢复 machine-local 文件（Baseline 明确 machine-local、不跨机复现）。

## 13. .agents/skills 审计

- 4 个正式 SKILL.md（knowledge-compiler / project-doc-maintainer / weekly-review / project-finalization），无临时文件、无密钥、无 runtime 数据、无绝对路径依赖。
- 3 个已 tracked；project-finalization 未跟踪（建议纳入）。
- Skill 应受 Git 版本控制（正式能力），结论明确。

## 14. Baseline / Tag / Commit 一致性

| 项 | 值 | 判定 |
|---|---|---|
| Tag baseline/rc-codex-wecom-20260820 | → 242f619 | ✓ 存在且指向正确 |
| Baseline-20260820.md/json git.commit | 242f619 | ✓ 与 Tag 一致 |
| HEAD | 86b25ae | Tag 后 4 个 commit，合法演进 |
| RAG Baseline bl-eval-20260817T162956 | 89.3% STABLE | Gate 0 复测一致（eval-20260822T180123 = 89.3%，delta 0.0） |
| Governance | passed | ✓ |
| Phase 3 | ACTIVE | 文档一致 |

结论：Baseline/Tag/Commit 状态可解释、一致。

## 15. Machine-local Baseline 审计（rc-codex-wecom-20260820）

- 与 JSON 基线（机器生成，权威）逐文件 SHA256 对比：**7/8 MATCH**。
- 唯一真实漂移：`~/.codex/config.toml`（Codex App 重写故障模式，基线文档已记录，不重建基线）。
- **Gate 0 遗留疑问已解决**：workspace_bindings.json 与 start-cc-connect.ps1 的“hash 差异”是 **Baseline-20260820.md 抄录笔误**（F44D→D44F、C0C→B0C），JSON 基线与当前文件一致。建议修正 MD 文档两处 hash（WARNING）。
- Git-reproducible vs Machine-local 边界：已明确分离——Vault 内 Git 资产可复现；外部 8 个文件属 machine-local，由 Bootstrap 负责。

## 16. GitHub Restore Matrix（clone 后可恢复性预审）

| 组件 | Git 纳管 | Clone 后可恢复 | 需要 Bootstrap | Machine-local |
|---|---|---|---|---|
| Vault 文档（根 README/AGENTS/HOME/CHANGELOG） | ✓ | ✓ | — | — |
| Wiki（20_Wiki） | ✓ | ✓ | — | — |
| Projects（30_Projects） | ✓ | ✓ | — | — |
| Skills（.agents/skills） | 3/4 | 部分（project-finalization 待纳入） | — | — |
| RAG 源码 + 测试 + 配置 | ✓ | ✓ | — | — |
| RAG index（main_vector_db） | ✗（ignored） | ✗ | ✓ 重建（update_index.py） | — |
| Python 3.14 | ✗ | ✗ | ✓ 安装 | 机器 |
| BGE embedding + reranker 模型 | ✗ | ✗ | ✓ 下载/缓存 + 改 config.yaml 路径 | 机器 |
| DeepSeek API Key | ✗ | ✗ | ✓ 环境变量 | 机器（HKCU） |
| Codex 配置（~/.codex） | ✗ | ✗ | ✓ | 机器 |
| MCP bridge（Documents/Codex） | ✗ | ✗ | ✓ 复制/安装 | 机器 |
| Windows Scheduler（3 个任务） | ✗ | ✗ | ✓ 注册脚本（已在 Git） | 机器 |
| cc-connect + WeCom 配置 | ✗ | ✗ | ✓ | 机器 |
| 10_Sources 真实文件 | 未纳管 | ✗（当前） | 待决策纳入 | — |
| 00_Inbox 私人 PDF | ✗ | ✗（预期） | 不恢复（私人资料） | — |

## 17. GitHub 安全发布模拟（不 push）

“如果现在 push 会携带什么”：
- 17 个 commit 全部历史 + 301 个跟踪文件（当前树 ~5.0MB，历史 blob 合计 ~5.7MB）
- **不会携带**：48 个未跟踪文件（00_Inbox PDF 39.4MB、10_Sources 3.65MB、weekly review + Gate 0 报告 + project-finalization skill）、218 个忽略文件、59 个不可达对象
- 发布内容可控、无 Secret、无大文件阻塞、无私人资料

## 18. Gate 0 遗留项复查

| 项 | 状态 |
|---|---|
| 4 个 weekly-review 测试 W33→W34 | 未修复（仍断言 W33）→ WARNING |
| knowledge.config.toml approval 配置 | 未添加 `default_tools_approval_mode="approve"` → WARNING |
| rc-codex hash 判定 | 已判定：MD 抄录笔误（JSON 基线正确，7/8 实际 MATCH）→ 已解决 |
| W34 snapshot system_errors=1 | 未重新生成（瞬时记录，非默认 Blocker）→ WARNING |

## 19. 建议（Gate 2 前，均不阻塞）

1. 纳入 Git：project-finalization/SKILL.md、每周复盘 W33/W34、Gate 0 审计报告（正式证据）
2. 10_Sources 纳管决策：建议纳入 7 个未跟踪 Source（总 ~3.65MB）或按 §8 规则选择
3. 00_Inbox：将私人 PDF 显式 gitignore（当前靠“不 add”兜底，建议确定性化）
4. .gitignore 补 `.pytest_cache/`
5. 修正 Baseline-20260820.md 两处 hash 笔误
6. 修复 4 个 weekly-review 测试断言（W33→W34）
7. knowledge.config.toml 添加 default_tools_approval_mode
8. config.yaml reranker 路径改为可配置（Bootstrap 项）
9. （可选）git gc 清理 ~67MB 不可达对象；评估 realclaudian main.js 是否移出 Git
10. （可选）重新生成 W34 快照清除瞬时 health error

## 20. 任务边界遵守

- 未创建 GitHub Repository / 未加 remote / 未 push / 未 commit / 未 tag / 未修改 Baseline
- 未修改 .gitignore / 未自动纳入 Source / 未删除任何文件 / 未重构
- 未修改任何 Git 跟踪内容；审计全部为只读命令
