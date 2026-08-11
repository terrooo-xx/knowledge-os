# 本次PDF知识导入分析

- 日期：2026-08-10
- 范围：`个人笔记/` 下 38 个 `.note.pdf`
- 原则：第一阶段只分析，不移动、不删除、不覆盖、不重命名任何原始 PDF

## 结论摘要

- 通用工程知识（类型A）：25 篇，建议整理为 `20_Wiki` 主题笔记
- 具体项目知识（类型B）：10 篇，建议归档到 `30_Projects`
- 原始参考资料（类型C）：3 篇，建议保留 PDF 并建立来源索引
- 工具/个人配置（类型D）：2 篇，暂不转 Wiki，保留原处
- 与现有 `20_Wiki` / `30_Projects` 已建笔记无重复（当前 Wiki 目录为空，仅 `.gitkeep`）
- PDF 之间存在主题重叠：FreeRTOS CubeMX 两篇、串口两篇、STM32 综合笔记两篇、电源/电机相关多篇
- 图片型 PDF（`stm32笔记`、`STM32学习`、`进制转换`）文本几乎不可提取，不建议直接转 Markdown 或直接 RAG，需要 OCR/人工转写

## 分类表格

| 文件 | 类型 | 领域 | 建议位置 | 是否转Markdown | 是否存在重复 | 处理建议 |
|---|---|---|---|---|---|---|
| CLion开发/CLion使用指南.note.pdf | A | 嵌入式开发环境 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 提取为“CLion 嵌入式开发环境配置”主题 |
| CPU与寄存器关系解析.note.pdf | A | 计算机基础 | 20_Wiki/01_计算机基础 | 是 | 否 | 转为 CPU/寄存器 Wiki |
| FreeRTOS/CubeMX配置/CubeMX中FreeRTOS的配置项说明.note.pdf | A | FreeRTOS/CubeMX | 20_Wiki/04_FreeRTOS | 是 | 与同目录 CubeMX配置FreeRTOS 重叠 | 与下一篇合并成“CubeMX 配置 FreeRTOS” |
| FreeRTOS/CubeMX配置/CubeMX配置FreeRTOS.note.pdf | A | FreeRTOS/CubeMX | 20_Wiki/04_FreeRTOS | 是 | 与上一篇重叠 | 合并，避免两个近义 Wiki |
| FreeRTOS/FreeRTOS任务状态.note.pdf | A | FreeRTOS | 20_Wiki/04_FreeRTOS | 是 | 否 | 转为任务状态 Wiki |
| FreeRTOS/FreeRTOS优先级与抢占式调度.note.pdf | A | FreeRTOS | 20_Wiki/04_FreeRTOS | 是 | 否 | 转为调度机制 Wiki |
| FreeRTOS/FreeRTOS工作框架.note.pdf | A | FreeRTOS | 20_Wiki/04_FreeRTOS | 是 | 否 | 转为 FreeRTOS 整体框架 Wiki |
| STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf | A | STM32/CubeMX | 20_Wiki/03_STM32 | 是 | 否 | 转为定时器配置 Wiki |
| STM32/STM32cubeMx使用笔记/时钟树.note.pdf | A | STM32/时钟 | 20_Wiki/03_STM32 | 是 | 否 | 转为时钟树 Wiki |
| STM32/stm32笔记.note.pdf | C | STM32 综合 | 保留 PDF 原始资料 | 否（图片型） | 与 嵌入式课程设计/STM32学习 重叠 | 保留原文，建立来源索引；OCR 后才可 RAG |
| STM32/串口通信.note.pdf | A | STM32/USART | 20_Wiki/03_STM32 | 是 | 与 模块_芯片_硬件笔记/串口使用及分类 相关 | 转 Wiki 并与“串口使用及分类”互链 |
| 个人数据库Obsidian/Git 配置.note.pdf | D | 工具配置 | 保留原处 | 否 | 否 | 个人工具笔记，后续归入 90_System 或保留 |
| 个人数据库Obsidian/安装与配置.note.pdf | D | 工具配置 | 保留原处 | 否 | 否 | 个人工具笔记，后续归入 90_System 或保留 |
| 嵌入式课程设计/2025年11月07日.note.pdf | B | 课程设计项目 | 30_Projects/嵌入式课程设计 | 否（过程记录） | 否 | 转为项目进度记录 |
| 嵌入式课程设计/STM32学习.note.pdf | C | STM32 综合 | 保留 PDF 原始资料 | 否（图片型） | 与 STM32/stm32笔记 重叠 | 保留原文，OCR 后才可 RAG |
| 嵌入式课程设计/项目进度跟踪/11月15号——12月3号.note.pdf | B | 课程设计项目 | 30_Projects/嵌入式课程设计 | 否（过程记录） | 否 | 转为项目进度记录 |
| 嵌入式课程设计/项目进度跟踪/12月4号——12月10号.note.pdf | B | 课程设计项目 | 30_Projects/嵌入式课程设计 | 否（过程记录） | 否 | 转为项目进度记录 |
| 嵌入式课程设计/项目进度跟踪/——11月14号.note.pdf | B | 课程设计项目 | 30_Projects/嵌入式课程设计 | 否（过程记录） | 否 | 转为项目进度记录 |
| 无人机开发/硬件选型.note.pdf | B | 无人机项目 | 30_Projects/无人机飞控 | 是 | 否 | 转为无人机硬件选型记录 |
| 模块_芯片_硬件笔记/DC电源插座引脚说明.note.pdf | A | 电源/硬件 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为电源接口 Wiki |
| 模块_芯片_硬件笔记/LED限流电阻选型.note.pdf | A | 硬件 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为 LED 限流计算 Wiki |
| 模块_芯片_硬件笔记/串口使用及分类.note.pdf | A | 通信协议 | 20_Wiki/05_通信协议 | 是 | 与 STM32/串口通信 相关 | 转 Wiki 并与 STM32 串口笔记互链 |
| 模块_芯片_硬件笔记/电容.note.pdf | A | 硬件 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为电容选型 Wiki |
| 模块_芯片_硬件笔记/阻抗匹配.note.pdf | A | PCB/硬件 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为阻抗匹配 Wiki |
| 模块_芯片_硬件笔记/IMU（惯性测量单元）/MPU-6050.note.pdf | A | 传感器 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为 IMU/MPU-6050 Wiki |
| 模块_芯片_硬件笔记/接收机/信号区分（PPM、S.Bus）.note.pdf | A | 通信协议 | 20_Wiki/05_通信协议 | 是 | 否 | 转为接收机协议 Wiki |
| 模块_芯片_硬件笔记/电机驱动/DRV8845 电机驱动.note.pdf | A | 电机驱动 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为 DRV8845 Wiki |
| 模块_芯片_硬件笔记/电机驱动/电机驱动选型.note.pdf | A | 电机驱动 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为电机驱动选型 Wiki |
| 模块_芯片_硬件笔记/电源/锂电池参数计算.note.pdf | A | 电源 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为锂电池参数 Wiki |
| 模块_芯片_硬件笔记/稳压（DcDc、LDO)/DC-DC（开关电源）与 LDO（线性稳压器）的选择.note.pdf | A | 电源 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为 DC-DC/LDO 选择 Wiki |
| 模块_芯片_硬件笔记/编码器/AS5600磁编码器.note.pdf | A | 编码器 | 20_Wiki/02_嵌入式基础 | 是 | 否 | 转为 AS5600 Wiki |
| 移动底盘控制器_硬件搭建/功能简要.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目功能说明 |
| 移动底盘控制器_硬件搭建/硬件系统框架.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目架构文档 |
| 移动底盘控制器_硬件搭建/硬件选型/STM32主控选型.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目选型记录 |
| 移动底盘控制器_硬件搭建/硬件选型/工控机选型.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目选型记录 |
| 移动底盘控制器_硬件搭建/项目适配工作场景/适配电机选型.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目选型记录 |
| 移动底盘控制器_硬件搭建/项目适配工作场景/项目适配场景.note.pdf | B | 移动底盘控制器 | 30_Projects/移动底盘控制器 | 是 | 否 | 转为项目场景说明 |
| 进制转换.note.pdf | C/A | 计算机基础 | 保留 PDF，转写后入 20_Wiki/01_计算机基础 | 否（图片型） | 否 | 需转写/OCR，建立来源链接 |

