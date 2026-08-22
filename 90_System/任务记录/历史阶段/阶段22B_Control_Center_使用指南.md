# Phase 22-B：Control Center 使用指南（操作手册 + 流程导航 + 状态引导）

- 日期：2026-08-17
- 类型：Control Center 新增「使用指南」只读页面
- 约束：不修改 RAG 算法、不改变治理逻辑

## 一、目标

让第一次使用 Control Center 的操作者仅通过「使用指南」页面完成：导入资料 → AI 待办 → 审核 Wiki → 核验 Source → 处理 Gap → 查看 RAG Evaluation → 理解 Governance/Baseline → 判断是否需要人工介入 → 理解 Weekly Review。

## 二、实现

- 主导航新增 `📖 使用指南`（仪表盘之后）
- GUIDE 内容结构（version 1.0 / updated 2026-08-17）：新手入口卡片 ×9、整体流程（Knowledge OS + RAG Query 双图，HTML/CSS）、页面职责表、常用操作（导入/审核批准 Wiki/核验 Source/处理 Gap/运行 Evaluation）、Governance、Baseline、FAQ、故障排查
- 布局：顶部搜索 / 左侧目录 / 右侧正文 / 底部上一节下一节
- 动态状态：Baseline / Baseline Status / Governance / Evaluation Required / 待审核 Wiki / 待核验 Source / Open P0/P1（全部 API 动态，不写死）+ 确定性「当前建议」
- graceful fallback：safeApi 捕获 API 失败，指南仍可读
- 只读：无 POST 写操作，仅渲染 + gotoView 跳转真实页面

## 三、真实浏览器验证（live 8765）

- 点击「使用指南」打开 PASS；TOC/搜索 PASS；Wiki Review / Source Verified（Mark Verified + src_git_config）/ RAG Evaluation / Governance 各节步骤 PASS；双流程图 PASS；动态状态（7 卡 + 当前建议）PASS；刷新 #guide 保持 PASS；无 JS 异常

## 四、测试

- 新增 test_control_center_guide.py（11 条）
- **386/386 通过**

## 五、学习记录

- JS 对象字面量内部引用自身（`${GUIDE.version}` 在 const GUIDE 初始化中）会触发 TDZ ReferenceError；自引用版本信息应拆成独立常量（GUIDE_META）后再引用
- 浏览器 DOM 验证时元素 id 要区分「顶层 section（gsec-*）」与「节内子标题（ops-*）」，否则验证查询取错元素误报
- 真实状态测试（wiki 数量等）会随系统变化，指南断言避免依赖具体数字（只断言结构/关键词）

## 六、最终状态

- Guide 页面 / Workflow Diagram / Dynamic Status / Git Source Verified 指引 / RAG Evaluation 指引 / Browser：全部 PASS
- Regression：386/386；RAG 算法修改：NO；Governance 逻辑修改：NO
