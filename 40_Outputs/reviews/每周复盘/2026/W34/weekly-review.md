# Knowledge OS Weekly Review

- period：`2026-W34`
- generated_at：`2026-08-22T22:49:38`

## Weekly Status

- 🟢 Knowledge OS：运行正常（health=ok，errors=0）
- 📈 Knowledge：本周新增 0 篇　变化：—
- 🟡 Review：6 项待人工处理（AI 已验证 8 / Judge 失败 0 / 判断中 0）
- 🟠 Gaps：5 个知识缺口待处理
- 🔵 Projects：2 个项目（无人机飞控=planning；移动底盘控制器=planning）
- 🟡 Risk：6 项 stale 复查风险

| 指标 | 当前值 | 状态 |
|---|---:|---|
| Knowledge Health | 未计算 | — |
| Wiki 总量 | 25 | — |
| 本周新增 | 0 | — |
| AI 已验证 | 8 | ✅ |
| 待人工审核 | 6 | ⚠ |
| Judge 失败 | 0 | ✅ |
| 知识缺口 | 5 | ⚠ |
| 活跃项目 | 2 | — |

## Health

- Health Score：75（good）
  - Knowledge Quality：78（good）
  - Review Health：66（attention）
  - Knowledge Gaps：47（warning）
  - Freshness：64（attention）
  - Project Activity：100（excellent）
  - System Reliability：100（excellent）
  - 影响因素：
    - − review_pending = 6（impact=medium）
    - − gaps_pending = 5（impact=medium）
    - − stale = 6（impact=medium）
    - + judge_failed = 0（impact=medium）
    - + system_health = 0（impact=low）
    - + gaps_resolved = 1（impact=low）

## 1. 本周摘要

根据知识库数据，本周共25篇Wiki文档，其中草稿9篇、已审阅13篇、稳定3篇。本周新增文档0篇，更新1篇（Git基础配置）。知识缺口共6项，其中5项待解决、1项已解决。待解决缺口涉及Obsidian Git配置、PX4 EKF卡尔曼滤波参数调整、WSL安装Ubuntu及ROS2 Nav2代价地图配置等主题。系统健康检查显示RAG、Wiki及架构均正常，无错误或警告。当前有2个项目处于规划阶段，均为架构设计阶段。另有6篇文档因需复审被标记为潜在风险。

## 2. Knowledge Growth

- 本周新增 Wiki：0
- 本周更新 Wiki：1
  - 更新：20_Wiki/01_计算机基础/Git基础配置.md

## 3. Wiki 状态

- 总数：25（draft 9 / reviewed 13 / stable 3 / unknown 0）
- draft Wiki：9（仅 Wiki 状态，非人工审核队列；人工队列见第 6 节 Review Queue）

## 4. Knowledge Gaps

- 待处理：5 / 累计：6
- [medium] Obsidian 的 Git 怎么配置？（suggested: create_wiki）
- [medium] PX4 无人机 EKF 卡尔曼滤波参数怎么调？（suggested: create_wiki）
- [medium] PX4 EKF 卡尔曼滤波参数怎么调？（suggested: create_wiki）
- [medium] WSL 里怎么装 Ubuntu？（suggested: create_wiki）
- [medium] ROS2 Nav2 代价地图怎么配置？（suggested: create_wiki）

## 5. Project Status

- 无人机飞控
  - status：planning | phase：架构设计 | updated：2026-08-12
  - progress：N/A（未提供结构化数据，禁止猜测）
  - next_step：N/A
  - blockers：无
- 移动底盘控制器
  - status：planning | phase：架构设计 | updated：2026-08-12
  - progress：N/A（未提供结构化数据，禁止猜测）
  - next_step：N/A
  - blockers：无

## 6. Review Queue

- AI 已验证：8
- 待人工审核：6（needs_review 6 + judge_failed 0）
- [medium] wiki_review：CubeMX配置FreeRTOS（部分一致；证据部分支持；缺失 11 项；来源不支持 1 项；警告 2 项）
- [medium] knowledge_gap：Obsidian 的 Git 怎么配置？（无法进行 LLM Judge（无可读取来源证据，无法进行 LLM Judge））
- [medium] knowledge_gap：PX4 无人机 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 4 项；警告 1 项）
- [medium] knowledge_gap：PX4 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 3 项；警告 2 项）
- [medium] knowledge_gap：WSL 里怎么装 Ubuntu？（证据不足；缺失 4 项；警告 1 项）
- [medium] knowledge_gap：ROS2 Nav2 代价地图怎么配置？（证据不足；缺失 1 项；警告 1 项）
- Stale 复查风险：
  - [high] Git基础配置（存在复查风险）
  - [high] WSL安装Ubuntu（存在复查风险）
  - [high] STM32-DMA-配置与使用（存在复查风险）
  - [high] STM32定时器PWM输出（存在复查风险）
  - [high] FreeRTOS任务通知（存在复查风险）
  - [high] FreeRTOS栈溢出检查（存在复查风险）

## 7. Stale Risk

- 20_Wiki/01_计算机基础/Git基础配置.md（status=reviewed，updated=2026-08-17，review_required=true，confidence=medium）：review_required
- 20_Wiki/01_计算机基础/WSL安装Ubuntu.md（status=reviewed，updated=2026-08-15，review_required=true，confidence=medium）：review_required
- 20_Wiki/03_STM32/STM32-DMA-配置与使用.md（status=stable，updated=2026-08-10，review_required=true，confidence=medium）：review_required
- 20_Wiki/03_STM32/STM32定时器PWM输出.md（status=reviewed，updated=2026-08-15，review_required=true，confidence=medium）：review_required
- 20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md（status=reviewed，updated=2026-08-15，review_required=true，confidence=medium）：review_required
- 20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md（status=reviewed，updated=2026-08-15，review_required=true，confidence=medium）：review_required

