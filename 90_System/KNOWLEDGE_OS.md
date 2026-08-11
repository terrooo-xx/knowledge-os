---
type: system
status: draft
domain: 系统规范
created: 2026-08-10
updated: 2026-08-10
---

# KNOWLEDGE_OS.md —— 知识库系统级架构与管理规范

> 本文档是知识库的**系统级上下文**和**管理宪法**，不是普通知识文档，也不是 README。
> 任何 AI Agent（尤其是 Codex）在对本知识库执行结构性操作（创建、修改、移动、删除、更新索引、更新 Wiki）之前，必须先阅读本文档。

## 一、文档定位

本文档描述知识库的完整运行规则：

- 这个知识库是什么；
- 知识库由哪些系统组成；
- 每一个一级、二级目录为什么存在；
- 每一种重要文件为什么存在；
- 哪些是源数据（Source of Truth），哪些是派生数据；
- 哪些目录由 AI 管理，哪些只能人工修改；
- 哪些内容可以自动生成，哪些操作必须经过人工审核；
- 知识从“导入 → 处理 → Wiki → RAG → 查询 → 更新”的完整生命周期；
- AI 在什么情况下应该修改、创建、移动文件、更新索引、更新 Wiki；
- AI 如何避免破坏知识库结构，如何判断文件归属；
- AI 如何处理冲突、重复、过时、待审核、无法确定归属的知识；
- 本架构文档自身的维护规则。

**规则关系**：本文档是知识库结构、AI 权限、数据生命周期相关规则的唯一系统级来源。根目录 `AGENTS.md`、`90_System/rag/AGENTS.md`、`.agents/skills/*`、`.agents/agents/*` 等只应**引用**本文档，不复制本文档内容，避免规则冲突。

## 二、知识库是什么（系统组成）

本知识库是个人嵌入式、机器人和无人机开发知识库，由以下子系统组成：

| 子系统               | 位置                                                   | 职责                     |
| ----------------- | ---------------------------------------------------- | ---------------------- |
| Inbox（原始资料入口）     | `00_Inbox/`                                          | 接收未经处理的原始资料，是知识导入的唯一入口 |
| Sources（来源与证据）    | `10_Sources/`                                        | 长期保留的数据手册、参考资料等原始证据    |
| LLM-Wiki（知识沉淀）    | `20_Wiki/` + `90_System/rag/scripts/wiki_compile.py` | 把资料编译成结构化、可持续维护的知识笔记   |
| RAG（检索系统）         | `90_System/rag/`                                     | 从原始资料和 Wiki 中检索、重排、回答  |
| Projects（项目文档）    | `30_Projects/`                                       | 具体项目的架构、模块、接口、决策、任务、问题 |
| Outputs / Reviews | `40_Outputs/` `50_Reviews/`                          | 对外输出、知识库检查与复盘报告        |
| AI Agent / Skill  | `.agents/`                                           | AI 可复用工作流定义            |
| Obsidian          | `.obsidian/`                                         | 本地笔记查看与编辑配置            |
| Control Center    | `90_System/control_center/`（阶段⑦ MVP 已实现）              | 人机协同控制面板（见第二十三章）        |
| Agent Interface  | `90_System/agent/`（阶段⑪-A）                            | 只读知识查询接口：Codex/Agent 经此查询，不直接访问 Wiki/Vector DB；MCP 接入规划中（阶段⑪-B） |

## 三、总体架构

```text
用户 / AI
   │
   ▼
00_Inbox（原始资料）
   │
   ▼
Ingestion / Processing（90_System/rag/scripts/inbox_processor.py + ingest_rag.py）
   ├── 文档解析（PDF / Markdown / TXT / HTML）
   ├── 分类（create_wiki / update_wiki / project_update / no_new_wiki / keep_raw）
   ├── Chunk（800 字，overlap 100）
   ├── Metadata（source / page / created_time / document_type / status）
   └── Embedding（BGE-small-zh-v1.5，写入向量库）
   │
   ▼
知识处理层
   ├── LLM-Wiki（wiki_compile.py → 20_Wiki/<领域>/ status: draft）
   ├── wiki_review.py（draft → reviewed → stable，人工确认）
   └── RAG 引擎（hybrid_query.py --store main：检索 main_vector_db 合并索引）
   │
   ▼
查询层（活动索引：main_vector_db = 20_Wiki + 30_Projects 合并）
   ├── Dense + BM25 混合检索 → reranker → evidence 评估
   ├── 证据充分 → LLM 回答（带来源）
   └── 证据不足 → Knowledge Gap 记录，不编造
   │
   ▼
AI / 用户
```

## 四、知识生命周期（以现有系统为准）

```text
原始资料（进入 00_Inbox）
   ↓
识别 / 解析（inbox_processor.py：只分析，不移动不删除原文）
   ↓
Processing（create_wiki → draft 建议；update_wiki → 更新建议；project_update → 30_Projects）
   ↓
审核（wiki_review.py：draft → reviewed → stable，默认禁止 draft → stable）
   ↓
Wiki（20_Wiki，frontmatter 状态：draft / reviewed / stable）
   ↓
RAG / Vector Index（update_index.py 增量索引，index_manifest.json 记录哈希）
   ↓
查询（hybrid_query.py --store main：main_vector_db 混合检索 → rerank → evidence）
   ↓
反馈 / 知识更新（新资料 → update_wiki 建议 / update_index --changed）
```

真实存在的知识状态：

