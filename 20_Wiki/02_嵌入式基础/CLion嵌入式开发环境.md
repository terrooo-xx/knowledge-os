---
type: wiki
domain: 02_嵌入式基础
status: reviewed
source:
  - 00_Inbox/待处理文件/个人笔记/CLion开发/CLion使用指南.note.pdf
created: 2026-08-10
updated: 2026-08-14
---

# CLion 嵌入式开发环境

## 核心概念

CLion 是电脑端开发环境，STM32 运行在 ARM Cortex-M 上，两者指令集不同，因此需要 ARM 交叉编译器生成 STM32 固件。交叉编译指在电脑 A 上编译，生成给设备 B 运行的程序。

## 工具链

- ArmGCC：ARM 交叉编译器，负责代码编译。
- OpenOCD：负责电脑和 STM32 调试器之间的通信，用于烧录和调试。
- CLion 自带 CMake、GDB 等编译调试环境，但 ARM 交叉编译环境需要自行安装。

## 环境配置

1. 建立专门放置编译环境的文件夹，路径不能包含中文字符，例如 `D:\DevEnv`。
2. 解压交叉编译环境后运行 `install.bat` 自动设置环境变量，或手动把 ArmGCC 的 bin 目录加入系统 Path。
3. 使用 CubeMX 创建工程时选择 Toolchain/IDE 为 CMake，生成代码后导入 CLion。
4. 在 CLion 中配置 OpenOCD 可执行文件路径，并选择对应调试器和芯片的 OpenOCD 配置文件，例如 ST-Link + STM32F405RGT6 使用 `stm32f4_stlink.cfg`。
5. 启用 RTOS 集成（自动或 FreeRTOS），调试时可在线程和变量面板查看 FreeRTOS 对象和任务状态。

## 常见问题

处理“缺少可选定义”警告时，在 FreeRTOS Config parameters 面板中将 `RECORD_STACK_HIGH_ADDRESS` 和 `GENERATE_RUN_TIME_STATS` 改为 Enabled，重新生成代码即可。

## 资料来源

- 00_Inbox/待处理文件/个人笔记/CLion开发/CLion使用指南.note.pdf