# Phase 17 Audit：Source → Wiki Compilation

- generated_at：`2026-08-16T13:38:15`

## 1. P0/P1 Gap 清单

- gap_freertos_config_debug（P0）FreeRTOS 实战配置与调试
- gap_git_config（P1）Obsidian Git 配置
- gap_stm32_cubemx_pwm（P1）STM32CubeMX 定时器 PWM 输出

## 2-5. Gap 详情 / 失败 Query / Knowledge Requirements / Source 覆盖 / Wiki 覆盖

### gap_freertos_config_debug（P0）FreeRTOS 实战配置与调试
#### wt_freertos_stack_overflow：FreeRTOS 栈溢出检查
- 决策：NEW_WIKI → 20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md
- Source：FreeRTOS Reference Manual V8.2.1（local=10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf, p.274-275, Stack overflow checking）
- 覆盖 Query：q_freertos_stack_overflow
  Knowledge Requirements：
  - [so_req_1] configCHECK_FOR_STACK_OVERFLOW 配置常量选择是否启用检测 (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.274)
  - [so_req_2] 启用时必须提供栈溢出钩子 vApplicationStackOverflowHook(TaskHandle_t*, signed char*) (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.274)
  - [so_req_3] 方法1（=1）快但可能漏检；方法2（=2）额外校验栈尾 n 字节模式 (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.275)
  - [so_req_4] 检测到溢出时内核调用 hook，传入任务句柄与任务名 (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.274)
  - [so_req_5] CubeMX 中该配置项的具体位置/验证方法 (covered=NO, source=?)
  Query Coverage Matrix：
  - q_freertos_stack_overflow: before=answered covered= likely_recoverable=unknown
  缺失知识点：CubeMX 中该配置项的具体位置/验证方法

#### wt_freertos_task_notification：FreeRTOS 任务通知
- 决策：EXPAND_EXISTING_WIKI → 20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md
- Source：FreeRTOS Reference Manual V8.2.1（local=10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf, p.82-86, RTOS task notifications）
- 覆盖 Query：q_freertos_task_notification
  Knowledge Requirements：
  - [tn_req_1] 任务通知是轻量级任务间通信，比信号量高效；可替代部分信号量/事件组 (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.82)
  - [tn_req_2] 启用条件 configUSE_TASK_NOTIFICATIONS（默认启用，设 0 每任务省 8B） (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.82)
  - [tn_req_3] 发送 API xTaskNotify/xTaskNotifyAndQuery + eAction 五种动作 + 返回值 pdPASS/pdFAIL (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.82,85)
  - [tn_req_4] 简单场景用 xTaskNotifyGive 替代二进制/计数信号量 (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.82)
  - [tn_req_5] 接收 API xTaskNotifyWait / ulTaskNotifyTake (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.86)
  - [tn_req_6] 典型调用示例（Listing 54：eSetBits/eNoAction/eSetValueWithOverwrite/WithoutOverwrite） (covered=YES, source=FreeRTOS Reference Manual V8.2.1, p.86)
  Query Coverage Matrix：
  - q_freertos_task_notification: before=answered covered= likely_recoverable=true

### gap_git_config（P1）Obsidian Git 配置
#### wt_git_config：Obsidian Git 配置
- 决策：EXPAND_EXISTING_WIKI → 20_Wiki/01_计算机基础/Git基础配置.md
- Source：Obsidian-Git Getting Started（官方插件文档）（local=10_Sources/工具链/Obsidian-Git_GettingStarted.md, Create new local repository / For existing remote repository）
- 覆盖 Query：q_git_config
  Knowledge Requirements：
  - [git_req_1] git user.name / user.email 身份配置 (covered=YES, source=Git 配置.note.pdf)
  - [git_req_2] 识别仓库（.git 文件夹、显示隐藏文件） (covered=YES, source=Git 配置.note.pdf)
  - [git_req_3] Obsidian-Git 插件安装与启用（社区插件 → Browse → Git → Enable） (covered=YES, source=Obsidian-Git Getting Started（官方插件文档）)
  - [git_req_4] 仓库初始化与远程配置：Initialize a new repo → Push 添加 origin；或 Clone existing remote repo（https/ssh URL 带 .git 后缀）；Edit remotes (covered=YES, source=Obsidian-Git Getting Started（官方插件文档）)
  - [git_req_5] 自动同步：Commit-and-sync（commit all + pull + push）；自动定时同步与启动自动 pull；常用命令 (covered=YES, source=Obsidian-Git plugin README（官方仓库）)
  - [git_req_6] 认证：桌面 HTTPS/SSH（指向 Authentication Guide）；GitHub 个人访问令牌最小权限（metadata 读 + contents/commit status 读写） (covered=YES, source=Obsidian-Git Getting Started（官方插件文档）)
  Query Coverage Matrix：
  - q_git_config: before=knowledge_missing covered= likely_recoverable=true
  说明：Source 已补齐（官方 Getting Started + README），覆盖插件安装/仓库初始化/远程/认证/自动同步；Wiki 保持 draft + review_required，不自动 approve