| 状态 | 含义 | 存放位置 |
|---|---|---|
| `inbox` | 原始资料待处理 | `00_Inbox/` |
| `pending_review` | 已生成更新建议，待人工确认 | `90_System/任务记录/Wiki更新建议_*.md` |
| `draft` | AI 生成、未审核的 Wiki | `20_Wiki/<领域>/` |
| `reviewed` | 人工审核通过 | `20_Wiki/<领域>/` |
| `stable` | 长期有效、稳定知识 | `20_Wiki/<领域>/` |
| `resolved` | 已解决的知识缺口 | `90_System/rag/tests/knowledge_gaps.yaml` |
| `archived` | 归档保留 | `90_System/archive/` |

现状说明（以代码为准）：

- **draft 参与 RAG**：`update_index.py` 不按状态过滤，draft 会进入 `main_vector_db` 并被检索；`evidence.py` 把 draft/unknown 视为低可信度（不足时记 `knowledge_insufficient`），而不是直接排除。
- **状态变化不自动触发 RAG 更新**：修改 Wiki 或流转状态后，需手动运行 `update_index.py --changed` 才会重索引。
- 当前 20 篇 Wiki 全部为 `draft`，尚无 `reviewed` / `stable`。

## 五、目录职责表

### 一级目录

| 路径 | 类型 | 作用 | 内容类型 | 生命周期 | AI 权限 | 人工权限 |
|---|---|---|---|---|---|---|
| `00_Inbox/` | 工作区 | 原始资料唯一入口 | 原始资料（md/pdf/txt/html） | 临时，处理完保留原文 | READ_ONLY + 只允许新增文件；可分析处理 | 可写 |
| `10_Sources/` | 知识层 | 长期来源与证据 | 数据手册、资料原文 | 长期 | 可新增引用；不修改原文 | 可写 |
| `20_Wiki/` | 知识层 | 结构化长期知识 | Wiki 笔记 | 长期 | CONTROLLED_WRITE：只生成 draft；禁止覆盖 reviewed/stable | 审核、改状态 |
| `30_Projects/` | 知识层 | 项目文档 | 架构/模块/接口/决策/任务/问题 | 项目生命周期 | CONTROLLED_WRITE：只生成项目 draft | 审核 |
| `40_Outputs/` | 输出层 | 对外输出 | 学习总结/技术方案/报告 | 长期 | 可生成候选 | 审核 |
| `50_Reviews/` | 输出层 | 检查与复盘 | 复盘报告/知识缺口/过期检查 | 定期 | 可生成报告 | 审核 |
| `90_System/` | 系统层 | 系统运行 | 规范/脚本/模板/提示词/日志/归档/RAG | 长期 | 见文件级权限，谨慎 | 可写 |
| `.agents/` | 系统层 | AI Agent 与 Skill 定义 | agent / skill 规范 | 长期 | REVIEW_REQUIRED | 可写 |
| `.obsidian/` | 配置 | Obsidian 本地配置 | json | 本地 | NO_TOUCH | 可写 |
| `.claudian/` | 本地数据 | 本地会话数据 | 会话 | 临时 | NO_TOUCH | 本地 |
| `.git/` | 版本 | Git 版本库 | git 对象 | 长期 | NO_TOUCH | 可管理 |

### 重要二级目录

| 路径                                                                                | 作用                                                                    |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `00_Inbox/AI聊天记录/`                                                                | AI 对话原始记录入口                                                           |
| `00_Inbox/临时笔记/`                                                                  | 临时想法与未整理笔记                                                            |
| `00_Inbox/图片截图/`                                                                  | 截图类原始资料                                                               |
| `00_Inbox/待处理文件/`                                                                 | 等待知识处理的主要文件                                                           |
| `00_Inbox/待处理文件/个人笔记/`                                                              | 用户导入知识库的原始资料（`.note.pdf` 等，Source；AI 只读分析，不修改）                 |
| `00_Inbox/网页剪藏/`                                                                  | 网页剪藏资料                                                                |
| `00_Inbox/行业情报/`                                                                  | 行业动态类资料                                                               |
| `10_Sources/<领域>/`                                                                | 按领域存放长期来源（FreeRTOS/ROS2/STM32/控制理论/数据手册/无人机飞控/移动底盘）                   |
| `20_Wiki/01_计算机基础/` ~ `20_Wiki/09_ROS2/`                                          | 按领域存放 Wiki 知识，不按状态建目录                                                 |
| `30_Projects/<项目>/architecture/ modules/ interfaces/ decisions/ tasks/ problems/` | 项目六类文档                                                                |
| `30_Projects/移动底盘控制器/硬件选型/ 项目适配/`                                                 | 项目专属子目录（选型、场景适配）                                                      |
| `40_Outputs/学习总结/ 技术方案/ 项目报告/ 对外材料/`                                              | 四类对外输出                                                                |
| `50_Reviews/每周复盘/ 知识缺口/ 过期内容检查/`                                                  | 三类检查报告                                                                |
| `90_System/archive/`                                                              | 归档目录（替代删除）                                                            |
| `90_System/logs/`                                                                 | 系统日志                                                                  |
| `90_System/prompts/`                                                              | 提示词模板                                                                 |
| `90_System/schemas/`                                                              | 数据结构定义（预留）                                                            |
| `90_System/scripts/`                                                              | PowerShell 自动化脚本                                                      |
| `90_System/templates/`                                                            | 笔记模板                                                                  |
| `90_System/任务记录/`                                                                 | AI 任务处理记录与更新建议                                                        |
| `90_System/rag/`                                                                  | RAG + LLM-Wiki 引擎（代码、配置、测试）                                           |
| `90_System/rag/database/`                                                         | 向量库与索引清单（派生数据，gitignored）                                             |
| `90_System/rag/cache/`                                                            | 模型缓存（派生数据，gitignored）                                                 |
| `90_System/control_center/`                                                     | 人机协同管理界面（server.py / service.py / static / activity_log.jsonl，阶段⑦）；支持 Windows 桌面一键启动（start_control_center.bat / create_desktop_shortcut.bat，阶段⑩.5）     |
| `90_System/agent/`                                                            | Agent Knowledge Interface（knowledge_service.py / knowledge_cli.py / README.md，只读，阶段⑪-A）  |
| `.agents/agents/`                                                                 | Agent 工作流定义（ingest/retrieval/review/wiki_compile）                     |
| `.agents/skills/`                                                                 | Codex Skills（knowledge-compiler/project-doc-maintainer/weekly-review） |

