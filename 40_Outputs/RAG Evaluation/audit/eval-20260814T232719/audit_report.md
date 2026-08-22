# Evaluation → Knowledge Gap 审计

- run_id：`eval-20260814T232719`

## 1. Top Failure Queries（8）

| Query | Final | Failure | Kind |
|---|---|---|---|
| q_freertos_stack_overflow | knowledge_missing | RAW_EVIDENCE_INSUFFICIENT | evidence_gap |
| q_freertos_task_notification | knowledge_missing | RAW_JUDGE_REJECTED | judge_gap |
| q_stm32_timer_pwm | knowledge_missing | RAW_JUDGE_REJECTED | judge_gap |
| q_stm32_low_power | knowledge_missing | RAW_JUDGE_REJECTED | judge_gap |
| q_px4_ekf | knowledge_missing | RAW_EVIDENCE_INSUFFICIENT | knowledge_gap |
| q_ros2_nav2 | knowledge_missing | RAW_EVIDENCE_INSUFFICIENT | evidence_gap |
| q_wsl_ubuntu | knowledge_missing | RAW_EVIDENCE_INSUFFICIENT | knowledge_gap |
| q_git_config | knowledge_missing | RAW_EVIDENCE_INSUFFICIENT | evidence_gap |

## 2. Failure 分类

- evidence_gap（证据不足（有候选但证据不充分））：3
- judge_gap（Judge 拒绝（有候选但 LLM Judge 判定不足））：3
- knowledge_gap（知识缺失（无可靠资料））：2

## 3-5. Gap 候选（Knowledge / Evidence / Retrieval）

- **gap_freertos_config_debug**（FreeRTOS 实战配置与调试，P0，open）
  - queries：q_freertos_stack_overflow, q_freertos_task_notification
  - failure_kinds：evidence_gap, judge_gap
  - source_available=True wiki_exists=True action=expand_wiki
  - sources：00_Inbox/待处理文件/FreeRTOS任务通知补充资料.md
  - wiki_target：{'existing': True, 'path': '20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md'}
- **gap_git_config**（Obsidian Git 配置，P1，open）
  - queries：q_git_config
  - failure_kinds：evidence_gap
  - source_available=True wiki_exists=False action=create_wiki
  - sources：00_Inbox/待处理文件/个人笔记/个人数据库Obsidian/Git 配置.note.pdf
  - wiki_target：{'existing': False}
- **gap_px4_ekf**（PX4 EKF 卡尔曼滤波调参，P2，open）
  - queries：q_px4_ekf
  - failure_kinds：knowledge_gap
  - source_available=False wiki_exists=False action=acquire_source
  - sources：（无）
  - wiki_target：{'existing': False}
- **gap_ros2_nav2**（ROS2 Nav2 代价地图配置，P2，open）
  - queries：q_ros2_nav2
  - failure_kinds：evidence_gap
  - source_available=False wiki_exists=False action=acquire_source
  - sources：（无）
  - wiki_target：{'existing': False}
- **gap_stm32_cubemx_pwm**（STM32CubeMX 定时器 PWM 输出，P1，open）
  - queries：q_stm32_timer_pwm
  - failure_kinds：judge_gap
  - source_available=True wiki_exists=True action=expand_wiki
  - sources：00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf
  - wiki_target：{'existing': True, 'path': '20_Wiki/03_STM32/STM32CubeMX定时器配置.md'}
- **gap_stm32_low_power**（STM32 低功耗模式配置，P2，open）
  - queries：q_stm32_low_power
  - failure_kinds：judge_gap
  - source_available=False wiki_exists=False action=acquire_source
  - sources：（无）
  - wiki_target：{'existing': False}
- **gap_wsl_ubuntu**（WSL 安装 Ubuntu，P2，open）
  - queries：q_wsl_ubuntu
  - failure_kinds：knowledge_gap
  - source_available=False wiki_exists=False action=acquire_source
  - sources：（无）
  - wiki_target：{'existing': False}

## 6. 已有 Wiki 但覆盖不足

- gap_freertos_config_debug：{'existing': True, 'path': '20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md'}
- gap_stm32_cubemx_pwm：{'existing': True, 'path': '20_Wiki/03_STM32/STM32CubeMX定时器配置.md'}

## 7. 已有 Source 但无 Wiki

- gap_git_config：00_Inbox/待处理文件/个人笔记/个人数据库Obsidian/Git 配置.note.pdf

## 8. 完全缺资料

- gap_px4_ekf
- gap_ros2_nav2
- gap_stm32_low_power
- gap_wsl_ubuntu

## 9. Gap 聚类

- gap_freertos_config_debug ← q_freertos_stack_overflow, q_freertos_task_notification
- gap_git_config ← q_git_config
- gap_px4_ekf ← q_px4_ekf
- gap_ros2_nav2 ← q_ros2_nav2
- gap_stm32_cubemx_pwm ← q_stm32_timer_pwm
- gap_stm32_low_power ← q_stm32_low_power
- gap_wsl_ubuntu ← q_wsl_ubuntu

## 10. P0/P1/P2 优先级

- P0：gap_freertos_config_debug
- P1：gap_git_config, gap_stm32_cubemx_pwm
- P2：gap_px4_ekf, gap_ros2_nav2, gap_stm32_low_power, gap_wsl_ubuntu

## 11. 建议 Wiki Improvement Tasks

- [P0] gap_freertos_config_debug → 扩充现有 Wiki
  - 已有 Wiki（CubeMX配置FreeRTOS）只列了 MINIMAL_STACK_SIZE / RECORD_STACK_HIGH_ADDRESS，缺少栈溢出检测与排查步骤
  - 任务通知有 Inbox Source 但未编译为 Wiki
- [P1] gap_git_config → 新建 Wiki（Draft）
  - 有 PDF Source（Git 身份配置）但未编译为 Wiki
- [P2] gap_px4_ekf → 获取可靠来源
  - 完全缺资料（已在 knowledge_gaps.yaml 记录）
- [P2] gap_ros2_nav2 → 获取可靠来源
  - 完全缺资料（已在 knowledge_gaps.yaml 记录）
- [P1] gap_stm32_cubemx_pwm → 扩充现有 Wiki
  - Wiki 有 PWM 模式选项，但缺少「输出 PWM 的完整配置步骤」（分频/ARR/占空比/引脚映射）
- [P2] gap_stm32_low_power → 获取可靠来源
  - 完全缺资料：低功耗待机模式无 Wiki 无 Source
- [P2] gap_wsl_ubuntu → 获取可靠来源
  - 完全缺资料（已在 knowledge_gaps.yaml 记录）

## 12. Golden Set 标注计划

- 优先标注：2 wiki-first + 2 fallback + 2 knowledge_missing（见 golden.yaml）

## 13. Before/After Benchmark 方案

- before：`eval-20260814T232719`
- after：补 Wiki + reindex 后重跑 evaluate_benchmark.py，用 evaluate_diff 对比

## 14. 最小修改文件

- 本阶段只新增诊断/注册表/测试；Wiki 修改以 draft 形式，遵守生命周期，不自动批准。
