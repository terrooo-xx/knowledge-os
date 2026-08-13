---
type: task-log
status: draft
domain: 系统总结
created: 2026-08-13
updated: 2026-08-13
---

# Phase 2 阶段总结：Knowledge OS、Weekly Review、Control Center 与 MCP

> 一句话定位：Phase 2 把个人知识库建设为「跨项目共享的只读知识层 Knowledge OS」，并提供每周复盘自动化、Control Center 管理入口与 Codex MCP 查询接口。
> 本文是 Phase 2 的正式阶段总结。未来 AI 阅读本文件即可了解系统当前状态，无需回溯全部历史聊天。

## 1. Phase 2 目标

- **Knowledge OS**：把 `20_Wiki`（draft / reviewed / stable）作为可信知识源，用 RAG 向量检索 + 重排 + 证据门 + LLM Judge 提供可靠回答，替代"直接翻文件"的检索方式。
- **Weekly Review**：每周五自动统计知识库状态（Wiki 数量与状态、知识缺口、项目进度、健康度），输出到 `40_Outputs/reviews`。
- **Outputs**：输出层与知识源分离（`40_Outputs`），复盘 / 报告不直接覆盖来源内容。
- **Control Center**：本地 Web 管理入口（human-in-the-loop），把 draft Wiki 审核、知识缺口处理、健康检查统一为 Action 列表。
- **Codex MCP integration**：让任意独立项目中的 Codex 通过只读 MCP 工具 `knowledge_search` 访问 Knowledge OS。

## 2. Phase 2 已完成能力

- **Wiki / RAG**：`20_Wiki` 结构 + `main_vector_db`；标准索引入口 `90_System/rag/scripts/update_index.py`，特殊摄入 `ingest_rag.py`（`--target raw/wiki`）。
- **Reranker**：bge-reranker-v2-m3（`hybrid_query.py` / `rag_engine/rerank.py`）。
- **Evidence Gate**：`assess_evidence`，`confidence_threshold: 0.78`。
- **LLM Judge**：DeepSeek 相关性判定，相关才 `answerable`。
- **fail-closed**：Judge 异常 / 超时 / 乱码 / 证据不足 → `knowledge_missing` / `retrieval_problem`，绝不猜答案。
- **knowledge_search**：只读统一检索入口（`90_System/rag/interface/knowledge_service.py`），MCP 仅暴露这一个工具。
- **Weekly Review**：`90_System/rag/scripts/review/weekly_review.py` + `metrics.py`，幂等（同周不重复生成，`--force` 才覆盖）。
- **Outputs**：`40_Outputs/reviews/每周复盘/YYYY/WNN/{weekly-review.md,snapshot.json}`。
- **Control Center**：`90_System/control_center/{server.py,service.py,static/index.html}`，API 见 §4。
- **每周五 18:00 Task Scheduler**：`register_task.ps1` 幂等注册 `Knowledge OS Weekly Review`（由 `config.yaml` 的 `weekly_review` 节控制：`enabled / weekday=friday / time=18:00`）。
- **手动生成**：`python 90_System/rag/scripts/review/weekly_review.py [--week 2026-W33] [--force] [--llm]`。
- **健康检查**：`90_System/scripts/knowledge_os_check.ps1`（结构漂移）、`rag_health_check.py`、`wiki_health_check.py`。
- **跨项目查询能力**：任意 cwd 经 MCP / Python 接口访问（阶段12C 在 `C:\Temp\DroneTest` 独立目录实测通过）。

## 3. 最终架构

```text
用户问题
  → Codex
  → knowledge_search（MCP 只读工具 / knowledge_service.py，mode=fast|deep|evidence_only）
  → Knowledge OS
  → Wiki 优先 → RAG（main_vector_db）→ Reranker → Evidence Gate → LLM Judge
  → Answer（deep 模式）/ 结构化证据 + Judge（fast 模式）/ knowledge_missing（fail-closed）
```

```text
Knowledge Base（20_Wiki + 30_Projects + knowledge_gaps.yaml）
  → Metrics（metrics.py，确定性统计）
  → Weekly Review（weekly_review.py，Task Scheduler 每周五 18:00 或手动）
  → Outputs（40_Outputs/reviews/每周复盘/YYYY/WNN/）
  → Control Center（本地 Web，Action 列表 + 只读 API + 经既有 rag_engine 的执行入口）
```

物理边界：`D:\KnowledgeBase\Obsidian Vault` 是唯一 Knowledge OS；独立工程（如 `D:\Projects\*`）通过 Codex + MCP 访问，不复制知识库、不把项目代码写入知识库。

## 4. 已实际验证的证据

