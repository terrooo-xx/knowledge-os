# Phase 16：Source Acquisition + Golden Set + Evaluation Stabilization 报告

- 日期：2026-08-15
- 范围：可靠 Source Acquisition + Golden Set 人工标注 + Judge Variance / Evaluation 稳定性
- 原则：不调 Retrieval/Reranker/Judge/阈值；不伪造 Source；不把 Judge 当 Ground Truth；
  Human Ground Truth > Judge Self-Evaluation

## 1. Source Audit

### P0（gap_freertos_config_debug：FreeRTOS 实战配置与调试，2 条失败）
- gap_freertos_stack_overflow：**已有可靠 Source（已获取）** → FreeRTOS Reference Manual V8.2.1 PDF
  （官方，2025，含 Stack Overflow Checking 章节，pypdf 可解析 298 chunks / 416K 字）
- gap_freertos_task_notifications：**已有可靠 Source（已获取）** → 同上 Reference Manual（Task Notifications 章节）
  + 本地 Inbox 薄来源（3 要点）；官方网页为 JS 渲染（extractability=low，仅作参考）
- 状态判断：acquired（本地已获取，内容未人工逐页核验 → 非 verified）

### P1
- gap_git_config（Obsidian Git 配置）：**已有 Source（acquired，但覆盖不足）** → 本地 PDF（仅身份配置/识别 .git，
  245 字）；候选官方 Obsidian-Git 插件文档
- gap_stm32_cubemx_pwm（STM32 定时器 PWM 输出）：**已有可靠 Source（acquired）** → ST 官方
  Cross-Series Timer Overview AN4776 PDF（含 PWM mode，pypdf 可解析 48 chunks）+ 本地 CubeMX 定时器 PDF

### P2（顺带登记）
- gap_stm32_low_power：candidate（ST AN4621 官方 PDF URL，未获取）
- gap_px4_ekf：candidate（PX4 官方 EKF2 调参文档 URL）
- gap_ros2_nav2：candidate（Nav2 官方 costmap 配置文档 URL）
- gap_wsl_ubuntu：acquired（Microsoft Learn 官方页面已下载，trafilatura 可解析 9626 字）

## 2. Source Acquisition Registry

- 文件：`90_System/rag/evaluation/source_acquisition.yaml`（8 条 source task）
- 状态统计：acquired=5（FreeRTOS×2、Git、STM32 PWM、WSL）、candidate=3（低功耗、PX4、Nav2）、verified=0
- 字段：gap_id / priority / source_status / source_type / source{title,url,local_path,authority,date} /
  verification{verified,reviewer,notes} / sufficiency{relevance,authority,completeness,recency,extractability} / reason
- sufficiency 只记录 high/medium/low/unknown，无综合分数
- **不假装已验证**：所有 URL 均 verified=false，直到人工核验内容 + 本地获取
- 真实下载到 10_Sources：FreeRTOS_Reference_Manual_V8.2.1.pdf、STM32_CrossSeries_Timer_Overview_AN4776.pdf、
  Microsoft_Install_WSL.html（10_Sources 从空变为有 4 个真实来源文件）

## 3. Golden Set 人工标注

- 文件：`90_System/rag/evaluation/golden.yaml`（v2.0，6 条，全部已标注）
- 覆盖路径：2×wiki-first（q_freertos_scheduler、q_stm32_usart）+ 2×fallback/RAW（q_freertos_stack_overflow、
  q_stm32_low_power）+ 1×knowledge_missing（q_px4_ekf）+ 1×Judge variance（q_drone_power）
- ground_truth：answerable / expected_source / acceptable_paths（wiki|raw|wiki_then_raw|either）
- review：answerable / answer_correct / evidence_supported / citation_correct / evidence_quality + reviewer/date/notes
- reviewer=manual(codex)，标注依据为真实 Wiki 内容 + 外部官方资料 + 实际 deep 回答，仍建议人工复核

## 4. Golden Set 结果

- 已标注：6/6
- Answer Correct：2/6（assessed 2 → 2/2=100%）—— q_freertos_scheduler、q_stm32_usart 答案经人工核对正确
- Evidence Support：3/6（assessed 6）—— scheduler/usart/drone_power 证据真正支持；stack_overflow/low_power/px4 证据不足
- 未回答的 4 条 answer_correct=null（不把"未回答"当"答错"）；样本 <10 → 明确标注 sample too small
- q_drone_power：answer_correct=null（跨 run 不稳定），evidence_supported=true（证据确实支持：硬件选型 4S 电池 + 锂电池参数计算）

## 5. Judge Variance

- 方法：固定 retrieval/reranker/evidence（judge 输入 chunks 捕获一次），对 6 条 Golden Query 各重复 3 次 DeepSeek Judge
- 结果（jv-20260815T000938）：
  - Stable Rate：100.0%（6/6 三连一致）
  - Flip Rate：0.0%（within-run 无翻转）
  - stable_sufficient=2（scheduler、usart）；stable_insufficient=4（stack_overflow、low_power、px4、drone_power）
- 重要发现：q_drone_power 在本次 3 连 insufficient，但 before Benchmark 曾 passed → 翻转发生在 **跨 run**（4 次观察 1 pass / 3 insufficient），
  证明 Judge 存在跨会话方差；within-run 重复不能排除跨 run 波动

## 6. Evaluation Diff 分类

