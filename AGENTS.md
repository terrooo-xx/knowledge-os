# AGENTS.md

## 系统目标

本仓库是个人嵌入式、机器人和无人机开发知识库。

主要领域：

- 计算机基础
- STM32
- FreeRTOS
- 通信协议
- 控制理论
- 无人机飞控
- 移动底盘控制器
- ROS 2
- 项目管理
- 技术问题排查

## 目录职责

- `00_Inbox`：未经处理的原始资料。
- `10_Sources`：长期保留的来源、证据和参考资料。
- `20_Wiki`：经过整理和验证的通用知识。
- `30_Projects`：具体项目的架构、模块、接口、决策、任务和问题记录。
- `40_Outputs`：学习总结、技术方案、项目报告、对外输出；`40_Outputs/reviews/` 为复盘与检查报告（每周复盘、人工知识缺口、过期内容检查）。

- `90_System`：模板、规范、提示词、任务记录和归档。
- `.agents/skills`：Codex 可复用工作流。


## Knowledge OS 规则

- RAG 引擎位于 `90_System/rag`；默认生产索引为 `main_vector_db`（`20_Wiki + 30_Projects` 合并，`update_index.py --target main` 维护）；`00_Inbox` 的 raw 检索仅通过显式 `--target raw` / `--store raw` 启用，不是默认生产路径。
- Wiki 生命周期为 `draft` -> `reviewed` -> `stable`，状态写在 frontmatter，不按状态建目录。
- `90_System/rag/database` 与 `90_System/rag/cache` 不提交 Git。
- AI 生成的 Wiki 必须保留来源，禁止覆盖 `reviewed` / `stable` 笔记。
- 系统级架构、目录职责、AI 权限、知识生命周期与 Source of Truth 的唯一依据是 `90_System/KNOWLEDGE_OS.md`。
- 执行结构性操作（创建/移动/删除/更新索引/更新 Wiki）前，先阅读 `90_System/KNOWLEDGE_OS.md`。

## 原始资料处理规则

1. 处理新资料前，先搜索现有 Wiki。
2. 优先更新已有知识页，不随意创建近义重复文件。
3. 原始资料不能被直接覆盖或删除。
4. 没有长期价值但需要保留的资料移动到 `90_System/任务记录/archive`。
5. 技术结论应尽量保留来源。
6. 官方文档、数据手册、标准和源代码优先级最高。
7. 社区文章和 AI 回答只能作为辅助资料。
8. 不确定的结论必须标记为“待验证”。
9. 新旧资料冲突时，不直接删除旧结论，应增加版本差异、适用条件或争议说明。
10. 不得编造参数、接口、测试结果、项目进度或引用来源。

## Wiki 编写规则

1. 一个文件主要解释一个概念。
2. 使用中文标题和中文字段。
3. 使用完整句子，不堆砌关键词。
4. 优先通过内部链接引用已有知识，不复制大段重复内容。
5. 知识笔记应说明：

   - 概念定义
   - 解决的问题
   - 核心原理
   - 工作过程
   - 实际应用
   - 相关概念
   - 常见误区
   - 资料来源

6. 修改笔记后更新 `updated` 字段。
7. 笔记状态只能使用：

   - `draft`
   - `reviewed`
   - `stable`

8. 无法确认正确性的内容保持 `draft`。
9. 不因为同一个词在多个领域出现，就错误地将内容合并。
10. 创建新知识页前，必须先检查同义词、别名和近义笔记。

## 项目文档规则

项目功能模块文档必须包含：

1. 功能说明
2. 主要实现单元
3. 协同模块
4. 主要接口
5. 具体实现路径
6. 输入数据
7. 输出数据
8. 异常处理
9. 验收标准
10. 相关文档
11. 变更记录

项目中的通用原理应链接到 `20_Wiki`，不要在项目文档中重复写完整基础知识。

## 安全规则

1. 不直接删除文件，只能移动到归档目录。
2. 批量修改前先报告修改范围。
3. 不修改原始数据手册、图片、附件和外部导入文件。
4. 不执行来源不明确的脚本。
5. 不在知识库中保存 API Key、Token、密码或其他密钥。
6. 每次任务结束后必须报告：

   - 新建文件
   - 修改文件
   - 移动文件
   - 跳过文件
   - 发现的问题
   - 待人工确认事项

