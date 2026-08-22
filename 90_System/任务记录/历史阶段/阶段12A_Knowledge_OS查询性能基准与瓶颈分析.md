---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑫-A：Knowledge OS 查询性能基准与瓶颈分析

> 只测量、定位、出方案，不实施优化、不 commit。基准脚本 `90_System/agent/benchmark_query.py`
> 通过 monkey-patch 分层计时，未修改任何生产源码。

## 1. 测试环境

- Codex desktop（本应用）；Python 3.14.6
- Embedding：BGE-small-zh-v1.5（sentence-transformers 本地缓存）
- Reranker：bge-reranker-v2-m3（本地 modelscope 缓存，`reranker.enabled=true`）
- LLM：DeepSeek（`deepseek-chat`，`DEEPSEEK_API_KEY` 环境变量）
- RAG：main_vector_db（29 文档 / 34 chunk）；hybrid_query 默认 main
- MCP：`knowledge-os` stdio server（`KNOWLEDGE_OS_VAULT=D:\KnowledgeBase\Obsidian Vault`）
- 测试日期：2026-08-11

## 2. 测试查询（6 个）

| 类别 | 查询 |
|---|---|
| A 稳定 Wiki | STM32 时钟树 HSI/HSE/PLL 怎么工作？ |
| A 稳定 Wiki | STM32 DMA 怎么工作？ |
| A 稳定 Wiki | FreeRTOS 任务优先级和抢占式调度是什么？ |
| B 知识缺口 | WSL 里怎么装 Ubuntu？ |
| B 知识缺口 | ICM-42688-P 的 SPI 读取应该注意什么？ |
| C 高相似错误主题 | ROS2 Nav2 代价地图怎么配置？ |

## 3. Cold / Warm 对比（每查询 3 次，单位 ms）

**离线纯本地（use_llm=False，Judge/LLM 关闭）**

| Query | 第1次(冷) | 第2次 | 第3次 | Avg(温) | Min | Max |
|---|--:|--:|--:|--:|--:|--:|
| A1 时钟树 | 9159 | 135 | 137 | 136 | 135 | 137 |
| A2 DMA | 8972 | 140 | 139 | 140 | 139 | 140 |
| A3 FreeRTOS | 9165 | 143 | 147 | 145 | 143 | 147 |
| B1 WSL | 13994 | 4448 | 4430 | 4439 | 4430 | 4448 |
| B2 ICM | 12098 | 3676 | 3658 | 3667 | 3658 | 3676 |
| C Nav2 | 8792 | 135 | 143 | 139 | 135 | 143 |

**真实 LLM（use_llm=True）**

| Query | 第1次(冷) | 第2次 | 第3次 | Avg(温) | Min | Max |
|---|--:|--:|--:|--:|--:|--:|
| A1 时钟树 | 11402 | 4511 | 4282 | 4397 | 4282 | 4511 |
| A2 DMA | 10949 | 3495 | 3442 | 3469 | 3442 | 3495 |
| A3 FreeRTOS | 11468 | 3691 | 4580 | 4136 | 3691 | 4580 |
| B1 WSL | 9619 | 4279 | 4253 | 4266 | 4253 | 4279 |
| B2 ICM | 9021 | 3622 | 3593 | 3608 | 3593 | 3622 |
| C Nav2 | 8441 | 1690 | 1499 | 1595 | 1499 | 1690 |

结论：冷启动 ~8.8-14s（BGE 模型加载主导）；**暖查询 answerable ~3.5-4.6s、缺失/fallback ~3.6-4.3s、Judge 拒绝 ~1.5-1.7s**。

## 4. Pipeline 分层耗时（暖，单次查询）

| Layer | 耗时 | 占总耗时(典型 answerable) |
|---|--:|--:|
| MCP transport | ~0.8s（含启动/握手；单次调用 ~0.1-0.3s） | 小 |
| config 初始化 | 3-20ms | ~0% |
| Embedding（warm，模型常驻） | ~100-110ms | ~2.5% |
| Dense + BM25 + Fuse（34 文档） | ~130ms | ~3% |
| Reranker | **3.2-4.3s**（每次调用重新加载模型） | 仅 fallback 查询 |
| Evidence Gate | ~0.2ms | ~0% |
| LLM Judge（DeepSeek） | ~0.9-1.6s | ~25% |
| Answer Generation（DeepSeek） | **2.3-3.5s** | ~65% |

## 5. LLM 调用统计

```text
answerable 查询：Judge 1 次 + Answer 1 次 = 共 2 次 DeepSeek API
Judge 拒绝（FP）：Judge 1 次 = 共 1 次
Knowledge Missing / retrieval_problem（heuristic 拦截）：0 次
```