- **knowledge_search 真实调用（2026-08-13，deep 模式）**：`STM32 DMA 配置步骤…` → `status=answerable`，`judge.relevance=relevant (0.95)`，返回 4 步配置流程答案；证据命中 `20_Wiki/03_STM32/STM32-DMA-配置与使用.md`（score 1.000，stable）。
- **STM32 DMA 查询**：deep 模式返回完整答案（使能时钟 → 初始化 DMA 通道 → 配置外设请求 → 使能并启动）。
- **FreeRTOS 查询**：阶段12C Q2 `FreeRTOS任务状态之间是什么关系？` → `answerable` + `relevant (1.0)`。
- **Judge relevant**：多场景 0.95 / 1.0；`fast` 模式仍保留 LLM Judge。
- **fail-closed**：原句"STM32 DMA 怎么配置"被 Judge 判"问题不完整"→ `knowledge_missing`；乱码查询 → `knowledge_missing`；Judge 连接错误 → `judge.error=true` + `knowledge_missing`；无资料外设（ICM-42688-P SPI）→ `retrieval_problem`（Evidence Gate 拦截）。
- **Weekly Review exit=0**：`2026-W33` snapshot.json 生成于 `2026-08-13T15:27:04`，`health.status=ok`、`errors=0`、`warnings=0`；脚本以 `exit $LASTEXITCODE` 上报。
- **Outputs 路径**：`40_Outputs/reviews/每周复盘/2026/W33/{weekly-review.md,snapshot.json}`。
- **Control Center APIs**：`/api/status`、`/api/dashboard`、`/api/wikis`、`/api/gaps`、`/api/health`、`/api/activity`、`/api/sources`、`/api/project_status`、`/api/sync`、`/api/weekly_review`、`/api/weekly_review/generate`、`/api/actions`、`/api/actions/batch/approve`。
- **Windows Task Scheduler**：`register_task.ps1` 幂等注册；`config.yaml` `weekly_review: {enabled: true, weekday: friday, time: "18:00"}`。
- **health checks**：`knowledge_os_check.ps1` 只读检查，退出码 0 = 无 ERROR，1 = 存在 ERROR。
- **跨项目**：阶段12C 从 `C:\Temp\DroneTest`（cwd ≠ Vault）经 MCP 查询成功；Q1–Q3 answerable+relevant，Q5 → `knowledge_missing`。

## 5. 关键设计决策

- **Wiki 优先**：`retrieval.wiki_first=true`，先查 Wiki 索引。
- **RAG fallback**：wiki / main 向量库分级；`raw_vector_db` 不作生产 fallback。
- **Evidence Gate**：启发式证据门（阈值 0.78），证据不足直接拦截。
- **LLM Judge**：Evidence 足够后仍需 Judge 判定 `relevant` 才 `answerable`。
- **fail-closed**：任何异常 / LLM 不可用 → 非 answerable 状态，绝不用 LLM 外部知识冒充库内答案。
- **Outputs 不直接覆盖来源**：输出独立到 `40_Outputs`，复盘产物不写回 Wiki / 来源。
- **Weekly Review 幂等**：同一周只生成一份产物，`--force` 才覆盖；统计全部确定性（LLM 仅允许总结/建议，失败则用确定性摘要）。
- **Control Center 作为统一管理入口**：只读 API；写操作（如 Wiki 状态、gap resolve）复用 `rag_engine.wiki_review.set_status` / `gaps.resolve_gap`，不直接改 Markdown / Vector DB。
- **knowledge_search 是标准检索入口**：代码 / Agent 一律走该接口，不把"直接全库搜索"作为标准路径。

## 6. 已解决的重要问题

- **MCP 注册 / 加载**：`~/.codex/config.toml` 的 `[mcp_servers.knowledge-os]`（command=python，args=`mcp_server.py`，env 含 `KNOWLEDGE_OS_VAULT`、`HF_HUB_OFFLINE=1`、`PYTHONIOENCODING=utf-8`）。阶段13 将 args 路径更新为 `90_System\rag\interface\mcp_server.py`；配置变更后需**重启 Codex** 才加载。
- **Python stdio handshake**：`mcp_server.py` 用 Python 标准库实现 JSON-RPC over stdio（Content-Length LSP 帧），stdout 仅输出 MCP 帧、日志走 stderr；`mcp_roundtrip.py` 实测 `initialize / tools/list / tools/call` 正常，handshake 问题已恢复。
- **config.toml 知识库 MCP 配置状态**：已写入并更新路径，待 Codex 重启生效。
- **Desktop MCP 当前最终状态**：2026-08-13 本会话 tools 未自动加载 `knowledge_search`（配置变更后未重启）；查询改用 Python 直接调用 `knowledge_service.knowledge_search`——与 MCP 同一只读链路（Retrieval → Evidence → Judge → Answer），非绕过。

