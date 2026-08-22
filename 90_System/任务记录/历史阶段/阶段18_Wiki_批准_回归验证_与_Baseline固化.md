# Phase 18：Wiki Approval → Regression Verification → Baseline 固化 报告

- 日期：2026-08-15
- 范围：验证批准后的 Wiki 在正式生命周期状态下仍稳定恢复 Benchmark Query，并把验证结果固化为正式 Evaluation Baseline
- 原则：不修改任何 RAG 逻辑；同批 28 Query 严格 Before/After；JUDGE_VARIANCE 不污染 Baseline

## 1. Wiki 状态确认（只读审计）

| Wiki | Phase17 状态 | Phase18 状态 | Review Required | 结果 |
|---|---|---|---|---|
| FreeRTOS栈溢出检查.md | draft | **reviewed** | true | ✅ 已批准 |
| FreeRTOS任务通知.md | draft | **reviewed** | true | ✅ 已批准 |
| STM32定时器PWM输出.md | draft | **reviewed** | true | ✅ 已批准 |
| WSL安装Ubuntu.md | draft | **draft** | true | ⚠ **未批准** |

- 批准动作已由后端记录：activity_log.jsonl 存在 `wiki_review/approve`（user_decision=approve，message "-> reviewed"）共 3 条；
  review_records.json 有 4 条 review_judge 记录。
- **用户前提有偏差：4 个 Wiki 中只有 3 个被批准，WSL安装Ubuntu.md 仍为 draft（仅有 auto_judge=judge_passed、recommendation=approve，无 approve 动作）。**
  本报告如实记录，不伪造批准。

## 2. Index 状态

- Before：43 chunks（phase17 reindex 后）
- After：43 chunks（批准后正式 Reindex，update_index.py --target main）
- 索引中 status 元数据：3 个已批准 Wiki=reviewed；WSL=draft（与文件一致）
- 4 个 Wiki 均在 main_vector_db 确认存在（栈溢出×2、任务通知×3、PWM×2、WSL×1 chunks）

## 3. Benchmark

- Query Count：28（同一 benchmark.yaml，benchmark_version=1.0，未增删改 Query）
- Run ID：`eval-20260815T163659`（phase18_post_approval）
- Coverage：82.1%（23/28）｜Knowledge Missing：17.9%（5/28）｜System Error：0

## 4. Phase 17 → Phase 18 Diff（eval-20260815T154946 → eval-20260815T163659）

- Recovered：0　Regressed：0　Unchanged：28　New failures：0
- 28 条 Query 全部状态一致（含 4 个已恢复 Query 与 q_drone_power）

## 5. 四个关键 Query（Post-Approval）

| Query | Phase17 Before | Phase17 After | Phase18 After | 结果 |
|---|---|---|---|---|
| q_freertos_stack_overflow | knowledge_missing | answered | **answered** | ✅ 稳定保持 |
| q_freertos_task_notification | knowledge_missing | answered | **answered** | ✅ 稳定保持 |
| q_stm32_timer_pwm | knowledge_missing | answered | **answered** | ✅ 稳定保持 |
| q_wsl_ubuntu | knowledge_missing | answered | **answered** | ✅ 稳定保持（内容已验证，正式状态仍 draft） |

4/4 已恢复 Query 全部保持，无一退化。

## 6. q_drone_power

- Phase18：knowledge_missing（RAW_JUDGE_REJECTED）
- 证据对比：命中文档集合与 Phase17/此前一致（锂电池参数计算、无人机硬件选型等同一批文档）
- 结论：**JUDGE_VARIANCE**（同证据仅 Judge 判定波动；不标记 REAL_REGRESSION，不污染 Baseline）
- Phase17→18 diff 中 q_drone_power 为 UNCHANGED_FAILED（两轮都失败），非新增回归

## 7. Baseline

- Baseline ID：`bl-eval-20260815T163659`
- Coverage：82.1%　Knowledge Missing：17.9%　Query Count：28　Benchmark Version：1.0
- Status：**UNVERIFIED**（严格按阶段定义：4 个 Wiki 未全部正式批准，WSL 仍 draft）
- Regression Protection 检查：Current=82.1% vs Baseline=82.1%，Delta=0.0pp，check_status=STABLE
- 固化文件：`40_Outputs/RAG Evaluation/baseline.json` + `baselines/bl-eval-20260815T163659.json` + `baseline.md`

## 8. Control Center

- 新增 `GET /api/rag/evaluation/baseline`：返回 baseline + current run + regression_check（delta/status/warning）
- RAG Evaluation 视图新增「Evaluation Baseline」卡：Baseline ID/Coverage/Status/Wiki Approval（3/4，待批准 WSL）/
  Current/Delta/Status 警告
- （注：测试中发现一个旧 server 进程占用 8765 导致 API 404，已清理并验证新路由正常）

## 9. Weekly Review（8.6 RAG Quality 新增）

- Baseline：82.1%（bl-eval-20260815T163659，UNVERIFIED）　Current Verification：82.1%　Delta：0.0pp　Status：STABLE
- ⚠ Baseline 未正式确立：存在未批准 Wiki（WSL 仍为 draft），批准后重跑确认可转 STABLE
- 其余：Coverage 82.1%、KM 17.9%、Query Recovery 4、Regression 1（JUDGE_VARIANCE）、Open Gaps 4 / Resolved 3

## 10. Tests

- 新增 test_evaluation_baseline.py（11 个测试）：批准状态检测、reindex 检测、同版本 benchmark、4 恢复保持、
  REAL_REGRESSION/JUDGE_VARIANCE、baseline 创建/STABLE/UNVERIFIED、delta、CC API、weekly metrics
- 修正 1 个既有测试（wiki 状态由 draft 变为 reviewed 的断言）
- 全量回归：**332/332 通过**（321 既有 + 11 新增）

## 11. 最终结论

- Phase 17 的 +10.7pp（71.4%→82.1%）已在批准后的正式状态与 Reindex 后**稳定复现**；
  4/4 恢复 Query 保持、0 真实回归、0 新失败。
- Baseline 数据已固化（82.1%），但因 WSL 未批准，正式状态为 UNVERIFIED；
  用户批准 WSL 后重跑 `evaluation_baseline.py --establish` 即可转为 STABLE。

---

## 最终数字

```
Phase 17 Coverage：82.1%（23/28）
Phase 18 Verification Coverage：82.1%（23/28）
Delta：0.0pp
4 个 Recovered Query 保持：YES（4/4）
REAL_REGRESSION：0
JUDGE_VARIANCE：1（q_drone_power，未计入回归）
Baseline：ESTABLISHED（数据已固化）／正式状态 UNVERIFIED（WSL 未批准）
Baseline Status：UNVERIFIED（批准 WSL 后重验可转 STABLE）
Regression：332/332（321 既有 + 11 新增）

说明：
- 用户前提"4 个 Wiki 已批准"与实际不符：3/4 已批准（reviewed），WSL安装Ubuntu.md 仍为 draft。
- 已恢复 Query 的验证不受影响（内容已入索引并保持回答）；仅正式生命周期状态待 WSL 批准。

下一阶段第一优先级：
1. 用户在 Control Center 批准 WSL安装Ubuntu.md → 重跑 evaluation_baseline.py --establish → Baseline 转 STABLE。
2. 将 Baseline Regression Check 纳入每次 Wiki 批量批准/Index 更新后的例行验证。
3. 继续为 gap_git_config 获取 Obsidian-Git 官方文档，为 P2 gap 做 Source Acquisition。
```