## 六、文件分类体系

所有文件统一归属以下类别，AI 按类别决定对待方式：

| 类别 | 说明 | AI 对待方式 |
|---|---|---|
| `SYSTEM` | 系统级规范与入口文档 | 高风险管理，改动需记录 |
| `CONFIG` | 配置文件（如 `config.yaml`） | 谨慎修改，改前确认影响 |
| `POLICY` | AI 行为规则（AGENTS.md / SKILL.md） | 高风险，不能随意修改 |
| `KNOWLEDGE` | 普通知识笔记 | 可生成 draft，禁止覆盖已审核 |
| `WIKI` | Wiki 笔记（frontmatter 有 status） | 只生成 draft，状态由人改 |
| `SOURCE` | 原始资料 | 尽量不修改原始内容 |
| `WORKFLOW` | 工作流定义（Agent / Skill） | 谨慎修改 |
| `INDEX` | 索引数据（index_manifest.json） | 可重新生成 |
| `METADATA` | 元数据 | 随源数据重建 |
| `DERIVED` | 程序生成数据（向量库） | 不人工编辑，通过源数据重新生成 |
| `CACHE` | 缓存 | 可删除重建，不属于核心知识 |
| `CODE` | 程序代码（.py / .ps1） | AI 可修改但必须经过测试 |
| `TEST` | 测试 | 随代码修改同步更新 |
| `LOG` | 日志与任务记录 | 追加，不覆盖历史 |
| `TEMP` | 临时文件 | 可清理 |
| `ARCHIVE` | 归档文件 | 只读保留 |
## 七、重要文件说明

### 根目录

| 文件 | 类型 | 用途 | 维护者 | AI 修改权限 | 风险 |
|---|---|---|---|---|---|
| `AGENTS.md` | POLICY | 根级 AI 行为规则 | 用户 | REVIEW_REQUIRED | 高 |
| `KNOWLEDGE_OS.md`（本文档，位于 90_System/） | SYSTEM | 系统级架构与管理规范，唯一入口 | 用户 + AI | REVIEW_REQUIRED（结构性变更后必须同步更新） | 高 |
| `README.md` | KNOWLEDGE | 人类入口说明 | 用户 + AI | SAFE_WRITE（小幅更新） | 低 |
| `HOME.md` | KNOWLEDGE | Obsidian 首页 | 用户 + AI | SAFE_WRITE | 低 |
| `interfaces.md` | KNOWLEDGE | 接口总览（当前为空，待补充） | 用户 | SAFE_WRITE（按需补充） | 低 |
| `CHANGELOG.md` | DERIVED | 变更记录，由 `update_changelog.ps1` 自动维护 | 脚本 | NO_TOUCH（人工不手写，交给脚本） | 低 |
| `.gitignore` | CONFIG | 忽略派生数据与本地配置 | 用户 | REVIEW_REQUIRED | 中 |

### 90_System/rag（RAG + LLM-Wiki 引擎）

