---
type: wiki
domain: 04_FreeRTOS
status: draft
source:
  - 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS工作框架.note.pdf
  - 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS任务状态.note.pdf
  - 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS优先级与抢占式调度.note.pdf
created: 2026-08-10
updated: 2026-08-11
---

# FreeRTOS 任务调度与状态

## 核心概念

FreeRTOS 可以理解为一个任务调度器加任务管理、任务通信机制，让单片机同时运行多个功能。每个任务像一个独立的小程序，核心是任务调度器 Scheduler，它决定下一秒 CPU 运行哪个任务。

## 工作原理

FreeRTOS 默认采用抢占式优先级调度：高优先级任务可以打断低优先级任务。优先级数字越大，任务优先级越高；调度器总是优先运行最高优先级的就绪态任务。同优先级任务采用时间片调度，多个任务轮流执行。

启动流程为：`main()` 初始化时钟，创建任务，最后启动调度器；调度器启动后 FreeRTOS 接管 CPU。

## 关键细节

任务状态包括：

- Running：当前正在占用 CPU 执行的任务。
- Ready：任务具备运行条件但还没有获得 CPU 执行权。
- Blocked：等待时间、资源或事件，例如延时、等待信号量、等待队列。
- Suspended：被人为停止，不参与调度，不会自动恢复，必须主动恢复。
- Deleted：任务被删除，释放 TCB 和任务栈。

每创建一个任务会对应创建一个 TCB（Task Control Block），用来保存任务运行所需信息。任务栈保存任务切换时的 CPU 寄存器（PC、SP、R0-R12）、局部变量和函数调用现场，保证切换后可以恢复执行。

任务饥饿的常见原因：高优先级任务长期占用 CPU、高优先级任务没有阻塞、优先级设计不合理。除最低优先级任务外，任务应通过延时或等待数据进入阻塞态或挂起态，让底层任务有机会运行。

## 实际应用

嵌入式实时系统中按紧急程度分配优先级，例如：紧急故障保护 > 电机控制 > 通信 > 传感器采集 > LED 闪烁 > 空闲任务。高优先级任务进入就绪时立即抢占低优先级任务。

## 相关概念

[[CubeMX配置FreeRTOS]]

## 资料来源

- 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS工作框架.note.pdf
- 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS任务状态.note.pdf
- 00_Inbox/待处理文件/个人笔记/FreeRTOS/FreeRTOS优先级与抢占式调度.note.pdf