## 8. Activity

- `2026-08-22 22:47:44` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 22:29:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 22:29:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 22:29:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 21:59:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 21:59:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 21:59:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 21:29:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 21:29:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 21:29:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 20:59:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 20:59:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 20:59:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 20:29:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 20:29:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 20:29:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 19:59:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 19:59:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 19:59:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 19:29:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 19:29:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 19:29:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 18:59:55` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 18:59:55` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 18:59:53` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 18:30:00` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 18:30:00` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）
- `2026-08-22 18:29:54` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-22 18:00:00` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=14，failed=0）
- `2026-08-22 18:00:00` [governance/control_center] evaluation：无待验证知识变化，跳过 Benchmark（index_change=false）

## 8.5 AI Weekly Insight

- summary：2026-W34 知识库总条目 25 篇，新增 0 篇，更新 1 篇；待审核 6 项，知识缺口 5 个，stale 6 项。健康评分 67（attention），其中知识质量 78（good）、知识缺口 47（warning）、新鲜度 64、系统可靠性 60。
- [high] 优先处理 5 个知识缺口，提升知识缺口维度评分。（知识缺口维度评分最低（47），且 gaps_pending 为 5。）
- [high] 安排 stale 条目的复查与更新，降低 stale 数量。（stale 数量从 1 增至 6，新鲜度评分 64（attention）。）
- [medium] 推进 6 项待审核条目的审核流程。（review_pending 为 6，审核健康评分 66（attention）。）

## 8.6 RAG Quality

- Answer Coverage：89.3%（run_id=`eval-20260822T180123`，28 条，mode=fast）
- Knowledge Missing：10.7%（system_error=0）
- Wiki Hit Rate：92.9%　Wiki Fallback Rate：3.6%　Fallback Recovery：0.0%
- RAW Answer Rate：0.0%　RAW Evidence Sufficient：0.0%
- Evidence Avg Window：4.4　P50 Latency：1992.6ms　P95 Latency：3495.0ms
### Main Failure Reasons
- RAW_EVIDENCE_INSUFFICIENT：2（7.1%）
- RAW_JUDGE_REJECTED：1（3.6%）
### Knowledge Gap Signals
- Likely Knowledge Gap：1　Evidence Gap：2　Retrieval Gap：0（Retrieval Gap 需人工确认）
- Open Knowledge Gaps：3　Resolved Gaps：4
- Query Recovery：2　Regression：0（eval-20260816T000233 → eval-20260816T135103）
- 回归分类：REAL_REGRESSION=0　JUDGE_VARIANCE=0　UNKNOWN=0
- Golden Set：6/6 reviewed　Answer Correct：2/6（assessed 2）　Evidence Support：3/6
- ⚠ Golden 样本过小（6 < 10），正确率仅作参考
- Judge Flip Rate：0.0%　Judge Stable Rate：100.0%（tested 6）
- Verified Sources：1　P0/P1 Source Gaps：0
- Source-backed Wiki Drafts：4　Queries Recovered This Week：1　Still Failed：0
- Open P0 Gaps：0　Open P1 Gaps：0
- Baseline：89.3%（bl-eval-20260817T162956，STABLE）　Current Verification：89.3%　Delta：0.0pp　Status：STABLE
- Governance：passed　Auto Verify：ON　Evaluation Required：NO（无）　Last Check：STABLE

## 9. System Health

- 综合状态：ok（errors=0，warnings=0）
- RAG：True（ERROR=0 WARNING=0 PASS=8 INFO=1）
- Wiki：True（errors=0，warnings=0）
- Architecture：True（汇总：PASS=96  WARNING=3  ERROR=0）

## 10. 本周建议

- 🔴 Git基础配置（存在复查风险，证据：review_required）
- 🔴 WSL安装Ubuntu（存在复查风险，证据：review_required）
- 🔴 STM32-DMA-配置与使用（存在复查风险，证据：review_required）
- 🔴 STM32定时器PWM输出（存在复查风险，证据：review_required）
- 🔴 FreeRTOS任务通知（存在复查风险，证据：review_required）
- 🟡 CubeMX配置FreeRTOS（部分一致；证据部分支持；缺失 11 项；来源不支持 1 项；警告 2 项）
- 🟡 Obsidian 的 Git 怎么配置？（无法进行 LLM Judge（无可读取来源证据，无法进行 LLM Judge））
- 🟡 PX4 无人机 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 4 项；警告 1 项）
- 🟡 PX4 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 3 项；警告 2 项）
- 🟡 WSL 里怎么装 Ubuntu？（证据不足；缺失 4 项；警告 1 项）
- 🟡 ROS2 Nav2 代价地图怎么配置？（证据不足；缺失 1 项；警告 1 项）
- 📋 项目进度字段缺失：请在 00_项目索引.md frontmatter 补充 progress 后再展示完成率。

## 11. 待验证事项

- 无人机飞控：progress 无结构化来源（Project status source insufficient），不得猜测完成率。
- 移动底盘控制器：progress 无结构化来源（Project status source insufficient），不得猜测完成率。
