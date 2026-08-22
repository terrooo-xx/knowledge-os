---
type: wiki
domain: 03_STM32
status: reviewed
source:
  - 10_Sources/STM32/STM32_CrossSeries_Timer_Overview_AN4776.pdf
created: 2026-08-15
updated: 2026-08-15
confidence: medium
review_required: true
---

# STM32 定时器 PWM 输出

## 概念定义

STM32 通用定时器可生成边沿对齐或中心对齐的 PWM 信号：周期与占空比分别由 ARR 与 CCRx 寄存器决定。

## PWM 模式配置步骤

（STM32 cross-series timer overview，AN4013 Rev 14，§2.5，p.17）

1. 配置输出引脚：
   a. 用 CCMRx 寄存器的 CCS 位选择输出模式；
   b. 用 CCER 寄存器的 CCxP 位选择极性。
2. 用 CCMRx 寄存器的 OCxM 位选择 PWM 模式（PWM1 或 PWM2）。
3. 分别在 ARR 与 CCRx 寄存器写入周期与占空比。
4. 设置 CCMRx 的预装载位（OCxPE）与 CR1 的 ARPE 位。
5. 选择计数模式：
   - PWM 边沿对齐：计数器必须配置为上计数或下计数；
   - PWM 中心对齐：计数器必须配置为中心对齐模式（CMS 位不等于 '00'）。
6. 使能捕获/比较输出（CCxE）。
7. 使能计数器（CEN）。

## 频率 / 占空比关系

（AN4013，§2.4 output compare timing，p.16）

- 计数时钟：`CK_CNT = CK_PSC / (PSC + 1)`（内部时钟下）。
- 比较更新率：`CCx update rate = CK_CNT / TIMx_ARRx`。
- 比较延迟：`CCx delay = CCRx / CK_CNT`。

即：定时器时钟经预分频 `PSC+1` 分频后，周期由 ARR 决定，脉冲宽度（占空比）由 CCRx 决定。

## 当前覆盖边界

- 本 Wiki 覆盖：寄存器级 PWM 输出配置步骤与频率/占空比公式（来自 ST 官方 AN4013）。
- CubeMX 图形界面配置项（如 Channel 设为 PWM Generation）见 [[STM32CubeMX定时器配置]]（该 Wiki 为 reviewed，本页不重复展开）；
  两者的人工合并与验证待审核。

## 相关概念

[[STM32CubeMX定时器配置]]　[[STM32时钟树]]

## 资料来源

- 10_Sources/STM32/STM32_CrossSeries_Timer_Overview_AN4776.pdf（AN4013 Rev 14，p.16-17）
