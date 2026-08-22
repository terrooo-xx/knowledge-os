---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑨：Evidence Intelligence 与知识回答安全增强

> 核心目标：解决阶段⑧残余 False Positive，让"检索相似"升级为"证据能回答问题"——
> 实现 LLM Relevance Judge（fail-closed、可开关、离线可 mock），并把阶段⑤遗留的
> Wiki 审核工作接入 Control Center 日常工作流（含批量审核二次确认）。

## 1. 阶段目标

1. 在 Heuristic Evidence Gate 之上增加 LLM Relevance Judge；
2. 将阶段⑧ FP=1/9 降至理想 0，且不恶化 FN；
3. Judge 必须 fail-closed、可关闭、离线可用 Mock；
4. Wiki Review / 批量审核接入 Control Center（二次确认、独立日志、幂等）。

## 2. 当前 Evidence Pipeline（阶段⑨后）

```text
Query
  → Similarity Retrieval（Dense + BM25 → Reranker）
  → Heuristic Evidence Gate（assess_evidence：阈值 + 主题词覆盖门控）
       ├─ 明显不足 → insufficient → Gap
       └─ 通过 → LLM Relevance Judge（仅当 evidence_judge.enabled 且 llm 可用）
                  ├─ RELEVANT → sufficient → Answer
                  └─ IRRELEVANT / Judge 失败 → insufficient → Gap
```

## 3. LLM Judge 设计

- 定位：证据判断器（RELEVANT / IRRELEVANT），**不是回答器**。
- 输入：Query + Top-K 检索片段（一次调用判断证据集合，不逐 chunk 调用）。
- 输出：`{"relevance": "relevant|irrelevant", "reason": "一句话原因", "confidence": 0.0~1.0}`。
- 三态（RELEVANT/PARTIAL/IRRELEVANT）暂不引入，保持二态避免复杂度失控（任务 §8 推荐）。
- 复用现有 LLM 层：`llm.create_llm` + `build_context`，仅替换提示词模板，无第二套 LLM client。
- 提示词：`90_System/prompts/relevance_judge.md`（明确"只提关键词≠能回答"、"多片段合起来能回答=relevant"）。

## 4. LLM Judge 实现

- 新模块 `rag_engine/judge.py`：`judge_relevance(query, chunks, cfg)`、`parse_judge_output(raw)`、`judge_enabled(cfg)`。
- 接入 `rag_engine/retrieval.py::answer_query`：heuristic sufficient 且启用时调用；结果写入返回的 `judge` 字段（可观测）。
- 配置：`evidence_judge: {enabled, top_k}`；`config.yaml` 生产 `enabled: true`，`config.py` DEFAULTS `enabled: false`（默认保守）。

## 5. Judge 输入输出（实测）

```text
Query: ROS2 Nav2 代价地图怎么配置？
Chunk: 工控机采用 Ubuntu + ROS2 + Nav2 运行环境...
Judge: {"relevance": "irrelevant", "reason": "只提到Nav2，没有配置方法", "confidence": 0.95}
最终: sufficient=false, gap_type=knowledge_missing
```

## 6. Fail Closed 机制

- Judge 内部 try/except：LLM 不可用 / 超时 / 输出非 JSON / JSON 字段非法 → 返回 `irrelevant + error=True`（fail closed）。
- retrieval.py 再加一层防御：`judge_relevance` 抛异常 → 降级 `irrelevant`（fail closed），绝不"默认 relevant"。
- 离线（`--no-llm` / provider=none/mock）自动跳过 Judge，保持原 Heuristic 行为。

## 7. False Positive 测试（阶段⑨）

| 查询 | 阶段⑧ | 阶段⑨ |
|---|---|---|
| ROS2 Nav2 代价地图怎么配置？ | **FP（sufficient）** | ✅ irrelevant → knowledge_missing |
| Obsidian 的 Git 怎么配置？ | 已修（heuristic 捕获） | ✅ knowledge_missing |
| WSL 里怎么装 Ubuntu？ | 已修 | ✅ knowledge_missing |

阶段⑨ 9 查询集：**FP = 0/9**（阶段⑧ 1/9）。

## 8. False Negative 测试

阶段⑨ 9 查询集：**FN = 0/9**（与阶段⑧一致，无恶化）。稳定 3 篇查询 judge 均 relevant、sufficient 保持 true，无回归。

## 9. 阶段⑧与阶段⑨对比