| 文件 | 类型 | 用途 | 输入 | 输出 | AI 修改权限 |
|---|---|---|---|---|---|
| `README.md` | KNOWLEDGE | RAG 引擎说明 | - | - | SAFE_WRITE |
| `AGENTS.md` | POLICY | RAG 引擎规则 | - | - | REVIEW_REQUIRED |
| `config.yaml` | CONFIG | RAG 配置（路径/分块/embedding/检索/reranker/LLM） | - | - | CONTROLLED_WRITE（改路径需同步本规范） |
| `requirements.txt` | CONFIG | Python 依赖 | - | - | CONTROLLED_WRITE |
| `scripts/ingest_rag.py` | CODE | 默认 `--target main` 摄取 20_Wiki + 30_Projects → main_vector_db（生产）；`--target raw/wiki` 为可选路径 | 20_Wiki/30_Projects（main）或 00_Inbox（raw） | main_vector_db / raw_vector_db / wiki_vector_db + metadata | CONTROLLED_WRITE（必须过测试） |
| `scripts/update_index.py` | CODE | 20_Wiki + 30_Projects → main_vector_db（默认活动索引）；`--target wiki` 为可选 | 20_Wiki/30_Projects | main_vector_db + index_manifest.json | CONTROLLED_WRITE |
| `scripts/hybrid_query.py` | CODE | 混合检索 + 重排 + 回答（默认 `--store main`） | 用户问题 | 回答 / evidence / gap | CONTROLLED_WRITE |
| `scripts/inbox_processor.py` | CODE | Inbox 分析 → 建议 | 00_Inbox 文件 | 任务记录日志 / draft | CONTROLLED_WRITE |
| `scripts/wiki_compile.py` | CODE | 编译 Wiki draft / 更新建议 / 项目 draft（`--action create/update/project --file`） | 00_Inbox 源资料 | 20_Wiki draft 或 任务记录建议 | CONTROLLED_WRITE |
| `scripts/wiki_review.py` | CODE | Wiki 状态流转（人工） | draft/reviewed | reviewed/stable | REVIEW_REQUIRED（执行者应是用户或经用户确认的 AI） |
| `scripts/reranker.py` | CODE | 重排工具 | chunks | 重排结果 | CONTROLLED_WRITE |
| `rag_engine/*.py` | CODE | 引擎模块（indexing/retrieval/evidence/gaps/wiki/wiki_compiler 等） | - | - | CONTROLLED_WRITE |
| `llm/*.py` | CODE | LLM 适配器（deepseek/openai/ollama/mock） | question + context | 回答 | CONTROLLED_WRITE |
| `database/index_manifest.json` | INDEX | 增量索引清单（文档哈希） | 文档 | 变化检测 | NO_TOUCH（由脚本重建） |
| `database/main_vector_db/records.jsonl` | DERIVED | 活动合并索引（20_Wiki + 30_Projects） | chunks + embeddings | 检索 | NO_TOUCH（可重建） |
| `database/raw_vector_db/`、`database/wiki_vector_db/` | DERIVED | 可选索引路径，当前为空 | - | - | NO_TOUCH（可重建） |
| `tests/*.py` | TEST | 引擎测试 | - | - | CONTROLLED_WRITE（改代码必改测试） |
| `tests/knowledge_gaps.yaml` | LOG | 知识缺口记录 | 查询 | 缺口条目 | CONTROLLED_WRITE（由查询流程追加） |
| `cache/` | CACHE | 模型缓存 | - | - | NO_TOUCH（可删除重建） |

### 90_System 其他

| 文件 | 类型 | 用途 | AI 修改权限 |
|---|---|---|---|
| `scripts/update_changelog.ps1` | CODE | CHANGELOG 自动维护（git pre-commit 触发） | CONTROLLED_WRITE |
| `scripts/knowledge_os_check.ps1` | CODE | 架构漂移检测（见第二十章），汇总 RAG Health | CONTROLLED_WRITE |
| `scripts/rag_health_check.py` | CODE | RAG 索引完整性只读健康检查（records/manifest/NUL/重复/orphan/一致性/gaps） | CONTROLLED_WRITE（默认只读运行） |
| `scripts/wiki_health_check.py` | CODE | Wiki frontmatter/status/source 只读健康检查 | CONTROLLED_WRITE（默认只读运行） |
| `control_center/server.py` | CODE | 本地 Control Center HTTP 服务（localhost:8765，stdlib http.server） | CONTROLLED_WRITE |
| `control_center/service.py` | CODE | Action 模型 / 幂等执行 / Activity Log / Health 聚合（调用现有 Wiki/Gap 函数） | CONTROLLED_WRITE |
| `control_center/activity_log.jsonl` | LOG | 人工决策审计日志（追加式） | SAFE_WRITE（追加） |
| `agent/knowledge_service.py` | CODE | Agent 只读知识查询接口（封装 retrieval→evidence→judge） | CONTROLLED_WRITE（只读运行） |
| `agent/knowledge_cli.py` | CODE | Agent 接口 CLI（`python 90_System/agent/knowledge_cli.py "问题"`） | CONTROLLED_WRITE |
| `阶段06/07/08_*.md` | SYSTEM | 各阶段评估与稳定化报告（status: draft） | REVIEW_REQUIRED |
| `prompts/rag_answer.md` | WORKFLOW | RAG 回答提示词 | CONTROLLED_WRITE |
| `prompts/wiki_compile.md` | WORKFLOW | Wiki 编译提示词 | CONTROLLED_WRITE |
| `prompts/处理单篇资料.md` 等 | WORKFLOW | 各类任务提示词 | CONTROLLED_WRITE |
| `templates/*.md` | WORKFLOW | 笔记模板（知识/任务/问题/复盘/决策/功能模块） | CONTROLLED_WRITE |
| `任务记录/*.md` | LOG | AI 任务处理记录与更新建议 | SAFE_WRITE（追加，不覆盖历史） |
| `archive/` | ARCHIVE | 归档文件 | SAFE_WRITE（只移动进来，不删除） |

### .agents

| 文件                             | 类型       | 用途           | AI 修改权限         |
| ------------------------------ | -------- | ------------ | --------------- |
| `agents/ingest_agent.md`       | WORKFLOW | 摄取工作流定义      | REVIEW_REQUIRED |
| `agents/retrieval_agent.md`    | WORKFLOW | 检索工作流定义      | REVIEW_REQUIRED |
| `agents/review_agent.md`       | WORKFLOW | 审核工作流定义      | REVIEW_REQUIRED |
| `agents/wiki_compile_agent.md` | WORKFLOW | Wiki 编译工作流定义 | REVIEW_REQUIRED |
| `skills/*/SKILL.md`            | WORKFLOW | Codex 可复用技能  | REVIEW_REQUIRED |

