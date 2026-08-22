# 阶段14：RAG Evaluation / Query Benchmark 实施报告

- 日期：2026-08-14
- 状态：完成
- 范围：只测量，不调参；不修改任何 RAG 检索 / Judge / 阈值 / Evidence Window

## 1. 审计结果

- 已有 Evaluation 能力（直接复用，不重建）：
  - `retrieval_trace`：完整决策链（initial_path / gate / fallback_reason / candidates / ranking / evidence / judge / answer）
  - `retrieval_gate`、`evidence_windows[]`、`judge`、`gap_type`、`evidence{sufficient,...}`
  - Control Center「检索 Trace」视图 + `POST /api/query/trace`
- 已有 Metrics：weekly review（wiki/gaps/health/review）+ review_records + activity log
- 缺失能力（本阶段补齐）：benchmark 数据集、evaluation runner、指标聚合、结构化报告、
  Control Center「RAG Evaluation」视图、Weekly Review 的 RAG Quality 引用
- Query history 无持久化：本阶段只实现“每次执行上报 + 最近一次运行可查”，不强行建库

## 2. Benchmark 数据集

- 文件：`90_System/rag/evaluation/benchmark.yaml`（benchmark_version=1.0，29 条真实查询）
- 覆盖领域：FreeRTOS(5)、STM32(5)、驱动(4)、硬件/选型(4)、通信协议(1)、
  移动底盘(3)、无人机(3)、机器人/工具链(4)
- 覆盖 query_type：fact / configuration / procedure / troubleshooting / comparison /
  concept / cross_document
- 覆盖路径预期：wiki 命中、wiki fallback、knowledge missing、跨文档
- `expected_*` 一律标注 `expected: heuristic/manual/unknown`，不作为 ground truth；
  `expected_source` 允许 `either/unknown`，不把路径写死

## 3. Golden Set

- 文件：`90_System/rag/evaluation/golden.yaml`（golden_version=1.0，6 条）
- 字段：ground_truth{answerable, relevant_sources, expected_path} +
  review{answerable, evidence_quality, answer_correct, evidence_supported, citation_correct} +
  reviewer/date
- 第一版人工标注全部为 null/unknown：不编造质量标签；等人工核对后填写

## 4. Evaluation Runner

- 文件：`90_System/rag/scripts/evaluate_benchmark.py`
- 行为：读取 benchmark → 逐条调用生产 `knowledge_service.knowledge_search`
  （默认 mode=fast，走完整 Wiki-first → Quality Gate → RAW fallback → BGE Reranker →
  Evidence → DeepSeek Judge 链）→ 记录 retrieval_trace/evidence/judge/latency
  → 聚合指标 → 写报告
- 禁止项：不重新实现 retrieval/embedding/rerank/judge；不改任何参数；不写知识库
- 进程内复用 embedder/store：`--warmup N` 吸收模型加载，后续为真实热查询
- 输出：`40_Outputs/RAG Evaluation/runs/<run_id>/`（meta.json + evaluation_records.jsonl +
  evaluation_report.json + evaluation_report.md）+ `latest.json` 指针
- CLI：`--benchmark/--golden/--config/--out/--limit/--mode fast|deep/--warmup/--no-llm/--json/--dry-run`

## 5. Metrics

- 文件：`90_System/rag/rag_engine/evaluation.py`（纯函数，无 UI/网络依赖）
- 指标：Answer Coverage / Knowledge Missing Rate / System Error Rate（严格拆分，不混算）；
  Wiki Hit / Gate Pass / Answer / Fallback / Fallback Recovery；
  RAW Query / Reranker Used / RAW Evidence Sufficient / RAW Answer / RAW KM；
  Fail-Closed 拆分；Evidence 窗口统计；Latency P50/P90/P95（线性插值）；
  By Domain / By Query Type；Golden 人工标注统计
- 禁止综合 RAG Score：只输出透明原始指标 + 分项，不设未经验证的权重总分
- 样本 < 20 明确标注 `sample_too_small`，不伪造趋势

## 6. Failure Taxonomy