## 分类说明

- 类型A（通用工程知识）：内容为 STM32、FreeRTOS、通信协议、电源、电机、传感器等可复用的原理和配置，适合先提取主题笔记再写入 `20_Wiki/<领域>/`，不按 PDF 文件名建 Wiki。
- 类型B（具体项目知识）：无人机和移动底盘控制器内容与 `30_Projects` 项目索引直接对应；嵌入式课程设计为独立课程项目，建议新建 `30_Projects/嵌入式课程设计` 后再归档。
- 类型C（原始参考资料）：三篇图片型大 PDF 无法直接文本提取，保留原文作为来源，RAG 需要先 OCR 或人工转写。
- 类型D（工具/个人配置）：Obsidian 安装与 Git 配置属于个人环境笔记，不进入工程 Wiki，建议后续单独归档。

## 去重说明

当前 `20_Wiki` 只有空领域目录，`30_Projects` 只有两个索引，因此不存在与已建笔记的重复。真正的重复风险在 PDF 之间：

- `CubeMX中FreeRTOS的配置项说明` 与 `CubeMX配置FreeRTOS` 应合并为一个 Wiki
- `STM32/stm32笔记` 与 `嵌入式课程设计/STM32学习` 主题重叠且均为图片型，统一保留为原始资料
- `STM32/串口通信` 与 `模块_芯片_硬件笔记/串口使用及分类` 应分成“STM32 USART 配置”和“串口协议基础”两个不同粒度，并互链

## 第二阶段建议（待人工确认）

1. 文本型 PDF 按上表主题提取为 `20_Wiki` / `30_Projects` Markdown，每篇保留 `source: 个人笔记/xxx.note.pdf`。
2. 图片型 PDF 不做强制转换：优先保留原文并建立“来源索引”，RAG 只索引转写后的 Wiki/文本。
3. 移动底盘控制器与无人机项目内容建议直接进入对应 `30_Projects`，不再复制到 `00_Inbox`。
4. 课程设计进度记录建议新建项目目录归档，避免散落在 `个人笔记`。
5. 第二阶段确认前，不移动、不删除、不覆盖任何 PDF。