## 八、源数据（Source of Truth）与派生数据

### 数据五分类

| 类别 | 定义 | 典型内容 | AI 处理 |
|---|---|---|---|
| `Source`（源数据） | 有外部原始来源、不可再生的证据 | `00_Inbox` 原始资料、`10_Sources`、`个人笔记`（含 `.note.pdf`）、外部导入文件（PDF/图片/附件） | 只读；只允许向 `00_Inbox` **新增**，不修改/删除/覆盖原文 |
| `Derived`（派生数据） | 由源数据或知识处理程序生成，可重建 | RAG chunk、embedding、`database/` 向量库、`cache/`、`index_manifest.json`、`CHANGELOG.md`、AI 生成的 draft Wiki / 项目文档 | 不人工编辑；修改源数据后通过脚本重新生成 |
| `Knowledge Asset`（已审核知识） | 已通过人工审核的知识资产，不是原始证据 | `reviewed` / `stable` Wiki、人工确认的项目正式文档 | AI 只读；修改必须人工审核 |
| `System`（系统数据） | 知识库运行所需的规则、配置与代码 | `AGENTS.md`、`KNOWLEDGE_OS.md`、`config.yaml`、脚本、模板、Skill/Agent 定义 | 高风险修改，见第九章风险等级 |
| `Temporary`（临时数据） | 短期存在，可清理 | 日志、`__pycache__`、`*.pyc`、临时文件 | 可清理 |

### 逐项判定（本阶段审查结论）

- **Inbox 中经过 AI 处理的文件**：仍是 `Source`。处理只产生派生输出（draft、更新建议），不改变原文，处理不改变其源数据身份。
- **draft Wiki**：`Derived`，由源资料编译而来、未审核；不是 Source。
- **reviewed / stable Wiki**：`Knowledge Asset`；frontmatter 的 `source` 指向其来源，但笔记本身不是原始证据。
- **项目 architecture/modules 文档**：人工编写、已审核的为 `Knowledge Asset`；AI 生成未审核的为 `Derived`（draft）。
- **AI 生成的项目文档**：默认 `Derived`（draft），人工审核后成为项目 `Knowledge Asset`。
- **外部导入 PDF 的原始文件**：`Source`（无论是否被解析或引用）。
- **`.note.pdf`**：`Source`（个人原始笔记，用户导入知识库的原始资料）；其文本需转写/OCR 后才能进入 RAG。已确认位置：`00_Inbox/待处理文件/个人笔记/`。
- **Obsidian note 与普通 Markdown**：是同一文件。本库所有 `.md` 笔记即 Obsidian 笔记；Obsidian 只是查看/编辑工具，不产生独立数据。

### 规则

- **源数据**：AI 不修改原文，只允许向 `00_Inbox` **新增**文件。
- **派生数据**：不人工编辑；修改源数据后通过脚本重新生成（如 `update_index.py --changed`）。
- **AI 禁止直接修改**：Embedding、Vector DB、Cache、Index、`CHANGELOG.md`。
- **修改正确姿势**：修改源数据 → 重新生成派生数据。
- **不得把“所有 Markdown”都当作 Source**：只有外部导入的原始资料属于 Source；AI 生成的 Markdown 属于 Derived，人工审核后的属于 Knowledge Asset。

## 九、AI 权限模型

| 权限 | 含义 | 典型目录/文件 |
|---|---|---|
| `READ_ONLY` | 可读，不能修改 | `00_Inbox` 原文、`10_Sources`、`个人笔记`、向量库 |
| `SAFE_WRITE` | 可创建、可修改、可移动 | `40_Outputs`、`50_Reviews`、`任务记录`（追加） |
| `CONTROLLED_WRITE` | 可修改，但必须符合规则并验证 | `20_Wiki`（只生成 draft）、RAG 脚本、模板 |
| `REVIEW_REQUIRED` | 可生成候选修改，不能直接生效 | `AGENTS.md`、`.agents/*`、Knowledge OS 文档、`wiki_review.py` 状态流转 |
| `NO_TOUCH` | 禁止自动修改 | `.obsidian/`、`.git/`、`database/`、`cache/`、`CHANGELOG.md` |

### 覆盖检查（本阶段审查结论）

五级权限已覆盖全部重要操作对象：Inbox（READ_ONLY + 新增）、Sources / 个人笔记（READ_ONLY）、Wiki（CONTROLLED_WRITE，只生成 draft）、Projects（CONTROLLED_WRITE）、Outputs / Reviews（SAFE_WRITE）、任务记录（SAFE_WRITE 追加）、RAG 脚本与配置（CONTROLLED_WRITE）、knowledge_gaps.yaml（CONTROLLED_WRITE 追加）、AGENTS.md / Skills / Agents / KNOWLEDGE_OS（REVIEW_REQUIRED）、CHANGELOG / 向量库 / 缓存 / `.git` / `.obsidian`（NO_TOUCH）。

### 修改风险等级（LOW / MEDIUM / HIGH / CRITICAL）

| 风险等级 | 定义 | 典型操作 | 对应权限 |
|---|---|---|---|
| `LOW` | 可逆、低影响 | 追加任务记录、整理临时文件、重建缓存 | SAFE_WRITE |
| `MEDIUM` | 影响局部功能 | 生成 draft Wiki、修改模板/提示词/配置、脚本小改 | CONTROLLED_WRITE |
| `HIGH` | 影响系统运行或核心知识 | 修改 RAG 核心代码（必须过测试）、修改 KNOWLEDGE_OS / AGENTS / Skill / Agent、批量修改文档 | CONTROLLED_WRITE + 测试 / REVIEW_REQUIRED |
| `CRITICAL` | 不可逆或破坏性 | 删除知识、覆盖 reviewed/stable、移动/重命名目录、修改权限模型、改 `.git` / `.obsidian`、改 Source of Truth | REVIEW_REQUIRED / NO_TOUCH |

