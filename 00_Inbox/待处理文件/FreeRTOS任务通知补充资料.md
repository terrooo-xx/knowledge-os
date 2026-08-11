# FreeRTOS 任务通知补充资料

FreeRTOS 任务通知是一种轻量级的任务间通信机制，比信号量更高效。

特点：

- 每个任务只有一个通知值，由其他任务或中断直接设置。
- 使用任务通知可以替代部分二进制信号量和计数信号量场景。
- 启用条件：需要在 CubeMX 的 FreeRTOS 配置中启用 USE_TASK_NOTIFICATIONS。