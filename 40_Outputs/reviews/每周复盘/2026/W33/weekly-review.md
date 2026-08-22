# Knowledge OS Weekly Review

- period：`2026-W33`
- generated_at：`2026-08-14T13:59:41`

## Weekly Status

- 🟢 Knowledge OS：运行正常（health=ok，errors=0）
- 📈 Knowledge：本周新增 20 篇（⚠ 初始化基线，暂不作为正常周增长趋势使用）　变化：—
- 🟡 Review：10 项待人工处理（AI 已验证 8 / Judge 失败 0 / 判断中 0）
- 🟠 Gaps：5 个知识缺口待处理
- 🔵 Projects：2 个项目（无人机飞控=planning；移动底盘控制器=planning）
- 🟡 Risk：1 项 stale 复查风险

| 指标 | 当前值 | 状态 |
|---|---:|---|
| Knowledge Health | 未计算 | — |
| Wiki 总量 | 20 | — |
| 本周新增 | 20 | ⚠ 初始化基线 |
| AI 已验证 | 8 | ✅ |
| 待人工审核 | 10 | ⚠ |
| Judge 失败 | 0 | ✅ |
| 知识缺口 | 5 | ⚠ |
| 活跃项目 | 2 | — |

## Health

- Health Score：74（attention）
  - Knowledge Quality：61（attention）
  - Review Health：56（warning）
  - Knowledge Gaps：47（warning）
  - Freshness：92（excellent）
  - Project Activity：100（excellent）
  - System Reliability：100（excellent）
  - 影响因素：
    - − review_pending = 10（impact=medium）
    - − gaps_pending = 5（impact=medium）
    - − stale = 1（impact=medium）
    - + judge_failed = 0（impact=medium）
    - + system_health = 0（impact=low）
    - + gaps_resolved = 1（impact=low）

## 1. 本周摘要

本周（2026-W33）知识库共有 Wiki 20 篇（draft 13 / reviewed 4 / stable 3）。
本周新增 Wiki 20 篇，更新 0 篇。
待处理知识缺口 5 条（累计 6 条）。
Review 分流：AI 已验证 8 / 待人工 10 / Judge 失败 0。
项目：无人机飞控（status=planning，phase=架构设计，progress=N/A）；移动底盘控制器（status=planning，phase=架构设计，progress=N/A）。
Stale 风险项 1 条；系统健康：ok（errors=0，warnings=0）。

## 2. Knowledge Growth

- 本周新增 Wiki：20（⚠ 初始化基线，暂不作为正常周增长趋势使用）
- 本周更新 Wiki：0
  - 新增：20_Wiki/01_计算机基础/CPU与寄存器.md；20_Wiki/02_嵌入式基础/AS5600磁编码器.md；20_Wiki/02_嵌入式基础/CLion嵌入式开发环境.md；20_Wiki/02_嵌入式基础/DC-DC与LDO选择.md；20_Wiki/02_嵌入式基础/DC电源插座引脚.md；20_Wiki/02_嵌入式基础/DRV8845电机驱动.md；20_Wiki/02_嵌入式基础/LED限流电阻选型.md；20_Wiki/02_嵌入式基础/MPU-6050惯性测量单元.md；20_Wiki/02_嵌入式基础/电容选型.md；20_Wiki/02_嵌入式基础/电机驱动选型.md；20_Wiki/02_嵌入式基础/锂电池参数计算.md；20_Wiki/02_嵌入式基础/阻抗匹配.md；20_Wiki/03_STM32/STM32 USART配置与使用.md；20_Wiki/03_STM32/STM32-DMA-配置与使用.md；20_Wiki/03_STM32/STM32CubeMX定时器配置.md；20_Wiki/03_STM32/STM32时钟树.md；20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md；20_Wiki/04_FreeRTOS/FreeRTOS任务调度与状态.md；20_Wiki/05_通信协议/PPM与S.Bus接收机信号.md；20_Wiki/05_通信协议/串口通信协议基础.md

## 3. Wiki 状态

- 总数：20（draft 13 / reviewed 4 / stable 3 / unknown 0）
- draft Wiki：13（仅 Wiki 状态，非人工审核队列；人工队列见第 6 节 Review Queue）

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
- 待人工审核：10（needs_review 10 + judge_failed 0）
- [medium] wiki_review：CLion嵌入式开发环境（警告 1 项）
- [medium] wiki_review：LED限流电阻选型（警告 1 项）
- [medium] wiki_review：锂电池参数计算（警告 1 项）
- [medium] wiki_review：STM32CubeMX定时器配置（警告 1 项）
- [medium] wiki_review：CubeMX配置FreeRTOS（部分一致；证据部分支持；缺失 11 项；来源不支持 1 项；警告 2 项）
- [medium] knowledge_gap：Obsidian 的 Git 怎么配置？（无法进行 LLM Judge（无可读取来源证据，无法进行 LLM Judge））
- [medium] knowledge_gap：PX4 无人机 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 4 项；警告 1 项）
- [medium] knowledge_gap：PX4 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 3 项；警告 2 项）
- [medium] knowledge_gap：WSL 里怎么装 Ubuntu？（证据不足；缺失 4 项；警告 1 项）
- [medium] knowledge_gap：ROS2 Nav2 代价地图怎么配置？（证据不足；缺失 1 项；警告 1 项）
- Stale 复查风险：
  - [high] STM32-DMA-配置与使用（存在复查风险）