- 分类（由 trace/judge/final 派生，不新增数据源）：
  WIKI_MISS / WIKI_BELOW_THRESHOLD / WIKI_EVIDENCE_INSUFFICIENT / WIKI_JUDGE_REJECTED /
  RAW_RETRIEVAL_WEAK / RAW_EVIDENCE_INSUFFICIENT / RAW_JUDGE_REJECTED /
  KNOWLEDGE_MISSING / SYSTEM_ERROR
- `system_error` 永远不算 `knowledge_missing`

## 7. Knowledge Gap Signals

- `answered`：已回答
- `likely_knowledge_gap`：无门槛内候选且预期不可回答/未知 → 很可能知识库缺失
- `evidence_gap`：Judge 拒绝或有候选通过门槛但证据不足 → 有资料但证据不完整
- `retrieval_gap`：预期有资料但检索未命中 → 需人工确认（本次为 0）

## 8. Evaluation Report

- 每次运行输出：`40_Outputs/RAG Evaluation/runs/<run_id>/evaluation_report.md`
- 含 Dataset / Overall / Wiki-First / RAW Retrieval / Fail-Closed / Evidence /
  Latency / By Domain / By Query Type / Golden Set / Failure Analysis /
  Knowledge Gap Signals / Recommendations
- `latest.json` 供 Control Center 与 Weekly Review 引用

## 9. Control Center

- `GET /api/rag/evaluation`：latest + runs 列表
- `GET /api/rag/evaluation/<run_id>`：完整报告
- `POST /api/rag/evaluation/run`：运行 Benchmark（子进程，900s 超时）
- 新视图「RAG Evaluation」：Answer Coverage / Knowledge Missing / Wiki Hit /
  Wiki Fallback / Fallback Recovery / RAW Answer / Evidence 窗口 / P50/P95 /
  Top Failure Reasons / Knowledge Gap Signals / Recent Benchmark Runs + 运行按钮
- 中英文术语与既有 UI 保持一致；不暴露 CoT

## 10. Weekly Review

- `metrics.collect_rag_evaluation()`：读取 latest.json（确定性，无则 None）
- 周报新增「## 8.6 RAG Quality」：Answer Coverage / Knowledge Missing /
  Wiki Hit / Fallback Recovery / RAW Answer / Evidence / P50/P95 /
  Main Failure Reasons / Knowledge Gap Signals
- snapshot.json 增加 `rag_evaluation` 字段；weekly_review_dashboard 增加 `rag_evaluation`
- 未运行 Benchmark 时周报正常生成，只提示“暂无 RAG Evaluation 数据”

## 11. 测试结果

- 新增：`tests/test_benchmark_metrics.py`（14）+ `tests/test_rag_evaluation.py`（9）= 23
- 覆盖：benchmark/golden schema、runner 调生产路径（mock）、wiki/raw metrics、
  fallback recovery、knowledge_missing vs system_error 拆分、latency 聚合、
  sample-too-small、golden 人工字段、failure taxonomy、gap signals、CC API、
  weekly review 引用、报告 markdown
- 全量回归：**265/265 通过**（既有 242 + 新增 23）

## 12. 真实 Benchmark 结果

- run_id：`eval-20260814T232719`（28 条 = 29 查询 − 1 warmup）
- 模型：embedding=BGE-small-zh-v1.5；reranker=bge-reranker-v2-m3；LLM=deepseek-chat（Judge）
- Warmup 总耗时（含模型加载）：22.6s；首个记录查询（warm 后）：1185ms
- 每查询耗时：P50=1352ms / P90=4141ms / P95=5206ms
  - Retrieval：P50=31ms；Rerank：P50=2547ms（CPU，最大单项耗时）；Judge：P50=1203ms

| 指标 | 值 |
|---|---:|
| Answer Coverage | 71.4%（20/28） |
| Knowledge Missing | 28.6%（8） |
| System Error | 0.0%（0） |
| Wiki Hit Rate | 89.3%（25） |
| Wiki Gate Pass Rate | 89.3% |
| Wiki Answer Rate | 71.4%（20） |
| Wiki Fallback Rate | 17.9%（5） |
| Fallback Recovery | 0.0%（0/5） |
| RAW Query Rate | 28.6%（8） |
| Reranker Used Rate | 28.6% |
| RAW Evidence Sufficient | 0.0% |
| RAW Answer Rate | 0.0% |