判定顺序：先定风险等级 → 再定权限等级 → 再执行。

## 十、人工审核边界

### 可以自动执行

- Inbox 文件解析与分类（inbox_processor.py，只写建议不写原文）；
- metadata 提取、chunk、embedding、索引更新（`update_index.py`）；
- 生成 `20_Wiki` 的 `status: draft` 笔记（wiki_compile.py）；
- 生成更新建议到 `90_System/任务记录/`；
- 检索、重排、回答、Knowledge Gap 记录；
- 临时文件整理、cache 重建、已批准知识的索引更新。

### 必须人工审核

- 删除知识或归档 `90_System/archive`；
- 合并冲突知识、改变核心 Wiki 结论；
- 修改 `reviewed` / `stable` 笔记；
- 修改系统架构、AI Policy、`AGENTS.md`、Knowledge OS 文档；
- 修改知识库目录结构、大规模移动/重命名文件；
- 修改权限模型、workflow、核心数据库结构；
- `draft → reviewed → stable` 状态流转（`wiki_review.py` 由人执行或经人确认）。

## 十一、AI 决策规则

**文件归属不确定时：**

```text
不知道文件放哪里
  → 不要随便创建目录
  → 查 KNOWLEDGE_OS.md 目录职责表
  → 仍无法判断 → 进入 review / pending → 请求人工决定
```

**发现重复知识时：**

```text
发现重复/近义 → 不直接删除
  → 比较来源、时间、可信度
  → 建立候选合并 → 需要人工确认时进入 review
```

**Wiki 与原始资料冲突时：**

```text
发现冲突 → 不自动覆盖
  → 标记 conflict，记录双方来源
  → 等待人工审核
```

**资料过时或无法验证时：**

```text
无法验证 → 标记“待验证” → 保持 draft
  → 不删除旧结论，增加版本差异/适用条件/争议说明
```

## 十二、AI 禁止操作

1. 不得随意删除知识、目录或文件（只能移动到 `90_System/archive`）；
2. 不得为了方便创建重复目录或 `xxx_final / xxx_v2 / xxx_new` 类文件；
3. 不得修改 Source of Truth（`00_Inbox` / `10_Sources` / `个人笔记` / 外部导入文件）；
4. 不得直接修改 Embedding、手工修改 Vector DB；
5. 不得绕过审核机制（如用 `--force` 覆盖 reviewed/stable）；
6. 不得自行改变知识状态（draft/reviewed/stable 流转必须人工确认）；
7. 不得因为检索结果不理想就擅自重构整个 RAG；
8. 不得修改系统级 Policy / AGENTS.md 而不检查影响、不记录；
9. 不得将临时数据当作长期知识；
10. 不得把未经审核的信息写入稳定 Wiki；
11. 不得为了“修复”一个问题而大范围破坏现有架构；
12. 不得在知识库中保存 API Key、Token、密码或其他密钥（一律从环境变量读取）。

## 十三、目录创建规则

原则：**默认不创建**。

只有同时满足以下条件才允许创建新目录：

```text
现有目录无法合理承载
+ 新目录具有长期稳定职责
+ 不会与已有目录重复
```

创建后必须同步：

```text
创建目录 → 更新 KNOWLEDGE_OS.md（职责表 + 结构地图）→ 定义 AI 权限 → 定义生命周期
```

## 十四、文件创建规则

AI 创建文件前必须判断：

- 是否已存在类似文件？是否应更新已有文件？
- 是否属于长期文件？还是只应进入 `00_Inbox` / `90_System/任务记录`？
- 应属于哪个目录？是否需加入索引（RAG）？
- 是否需更新架构文档或 CHANGELOG？

禁止制造 `xxx_final.md / xxx_new.md / xxx_v2.md / xxx_new_final.md` 这类失控文件。

## 十五、文档规范

- **Markdown 文档**：统一标题层级（`#` 一级、`##` 二级）、frontmatter（type/status/domain/created/updated/sources）、中文标题、完整句子、内部链接优先。
- **系统文档**（架构/规则/流程/设计/决策/规范）：放 `90_System/` 或 `30_Projects/<项目>/architecture|decisions`。
- **知识文档**（事实/概念/经验/技术知识）：放 `20_Wiki/<领域>/`，用知识笔记模板。
- **AI 工作文档**（任务/review/workflow/decision/logs）：放 `90_System/任务记录/`。
- 四类文档不得混淆；通用原理链接 `20_Wiki`，不在项目文档中重复。

## 十六、命名规范

- **目录**：`NN_领域`（如 `03_STM32`）或语义明确的中文名（如 `硬件选型`）；不按状态建目录。
- **Wiki 文件**：用主题名（如 `STM32-DMA-配置与使用.md`），不用 PDF 文件名或“new/temp/final”后缀。
- **Python**：snake_case（已有 `rag_engine/*.py`、`scripts/*.py`）。
- **PowerShell**：snake_case（已有 `update_changelog.ps1`）。
- **JSON/YAML**：snake_case 或 kebab-case，保持现有风格（`index_manifest.json`、`knowledge_gaps.yaml`）。
- **临时文件**：加 `tmp` 前缀或放系统临时目录，禁止用 `test2 / old / backup` 作为长期名称。

