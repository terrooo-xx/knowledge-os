# Phase 19 Audit：Baseline Regression Governance

- 日期：2026-08-16
- 方式：只读审计（未修改代码前）

## 1. 当前 Wiki Approval 流程
- `service.execute_action(action_id="wiki_review:...", "approve")` → `set_status(path, "reviewed")` + `_append_log`
- `service.batch_approve(ids, confirm=True)` 已存在：循环执行 approve，每项独立日志、幂等
- 无任何「评估标记」在批准后产生 → 批准与 Evaluation 之间没有自动连接

## 2. 当前 Index Update 流程
- `service.sync_kb()` → `_run_py("scripts/update_index.py", ["--changed", "--target", "main"])`
- 计算 added/modified/deleted（manifest 前后对比 + update_index 输出）
- 更新 `sync_state.json` + 写 activity log；无「索引变化 → 需评估」标记

## 3. 当前 Evaluation 流程
- `service.run_evaluation()` → 子进程 `evaluate_benchmark.py`（生产路径），写 latest.json + activity log
- 纯手动触发；无状态机、无自动 Baseline Check

## 4. 当前 Baseline Check
- `scripts/evaluation_baseline.py --check`（CLI）→ regression_check（delta/status/warning）
- 仅人工执行；不自动接入 Evaluation 或治理

## 5. 当前 Scheduler / Preflight
- `register_review_preflight_task.ps1`：Review Preflight 每 30 分钟定时（LLM Judge 预处理），与 Evaluation 无关
- Weekly Review 定时任务存在；无 Evaluation 定时触发

## 6. 当前 Activity Log
- `activity_log.jsonl`（append-only JSONL）：approve / sync / evaluation / diff / governance 均已记录（本次新增 governance 类型）
- 链路完整但缺少「状态机」聚合

## 7. 可以直接复用的机制
- `evaluate_benchmark.py`（生产 Evaluation）
- `evaluation_diff.py`（query-level diff）
- `evaluation_baseline.py`（baseline + regression_check + establish）
- `batch_approve`（批量批准已存在）
- `activity_log`（全链路审计）
- `weekly review`（8.6 RAG Quality）
- `run_evaluation` / `sync_kb` / `execute_action`（触发点）

## 8. 缺失的治理连接
- 无 `evaluation_required` 标记（批准/索引变化后不会自动标记）
- 无状态机（idle/required/running/passed/improved/regressed/failed）
- 无「批量变化 → 一次 Evaluation」聚合（batch_approve 已存在但无单次触发标记）
- 无自动 Baseline Check（Evaluation 成功后不会自动跑 regression_check）
- 失败/回归运行无 baseline 保护（手动 establish 会覆盖）
- CC 无 Pending/Running/Result 视图；Weekly 无治理状态

## 9. 推荐最小状态机
- idle → required（知识变化：wiki_approved / index_updated / source_updated，批量合并）→ running → passed / improved / regressed / failed
- failed/regressed 不覆盖 baseline；JUDGE_VARIANCE 不判为回归；failed 可重跑
- 手动 Run Evaluation 仍可用，成功后自动 finalize governance

## 10. 最小修改文件集合
- 新增：`rag_engine/evaluation_governance.py`（状态机）、`scripts/evaluation_governance.py`（CLI）、`tests/test_evaluation_governance.py`
- 修改：`service.py`（approve/sync/run_evaluation 挂钩 + governance API + verify）、`server.py`（2 路由）、`index.html`（Governance 卡）、`metrics.py`/`weekly_review.py`（治理指标）

## 11. 风险
- 挂钩写入全局状态文件 → 测试隔离：治理状态路径动态跟随 `EVAL_ROOT`，既有测试需补 EVAL_ROOT 补丁（已处理）
- 每次小修改不跑 Benchmark → 由 required 状态合并为一次 batch（不逐条触发）
- 真实 Benchmark 昂贵 → verify 仅当 required/failed 时执行；纯查看不触发