7. 重大修改前检查 Git 状态。
8. 如果工作区存在未提交修改，不得擅自覆盖用户修改。
9. 无法安全判断时停止修改对应文件，并写入报告。
10. 不允许使用危险性删除命令。

## Inbox 与 Knowledge Gap 规则

- 新资料统一进入 `00_Inbox`，用户不需要手工判断领域；来源子目录只表示输入来源，不代表最终知识分类。
- 使用 `90_System/rag/scripts/inbox_processor.py` 做“分析 → 建议 → Draft”：第一版不自动覆盖正式 Wiki，`create_wiki` 只生成 `status: draft`，`update_wiki` 只生成更新建议。
- 查询证据不足时记录 Knowledge Gap 到 `90_System/rag/tests/knowledge_gaps.yaml`，不让 LLM 自动用外部知识补全。
- 原始资料禁止自动删除、覆盖、移动或重命名；处理记录写入 `90_System/任务记录/`。

## LLM-Wiki 编译规则

- `wiki_compile.py` 只能生成 `status: draft`，禁止直接修改 `reviewed` / `stable` Wiki。
- AI 不自动把 draft 升级为 reviewed/stable；状态流转由用户通过 `wiki_review.py` 人工确认。
- `update_wiki` 只生成更新建议和可审查内容，用户确认后才可修改 Wiki。
- Wiki 正文必须来自 Inbox 资料或已有 Wiki，禁止用 LLM 自身知识补写无来源细节。
- 增量 RAG 使用 `index_manifest.json`，未变化文档不重新 embedding。

## AI Context Loading Protocol（任务开始必读）

复杂任务开始时，按顺序建立系统上下文（避免每次从零扫描全库）：

```text
1. 读取 AGENTS.md（操作规则）
2. 读取 90_System/KNOWLEDGE_OS.md（架构宪法：应是什么）
3. 读取 90_System/system_profile.md（当前全貌：现在是什么）
4. 检查 profile freshness：
   python 90_System/scripts/system_profile_generator.py --check
   - CURRENT  → 建立总体上下文
   - STALE    → 先对变化区域做验证，再进入任务
5. 进入任务相关的深度源码审阅
```

`system_profile` 是「避免从零认识项目」，不是「替代读源码」；任务相关部分仍须以源码/运行结果为准。

## Source of Truth Hierarchy

1. 当前源码 / 当前运行结果（最高）
2. 当前配置（config.yaml / config.local.yaml 等）
3. `90_System/KNOWLEDGE_OS.md`（架构与权限宪法）
4. `90_System/system_profile.md`（当前状态摘要——**不是高于源码的真相**）
5. 最新正式审计/治理报告（40_Outputs/reviews/）
6. 历史任务记录（90_System/任务记录/）
7. README / HOME
8. 旧报告 / 历史聊天（最低，仅参考）

若 Profile 与源码冲突：**源码优先，随后更新 Profile**。

## System Profile 更新规则

- `system_profile.md` 是版本绑定的当前状态快照（frontmatter 含 `source_commit`）。
- 什么变化必须更新 Profile：架构变化、目录职责变化、RAG pipeline 变化、Control Center 变化、MCP 变化、
  Codex/AI Runtime 变化、Bootstrap 变化、Python/model 要求变化、Git boundary 变化、Baseline 变化、
  新核心组件加入/删除、新电脑前置环境变化。
- 动态字段刷新：`python 90_System/scripts/system_profile_generator.py --update`；稳定描述人工维护。
- 提交含架构/状态变化前，先 `--update` 再提交。

## Change Impact Rules

| 修改 | 需要更新 |
|---|---|
| 架构变化 | KNOWLEDGE_OS.md + system_profile.md |
| 新核心组件 | system_profile.md + AGENTS.md（必要时） |
| Bootstrap 变化 | system_profile.md + Bootstrap 文档 |
| AI Runtime 变化 | system_profile.md |
| Baseline 变化 | system_profile.md + Baseline evidence |
| Git boundary 变化 | system_profile.md + Governance |
| README-only 修改 | README，不要求更新 Profile |

