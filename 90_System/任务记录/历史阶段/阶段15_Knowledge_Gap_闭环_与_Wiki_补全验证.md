# 阶段15：Knowledge Gap 闭环与 Wiki 补全验证报告

- 日期：2026-08-15
- 范围：Evaluation 失败 → Knowledge Gap → Wiki 补全 → Reindex → Benchmark → Diff
- 原则：不修改任何 RAG 参数/Judge/阈值；Wiki 修改只以 draft 形式，遵守生命周期；不编造无来源知识

## 1. 审计结果（基于真实 Benchmark eval-20260814T232719）

- 8 个失败 Query 全部来自 28 条真实 Benchmark（Coverage 71.4%，KM 28.6%）
- 失败分类（5 分类，不把所有 knowledge_missing 当知识缺口）：
  - evidence_gap=3（q_freertos_stack_overflow、q_ros2_nav2、q_git_config）
  - judge_gap=3（q_freertos_task_notification、q_stm32_timer_pwm、q_stm32_low_power）
  - knowledge_gap=2（q_px4_ekf、q_wsl_ubuntu）
  - retrieval_gap=0、system_error=0
- 关键判断：8 个失败里 6 个是「有候选但证据/Judge 不通过」或「有 Source 未编译」，
  只有 2 个（PX4 EKF、WSL）是真正无可靠资料的 knowledge_gap

## 2. Gap 注册表（90_System/rag/evaluation/gaps.yaml）

7 个 Gap（按知识边界聚类，非按 Query 逐条建 Wiki；每个 Gap 保留证据）：
- gap_freertos_config_debug（P0，open）← q_freertos_stack_overflow + q_freertos_task_notification
- gap_git_config（P1，open）← q_git_config
- gap_stm32_cubemx_pwm（P1，open）← q_stm32_timer_pwm
- gap_stm32_low_power（P2，open）← q_stm32_low_power
- gap_px4_ekf（P2，open）← q_px4_ekf
- gap_ros2_nav2（P2，open）← q_ros2_nav2
- gap_wsl_ubuntu（P2，open）← q_wsl_ubuntu

每个 Gap 含 signals（query_count/knowledge_missing/evidence_insufficient/judge_rejected）、
source_available、wiki_exists、wiki_target、recommended_action、problem、
evidence{query_ids, failure_types, failure_kinds, existing_wikis, retrieval_traces}。

## 3. 有 Source 可编译 / 无 Source

- 有 Source：gap_freertos_config_debug（任务通知 Inbox md）、gap_git_config（PDF）、
  gap_stm32_cubemx_pwm（定时器 PDF，但目标是 reviewed Wiki）
- 无 Source（acquire_source）：gap_stm32_low_power、gap_px4_ekf、gap_ros2_nav2、gap_wsl_ubuntu

## 4. Wiki 补全执行（本阶段只做「新 Wiki Draft」，遵守生命周期）

依据 AGENTS.md：AI 只能生成 draft、不得直接修改 reviewed/stable Wiki、正文必须来自已有资料。
- 新建 20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md（draft，来源：Inbox FreeRTOS任务通知补充资料.md）
- 新建 20_Wiki/01_计算机基础/Git基础配置.md（draft，来源：Git 配置.note.pdf）
- 未修改 reviewed 的 STM32CubeMX定时器配置.md（PWM 扩充以任务形式留待人工审核）；
  无 Source 的 4 个 Gap 不编造内容，只登记 acquire_source

## 5. Reindex

- update_index.py --target main：34 → 36 chunks（新增 2 个 draft Wiki 均进入索引）
- 验证：20_Wiki/01_计算机基础/Git基础配置.md、20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md 均在 main_vector_db

## 6. Benchmark After（eval-20260815T002430，真实执行）

- Answer Coverage：67.9%（19/28）｜Knowledge Missing：32.1%（9）｜System Error：0%
- Wiki Hit Rate：89.3%｜Wiki Fallback Rate：21.4%（6）｜Fallback Recovery：0.0%（0/6）
- RAW Answer Rate：0.0%｜RAW Evidence Sufficient：0.0%
- P50=1247ms / P95=5103ms

## 7. Diff（Before → After，query 级）

- Recovered：0
- Unchanged：27
- Regressed：1（q_drone_power：answered → knowledge_missing）
- New failures：0
- Query Recovery Rate：0.0%
- 回归分析：q_drone_power 的检索候选几乎一致（top5 相同来源、相同分数），
  差异在 DeepSeek Judge 判定（passed → insufficient），属 Judge 随机性而非索引回归

## 8. 为什么 0 恢复

