# 阶段⑫-C：Knowledge OS 实际项目接入与 Codex 使用流程验证

> 阶段：⑫-C（2026-08-11）｜目标：验证 Knowledge OS 作为**独立外部工程知识层**，从任意项目目录经 Codex/MCP 真实可用。
> 原则：不大规模改 RAG 架构；不削弱 Evidence Gate / LLM Judge / knowledge_missing / fail-closed；不把项目代码写入知识库，也不把知识库复制进项目。

## 1. 当前 Knowledge OS 使用架构

```text
独立工程项目（如 C:\Temp\DroneTest，cwd ≠ Knowledge OS）
        │ Codex
        ▼
Knowledge OS MCP（knowledge_search，默认 mode=fast）
        ▼
Knowledge OS：Retrieval → Reranker → Evidence Gate → LLM Judge → Answer/Gap（只读）
```

- Vault 根目录由环境变量 `KNOWLEDGE_OS_VAULT` 指定，缺省按 `mcp_server.py` 文件位置反推，**绝不依赖当前工作目录**（`knowledge_service.VAULT_ROOT`）。
- 项目代码与 Knowledge OS 物理独立、互不复制；各项目共享同一外部知识层。

## 2. 独立项目如何访问 Knowledge OS

- Codex 配置 `~/.codex/config.toml`：`[mcp_servers.knowledge-os]`，command=python，args=`mcp_server.py`，env 含 `KNOWLEDGE_OS_VAULT=D:\KnowledgeBase\Obsidian Vault`、`HF_HUB_OFFLINE=1`、`PYTHONIOENCODING=utf-8`。
- 在任意项目目录启动 Codex 即自动加载 MCP；`tools/list` 只暴露一个只读工具 `knowledge_search`（无任何写工具）。
- 本次实测从 `C:\Temp\DroneTest`（临时跨项目验证环境，仅 README.md + firmware/main.c 占位，不属于知识库）调用成功。

## 3. MCP 跨项目验证结果（cwd=C:\Temp\DroneTest，真实 LLM）

| 场景 | 查询 | mode | status | judge | evidence | 来源（source_trace 摘要） | 端到端耗时 |
|---|---|---|---|---|---|---|---|
| env 指向 Vault | STM32 DMA怎么工作？ | fast | answerable | relevant (0.95) | 5 | 20_Wiki/03_STM32/STM32-DMA-配置与使用.md 等 | 9.54s（含模型冷加载） |
| 不设 env（按文件位置反推） | STM32时钟树HSI/HSE/PLL怎么工作？ | fast | answerable | relevant (0.95) | 5 | 20_Wiki/03_STM32/STM32时钟树.md 等 | 9.48s（含模型冷加载） |
| env 指向 Vault | 详细解释STM32 DMA工作机制 | deep | answerable | relevant (0.95) | 5 | 20_Wiki/03_STM32/STM32-DMA-配置与使用.md 等 | 16.66s（含 Answer 生成） |

- `tools/list` 确认 `knowledge_search` 的 inputSchema 含 `mode` 枚举 `fast/deep/evidence_only`，**默认 fast**；description 已写明"外部工程知识库，不是当前项目代码库"。
- 结论：当前工作目录 ≠ Knowledge OS 时，MCP 仍能正确访问 `D:\KnowledgeBase\Obsidian Vault` 并返回 Wiki / Evidence / Judge / Source，跨项目访问成立。

## 4. Fast / Deep 验证结果（暖启动，单进程复用 embedder/reranker）

| 查询 | fast 耗时 | deep 耗时 | 差异 |
|---|---|---|---|
| Q3 STM32 DMA | **1579ms** | **5236ms** | deep ≈ fast + 3.7s（Answer 生成 1 次 DeepSeek） |

- 暖启动 fast 模式约 **0.8–1.6s（秒级）**，达到"正常情况下约 1 秒级"目标。
- deep 模式额外执行 Answer Generation（Q3 返回 919 字符答案）；MCP deep 场景返回 2127 字符答案。
- 冷加载（新进程第一次查询，BGE + reranker）约 9–10s；MCP 服务长驻后无此成本（已有启动预热 `_warmup`）。

## 5. 5 个真实查询测试结果（独立项目目录，暖启动）

| # | 查询 | 预期 | 实测 status | Judge | 结论 |
|---|---|---|---|---|---|
| Q1 | STM32时钟树HSI/HSE/PLL怎么工作？ | answerable + relevant | answerable | relevant (1.0) | 通过 |
| Q2 | FreeRTOS任务状态之间是什么关系？ | answerable | answerable | relevant (1.0) | 通过 |
| Q3 | STM32 DMA怎么工作？ | answerable | answerable | relevant (1.0) | 通过 |
| Q4 | ICM-42688-P的SPI读取应该注意什么？ | fail-closed 无答案 | **retrieval_problem** | 未触发（证据不足，heuristic 拦截） | 通过（fail-closed；见 §6/§13） |
| Q5 | ROS2 Nav2代价地图怎么配置？ | knowledge_missing + judge=irrelevant | **knowledge_missing** | irrelevant (0.95) | 通过（无关键词误答） |

## 6. knowledge_missing 验证

- Q5 正确返回 `knowledge_missing`：检索到高相似内容但 Judge 判定 irrelevant → 不生成答案，`gap:{status:"pending"}` 只读报告、不写入 gaps.yaml。
- Q4 返回 `retrieval_problem`：知识库仅在 `30_Projects/无人机飞控/硬件选型.md` 提及 ICM-42688-P、无 SPI 读取资料，Evidence Gate 判定不足并 fail-closed（与 12B 基线记录一致）。
- 本阶段验证后状态无新增变化：gaps.yaml = 1 resolved + 5 pending；activity_log.jsonl = 6 行；Wiki = draft 13 / reviewed 4 / stable 3；main_vector_db = 34 records。**查询全程只读，无污染。**

