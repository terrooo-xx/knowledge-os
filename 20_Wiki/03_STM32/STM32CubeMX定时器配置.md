---
type: wiki
domain: 03_STM32
status: draft
source:
  - 00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf
created: 2026-08-10
updated: 2026-08-11
---

# STM32CubeMX 定时器配置

## 核心概念

CubeMX 定时器配置页中的 Combined Channels 将多个通道配对，实现更复杂的信号生成或测量。普通单通道 PWM 输出不需要开启，直接把对应 Channel 设为 PWM Generation，Combined Channels 保持 Disable 即可。

## 组合通道模式

- PWM 组合输出：生成带相位差、延迟的 PWM 信号，例如电机控制的多相 PWM。
- PWM Input on CH1/CH2：自动测量外部 PWM 的频率和占空比，会自动绑定 2 个通道到同一引脚。
- Encoder Mode：将 2 个通道配置为正交编码器接口，读取编码器位置或速度信号。
- XOR ON / Hall Sensor Mode：通道输出为两路信号的异或结果，或适配三相霍尔传感器输入。

## TIM1 通道模式

高级定时器 TIM1 的通道输出模式包括：

- PWM Generation No Output：只配置 PWM 模式但不输出信号。
- PWM Generation CH1：仅输出主通道 CH1 的 PWM。
- PWM Generation CH1N：仅输出互补通道 CH1N 的 PWM。
- PWM Generation CH1 CH1N：同时输出主通道和互补通道，适合电机驱动、H 桥电路。

互补通道输出与主通道反向，必须配合死区时间使用，避免上下桥臂直通。

## 相关概念

[[STM32时钟树]]

## 资料来源

- 00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf