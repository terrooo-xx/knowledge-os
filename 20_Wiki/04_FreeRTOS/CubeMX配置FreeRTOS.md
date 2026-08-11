---
type: wiki
domain: 04_FreeRTOS
status: draft
source:
  - 00_Inbox/待处理文件/个人笔记/FreeRTOS/CubeMX配置/CubeMX中FreeRTOS的配置项说明.note.pdf
  - 00_Inbox/待处理文件/个人笔记/FreeRTOS/CubeMX配置/CubeMX配置FreeRTOS.note.pdf
created: 2026-08-10
updated: 2026-08-11
---

# CubeMX 配置 FreeRTOS

## 核心概念

CubeMX 中通过图形界面配置 FreeRTOS 内核参数，生成工程后由代码管理任务、队列和内核行为。配置项决定接口标准、任务调度方式、内存分配方式和系统节拍来源。

## 关键配置

接口与内核：

- CMSIS-RTOS 接口可选择 v1 或 v2，推荐 v2，结构更规范、可移植性更好。
- FreeRTOS version 和 CMSIS-RTOS version 决定接口封装方式。
- ENABLE MPU：启用后限制任务访问的内存区域，适合需要任务隔离的安全系统。
- ENABLE FPU：任务使用浮点运算时启用，FreeRTOS 会在任务切换时保存和恢复浮点寄存器。

内核设置：

- USE_PREEMPTION：启用抢占式调度。
- CPU_CLOCK_HZ：CPU 时钟频率，CubeMX 通常强制设为 SystemCoreClock。
- TICK_RATE_HZ：系统节拍频率，常见 1000Hz，即 1ms 一个 tick。
- MAX_PRIORITIES：最大任务优先级数量。
- MINIMAL_STACK_SIZE：任务最小堆栈大小。
- MAX_TASK_NAME_LEN：任务名称最大长度。
- USE_16_BIT_TICKS：16 位节拍计数器，资源极受限时才建议启用。
- IDLE_SHOULD_YIELD：空闲任务是否让出 CPU。
- USE_MUTEXES / USE_RECURSIVE_MUTEXES：互斥锁与递归互斥锁。
- USE_COUNTING_SEMAPHORES：计数型信号量。
- QUEUE_REGISTRY_SIZE：队列注册表大小，用于调试工具查看队列。
- USE_TICKLESS_IDLE：Tickless Idle 低功耗模式。
- USE_TASK_NOTIFICATIONS：任务通知机制。
- RECORD_STACK_HIGH_ADDRESS：记录任务堆栈高地址值，用于堆栈监控。

内存管理：

- 内存分配方式可选择 Dynamic 或 Static。静态分配在编译时预分配资源，确定性和安全性更高。
- 总堆大小决定动态分配任务栈、队列等资源的总量。
- heap_4 支持合并相邻空闲块，适合频繁分配和释放的场景。

## Timebase Source 设置

FreeRTOS 本身需要一个周期性系统节拍，通常使用 SysTick；因此 CubeMX 中应将 HAL 库的 Timebase Source 设置为其他硬件定时器。SysTick 给 FreeRTOS 做系统节拍，其他 TIM 给 HAL 库做时间基准。这里配置的是 HAL 时间基准，不是 CPU 主频；主频在 Clock Configuration 页面设置。

## 任务与队列配置

在 Tasks and Queues 中编辑任务名称和入口函数。Entry Function 是任务执行的逻辑代码，这里只是起名字，实际入口函数在代码中实现。

## 相关概念

[[FreeRTOS任务调度与状态]]

## 资料来源

- 00_Inbox/待处理文件/个人笔记/FreeRTOS/CubeMX配置/CubeMX中FreeRTOS的配置项说明.note.pdf
- 00_Inbox/待处理文件/个人笔记/FreeRTOS/CubeMX配置/CubeMX配置FreeRTOS.note.pdf