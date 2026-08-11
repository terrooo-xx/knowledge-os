---
type: wiki
domain: 03_STM32
status: stable
source:
  - 00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/时钟树.note.pdf
created: 2026-08-10
updated: 2026-08-10
---

# STM32 时钟树

## 核心概念

STM32 时钟系统通过 HSI/HSE、PLL 和分频器为 CPU 与外设提供时钟。HSI 是内部高速时钟，集成在 MCU 内，不需要外接晶振和电容，上电即可振荡；HSE 是外部晶振时钟，精度更高但需要硬件。

## 主要时钟源

- HSI：16MHz 内部时钟，可作为 PLL 主输入生成 SYSCLK，也可直接作为备用或低速时钟源。频率受温度、电压影响较大。
- HSE：4-26MHz 外部晶振，稳定性更好，搭配 PLL 后系统时钟抖动更小。
- LSE：32.768kHz，用于 RTC 精准计时，可支持 VBAT 供电长期运行。
- LSI：40kHz 低速内部时钟，用于 IWDG、RTC 备用和低功耗唤醒。

PLL 是频率倍频和分频模块，解决基础时钟频率低与 CPU/外设需要高频时钟的矛盾。

## 搭配方式

- HSI→PLL：无外部硬件、快启动、低成本，但精度低，USB 容易不稳定，适合小尺寸低成本项目。
- HSE→PLL：精度高、时钟稳定、支持 CSS，USB 通信可靠，但需要外接晶振电容，适合工业控制和有 USB/以太网的项目。

## 时钟安全与看门狗

CSS（Clock Security System）只监控 HSE，不监控 HSI、LSE 或 LSI。当 HSE 作为时钟源时，检测到时钟丢失或故障会立即触发中断或系统复位，CSS 由 LSI 单独驱动，不受主时钟故障影响。

IWDG 是硬件级独立看门狗，独立于 CPU 和主时钟。只要 CPU 没有按时喂狗，IWDG 就会强制触发系统复位。

## BYPASS Clock Source

勾选旁路时，芯片时钟引脚直接接收外部已经振荡好的时钟信号，内部振荡器电路不工作；不勾选时，引脚连接无源晶振，由内部振荡器电路驱动晶振产生时钟。

## 相关概念

[[STM32CubeMX定时器配置]]

## 资料来源

- 00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/时钟树.note.pdf