| 指标 | 阶段⑧ | 阶段⑨ |
|---|---|---|
| FP | 1/9 | **0/9** |
| FN | 0/9 | 0/9 |
| 稳定 3 篇 | 正常 | 正常（judge=relevant） |
| 判断链路 | Similarity+Topic Coverage | +LLM Judge |

## 10. Wiki Review / 批量审核

- Control Center 已显示 16 条 draft wiki_review（AI 建议 approve/review）+ 4 条 pending Gap。
- 新增 **批量批准**：`POST /api/actions/batch/approve`（body `{ids, confirm:true, actor}`）。
- 安全要求全部满足：显示数量/目标/状态/AI 建议；`confirm=true` 二次确认（缺省拒绝执行）；**逐项独立执行**，单项失败不影响其他；Activity Log **每个 Wiki 单独记录**；幂等（二次执行 already_done）。
- UI：Wiki Review 页新增复选框 + "确认批准选中项"（confirm 弹窗）。

## 11. Source 检索评估

- 结论（沿用阶段⑥+复测）：Wiki 不足时 `--store raw` 能检索到 Source，但 raw 未生产化、薄源被 evidence 门控判 insufficient——"Source 能提供有用证据"取决于源文本质量。
- 最小修改方案（仅建议，不实施）：未来若启用 Source fallback，可在 main insufficient 且 raw 非空时自动二次检索 raw；当前 raw 保留为可选工具。

## 12. 离线测试

- `tests/test_judge.py`（全部离线，无真实 LLM）：parse 正常/围栏 JSON/非法 JSON/空输出；judge relevant/irrelevant/failure(fail closed)/disabled/offline-skip 共 11 用例 PASS。
- `tests/test_control_center.py` 新增批量审核用例（confirm 缺失拒绝、逐项成功/失败、幂等、单条日志）PASS。
- 全量 16 个测试文件 PASS。

## 13. Health Check

```text
knowledge_os_check：ERROR=0，WARNING=3（不变），PASS=98
rag_health（main）：ERROR=0，PASS=8，INFO=1
```
阶段⑨未引入新的 ERROR。

## 14. 修改文件

| 文件 | 修改 | 测试 |
|---|---|---|
| `90_System/rag/rag_engine/judge.py`（新） | LLM Relevance Judge + parse + fail closed | test_judge PASS |
| `90_System/rag/rag_engine/retrieval.py` | 接入 judge（含防御性 fail-closed）、返回 judge 字段 | test_judge/test_main_query PASS |
| `90_System/rag/prompts/relevance_judge.md`（新） | Judge 提示词 | - |
| `90_System/rag/rag_engine/config.py` / `config.yaml` | `evidence_judge` 配置（DEFAULTS off / 生产 on） | - |
| `90_System/rag/tests/test_judge.py`（新） | 11 个离线用例 | PASS |
| `90_System/control_center/service.py` / `server.py` / `static/index.html` | 批量批准（确认/逐项/独立日志/幂等）+ UI 复选框 | test_control_center PASS |

## 15. 未解决问题

- 阶段⑨评估查询新增 3 条真实 pending Gap（PX4 无人机 EKF、PX4 EKF、WSL Ubuntu）——均为知识库确实缺失的主题，按真实缺口保留，可人工 ignore/删除。
- Judge 依赖生产 LLM（DeepSeek）：每次 heuristic 通过的问题多一次 LLM 调用（成本与联网要求）；离线模式自动跳过。
- Judge 为二态；PARTIAL 场景（多片段组合）依赖提示词引导，未做专门量化。
- Source fallback 仍为可选工具（raw 未生产化）。
- 4 个图片型 PDF 未 OCR（既定不做）。

## 16. 是否需要进一步增强

- 建议阶段⑩候选：① Judge 结果进入 Activity/审计（谁被拒、为什么）；② Judge 置信度阈值可配置（<0.5 且 relevant 时仍放行等）；③ 对 PARTIAL 场景增加组合相关性判定；④ Source fallback 自动路由评估。
- 本阶段不再扩。

## 17. 阶段⑩建议

1. 把 Judge 决策写入审计（可解释性增强）；
2. 批量审核工作流正式启用（把 16 条 draft 按阶段⑤ APPROVE 建议批量送审，逐条人工确认）；
3. 评估 Source fallback 自动路由（main 不足→raw）；
4. 首次 Git 基线提交（需授权）。

## 18. Git 状态

`commit = NO`，`push = NO`。本阶段改动均为未跟踪文件（judge.py、retrieval.py、relevance_judge.md、config、test_judge.py、control_center 批量审核），未覆盖用户已有修改。建议：当前仓库已形成完整稳定基线，可在你授权后建立首次 commit。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