两个新增 draft Wiki 内容极薄（Inbox 来源只有 3 个要点 / PDF 只有 245 字），
且查询问的是「怎么使用/怎么配置」这类操作步骤，来源本身不含操作步骤。
按 AGENTS.md「禁止用 LLM 自身知识补写无来源细节」，不能编造步骤 → 无法恢复查询。
这是诚实的结果：**真正瓶颈是 Source 缺失/过薄，而不是 Wiki 编译能力**。

## 9. Control Center / Weekly Review

- 新增：`GET /api/gaps/evaluation`、`GET /api/gaps/evaluation/<id>`、`POST /api/gaps/diagnose`、
  `GET /api/rag/evaluation/diff`、`POST /api/rag/evaluation/diff`
- Knowledge Gaps 视图增强：RAG Evaluation 来源表（出现次数/失败类型/Query/Source/Wiki/优先级/建议/状态/详情）
- RAG Evaluation 视图：Before/After Diff 面板（Recovered/Regressed/New failures）
- Weekly Review 8.6：Open Knowledge Gaps=7、Resolved=0、Query Recovery=0、Regression=1

## 10. 测试

- 新增 test_knowledge_gap_pipeline.py（10）+ test_evaluation_diff.py（6）= 16
- 覆盖：failure→gap 分类、已有 Wiki 不足→wiki_improvement、无 Source→acquire_source、
  聚类、优先级、before/after 对比、recovered/regressed、gap 自动 resolved、
  CC API、Weekly Review metrics、markdown 渲染
- 全量回归：**281/281 通过**（265 既有 + 16 新增）

## 11. 主要发现

1. 8 个失败中 6 个是「内容不足/来源未编译」，只有 2 个是真正知识缺失——审计分类有效。
2. 本轮 Wiki 补全 0 恢复 + 1 回归（Judge 随机性），证明：**薄来源编译成 Wiki 不能改善回答，
   反而可能引入候选噪声**；下一步必须优先获取可靠 Source。
3. Fallback Recovery 持续为 0%（5 次 → 6 次），RAW fallback 在现有知识面上无救回价值。
4. Judge 方差已实际影响结果（同一证据 passed/insufficient 翻转），
   Benchmark 的 query 级 diff 比总 Coverage 更能暴露这类问题。

## 12. 当前最大问题

- **Source 层是主要瓶颈**：FreeRTOS 栈溢出/任务通知、Git、STM32 低功耗、PX4 EKF、
  ROS2 Nav2、WSL 都没有足够可靠的操作类资料；Wiki 编译只能忠实转写已有内容。
- 其次：RAW fallback（含 Reranker ~2s + Judge ~1.2s）持续 0 救回，属于成本无收益路径。

## 13. 下一阶段建议（按数据驱动）

1. 优先获取 Source（P0/P1）：FreeRTOS 栈溢出检测、任务通知 API 用法、Git 完整配置步骤、
   STM32CubeMX PWM 输出步骤 → 放入 10_Sources / 00_Inbox → 重新编译 draft → Review → Reindex → Benchmark。
2. 人工核对 q_drone_power 的 Judge 方差（同一证据两次判定不同），决定是否需要固定 Judge 输入/重试。
3. 人工标注 Golden Set（2 wiki-first + 2 fallback + 2 knowledge_missing），
   用 answer_correct/evidence_supported 校验 Judge 不是 ground truth。
4. 评估 RAW fallback 成本收益：救回率持续为 0 时，考虑在后续阶段提出「是否关闭/降频 fallback」的
   数据论证（本阶段不改任何参数）。

---

## 最终结论

```
Before Coverage：71.4%（20/28）
After Coverage：67.9%（19/28）
Coverage Improvement：−3.5pp（0 recovered，1 regressed，均为真实测量）
Fallback Recovery Before：0.0%（0/5）
Fallback Recovery After：0.0%（0/6）
Knowledge Missing Before：28.6%（8）
Knowledge Missing After：32.1%（9）
Recovered Queries：0
Regressed Queries：1（q_drone_power，Judge 随机性，检索候选未变）
Open Knowledge Gaps：7
Resolved Gaps：0
Golden Set Answer Correctness：未人工标注（null，不编造）
Golden Set Evidence Support：未人工标注（null，不编造）
Regression：281/281（既有 265 + 新增 16）

结论：当前 Knowledge OS 的下一主要瓶颈是「可靠 Source 缺失/过薄」——
本阶段闭环已可运行（Failure→Gap→Wiki Draft→Reindex→Benchmark→Diff），
并如实显示：薄来源编译成 Wiki 不能恢复查询（0 recovered），且 Judge 随机性会造成
query 级回归（1 regressed）。下一步应先获取 P0/P1 Gap 的可靠来源并人工标注
Golden Set，而不是继续增加薄 Wiki 或调检索参数。
```