## Verification Protocol

按变更范围升级验证（不要每个小文档编辑都跑完整 RAG Regression）：

- **Local verification**（文档/注释/小改动）：无测试要求，但须检查 git diff。
- **Component verification**（代码/配置/脚本改动）：运行相关 pytest + 相关脚本健康检查。
- **System verification**（RAG/Control Center/MCP/Bootstrap/架构）：pytest 全套 + `rag_health_check.py` +
  `wiki_health_check.py` + 必要时 Baseline Regression（`evaluate_benchmark.py`，REAL_REGRESSION=0 为门禁）。

修改后流程：修改 → 相关测试 → Health Check → 必要时 Baseline Regression → 检查 git diff →
更新 System Profile（如涉及）→ 任务完成报告。

## Machine-local / Secret Boundary

```text
Git assets ≠ Runtime ≠ Machine-local ≠ Secrets ≠ Private data
```

- Git assets：正式知识/代码/配置/审计证据（进 Git）。
- Runtime：vector db / cache / eval runs / activity_log 等（gitignored，可重建）。
- Machine-local：Python、模型缓存、~/.codex、~/.cc-switch、Scheduler、config.local.yaml（gitignored）。
- Secrets：API Key / Token / 密码 / 私钥（绝不进 Git/Vault/日志/报告；只检查存在性）。
- Private data：00_Inbox 个人笔记 PDF 等（gitignored，不自动纳入）。

禁止：把 API Key 写入 Git、把 Codex/CC Switch user 配置放入 Vault、把模型缓存/venv 放入 Git、
把私人 Inbox 自动纳入 Git、把 machine-local 配置复制进 Vault。

## Bootstrap 规则

- Bootstrap（90_System/scripts/bootstrap.ps1 + bootstrap_helper.py）职责：**恢复运行环境**。
- 自动安装：Codex（npm）；自动配置：venv/deps/models/reranker/index/Codex config/DeepSeek provider/MCP/approval/scheduler/Control Center。
- 用户提供：GitHub 认证、DeepSeek API Key、Python 3.14.x（必须预装）、CC Switch 官方安装器（若缺失）。
- Bootstrap 不负责：知识内容管理、Wiki approval、Git commit/push、Secret 上传、私人资料恢复。
- 新电脑前置环境定义见 `system_profile.md` 第 16 章与 Bootstrap 报告。

## 任务完成定义

任务结束必须报告：新建文件 / 修改文件 / 移动文件 / 跳过文件 / 发现的问题 / 待人工确认事项。
涉及系统变化时，明确：Health Check 结果、Baseline 是否受影响、System Profile 是否需要更新、是否已更新。

## Git 版本治理规则

- 版本治理体系（Commit / Baseline / Tag / Phase / Project Summary）的唯一权威依据是 `90_System/KNOWLEDGE_OS.md` 第二十八章；本文件只引用，不复制。
- 禁止自动 commit、禁止 push；**仅当任务明确授权 commit/push 时才执行**。当前仓库已有 remote（`origin = https://github.com/terrooo-xx/knowledge-os`，PRIVATE）。
- commit message 格式：`[<phase|project>] <type>: <摘要>`（type ∈ feat / fix / docs / chore / refactor / test）。
- 一个 commit 只表达一个逻辑变更；禁止 `git add -A`；必须按明确文件清单精确 `git add`。
- 提交前必须：列文件清单 → `git diff` → `git diff --cached` → 敏感信息扫描 → 确认无 USER_WORK / IGNORE 混入。
- 运行时/派生文件（`.obsidian/graph.json`、`activity_log.jsonl`、`.changelog_state.json`、`review_records.json`、RAG Evaluation 运行产物等）禁止作为正式成果提交。
- 正式里程碑使用 Tag：`baseline/<baseline_id>`；不为每个 commit / weekly review / evaluation run 创建 tag。
- Phase 状态流转（尤其 CLOSED）必须人工确认；AI 不擅自关闭 Phase。