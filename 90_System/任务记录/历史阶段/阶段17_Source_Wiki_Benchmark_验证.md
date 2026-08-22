# Phase 17：Source → Wiki 编译 → 人工审核 → Reindex → Benchmark 验证 报告

- 日期：2026-08-15
- 范围：把已获取的高质量 Source 编译成 gap-driven Wiki，经 Reindex 与 28 条真实 Benchmark 的 Query-level Diff 验证是否恢复失败查询
- 原则：Source > Wiki > Query Answer > 主观感觉；禁止为提覆盖率改 Judge/Retrieval/Chunking/Reranker/fail-closed；不自动 approve

## 1. Source Audit（P0/P1）

### P0 gap_freertos_config_debug（2 条失败）
- Source：FreeRTOS Reference Manual V8.2.1（official，10_Sources，pypdf 可解析 298 chunks）
- 定位：栈溢出 p.274-275；任务通知 p.82-86
- 决策：栈溢出=NEW_WIKI；任务通知=EXPAND（复用阶段15 draft）

### P1 gap_stm32_cubemx_pwm（1 条失败）
- Source：ST AN4013 cross-series timer overview（official，10_Sources，48 chunks）
- 定位：§2.5 Timer in PWM mode p.16-17
- 决策：NEW_WIKI（现有 CubeMX 定时器 Wiki 为 reviewed，AI 不可修改）

### P1 gap_git_config（1 条失败）
- Source：本地 PDF 仅身份配置/.git 识别（245 字）；Obsidian-Git 官方文档为 candidate 未获取
- 决策：EXPAND 现有 draft，但 coverage=partial，标 source-limited，不硬写完整流程

## 2. Wiki Drafts（4 个，全部 status=draft + review_required）

| Wiki | Action | Source 定位 | 内容范围 |
|---|---|---|---|
| 20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md | NEW | RM p.274-275 | configCHECK_FOR_STACK_OVERFLOW、hook 原型、方法1/2、覆盖边界 |
| 20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md | EXPAND | RM p.82-86 | 启用条件、xTaskNotify/AndQuery、eAction 5 种、xTaskNotifyGive、接收 API、示例 |
| 20_Wiki/03_STM32/STM32定时器PWM输出.md | NEW | AN4013 p.16-17 | PWM 配置步骤 1-7、频率/占空比公式、对齐模式、覆盖边界 |
| 20_Wiki/01_计算机基础/WSL安装Ubuntu.md | NEW | Microsoft Learn HTML | wsl --install、发行版选择、用户设置 |
| 20_Wiki/01_计算机基础/Git基础配置.md | EXPAND(边界) | 本地 PDF | 增加 coverage=partial 边界说明（source-limited） |

## 3. Human Review

- 本阶段不自动 approve：4 个新 Wiki 均为 status=draft + review_required=true，等待人工审核
- Golden q_freertos_stack_overflow 状态变化（未回答→已回答）→ 标注 review_required=true 待人工复核，不自动改人工标注

## 4. Reindex

- Before Index：36 chunks → After Index：43 chunks（+7）
- 新增/更新 Wiki：5 个；index_manifest 重建（rebuilt=True）
- 新 Wiki 均在 main_vector_db 确认索引

## 5. Benchmark Before / After（28 条同一批 Query）

- Coverage：71.4%（20/28）→ **82.1%（23/28）**
- Knowledge Missing：28.6%（8）→ 17.9%（5）
- Wiki Hit Rate：89.3% → 92.9%
- Wiki Fallback Rate：17.9%（5）→ 10.7%（3）
- Fallback Recovery：0% → 0%（无 fallback 救回，但 fallback 次数下降）

## 6. Query-level Diff（eval-20260814T232719 → eval-20260815T154946）

- **Recovered：4**（q_freertos_stack_overflow、q_freertos_task_notification、q_stm32_timer_pwm、q_wsl_ubuntu）
- Unchanged：23；Regressed：1；New failures：0
- **Query Recovery Rate：50.0%**（4/8 此前失败）
- q_drone_power 保持 **JUDGE_VARIANCE**（命中同批文档，仅 Judge 跨 run 翻转）；REAL_REGRESSION=0
- 未恢复：q_git_config（source-limited，预测正确）、q_stm32_low_power / q_px4_ekf / q_ros2_nav2（P2 无来源）

## 7. Golden Set

