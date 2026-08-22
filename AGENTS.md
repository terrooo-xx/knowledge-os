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

## Git 版本治理规则

- 版本治理体系（Commit / Baseline / Tag / Phase / Project Summary）的唯一权威依据是 `90_System/KNOWLEDGE_OS.md` 第二十八章；本文件只引用，不复制。
- 禁止自动 commit、禁止 push；当前仓库无 remote，不创建。
- commit message 格式：`[<phase|project>] <type>: <摘要>`（type ∈ feat / fix / docs / chore / refactor / test）。
- 一个 commit 只表达一个逻辑变更；禁止 `git add -A`；必须按明确文件清单精确 `git add`。
- 提交前必须：列文件清单 → `git diff` → `git diff --cached` → 敏感信息扫描 → 确认无 USER_WORK / IGNORE 混入。
- 运行时/派生文件（`.obsidian/graph.json`、`activity_log.jsonl`、`.changelog_state.json`、`review_records.json`、RAG Evaluation 运行产物等）禁止作为正式成果提交。
- 正式里程碑使用 Tag：`baseline/<baseline_id>`；不为每个 commit / weekly review / evaluation run 创建 tag。
- Phase 状态流转（尤其 CLOSED）必须人工确认；AI 不擅自关闭 Phase。