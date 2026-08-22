# Phase 19：Baseline Regression Governance 实施报告

- 日期：2026-08-16
- 范围：把 Baseline Regression Check 从「人工记得执行的工具」升级为 Wiki/Source/Index 治理流程中的标准质量门禁与自动验证
- 原则：不修改 Retrieval/Reranker/Judge/Evidence Window/Chunking/threshold/Fail-Closed/Benchmark/Baseline 指标定义

## 1. 审计结果
- 已有：batch_approve（批量）、update_index（增量）、evaluate_benchmark（生产）、evaluation_diff（query 级）、
  evaluation_baseline（check/establish）、activity_log、weekly review、preflight 定时任务
- 缺失：evaluation_required 标记、状态机、批量→一次评估聚合、自动 Baseline Check、失败/回归的 baseline 保护、
  CC/Weekly 的治理状态视图（详见 40_Outputs/RAG Evaluation/governance/audit_report.md）

## 2. 实际触发链（实施后）
```
Wiki Approve / Index 变化 / Source 更新
        ↓  （batch_approve 多次批准合并为一次）
evaluation_required = true（evaluation_state.json，reasons 聚合）
        ↓
run_evaluation / governance verify（生产 Benchmark）
        ↓
自动 Baseline Regression Check（regression_check vs baseline.json）
        ↓
passed / improved / regressed / failed
（failed/regressed 不覆盖 baseline；JUDGE_VARIANCE 不判为回归）
```

## 3. Evaluation Required
- 触发：wiki_approved（execute_action approve）、index_updated（sync_kb 且 added+modified+deleted>0）、
  source_updated、manual_request
- 不触发：纯查看 / CC 浏览 / activity 浏览
- 状态文件：`40_Outputs/RAG Evaluation/evaluation_state.json`（status/reasons/batch/run_id/baseline_id/check/error）

## 4. Batch Evaluation
- 多次 approve / 多次变化 → 同一 required 状态（reasons 聚合、batch 计数），只跑一次 Benchmark
- batch_approve 已存在（每项独立日志、幂等），Governance 在其基础上聚合为一次验证

## 5. Baseline Check（自动）
- `run_evaluation` 成功后自动 `_finalize_governance_run()`：regression_check + 状态更新
- `run_baseline_verification()` / CLI `--verify`：required/failed 时运行生产 Benchmark → 自动 Check
- 仅在知识变化 + STABLE/IMPROVED 时重建立 baseline；REGRESSED/FAILED 保留旧 baseline

## 6. 状态机
- idle → required（批量聚合）→ running → passed / improved / regressed / failed
- failed 可重跑（should_verify 含 failed）；JUDGE_VARIANCE 永不为 regressed；失败执行不是 regressed

## 7. Control Center
- `GET /api/rag/evaluation/governance`：status / required / running / run_id / baseline_id / last check
- `POST /api/rag/evaluation/verify`：手动触发验证（required/failed 时执行，idle 跳过）
- RAG Evaluation 视图新增「Evaluation Governance」卡（状态/待验证/上次 Check/验证按钮）

## 8. Activity Log
- 新增 governance 事件：governance_verify（running/failed/passed 等）、governance_finalize（自动 Check 结果）
- 全链路：approve → governance required → evaluation → baseline check 均在 activity_log 可追溯

## 9. Weekly Review（8.6 RAG Quality）
- Governance：passed　Evaluation Required：NO（无）　Last Check：STABLE
- 待验证时显示：⚠ 存在待验证知识变更：请运行 Benchmark + Baseline Check 后再视为已验证

## 10. Scheduler / Preflight
- 不新建第二套调度；提供 CLI `evaluation_governance.py --verify` 作为调度/手动入口（复用现有 evaluate_benchmark /
  evaluation_baseline）；现有 Review Preflight 定时任务保持不变

## 11. 测试结果
- 新增 test_evaluation_governance.py（14）：approve→required、批量合并、index 变化→required、
  index 无变化→不触发、required→running、成功→passed、改进→improved、真实回归→regressed、
  judge variance→非回归、失败→failed、failed 重跑、activity log、CC state、weekly、手动 run、
  failed 不覆盖 baseline
- 修正既有测试隔离：治理状态路径动态跟随 EVAL_ROOT；test_control_center 补 EVAL_ROOT 补丁
- 全量回归：**346/346 通过**（332 既有 + 14 新增）

## 12. 真实验证 Scenario A-E
- A 无知识变化：CLI --verify → "无待验证的知识变化，跳过"（required=false）✅
- B 批准一个 Wiki：execute_action → governance status=required（测试模拟）✅
- C 批量批准：两次 approve → reasons 合并、batch=2、仍是一个 required ✅
- D Evaluation Failure：evaluate_benchmark 失败 → status=failed（不是 regressed）✅
- E Judge Variance：q_drone_power diff regression_class=JUDGE_VARIANCE、REAL_REGRESSION=0 ✅

## 13. 性能影响
- 纯查看/无变化零开销（不触发 evaluation）
- 知识变化仅置位 required（毫秒级）；真正的 Benchmark 只在 verify 时执行一次（batch 合并）
- Governance 状态为单文件 JSON，无新服务/线程

## 14. 当前限制
- 触发点是「标记 required」，实际 Benchmark 仍需显式 verify（手动/调度），未自动定时跑（避免无变化时浪费）
- 自动化程度取决于调度接入（提供 CLI 入口，未改 Windows 计划任务）
- index_updated 的「知识变化」由 sync_kb 的 added/modified/deleted 判定，未覆盖纯 frontmatter 元数据变化

## 15. 下一阶段建议
- 把 `evaluation_governance.py --verify` 接入现有 Windows 定时任务（如 preflight 同频，但仅在 required 时执行）
- 扩展 index 变化检测到 content hash / 元数据变化
- 把 governance required 状态纳入 CC dashboard 顶栏提示

---

## 最终数字

```
Wiki Approve → Evaluation Required：YES
Index Change → Evaluation Required：YES（仅实际变化时）
Batch Evaluation：YES（多次变化 → 一次验证）
Automatic Baseline Check：YES（Evaluation 成功后自动）
Judge Variance 正确分类：YES（JUDGE_VARIANCE ≠ REGRESSED）
Evaluation Failure 正确分类：YES（failed ≠ regressed）
Auto Rollback：NO
Control Center：PASS
Weekly Review：PASS
Activity Log：PASS
Regression：346/346（332 既有 + 14 新增）
Baseline：82.1%（bl-eval-20260816T000233）
Final Status：STABLE
```