### gap_stm32_cubemx_pwm（P1）STM32CubeMX 定时器 PWM 输出
#### wt_stm32_pwm：STM32 定时器 PWM 输出
- 决策：NEW_WIKI → 20_Wiki/03_STM32/STM32定时器PWM输出.md
- Source：STM32 cross-series timer overview (AN4013 Rev 14)（local=10_Sources/STM32/STM32_CrossSeries_Timer_Overview_AN4776.pdf, p.16-17, 2.5 Timer in PWM mode）
- 覆盖 Query：q_stm32_timer_pwm
  Knowledge Requirements：
  - [pwm_req_1] PWM 输出配置步骤（引脚 CCS/CCxP → OCxM 选 PWM1/2 → ARR/CCRx → 预装载 → 计数模式 → CCxE → CEN） (covered=YES, source=STM32 cross-series timer overview, p.17)
  - [pwm_req_2] 频率/占空比关系：CK_CNT=CK_PSC/(PSC+1)；CCx update rate=CK_CNT/ARR；CCRx 决定脉冲宽度 (covered=YES, source=STM32 cross-series timer overview, p.16)
  - [pwm_req_3] 边沿对齐（up/down）与中心对齐（CMS!=00）计数模式 (covered=YES, source=STM32 cross-series timer overview, p.17)
  - [pwm_req_4] CubeMX 界面配置项（Channel=PWM Generation 等） (covered=NO, source=?)
  Query Coverage Matrix：
  - q_stm32_timer_pwm: before=answered covered= likely_recoverable=unknown
  缺失知识点：CubeMX 界面配置项（Channel=PWM Generation 等）

## 6-7. Wiki 缺失知识点 / NEW vs EXPAND 决策

- gap_freertos_config_debug/wt_freertos_stack_overflow：NEW_WIKI　缺失：CubeMX 中该配置项的具体位置/验证方法
- gap_freertos_config_debug/wt_freertos_task_notification：EXPAND_EXISTING_WIKI　缺失：（无）
- gap_git_config/wt_git_config：EXPAND_EXISTING_WIKI　缺失：（无）
- gap_stm32_cubemx_pwm/wt_stm32_pwm：NEW_WIKI　缺失：CubeMX 界面配置项（Channel=PWM Generation 等）

## 8. Source Traceability 方案

- PDF：source{title, local_path, page, section, url}；HTML：source{title, url, section/heading}。
- 编译后的 Wiki 正文引用 source 时附 page/section，保证人工审核可回到原文。

## 9. likely_recoverable 判断

- wt_freertos_stack_overflow：unknown
- wt_freertos_task_notification：true
- wt_git_config：true
- wt_stm32_pwm：unknown

## 10. 第一批 Wiki Improvement Tasks

- [P0] wt_freertos_stack_overflow → NEW_WIKI（20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md）
- [P0] wt_freertos_task_notification → EXPAND_EXISTING_WIKI（20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md）
- [P1] wt_git_config → EXPAND_EXISTING_WIKI（20_Wiki/01_计算机基础/Git基础配置.md）
- [P1] wt_stm32_pwm → NEW_WIKI（20_Wiki/03_STM32/STM32定时器PWM输出.md）
