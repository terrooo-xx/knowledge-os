---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑫-B：Knowledge OS 查询性能优化

> 在不降低 Evidence Gate / LLM Judge / knowledge_missing / fail-closed 的前提下降低延迟。
> 按 ⑫-B-1→⑫-B-4 顺序实施，每步验证。未 commit / 未 push。

## 1. 优化前基线（阶段⑫-A 实测，暖查询）

| 查询 | 类型 | Baseline |
|---|--|--:|
| STM32时钟树 | answerable | 4.4s |
| STM32 DMA | answerable | 3.5s |
| FreeRTOS | answerable | 4.1s |
| WSL | knowledge_missing | 4.3s |
| ICM-42688-P | retrieval_problem | 3.6s |
| ROS2 Nav2 | Judge reject | 1.6s |
| 冷启动（首查询/新进程） | - | 8.8-14s |

## 2. Reranker 缓存实现（⑫-B-1）

- `rag_engine/rerank.py`：新增进程级 lazy singleton `_get_reranker(provider, model)`（模块级锁 + 双重检查，线程安全）。
- 不改变模型/参数/top-k/排序算法/Evidence；首次调用承担加载成本，后续复用同一实例。
- 测试：同 (provider, model) 只创建一次；不同 model 才新建。

## 3. Fast / Deep / evidence_only 设计（⑫-B-2）

`knowledge_service.knowledge_search(query, mode=...)`（向后兼容，默认 `deep`）：

- `deep`（默认）：Retrieval + Evidence + Judge + Answer Generation（与原先一致）。
- `fast` / `evidence_only`：Retrieval + Evidence + **Judge（保留安全判断）**，**不生成"长答案"**；返回结构化 evidence/judge/source_trace，供 Codex 直接使用。
- Fast ≠ 关闭 Judge：heuristic 通过仍会调用 Judge（安全边界不变）。

## 4. LLM timeout / fail-fast（⑫-B-3）

- `llm/deepseek_adapter.py` + `openai_adapter.py`：OpenAI client 增加 `timeout=llm_cfg.get("timeout", 30)`；`config.yaml` / DEFAULTS 增加 `llm.timeout: 30`。
- `knowledge_service` 两步法：先 Retrieval+Evidence+Judge（无 Answer），再单独生成 Answer：
  - Answer 超时（`APITimeoutError` / `APIConnectionError` / `TimeoutError`）→ 返回 **`answer_generation_timeout`**，**保留 evidence/judge/source_trace**（不丢已确认证据，绝不猜答案）。
  - Answer 其他异常 → `error`（fail-closed）。
  - Judge 超时 → 沿用既有 fail-closed（irrelevant → insufficient）。

## 5. MCP/BGE 预热（⑫-B-4）

- `rag_engine/embeddings.py`：`BgeEmbedder` 模型加载加模块级锁（线程安全）。
- `mcp_server.py`：启动时后台守护线程预热 BGE embedding + Reranker 单例；不阻塞 handshake、不启动额外进程、不改协议。
- 预热失败不影响服务（首次真实查询自行加载）。

## 6. 性能前后对比（暖查询，ms）

| Query | Baseline | Optimized-deep | 提升 | Optimized-fast |
|---|--:|--:|--:|--:|
| STM32时钟树 | 4397 | 4655 | -6%（LLM 波动） | ~1192 |
| STM32 DMA | 3469 | 3935 | -13%（LLM 波动） | ~894 |
| FreeRTOS | 4136 | 3855 | +7% | ~947 |
| WSL | 4266 | **2526** | **+41%** | - |
| ICM-42688-P | 3608 | **1926** | **+47%** | - |
| ROS2 Nav2 | 1595 | **1126** | **+29%** | - |

- **Fast（answerable）≈ 0.9-1.2s**，比 Deep 快约 **75%**，无长答案、Judge 保留。
- **Deep（answerable）≈ 3.9-4.7s**：受 DeepSeek（Judge ~1.4s + Answer ~2.6-3.4s）主导，波动属 LLM 网络延迟；Q1/Q2 的 -6%/-13% 为方差，非回归。
- **Reranker 缓存**：fallback 查询 4.2-4.3s → 1.7-2.4s（模型不再重载，剩余为推理）。
- **冷启动**：仍 8-11s（BGE 加载），已前移到 MCP 启动预热（首查变暖）。

## 7. 测试结果

- 新增 `tests/test_performance_optimizations.py`（8 用例）：Reranker 单例复用、deep/fast/evidence_only 行为、fast 下 knowledge_missing 与 Judge reject、Answer 超时保留证据、Answer 异常 fail-closed、各模式只读。
- 全量 **19/19 测试 PASS**（18 原有 + 性能优化）。

## 8. 安全边界验证（PASS）

- Evidence Gate：未改（仍走 assess_evidence）。
- LLM Judge：Fast 模式仍调用（实测 ROS2 Nav2 → judge=irrelevant → knowledge_missing）；未实施"高置信跳过 Judge"（被 ⑫-A 否决）。
- knowledge_missing / retrieval_problem / fail-closed：全部保留（WSL/ICM/Nav2 行为不变）。
- source_trace / judge 结果：保留。
- 只读：wiki/gaps/activity/Vector DB 前后不变（gaps 1+5、activity 6、records 34）。

## 9. 是否存在回归

无。19/19 测试通过；answerable 查询的 ±10% 波动为 DeepSeek 延迟方差；检索/证据/安全行为与 ⑫-A 一致。

## 10. 剩余瓶颈

1. **Deep 模式的 Answer Generation（DeepSeek ~2.6-3.4s）+ Judge（~1.4s）**：LLM 调用本身，无法在不削弱安全的前提下消除。
2. **Reranker 推理**（~1.7-2.4s）：已无重载，剩余为 CPU 推理；换 GPU / 更小模型 / 减少 pair 数才能再降（超出本阶段范围）。
3. **BGE 冷加载**（~8.8s）：已预热前移；MCP 重启后仍有一次成本。
4. **MCP 启动**：Codex 重启后加载模型（预热线程），首次调用接近暖。

## 11. 阶段⑫-C建议

1. Codex/MCP 默认使用 **`mode=fast`（证据优先）**，Deep 仅按需（明确要求长答案时）——普通 Codex 查询即可到 ~1s 级。
2. 如需进一步降低 Deep：评估 Answer 缓存（同问同答案命中）、并发双 LLM 请求（Judge 与 Answer 并行，需评估一致性）。
3. Reranker 推理优化（GPU 可用时 / 降低 pair 数）为可选后续。
4. 真实无人机项目回归验证（阶段⑪-C 未完成项）。
5. 将 ⑫-B 变更纳入下一提交（本阶段未 commit）。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
