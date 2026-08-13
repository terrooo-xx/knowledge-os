# 个人工程知识库

这是一个个人工程知识库，用于长期积累嵌入式、机器人和无人机开发相关的资料、知识与项目经验。

## 使用方式

- 使用 Obsidian 查看和编辑本知识库。
- 使用 Codex 辅助整理、检查和维护知识库。

## 覆盖领域

- STM32 嵌入式开发
- FreeRTOS
- 无人机飞控
- 移动底盘控制器
- ROS 2
- 机器人技术
- 控制理论
- 项目架构设计
- 技术问题排查
- 开发任务管理

## 目录职责

- `00_Inbox`：未经处理的原始资料。
- `10_Sources`：长期保留的来源、证据和参考资料。
- `20_Wiki`：经过整理和验证的通用知识。
- `30_Projects`：具体项目的架构、模块、接口、决策、任务和问题记录。
- `40_Outputs`：学习总结、技术方案、项目报告、对外输出；`40_Outputs/reviews/` 为复盘与检查报告（每周复盘、人工知识缺口、过期内容检查）。

- `90_System`：模板、规范、提示词、任务记录和归档。
- `.agents/skills`：Codex 可复用工作流。

## 基本流程

原始资料进入 `00_Inbox`，由 AI 判断资料价值，整合进结构化 Wiki，应用到具体项目，项目经验再回流 Wiki。

## 维护规则

- 不直接删除原始资料。
- 批量修改前先使用 Git 保存版本。
- 详细规则见 `AGENTS.md`。

## Knowledge OS（RAG + LLM-Wiki）

本库按 Knowledge OS 思路运行：`00_Inbox` 保存原始资料，`20_Wiki` 沉淀长期知识，RAG 引擎负责检索。

- 架构（生产 RAG）：`20_Wiki + 30_Projects` -> `90_System/rag/scripts/update_index.py`（默认 `--target main`）-> `main_vector_db` -> `hybrid_query.py`（默认 `--store main`）-> LLM / Wiki。
- 系统级架构与管理规范（目录职责、AI 权限、知识生命周期、Source of Truth）：`90_System/KNOWLEDGE_OS.md`。
- 添加资料：把 PDF / Markdown / TXT / HTML 放入 `00_Inbox`，运行 `inbox_processor.py` 分析分类，经人工审核成为 Wiki / 项目知识资产后，运行 `update_index.py --changed` 更新生产索引 `main_vector_db`。`raw_vector_db` 是可选 Source 检索工具，不是默认生产索引。
- 运行检索：`python 90_System/rag/scripts/hybrid_query.py "问题"`。
- 生成 Wiki：`python 90_System/rag/scripts/wiki_compile.py --action create --file "00_Inbox/xxx.md" --domain 03_STM32`。
- Obsidian 使用：Wiki 状态用 frontmatter 的 `status`（`draft` / `reviewed` / `stable`），笔记间用 `[[双链]]`。
- 详细配置和数据流见 `90_System/rag/README.md`。
