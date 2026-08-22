---
type: wiki
domain: 04_FreeRTOS
status: reviewed
source:
  - 10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf
  - 00_Inbox/待处理文件/FreeRTOS任务通知补充资料.md
created: 2026-08-15
updated: 2026-08-15
confidence: medium
review_required: true
---

# FreeRTOS 任务通知

## 概念定义

FreeRTOS 任务通知是一种轻量级的任务间通信机制，比信号量更高效。

## 启用条件

- 任务通知功能**默认启用**；可通过在 `FreeRTOSConfig.h` 中设置 `configUSE_TASK_NOTIFICATIONS` 为 0 从构建中排除（每个任务可节省 8 字节）。
- （来源：FreeRTOS Reference Manual V8.2.1，p.82/86）

## 核心特点

- 每个任务只有一个通知值，由其他任务或中断直接设置。
- 使用任务通知可以替代部分二进制信号量和计数信号量场景。

## 发送通知（xTaskNotify / xTaskNotifyAndQuery）

`xTaskNotify()` 用于直接向任务发送事件并可能解除其阻塞，同时可选地更新接收任务的通知值。
`xTaskNotifyAndQuery()` 额外用 `pulPreviousNotifyValue`（可为 NULL）输出修改前的通知值。

`eAction` 可选值（FreeRTOS Reference Manual V8.2.1，p.82/85）：

- `eSetBits`：通知值与 `ulValue` 按位或；可用作更快、更轻量的事件组替代。
- `eIncrement`：通知值加 1（不使用 `ulValue`）。
- `eSetValueWithOverwrite`：无条件把通知值设为 `ulValue`（即使任务已有挂起通知）。
- `eSetValueWithoutOverwrite`：任务已有挂起通知时不修改并返回 `pdFAIL`，否则设为 `ulValue`。
- `eNoAction`：仅通知、不改变通知值。

返回值：除 `eSetValueWithoutOverwrite` 未更新外，均返回 `pdPASS`。

## 简单场景：xTaskNotifyGive

当通知值用作二进制/计数信号量的更轻更快替代时，使用更简单的 `xTaskNotifyGive()` API，而不是 `xTaskNotify()`。

## 接收通知

接收任务通过 `xTaskNotifyWait()` 或 `ulTaskNotifyTake()` 获取通知值（FreeRTOS Reference Manual V8.2.1，p.86）。

## 调用示例

（FreeRTOS Reference Manual V8.2.1，p.86，Listing 54，节选）

```c
uint32_t ulPreviousValue;

/* 设置 xTask1Handle 通知值的 bit8，不需要旧值则传 NULL */
xTaskNotifyAndQuery( xTask1Handle, ( 1UL << 8UL ), eSetBits, NULL );

/* 通知 xTask2Handle（可能解除阻塞）但不改通知值，旧值保存到 ulPreviousValue */
xTaskNotifyAndQuery( xTask2Handle, 0, eNoAction, &ulPreviousValue );

/* 无条件把 xTask3Handle 通知值设为 0x50 */
xTaskNotifyAndQuery( xTask3Handle, 0x50, eSetValueWithOverwrite, &ulPreviousValue );

/* 只有不覆盖任务尚未读取的通知值时才设置 0xfff */
if( xTaskNotifyAndQuery( xTask4Handle, 0xfff, eSetValueWithoutOverwrite, &ulPreviousValue ) == pdPASS ) {
    /* 通知值已更新 */
} else {
    /* 通知值未更新 */
}
```

## 相关概念

[[CubeMX配置FreeRTOS]]　[[FreeRTOS任务调度与状态]]

## 资料来源

- 10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf（p.82-86，RTOS task notifications）
- 00_Inbox/待处理文件/FreeRTOS任务通知补充资料.md