## 7. 已知限制

- **pytest 环境**：当前默认 Python（`C:\Python314`）未安装 pytest；测试套件已就绪（`test_agent_knowledge_service`、`test_cli_contract`、`test_mcp_server`、`test_full_chain` 等），但需在含 pytest 的环境运行（遵守"不安装依赖"原则，未在本机验证）。
- **test_full_chain 离线行为**：使用 mock LLM adapter（不调用 DeepSeek）与 `config.local.yaml` 的本地测试向量库（`90_System/rag/database/test_*`，已被 `.gitignore` 排除）；需要本地缓存的 BGE embedder/reranker，`HF_HUB_OFFLINE=1` 下可离线运行。
- **MCP 需重启 Codex**：配置变更后本会话内不会自动出现该工具。
- **冷启动成本**：新进程首次查询约 9–10s（模型加载）；暖启动 fast 约 0.8–1.6s。
- **Judge 对含糊问题的 fail-closed**：原句"STM32 DMA 怎么配置"被判"问题不完整"→ `knowledge_missing`；需补全描述才能通过（属有意为之的保守行为）。

## 8. 当前项目状态

- **Git branch**：`master`。
- **Git 工作区**：Phase 2 归档 commit 前有 59 个未提交项；归档完成后见 `git status`（见下方 Phase 2 归档报告 / commit hash）。
- **Phase 2 commit**：`（见 90_System/任务记录/Phase 2/Phase 2-归档报告.md 或 git log）`。
- **未处理事项**：`activity_log.jsonl`、`.changelog_state.json`、`.obsidian/graph.json` 为运行时 / 本机状态（已 tracked，建议后续单独评估移出版本控制）；`00_Inbox/待处理文件/个人笔记`、`40_Outputs/reviews/每周复盘/2026`、`90_System/archive/嵌入式课程设计` 未纳入 Git（用户资料 / 生成产物，磁盘内容不动）。
- **外部依赖**：DeepSeek API（`DEEPSEEK_API_KEY` 环境变量）、BGE embedder / reranker 本地缓存、Python 3.14 + torch/transformers、`modelscope` 模型缓存路径（`config.local.yaml` 中为机器相关路径）。

## 9. 给未来 AI 的操作规则

- "根据我的知识库"类问题，**优先使用 `knowledge_search`**，不要直接把"直接搜索 Vault"作为标准路径。
- 不要绕过 Knowledge OS 的 Evidence Gate / LLM Judge / fail-closed 直接全库检索。
- 证据不足时保持 fail-closed：返回 `knowledge_missing` 时明确说"知识库没有足够资料"，不得声称答案来自知识库。
- 知识库事实与 Agent 推理必须区分：标注 `[Knowledge OS]` 与 `[Agent Reasoning]`。
- 修改知识库结构前先阅读 `90_System/KNOWLEDGE_OS.md` 与 `90_System/rag/README.md`。
- 新项目应能独立访问 Knowledge OS（MCP 配置在 `~/.codex/config.toml`），不复制知识库。
- 不要重复实施 Phase 2 已完成的功能（RAG 链路、检索接口、Weekly Review、Control Center、MCP 均已就绪）。
- 不要把 `database/`、`cache/`、模型、日志、`__pycache__` 等运行时内容提交进 Git。

## 10. Phase 3 起点

Phase 3 从以下方向开始，**不重建 Phase 2 已完成的系统**：

1. 重启 Codex 后验证 MCP `knowledge_search` 自动加载，恢复"Codex 内直接调用"路径。
2. 知识内容治理：`00_Inbox/待处理文件/个人笔记` 的 PDF 导入（inbox_processor → wiki_compile），draft → reviewed 审核闭环。
3. 版本控制卫生：评估 `activity_log.jsonl`、`.changelog_state.json`、`.obsidian/graph.json` 移出版本控制（需用户确认）。
4. 按需扩展 Control Center（如写操作权限模型、批量 Action），以及 Weekly Review 的 LLM 摘要质量。

---

### 关联文档

- 架构：`90_System/KNOWLEDGE_OS.md`
- RAG 接口：`90_System/rag/README.md`、`90_System/rag/interface/README.md`
- 阶段记录（历史）：`90_System/archive/stages/阶段11A / 11B / 12A / 12B / 12C`
- 阶段13（结构治理）：`90_System/任务记录/阶段13_架构去重与结构治理报告.md`