- Fail-Closed 拆分：RAW_EVIDENCE_INSUFFICIENT=5（17.9%）、RAW_JUDGE_REJECTED=3（10.7%）
- Evidence：Avg Window=4.4，多窗口率=100%，Avg 字符/查询=2873
- By Domain 失败最多：tooling（0/2）、robot（0/1）、drone（2/3）、freertos（3/5）、stm32（3/5）
- By Query Type：configuration 50%（6/12）最弱；troubleshooting 0%（0/1）
- Gap Signals：likely_knowledge_gap=2（px4_ekf、wsl_ubuntu）、evidence_gap=6、
  retrieval_gap=0（无“预期有资料但检索未命中”）

## 13. 主要发现

1. **Wiki-first 可靠**：25/28 通过门槛，20/28 直接由 Wiki 回答（71.4%），0 系统错误。
2. **RAW fallback 当前无救回价值**：5 次 fallback 全部最终 knowledge_missing，
   Fallback Recovery=0%。fallback 引入 rerank(≈2.5s)+judge(≈1.2s) 成本但未救回任何查询。
3. **Reranker 是最大单项延迟**：P50≈2.5s（CPU 上 bge-reranker-v2-m3），占 warm 查询总耗时大头。
4. **Judge/Fail-Closed 行为合理**：8 个 knowledge_missing 全部有明确原因
   （5 证据不足 + 3 Judge 拒绝），没有“有候选却误答”的情况；system_error=0。
5. **知识面缺口集中**：PX4 EKF、ROS2 Nav2、WSL、Git 配置、STM32 低功耗、FreeRTOS 栈溢出/
   任务通知、STM32CubeMX PWM 输出（Judge 拒绝，说明 Wiki 内容覆盖了术语但未真正回答）。
6. **query_type=configuration 是最大失败类型**（50% 覆盖率），知识库对“如何配置/调参”
   类问题支撑最弱。

## 14. 当前最大问题

- 直接回答：**RAW fallback 对 Wiki 未命中/证据不足的查询救回率为 0，且引入 ~2.5s Reranker +
  ~1.2s Judge 的成本**；8 个失败全部指向知识库内容缺口（尤其 configuration/troubleshooting 类），
  而不是检索算法本身（retrieval_gap=0，检索层 P50 仅 31ms）。

## 15. 下一阶段建议（按数据驱动，不在本阶段改参数）

1. 治理知识面：按 Top Failure 补齐 PX4 EKF、ROS2 Nav2、WSL、Git、STM32 低功耗、
   FreeRTOS 栈溢出/任务通知、CubeMX PWM 输出等 Wiki 内容，然后重跑 Benchmark 看覆盖率变化。
2. 评估 Reranker 成本收益：Fallback Recovery=0 时，考虑是否在 RAW fallback 路径降低
   reranker 频率或换更轻模型（需先验证再改，本阶段未改）。
3. 人工标注 Golden Set 6 条，获得 answer_correct/evidence_supported/citation_correct 基线。
4. 把 Benchmark 纳入每周回归：Weekly Review 已引用 latest.json，可形成周维度 RAG 质量趋势。

---

## 最终结论

```
Benchmark Query 数：28（数据集 29，含 1 warmup）
Answer Coverage：71.4%（20/28）
Knowledge Missing：28.6%（8/28）
Wiki Hit Rate：89.3%
Wiki Fallback Rate：17.9%（5/28）
Fallback Recovery：0.0%（0/5）
RAW Answer Rate：0.0%（0/8）
Evidence Sufficiency（RAW）：0.0%（0/8）
P50：1352ms
P95：5206ms
Top Failure：RAW_EVIDENCE_INSUFFICIENT（5）+ RAW_JUDGE_REJECTED（3）
Likely Knowledge Gap：2（px4_ekf、wsl_ubuntu）
Likely Retrieval Gap：0
Regression：265/265（既有 242 + 新增 23）
结论：当前 Knowledge OS 的主要瓶颈是「知识面内容缺口 + RAW fallback 救回率为 0」，
即配置/排障类查询缺资料（configuration 覆盖率仅 50%），而检索与判定链路本身
（retrieval_gap=0、system_error=0）没有明显问题；下一步应先按 Top Failure 补知识，
再重跑 Benchmark 验证，而不是调检索参数。
```
