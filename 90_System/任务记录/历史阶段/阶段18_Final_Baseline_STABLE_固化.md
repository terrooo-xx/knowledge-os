# Phase 18 Final：Baseline STABLE 固化报告

- 日期：2026-08-16
- 范围：确认 WSL 批准 → 正式 Reindex → WSL Approval Post-Verification Benchmark → 重新建立 Baseline → 从 UNVERIFIED 提升为 STABLE
- 原则：不修改 RAG；同一批 28 Query；JUDGE_VARIANCE 不阻止 STABLE

## 1. Wiki Approval

- FreeRTOS 栈溢出：reviewed ✅
- FreeRTOS 任务通知：reviewed ✅
- STM32 PWM：reviewed ✅
- WSL Ubuntu：**reviewed ✅（本次新批准）**
- Approved：**4 / 4**
- WSL 批准有真实后端记录：activity_log.jsonl 存在 `wiki_review/approve`（user_decision=approve，message "-> reviewed"）
- 说明：按当前生命周期，`review_required` 字段在 approve 后仍保留 true（set_status 只改 status/updated，
  与既有 reviewed/stable Wiki 一致）；批准信号以 `status: reviewed` 为准

## 2. Index

- Before：43 chunks（WSL 元数据为 draft）
- After：43 chunks（正式 Reindex 后 WSL 元数据刷新为 reviewed）
- 4 个 Wiki 均确认在 main_vector_db，status 元数据全部 = reviewed

## 3. Benchmark

- Version：1.0（同一 benchmark.yaml，未增删改 Query）
- Query Count：28
- Run ID：`eval-20260816T000233`（WSL Approval Post-Verification）
- Coverage：**82.1%（23/28）**
- Knowledge Missing：17.9%（5/28）
- System Error：0

## 4. Recovered Queries（4/4 保持）

| Query | Final | Path/Source | Evidence | Judge |
|---|---|---|---|---|
| q_freertos_stack_overflow | answered | wiki_first / FreeRTOS栈溢出检查 | sufficient | passed |
| q_freertos_task_notification | answered | wiki_first / FreeRTOS任务通知 | sufficient | passed |
| q_stm32_timer_pwm | answered | wiki_first / STM32定时器PWM输出 | sufficient | passed |
| q_wsl_ubuntu | answered | wiki_first / WSL安装Ubuntu | sufficient | passed |

- Recovered retained：**4 / 4**

## 5. q_drone_power

- Classification：JUDGE_VARIANCE（证据/检索与既往一致，仅 Judge 跨 run 判定波动）
- Phase18→Final diff：UNCHANGED_FAILED（两轮均为 knowledge_missing），不计为回归
- Conclusion：不污染 Baseline；REAL_REGRESSION = 0

## 6. Baseline

- Baseline ID：`bl-eval-20260816T000233`（替换旧的 UNVERIFIED bl-eval-20260815T163659）
- Coverage：82.1%　Knowledge Missing：17.9%　Query Count：28　Benchmark Version：1.0
- Delta：0.0pp（vs 自身/Phase18 均为 0.0pp）
- Status：**STABLE**
- Regression Protection `--check`：current=82.1% vs baseline=82.1%，delta=0.0pp，status=STABLE，无关键 warning

## 7. Control Center

- `/api/rag/evaluation/baseline`：baseline=bl-eval-20260816T000233，82.1%，STABLE，Wiki Approval 4/4（pending=0），check delta=0 STABLE
- RAG Evaluation 视图「Evaluation Baseline」卡显示 4/4、STABLE；不再显示 WSL 待批准

## 8. Weekly Review（8.6 RAG Quality）

- Baseline：82.1%（bl-eval-20260816T000233，STABLE）　Current Verification：82.1%　Delta：0.0pp　Status：STABLE
- 旧的「⚠ WSL 未批准」警告已不再出现（仅当 status=UNVERIFIED 时显示）；历史记录未删除

## 9. Tests

- 更新 test_evaluation_baseline.py：4/4 approved → establish → **STABLE**（3 处断言从 UNVERIFIED/3-approved 改为 STABLE/4-approved）
- 更新 test_wiki_benchmark_validation.py：最新 diff 语义（Phase18→Final 验证 run：0 recovered/0 regressed）
- 全量回归：**332/332 通过**

## 10. 最终结论

- Phase 18 核心目标达成：82.1% 已从 UNVERIFIED 正式提升为 **STABLE** Baseline。
- 4/4 Source-backed Wiki 全部批准、4/4 恢复 Query 保持、REAL_REGRESSION=0、JUDGE_VARIANCE=1（q_drone_power，未阻止 STABLE）。
- Baseline 固化文件：`40_Outputs/RAG Evaluation/baseline.json` + `baselines/bl-eval-20260816T000233.json` + `baseline.md`

---

## 最终数字

```
4/4 Wiki Approved：YES
4/4 Recovered Retained：YES
REAL_REGRESSION：0
JUDGE_VARIANCE：1（q_drone_power，诊断信息，不阻止 STABLE）
Coverage：82.1%（23/28）
Baseline：ESTABLISHED（bl-eval-20260816T000233）
Baseline Status：STABLE
Regression：332/332
Phase 18：COMPLETE

下一阶段第一优先级：
1. 将 Baseline Regression Check 纳入后续 Wiki 批量批准 / Source 更新 / Index 更新后的例行验证。
2. 继续为 gap_git_config 获取 Obsidian-Git 官方文档，为 P2 gap（低功耗/PX4/Nav2）做 Source Acquisition。
3. 扩展 Golden Set 人工标注（覆盖新恢复的 Wiki 查询），逐步用 Human Ground Truth 校验 Baseline Coverage。
```