## 7. Stale Risk

- 20_Wiki/03_STM32/STM32-DMA-配置与使用.md（status=stable，updated=2026-08-10，review_required=true，confidence=medium）：review_required

## 8. Activity

- `2026-08-14 13:31:17` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-14 13:31:15` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-14 13:01:19` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-14 13:01:16` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-14 12:39:04` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-14 12:39:02` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-14 00:01:16` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-14 00:01:14` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 23:31:16` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-13 23:31:14` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 23:01:16` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-13 23:01:14` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:31:16` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=18，failed=0）
- `2026-08-13 22:31:14` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:04:58` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=manual，judged=0，reused=18，failed=0）
- `2026-08-13 22:04:56` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=manual）
- `2026-08-13 22:03:09` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=manual，judged=0，reused=18，failed=0）
- `2026-08-13 22:03:06` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=manual）
- `2026-08-13 22:02:12` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=19，failed=0）
- `2026-08-13 22:02:10` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=1，reused=18，failed=0）
- `2026-08-13 22:02:10` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:02:09` [review_judge/control_center] 20_Wiki/04_FreeRTOS/任务通知补充_待审候选.md：Review Judge 完成（needs_review, consistency=consistent, recommendation=approve）
- `2026-08-13 22:02:05` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=0，reused=19，failed=0）
- `2026-08-13 22:02:05` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:02:03` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=1，reused=18，failed=0）
- `2026-08-13 22:02:03` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:02:01` [review_judge/control_center] 20_Wiki/04_FreeRTOS/任务通知补充_待审候选.md：Review Judge 完成（judge_passed, consistency=consistent, recommendation=approve）
- `2026-08-13 22:01:57` [review_preflight_started/control_center] ：Review Preflight 开始（trigger=scheduled）
- `2026-08-13 22:01:38` [review_preflight_finished/control_center] ：Review Preflight 完成（trigger=scheduled，judged=1，reused=18，failed=0）
- `2026-08-13 22:01:36` [review_judge/control_center] 20_Wiki/04_FreeRTOS/任务通知补充_待审候选.md：Review Judge 完成（judge_passed, consistency=consistent, recommendation=approve）

## 8.5 AI Weekly Insight

- summary：2026-W33 知识库新增 20 篇 wiki（无更新），总数为 20；审核积压 10 项、知识缺口待处理 5 项、stale 风险 1 项，健康评分 74（attention），其中 review_health 56（warning）、knowledge_gaps 47（warning）、knowledge_quality 61（attention），freshness 92、project_activity 100、system_reliability 100（均 excellent）。
- [high] 优先处理 10 项待审核内容，提升 review_health 评分。（review_health 处于 warning 状态，审核积压影响知识质量。）
- [high] 处理 5 项知识缺口，提升 knowledge_gaps 评分。（knowledge_gaps 评分最低（47），缺口待处理较多。）
- [medium] 复查 1 项 stale 内容，避免知识过期。（stale 风险存在，需及时更新。）

## 9. System Health

- 综合状态：ok（errors=0，warnings=0）
- RAG：True（ERROR=0 WARNING=0 PASS=8 INFO=1）
- Wiki：True（errors=0，warnings=0）
- Architecture：True（汇总：PASS=96  WARNING=2  ERROR=0）

## 10. 本周建议

- 🔴 STM32-DMA-配置与使用（存在复查风险，证据：review_required）
- 🟡 CLion嵌入式开发环境（警告 1 项）
- 🟡 LED限流电阻选型（警告 1 项）
- 🟡 锂电池参数计算（警告 1 项）
- 🟡 STM32CubeMX定时器配置（警告 1 项）
- 🟡 CubeMX配置FreeRTOS（部分一致；证据部分支持；缺失 11 项；来源不支持 1 项；警告 2 项）
- 🟡 Obsidian 的 Git 怎么配置？（无法进行 LLM Judge（无可读取来源证据，无法进行 LLM Judge））
- 🟡 PX4 无人机 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 4 项；警告 1 项）
- 🟡 PX4 EKF 卡尔曼滤波参数怎么调？（证据不足；缺失 3 项；警告 2 项）
- 📋 项目进度字段缺失：请在 00_项目索引.md frontmatter 补充 progress 后再展示完成率。

## 11. 待验证事项

- 无人机飞控：progress 无结构化来源（Project status source insufficient），不得猜测完成率。
- 移动底盘控制器：progress 无结构化来源（Project status source insufficient），不得猜测完成率。
