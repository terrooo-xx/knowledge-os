---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑪-A：Agent Knowledge Interface

> 把 Knowledge OS 现有可靠查询链（Retrieval → Heuristic Evidence → LLM Judge → Answer/Gap）
> 封装成稳定、只读、可被未来 Codex/MCP 调用的 Agent Knowledge Interface。

## 1. 为什么需要 Agent Interface

- 独立工程（如无人机项目）与 Knowledge OS 分离；两者只通过知识接口连接，不复制文件、不移动目录。
- Agent 不能直接摸 Wiki / Vector DB，必须经过 Evidence/Judge 安全机制，避免"相似即回答"。
- 为阶段⑪-B 的 Codex / MCP 正式接入提供稳定的函数级接口。

## 2. Project 与 Knowledge OS 的关系

```text
独立项目（DroneFlightController 等）
    ↓ Codex
Knowledge OS Query Interface（90_System/agent/）
    ↓ 现有 Knowledge OS（Retrieval/Evidence/Judge/Gap）
可靠知识
```

- 本项目不移动、不复制任何知识库内容到外部项目。

## 3. Agent Query Architecture

```text
Codex / Agent
  → knowledge_search(query)
      → 现有 rag_engine.retrieval.answer_query（main_vector_db）
          → Dense + BM25 → Reranker
          → Heuristic Evidence Gate
          → LLM Relevance Judge（fail-closed、可开关）
      → Sufficiency → Answer / knowledge_missing
```

接口只做"输入标准化 → 调用现有链 → 输出标准化"，**不复制** embedding/检索/evidence/judge 逻辑。

## 4. API / Service 设计

- `90_System/agent/knowledge_service.py::knowledge_search(query, *, use_llm, top_k, cfg/config_path, embedder, raw_store, wiki_store, llm_answer)`。
- 组件可注入以便离线测试；默认构建生产 main 索引。
- CLI：`python 90_System/agent/knowledge_cli.py "问题" [--no-llm] [--top-k N]`。

## 5. Query 输入

```json
{ "query": "FreeRTOS任务优先级和抢占式调度怎么工作？" }
```

## 6. Query 输出

```json
{
  "query": "...",
  "status": "answerable | knowledge_missing | knowledge_insufficient | retrieval_problem | answer_quality_problem | error",
  "answer": "str | null",
  "evidence": [{"title", "source", "score", "status"}],
  "sufficient": true|false,
  "judge": {"relevance", "confidence", "reason"} | null,
  "gap": {"status": "pending"} | null,
  "source_trace": ["20_Wiki/..."],
  "reason": "Evidence 判定原因"
}
```

- `status=answerable` 仅当 Evidence 充分且 Judge 为 relevant（或 Judge 未启用）。
- `knowledge_missing` 为正式状态；`answer=null`，绝不猜测。

## 7. Evidence

- 复用现有 `assess_evidence`（阈值 + 主题词覆盖门控）。
- 输出 evidence 列表保留 `title/source/score/status`，供 Codex 追溯。

## 8. Judge

- 复用现有 `LLM Relevance Judge`（`rag_engine.judge`），由 `answer_query` 自动触发（heuristic 通过且启用时）。
- 实测：`ROS2 Nav2 代价地图怎么配置？` → judge=irrelevant(1.0) → `knowledge_missing`（高相似被拒）。

## 9. knowledge_missing

- 证据不足 / Judge 拒绝 / LLM 不可用 / 异常 → 返回 `knowledge_missing`（或对应 gap 类型），`answer=null`，`gap.status=pending`。
- 只读报告 Gap；本阶段默认**不自动写入** knowledge_gaps.yaml（避免 Agent 查询污染缺口库；未来可 opt-in `record_gap`）。

## 10. Source Traceability

- `source_trace` 返回来源路径集合；`evidence[].source` 为具体 Wiki/Project 路径，可一路追到原始 Source（frontmatter）。

## 11. Read-only Boundary

- 接口为只读：不修改 Wiki / Vector DB / Gap / Markdown；不做 approve/resolve。
- 测试 `test_read_only_no_writes` 验证查询前后 gaps.yaml、activity_log.jsonl、Wiki frontmatter 均不变。
- 未来 WRITE/REVIEW/APPROVE/RESOLVE 权限留给后续阶段。

## 12. CLI

```powershell
python 90_System/agent/knowledge_cli.py "STM32时钟树HSI/HSE/PLL怎么工作？"
python 90_System/agent/knowledge_cli.py "问题" --no-llm   # 离线
```

## 13. 测试

- 新增 `tests/test_agent_knowledge_service.py`（8 用例，全离线）：稳定知识 answerable、knowledge_missing、Judge irrelevant 拒绝、Evidence/Source 字段保留、只读无写入、LLM 不可用 fail-closed、LLM 异常 fail-closed、异常查询结构化返回。
- 全量 **17/17 测试 PASS**（16 原有 + Agent）。
- 真实 CLI 验证（含 LLM）：
  - `STM32时钟树HSI/HSE/PLL怎么工作？` → answerable, judge=relevant(0.95), 有回答 ✅
  - `WSL里怎么装Ubuntu？` → knowledge_missing, answer=null ✅
  - `ROS2 Nav2代价地图怎么配置？` → knowledge_missing, judge=irrelevant(1.0) ✅（高相似被拒）
  - `ICM-42688-P的SPI读取应该注意什么？` → retrieval_problem（库中无此知识，不强行回答）✅

## 14. Future MCP

- `knowledge_search` 设计为未来 MCP Tool 的函数基础（输入 query → 结构化 JSON）。
- 阶段⑪-B 再实现 MCP Server / Codex 接入；**本阶段不实现**，KNOWLEDGE_OS.md 只标注 "MCP planned / future"。

## 15. Health / 回归

```text
17/17 tests PASS
knowledge_os_check：ERROR=0（WARNING=3 既有，PASS=98）
rag_health：ERROR=0 PASS=8
wiki_health：ERROR=0 PASS=20
```

## 16. Git

- 新增 commit：`Knowledge OS: add agent knowledge query interface`（不 push）。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