## 7. Judge fail-closed 验证

- fast 模式**仍保留 LLM Judge**：Q5 实测 Judge=irrelevant → knowledge_missing（未实施 12A 否决的"高置信跳过 Judge"）。
- Judge 异常/超时 → relevance=irrelevant + error=true（fail-closed），由 `retrieval.answer_query` 兜底，测试覆盖（test_judge、test_mcp_server）。
- deep 模式 Answer 超时 → `answer_generation_timeout`，保留证据/Judge（test_performance_optimizations 覆盖）。

## 8. 当前实际使用方法（Codex）

```text
D:\KnowledgeBase\Obsidian Vault      # Knowledge OS（唯一）
D:\Projects\DroneFlightController    # 独立工程项目
D:\Projects\MobileChassis
D:\Projects\OtherProject
```

- 普通开发：`knowledge_search(query="...", mode="fast")` → 拿结构化证据 + Judge，Codex 自行组织回答。
- 需要完整解释：`knowledge_search(query="详细解释...", mode="deep")`。
- 查询策略（写入了 `90_System/agent/README.md`）：A 当前代码问题先读项目再按需查库；B 通用知识直接查；C 未知硬件查询且 missing 时区分 `[Knowledge OS]` 与 `[Agent Reasoning]`；D 设计决策查库 + 结合项目分析。

## 9. 文档修改

- `90_System/agent/mcp_server.py`：`knowledge_search` 默认 mode=fast；schema 增加 `mode` 枚举（fast/deep/evidence_only）；tool description 重写为"外部工程知识库，非当前项目代码库"，并给出适用场景与 deep 使用条件。
- `90_System/agent/README.md`：追加「实际项目使用方式」「推荐查询策略（Codex）（情况 A-D）」「Knowledge OS 与项目知识边界」。
- `90_System/阶段12C_跨项目Codex集成与实际使用验证.md`：本报告。
- （随本提交一并纳入的阶段⑫-A/B 改动：benchmark_query.py、test_performance_optimizations.py、rerank.py 进程级缓存、embeddings.py 加载锁、knowledge_service.py fast/deep/evidence_only、deepseek/openai adapter 超时、config.yaml/config.py、12A/12B 报告。）

## 10. 测试结果

- **19/19 测试文件全 PASS**（18.9s）：含 `test_mcp_server.py`（9 用例：握手/tools list/call/fail-closed/stdio 往返）与 `test_performance_optimizations.py`（8 用例：reranker 单例、fast/deep/evidence_only、fast 下 missing 与 Judge reject、Answer 超时、fail-closed、只读）。
- 回归命令：逐文件 `python 90_System/rag/tests/test_*.py`（HF_HUB_OFFLINE=1，PYTHONIOENCODING=utf-8）。

## 11. Health

| 检查 | 结果 |
|---|---|
| knowledge_os_check.ps1 | PASS=98 WARNING=3 **ERROR=0**（3 个 WARNING 均为既有：interfaces.md 占位、00_Inbox 35 个待处理文件、Git 17 处未提交） |
| rag_health_check.py | **ERROR=0**（PASS=8，pending gaps=5 仅报告） |
| wiki_health_check.py | **ERROR=0**（PASS=20） |

## 12. Git commit

- message：`Knowledge OS: validate cross-project Codex integration`（未 push）。
- 纳入：阶段⑫-A/B/C 全部代码与文档改动（见 §9）。
- 排除：`00_Inbox/待处理文件/个人笔记/`、`90_System/archive/嵌入式课程设计/`（用户源材料，不提交）；`90_System/scripts/.changelog_state.json`（pre-commit 钩子状态文件，提交后仍保持工作区未提交，属既有行为）；`90_System/rag/database|cache`（gitignored）。

## 13. 未解决问题

1. **Q4 分类为 retrieval_problem 而非 knowledge_missing**：知识库有 `硬件选型.md` 提及 ICM-42688-P 但无 SPI 读取资料，Evidence Gate 正确 fail-closed；若要 Q4 变为 answerable，需补充 ICM-42688-P 数据手册/使用资料并编译进 Wiki。
2. **新进程首次查询冷启动约 9–10s**：MCP 长驻后无此问题；临时项目"即开即用"首查仍偏慢，可后续评估随系统启动预载（本阶段不做）。
3. **benchmark_query.py 多 run 分层计时重复计数**：`_install_wrappers` 每次 run_one 重复包装模块级函数，多次调用时 `layers_ms` 会按调用次数叠加重复条目（`total_ms` 仍准确）。单次 CLI 调用不受影响；本阶段以单进程暖启动计时为准。
4. **Codex 会话内 MCP 需重启才生效**：改 `config.toml`/`mcp_server.py` 后需重启 Codex；当前会话不会自动出现该工具（既有约束）。

## 14. 下一阶段建议

- 把 `C:\Temp\DroneTest` 场景迁移到真实项目（如 `D:\Projects\DroneFlightController`）做一次端到端 Codex 实测，覆盖情况 A（"这个 FreeRTOS 任务为什么没运行"类问题）。
- 可选：MCP 进程开机常驻/预热策略，消除跨项目首查冷启动。
- 可选：为 `knowledge_search` 增加 `record_gap=True` 的显式缺知识上报开关（本阶段保持只读、不自动写）。
- 后续阶段可设计 Project → Knowledge OS 的 Knowledge Capture（本阶段明确不做）。

---
*验证数据来源：`C:\Temp\DroneTest` 跨项目 MCP 实测 + 单进程暖启动计时（真实 DeepSeek Judge/Answer）+ 19/19 测试 + 三份 Health 检查。*