- Affected Golden：q_freertos_stack_overflow（已 RECOVERED → review_required=true，原标注保持，待人工复核）
- q_drone_power：仍为 Judge variance 案例（answer_correct=null 不变）
- Correctness：2/6（assessed 2）；Evidence Support：3/6（均未自动改动）

## 8. Gap Resolution

- **Resolved：3**（gap_freertos_config_debug P0、gap_stm32_cubemx_pwm P1、gap_wsl_ubuntu P2）
- Still Open：4（gap_git_config P1 source-limited、gap_stm32_low_power / gap_px4_ekf / gap_ros2_nav2 P2 无来源）
- 自动判定依据：gap 全部 query 在 after 中 answered（evaluation_diff 自动 resolved）

## 9. Control Center

- RAG Evaluation 视图新增「Wiki Compilation」卡：Recovered/Regressed/Resolved/Open P0-P1/Source-backed Drafts
- gaps 视图：gap_freertos_config_debug 等显示 resolved + source_status=acquired
- `/api/rag/evaluation/diff`、`/api/gaps/evaluation` 返回最新恢复/回归数据

## 10. Weekly Review（8.6 RAG Quality）

- Answer Coverage 82.1%、Knowledge Missing 17.9%、Wiki Hit 92.9%、Fallback 10.7%
- Query Recovery 4、Regression 1（JUDGE_VARIANCE）、Open Gaps 4、Resolved 3、Open P0=0 / Open P1=1
- Source-backed Wiki Drafts 4、Queries Recovered This Week 3（P0/P1 计划内；另 WSL P2 恢复 1 条，共 4）
- Golden 6/6、Judge Flip 0%、Verified Sources 0、P0/P1 Source Gaps 0

## 11. 测试

- 新增：test_wiki_compilation.py（6）、test_query_coverage_matrix.py（3）、test_wiki_benchmark_validation.py（7）= 16
- 覆盖：Gap→Wiki task、Source traceability、NEW/EXPAND 决策、draft+review_required、coverage matrix、
  likely_recoverable、before/after diff、RECOVERED/REAL_REGRESSION/JUDGE_VARIANCE、golden regression、
  reindex 元数据、CC API、Weekly metrics
- 全量回归：**321/321 通过**（305 既有 + 16 新增）

## 12. 当前主要结论

- **可靠 Source 经 gap-driven Wiki 编译 + Reindex 后，真实恢复了 4 条失败查询（Coverage 71.4%→82.1%）**，
  首次在真实开发查询上产生可测量的知识恢复，且未改任何检索参数、未放宽 Judge。
- 恢复的 Wiki 全部来自官方 Source 且带 page/section 溯源；draft + review_required 等待人工审核。
- q_git_config 未恢复符合 source-limited 预测（薄来源不硬写）；P2 四类 gap 仍缺来源。

---

## 最终数字

```
Wiki Drafts Created：4（另 1 个 Git 加覆盖边界）
Human Approved：0（全部 draft + review_required，等待人工审核）
Sources Used：3（FreeRTOS RM、ST AN4013、Microsoft Learn）+ 本地 PDF
Reindexed：YES（36 → 43 chunks）
Before Coverage：71.4%（20/28）
After Coverage：82.1%（23/28）
Coverage Improvement：+10.7pp
Recovered Queries：4
Regressed Queries：1（q_drone_power）
JUDGE_VARIANCE：1（q_drone_power）
Fallback Recovery Before：0%（0/5）
Fallback Recovery After：0%（0/3，fallback 次数 5→3）
Resolved Gaps：3（P0×1、P1×1、P2×1）
Open P0：0
Open P1：1（gap_git_config，source-limited）
Golden Set Correctness：2/6（assessed 2）
Evidence Support：3/6
Regression：321/321（305 既有 + 16 新增）

本阶段是否真正改善了知识覆盖：YES
真正恢复的 Query：q_freertos_stack_overflow、q_freertos_task_notification、q_stm32_timer_pwm、q_wsl_ubuntu
没有恢复的主要原因：q_git_config 为 source-limited（薄来源不覆盖 Obsidian 同步）；P2 四类 gap 仍无可靠来源
下一阶段第一优先级：人工审核这 4 个 Source-backed Draft Wiki → Approve → 重跑 Benchmark 固化恢复；
并为 gap_git_config 获取 Obsidian-Git 官方插件文档，为 P2 gap 继续 Source Acquisition。
```
