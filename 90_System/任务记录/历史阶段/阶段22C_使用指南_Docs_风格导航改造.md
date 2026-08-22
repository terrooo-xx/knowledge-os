# Phase 22-C：Docs-style 使用指南导航改造

- 日期：2026-08-18
- 类型：Control Center「使用指南」信息架构 / 导航 / 渲染改造
- 约束：不修改 RAG、Governance、Evaluation、Knowledge OS 核心逻辑

## 一、目标
把「使用指南」从「所有章节堆在一个长页面」改造成类似开发者文档站的分章节阅读界面：左侧固定目录 + 右侧只渲染当前章节。

## 二、实现
- 章节模型：GUIDE_SECTIONS 树（父级总览 + 子级页面/操作章节），每个章节有稳定 id/title/slug；guideFlatten() 有序扁平化
- 路由：#guide = 首页；#guide/<slug> = 章节；resolveGuideRoute() 解析；切换 push history
- 渲染：只渲染当前章节（不再全量插入 DOM）；首页含动态状态 7 卡 + 当前建议 + 入口卡片 + 全部章节
- Sidebar：sticky 固定 + 层级缩进 + active 高亮；移动端收缩为「📑 目录」抽屉
- 搜索：标题 + 内容全文匹配；排序 = 标题命中 > 章节开头命中 > 次数 > 子章节优先；点击结果直接进章节
- 面包屑 + 上一章/下一章（路由切换，不滚动）
- 动态状态：首页完整 7 卡 + 建议；具体章节只显示轻量一行状态
- Workflow 双图只在 #guide/workflow 独立章节
- 版本升级：Guide 1.0 → 1.1（GUIDE_META）

## 三、真实验证（live 8765）
首页/流程/页面说明/Wiki Review/Source Verification/RAG Evaluation 各章节只渲染当前内容；刷新保持；后退/前进正确；搜索 Mark Verified → 核验 Source；深链直接进入；无 JS 异常。

## 四、测试
- 更新 test_control_center_guide.py（11）+ test_control_center_rag_evaluation_view.py（1）
- 新增 test_control_center_guide_navigation.py（15）
- **401/401 通过**

## 五、学习记录
- JS `Array.prototype.sort` 的 comparator 方向容易写反（父级/子级 boost 反了导致父级总览排在子级前面）；排序判断要逐条正向验证
- 搜索排序加入「章节开头命中（headHit）」比纯次数更能体现核心主题相关性
- 深链/刷新/后退前进的关键：章节切换必须 push history（location.hash=），不能用 replaceState

## 六、最终状态
- Guide Docs-style / Section Navigation / Search / Deep Link / Browser History / Current Section Only / Page Navigation / Browser：全部 PASS
- Regression：401/401；RAG 修改：NO；Governance 修改：NO