## 十七、规则优先级

规则冲突时按以下顺序裁决（结合现有工程实际确定）：

```text
1. 系统安全边界（不删除原文、不覆盖已审核、不泄露密钥、不改 .git/.obsidian）
2. Knowledge OS 核心规则（本文档）
3. 根目录 AGENTS.md
4. 90_System/rag/AGENTS.md
5. 具体 Skill / Agent 工作流
6. 任务临时要求
```

即：**任务临时要求不得覆盖系统安全边界和 Knowledge OS 核心规则。**

## 十八、架构文档自身的维护规则

Knowledge OS 文档本身属于知识库，结构变化时必须同步更新：

- 新增目录 → 更新目录职责表 + 结构地图 + 权限 + 生命周期；
- 删除/合并目录 → 删除对应定义，检查引用（Agent / Script / RAG 配置）；
- 修改 workflow → 更新生命周期说明 + AI 行为规则；
- 修改文件分类 / 权限模型 → 更新对应章节；
- 每次更新后修改 `updated` 字段；本文件当前为 `draft`，由人工审核后升级。

## 十九、架构漂移检测（knowledge_os_check）

`90_System/scripts/knowledge_os_check.ps1` 用于检测“文档描述”与“实际结构”的漂移：

- 扫描实际一级目录与重要文件；
- 与本文档记录的规范结构比较；
- 检测：未记录目录、重要文件缺失、重要二级目录缺失、空知识目录、Inbox 待处理堆积、派生数据存在性、Git 未提交变更；
- 输出 `PASS` / `WARNING` / `ERROR` 与汇总。

运行方式：

```powershell
powershell -ExecutionPolicy Bypass -File 90_System/scripts/knowledge_os_check.ps1
```

### 健康检查职责边界

- `knowledge_os_check.ps1` 只负责**架构一致性**（文档 vs 实际结构），并汇总 `rag_health_check.py` 结果。
- `rag_health_check.py` 负责 **RAG 索引完整性**（records/manifest/NUL/重复/orphan/一致性/gaps），默认只读。
- `wiki_health_check.py` 负责 **Wiki frontmatter/status/source** 只读检查，不改变状态。
- RAG 功能正确性由 `90_System/rag/tests/*` 负责；Wiki 状态流转由 `wiki_review.py` 及对应测试负责；Workflow 正确性由 Skill/Agent 流程负责。
- 健康检查默认只读；未来的 `--repair` / `--rebuild` 必须作为独立功能，不混入检查。

## 二十、AI 进入知识库后的标准流程

任何 AI Agent 第一次进入知识库时：

```text
1. 找到 90_System/KNOWLEDGE_OS.md
2. 阅读系统级架构（本文档）
3. 阅读 AI 管理规则（权限 / 审核边界 / 禁止操作）
4. 判断任务涉及哪些目录
5. 阅读相关目录职责与文件规则
6. 再开始执行任务
```

禁止“进入项目 → 直接修改文件”。

## 二十一、AI 任务执行流程

```text
任务输入
  → 识别任务类型
  → 定位相关知识域
  → 读取 Knowledge OS 与相关目录规则
  → 判断权限
  → 执行 / 生成候选修改
  → 验证
  → 更新索引（如涉及 Wiki/资料变更）
  → 更新 Wiki / RAG
  → 更新架构文档（如涉及结构变化）
  → 记录结果到 90_System/任务记录/
```

## 二十二、与 LLM-Wiki / RAG / Inbox / Obsidian 的关系

```text
Knowledge OS（本文档：定义知识库如何工作）
   ├── Inbox（接收新资料）
   ├── Ingestion（解析、分类、chunk、embedding）
   ├── LLM-Wiki（沉淀稳定、结构化知识）
   ├── RAG（从原始/长尾资料检索）
   ├── Vector DB（语义检索索引，派生数据）
   ├── Agent / Skill（执行工作流）
   └── Obsidian（人机查看与编辑）
```

职责边界：

- **LLM-Wiki**：沉淀稳定、结构化、可持续维护的知识（`20_Wiki`）。
- **RAG**：从原始 / 长尾 / 未完全结构化知识中检索信息（`90_System/rag`）。
- **Vector DB**：提供语义检索索引（派生，可重建）。活动索引为 `main_vector_db`（20_Wiki + 30_Projects 合并）；`raw_vector_db` / `wiki_vector_db` 为可选路径（当前为空）。
- **Inbox**：接收新资料（源数据）。
- **Obsidian**：本地查看与编辑，不做结构管理。

## 二十三、Control Center 管理边界（Status: ACTIVE，阶段⑦ MVP 已实现）

**Status: ACTIVE（第一版）** —— Control Center 已作为本地人机协同控制面板实现（`90_System/control_center/`，`python server.py` → http://127.0.0.1:8765，Python 标准库 http.server，无新增依赖）。审核、approve、reject、resolve、ignore 等人工决策通过 UI → API → service 调用现有 Knowledge OS 函数（`wiki_review.set_status` / `gaps.resolve_gap` / health check），**不复制 Wiki 状态逻辑、不直接修改 Markdown 或 Vector DB**。

未来 Control Center 的定位是 **Knowledge OS 的人机协同控制面板**，不是另一个独立知识系统：