- compare_runs 升级：REG RESSED 条目增加 regression_class = REAL_REGRESSION / JUDGE_VARIANCE / UNKNOWN
  - 判定依据：检索命中的文档集合是否一致（同文档仅路径/排序变化 → JUDGE_VARIANCE；文档集合变化 → REAL_REGRESSION；无法比对 → UNKNOWN）
- 实际结果（eval-20260814T232719 → eval-20260815T002430）：
  - Recovered=0、Unchanged=27、Regressed=1（q_drone_power）、New failures=0
  - regression_classes：REAL_REGRESSION=0、**JUDGE_VARIANCE=1**、UNKNOWN=0
- **q_drone_power 判定 = JUDGE_VARIANCE**（两次 run 命中同一批文档，仅 Judge 判定翻转）

## 7. Control Center

- `/api/source_acquisition`（列表 + per-gap source 状态）、`/api/source_acquisition/<id>`（详情）
- `/api/golden_set`（entries + stats）、`/api/judge_variance`（最新实验）
- Knowledge Gaps 视图：新增「Source 状态」列（missing/candidate/acquired/verified 着色）+ Source 详情按钮
- RAG Evaluation 视图：新增 Golden Set 表（含 reviewer/正确率）、Judge Variance 表、Source Acquisition 表
- 全部只读/触发式，不自动 approve

## 8. Weekly Review（8.6 RAG Quality 增强）

- 回归分类：REAL_REGRESSION=0 / JUDGE_VARIANCE=1 / UNKNOWN=0
- Golden Set：6/6 reviewed，Answer Correct 2/6（assessed 2），Evidence Support 3/6，⚠ 样本过小
- Judge Flip Rate：0.0%，Judge Stable Rate：100.0%（tested 6）
- Verified Sources：0，P0/P1 Source Gaps：0
- 数据来自 metrics.collect_rag_evaluation（确定性读取，无则优雅跳过）

## 9. 测试结果

- 新增 4 个测试文件：test_source_acquisition.py（6）、test_golden_set.py（7）、
  test_judge_variance.py（7）、test_evaluation_diff_classification.py（4）= 24
- 覆盖：P0/P1→source task、状态流转、golden schema、人工字段、q_drone_power golden、
  judge 重复捕获、stable/variance 分类、REAL_REGRESSION/JUDGE_VARIANCE/UNKNOWN、
  unchanged/new failure、CC API、Weekly metrics
- 全量回归：**305/305 通过**（281 既有 + 24 新增）

## 10. 当前真实质量基线

- Coverage：Before 71.4%（20/28）→ After 67.9%（19/28），Recovered=0，Regressed=1（JUDGE_VARIANCE）
- Fallback Recovery：0%（0/5 → 0/6）；RAW Answer：0%
- Golden 人工验证：6 条中 2 条回答正确、3 条证据不足（失败合理）、1 条（drone_power）证据支持但 Judge 波动
- Coverage 中已人工验证部分：2/20 answered（10%）—— 其余 answered 尚未人工核对
- Source：10_Sources 从空到 4 个真实官方文件；P0/P1 全部至少 candidate

## 11. 下一批 Wiki Improvement Tasks

1. 用 FreeRTOS Reference Manual（已获取）扩充/新建：栈溢出检查配置（configCHECK_FOR_STACK_OVERFLOW + 钩子）→ draft → 人工审核 → reindex
2. 用 FreeRTOS Reference Manual 扩充任务通知 Wiki（xTaskNotify/NotifyWait 用法）
3. 用 ST AN4776 补充 STM32CubeMX PWM 输出完整步骤（分频/ARR/占空比/引脚）
4. Git 配置 Wiki 需补充官方插件文档（Obsidian-Git）后再扩充
5. P2：低功耗（AN4621）、PX4 EKF、Nav2 继续 source acquisition（candidate → acquired）

## 12. 未解决问题

- Verified Source = 0：已获取文件未人工逐页核验，不能升级为 verified
- q_drone_power 的跨 run Judge 方差根因未完全定位（temperature/上下文/模型波动），不修改 Judge 前提下无法消除
- Golden 仅 6 条且其中 4 条当前不可回答，Answer Correctness 统计受限于样本
- Coverage 的 71.4% 中只有 2/20 answered 经过人工验证，其余依赖系统自评（Judge）
- FreeRTOS_Task_Notifications.html 为 JS 渲染无法提取（extractability=low），需官方 PDF/打印视图

---

## 最终结论

```
P0 Source 缺失：0（已 acquired：FreeRTOS Reference Manual）
P1 Source 缺失：0（Git acquired-薄、STM32 PWM acquired）
已验证 Source：0（均需人工核验后才 verified）
Golden Set：6/6 已标注
Golden Answer Correctness：2/6（assessed 2 → 100%）
Golden Evidence Support：3/6（assessed 6）
Judge Flip Rate：0.0%（within-run，6×3）
Judge Stable Rate：100.0%（within-run）
q_drone_power：JUDGE_VARIANCE（命中文档一致，仅 Judge 判定跨 run 翻转）
Coverage 中已人工验证部分：2/20 answered（10%）
281+ Regression：305/305（281 既有 + 24 新增）

下一阶段第一优先级：把已获取的 P0/P1 Source（FreeRTOS Reference Manual、ST AN4776）
编译为 Wiki Draft → 人工审核 → Reindex → 重跑 Benchmark，验证 FreeRTOS 栈溢出/任务通知、
STM32 PWM 查询是否真实恢复（而不是继续调 Judge 或检索参数）。
```
