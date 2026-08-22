---
type: wiki
domain: 04_FreeRTOS
status: reviewed
source:
  - 10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf
created: 2026-08-15
updated: 2026-08-15
confidence: medium
review_required: true
---

# FreeRTOS 栈溢出检查

## 概念定义

FreeRTOS 内核提供栈溢出检查：通过配置常量 `configCHECK_FOR_STACK_OVERFLOW` 选择是否启用检测（0=关闭）。

## 关键配置

- `configCHECK_FOR_STACK_OVERFLOW`：选择使用哪种检测方法（0/1/2）。
- 只要该值不为 0，应用程序必须提供栈溢出钩子（Hook）函数，内核在检测到栈溢出时调用它。

## 栈溢出钩子函数

钩子函数必须命名为 `vApplicationStackOverflowHook()`，原型如下（FreeRTOS Reference Manual V8.2.1，p.274，Listing 201）：

```c
void vApplicationStackOverflowHook( TaskHandle_t *pxTask, signed char *pcTaskName );
```

- 内核会把超出栈空间的任务的句柄与名称分别通过 `pxTask`、`pcTaskName` 传入钩子函数。
- 注意：栈溢出可能已破坏栈上的数据，钩子内应尽快处理。

## 检测方法

- **方法一**（`configCHECK_FOR_STACK_OVERFLOW = 1`）：速度快，但**不一定捕获所有**栈溢出。
- **方法二**（`configCHECK_FOR_STACK_OVERFLOW = 2`）：包含方法一的检查；此外在任务创建时把任务栈填充为已知模式，
  方法二会校验有效栈区末尾若干字节的模式是否仍未被改写，若被改写则调用钩子。效率略低于方法一，但仍很快，能捕获大多数栈溢出。

（来源：FreeRTOS Reference Manual V8.2.1，p.274-275，Stack overflow checking）

## 当前覆盖边界

- 本 Wiki 覆盖：configCHECK_FOR_STACK_OVERFLOW 常量、钩子原型、方法一/二区别。
- 不覆盖：CubeMX 图形界面中该配置项的具体位置与「如何验证」——该部分目前无本地来源支持，需人工补充 CubeMX 文档后确认。

## 相关概念

[[CubeMX配置FreeRTOS]]　[[FreeRTOS任务调度与状态]]

## 资料来源

- 10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf（p.274-275）