## 6. MCP vs Direct

| Mode | 耗时（Q1 时钟树，冷进程） |
|---|--:|
| Direct knowledge_search | 11.4s |
| MCP → knowledge_search | 12.2s |

**MCP 额外开销 ≈ 0.8s（含进程启动+握手），单次调用传输开销 ~0.1-0.3s → 不是瓶颈。**

## 7. 性能瓶颈结论（排序）

1. **Answer Generation（DeepSeek LLM）**：~2.3-3.5s/answerable 查询，占典型查询 ~65%。这是"再生成长答案"的成本。
2. **Reranker 模型每次重载**：`rag_engine/rerank.py` 每次调用 `CrossEncoder(...)` 重新加载 bge-reranker-v2-m3 → **每次 ~3.2-4.3s**（WSL/ICM 等 fallback 查询的固定开销，且与 LLM 无关）。**这是最大的、可本地修复的瓶颈**。
3. **BGE 模型冷加载**：~8.8s，仅每次新进程第一次查询（进程内常驻，暖 ~100ms；MCP 服务长驻后无此成本）。
4. **LLM Judge（DeepSeek）**：~0.9-1.6s/次（heuristic 通过才触发）。
5. **MCP transport**：~0.8s（含启动；可忽略）。
6. **Retrieval / Evidence**：~130ms / ~0.2ms，可忽略。

> 说明：早前观察的 62.6s / 31.8s 为**冷启动（BGE 9s + 进程初始化）+ DeepSeek 网络波动**的极端值；稳态暖查询实测 **answerable ≈ 3.5-4.6s、Judge 拒绝 ≈ 1.5-1.7s**。

## 8. 阶段⑫-B 建议（最小优化方案，均未实施）

| 方案 | 收益 | 风险 | 复杂度 | 影响安全边界 | 建议 |
|---|---|---|---|---|---|
| A. 高置信跳过 Judge | answerable 省 ~1s | **中高**：会重新引入 ROS2 Nav2 类 FP（heuristic 覆盖词但 Judge 拒） | 低 | 是（削弱 Judge） | **暂不实施** |
| B. Codex 默认只返回结构化知识/证据，不再生成"长答案" | answerable 省 ~2.3-3.5s（减半） | 低（evidence/judge 仍在；Codex 自行综合） | 低 | 否 | **强烈建议**（MCP 增加 `evidence_only` 模式） |
| C. Fast / Deep 两种查询模式 | Fast=retrieval+evidence（~0.3s）；Deep=完整（~4s） | 低 | 中 | 否（Fast 明确标注"无 Judge"） | 建议（与 B 结合） |
| D. Reranker 模型常驻（缓存 CrossEncoder 单例） | fallback 查询 3.2-4.3s → ~0.3-0.5s | 低（~2GB 内存常驻） | 低 | 否 | **强烈建议（最大本地优化点）** |
| E. LLM timeout / fail-fast | 避免慢 LLM 拖到数十秒 | 低（fail-closed 保留：超时→knowledge_missing） | 低 | 否 | 建议 |
| F. MCP 启动预热 BGE | 首查询 11s → ~3s | 低 | 低 | 否 | 建议 |

## 9. 关键结论（回答任务问题）

1. 30-60s 瓶颈：**冷启动（BGE 加载）+ DeepSeek 波动**；稳态普通查询 ~4s。
2. BGE 是否重复加载：**进程内不重复**（暖 ~100ms）；每次新进程冷载 ~8.8s；MCP 长驻后常驻。
3. Dense/BM25：~130ms（合在 retrieval 层）；Reranker：**3.2-4.3s（每次重载，最大本地瓶颈）**。
4. Evidence Gate：~0.2ms，可忽略。
5. Judge：~0.9-1.6s/次。
6. Answer：~2.3-3.5s/次。
7. answerable 查询 = **2 次** DeepSeek 调用（Judge+Answer）。
8. MCP：**不是瓶颈**（+~0.8s 含启动）。
9. Cold vs Warm：~8.8-14s vs ~0.14-4.6s（差距主要在 BGE 冷加载 + 慢 LLM）。
10. 最值得优化：**① Reranker 模型缓存（D）；② Answer 默认关闭/证据优先（B+C）；③ LLM 超时（E）**。

## 10. 数据污染与回归

- gaps.yaml：1 resolved + 5 pending（不变）；activity_log：6 行（不变）；Wiki：3/4/13（不变）；main_vector_db：34 records（不变）。
- 原有 18/18 测试全部 PASS；无新 pending Gap；未 commit / 未 push。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