```text
用户 → Control Center → Knowledge OS Workflow → AI Agent → Wiki / RAG / Inbox
```

规划统一管理：Inbox、Review、Approve、Resolve、Conflict、Wiki 状态、AI Task、Workflow、错误、系统状态、架构健康度。实现时必须与本规范保持一致，不新增独立知识系统。

## 二十四、知识库结构地图（实际结构）

```text
个人工程知识库/
├── .agents/                     # AI Agent 与 Skill 定义
│   ├── agents/                  # ingest / retrieval / review / wiki_compile
│   └── skills/                  # knowledge-compiler / project-doc-maintainer / weekly-review
├── .obsidian/                   # Obsidian 配置（本地）
├── 00_Inbox/                    # 原始资料入口
│   ├── AI聊天记录/ 临时笔记/ 图片截图/ 网页剪藏/ 行业情报/
│   └── 待处理文件/（含 个人笔记/：用户导入知识库的原始资料，.note.pdf 为主，Source）
├── 10_Sources/                  # 长期来源（FreeRTOS/ROS2/STM32/控制理论/数据手册/无人机飞控/移动底盘）
├── 20_Wiki/                     # 长期知识（01_计算机基础 … 09_ROS2）
├── 30_Projects/                 # 项目文档
│   ├── 无人机飞控/              # architecture/ modules/ interfaces/ decisions/ tasks/ problems/
│   └── 移动底盘控制器/          # 同左 + 硬件选型/ 项目适配/
├── 40_Outputs/                  # 学习总结/ 技术方案/ 项目报告/ 对外材料
├── 50_Reviews/                  # 每周复盘/ 知识缺口/ 过期内容检查
├── 90_System/                   # 系统运行
│   ├── archive/ logs/ prompts/ schemas/ scripts/ templates/ 任务记录/
│   ├── KNOWLEDGE_OS.md          # 本文档（系统级唯一入口）
│   ├── control_center/          # 人机协同管理 UI/API（阶段⑦）
│   ├── agent/                   # Agent 只读知识查询接口（阶段⑪-A）
│   └── rag/                     # RAG + LLM-Wiki 引擎
│       ├── rag_engine/ llm/ scripts/ tests/
│       └── database/ cache/     # 派生数据，gitignored
├── 00_Inbox/待处理文件/个人笔记/  # 个人学习原始笔记（.note.pdf 为主，用户 2026-08-10 移入，归属待确认）
├── AGENTS.md / README.md / HOME.md / CHANGELOG.md / interfaces.md / .gitignore
```

## 二十五、文件重要性等级

| 等级 | 说明 | 示例 | 修改要求 |
|---|---|---|---|
| L0 | 系统核心 | KNOWLEDGE_OS.md、AGENTS.md、rag 核心脚本 | 必须谨慎、必须验证、必须记录 |
| L1 | 系统配置 | config.yaml、.gitignore、requirements.txt | 修改前确认影响 |
| L2 | 核心知识 | reviewed/stable Wiki、项目正式文档 | 人工审核 |
| L3 | 普通知识 | draft Wiki、普通笔记 | 可 AI 生成，需来源 |
| L4 | 派生数据 | database/、cache/、index_manifest.json、CHANGELOG.md | 可自动重建 |
| L5 | 缓存/临时 | __pycache__、*.pyc、日志 | 可删除 |

## 二十六、验证方式

- 结构一致性：`knowledge_os_check.ps1` 对比实际目录与本规范；
- 文件一致性：重要文件与本规范“重要文件说明”对比；
- 权限一致性：AI 权限与实际 Workflow（AGENTS.md / RAG AGENTS.md / Skill）对比；
- Wiki 一致性：frontmatter 状态是否符合 draft → reviewed → stable；
- RAG 一致性：Source → Chunk → Embedding → `main_vector_db`（活动索引）链路是否按脚本运行；`raw_vector_db` / `wiki_vector_db` 为空属正常（可选路径未启用）。
- Control Center 一致性：当前未实现（Status: PLANNED），待实现后按第二十三章验证。

## 二十七、Knowledge OS 自维护规则

1. Knowledge OS 是系统级规范，是知识库结构、权限、生命周期的唯一入口。
2. Knowledge OS 不等于普通知识，不适用普通知识笔记的编辑规则。
3. Knowledge OS 的修改属于高风险操作（HIGH / REVIEW_REQUIRED）。
4. AI 可以提出修改，但不能因为普通任务随意修改；涉及本文件必须先说明修改依据。
5. 架构发生变化（目录/文件/权限/生命周期/RAG/Workflow）时必须同步更新本文档。
6. 每次修改后必须运行 `knowledge_os_check.ps1` 验证一致性，并将结果写入报告。
7. 重大修改必须人工审核后生效；本文档状态流转（draft → reviewed → stable）由人工确认。
8. 不允许创建第二个系统级规范入口；其他文档只能引用本文档，不复制内容。
9. 其他 Agent / Skill 引用 Knowledge OS 时只引用路径与章节号，不得复制章节内容。
10. Knowledge OS 与实际目录结构不一致时必须报告漂移，不得静默修改任一方。

---

*本文档由 AI 起草（2026-08-10），本阶段（2026-08-10）已完成架构审查与固化：修正 RAG 活动索引描述、完善 Source of Truth 判定、增加修改风险等级与自维护规则。当前状态 `draft`，待人工审核后升级为 `stable`。*