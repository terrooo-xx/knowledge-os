# Phase 22-C：Docs-style 使用指南导航改造报告

- 日期：2026-08-18
- 范围：只改「使用指南」信息架构 / 导航 / 渲染；不修改 RAG、Governance、Evaluation、Knowledge OS 核心逻辑

## 1. 当前问题根因
- 原 Guide 一次性把全部章节渲染进同一长页面（GUIDE.sections 全量输出），左侧目录点击只 scrollIntoView，URL 不反映章节，无独立阅读位置。
- 状态源有三个（DOM 滚动位置 + hash + 内部 section state），不一致。

## 2. UI 改造
- 改为 Docs 风格：左侧固定/sticky 目录 + 右侧**只渲染当前章节**；顶部搜索 + 面包屑 + 底部上一章/下一章。
- 右侧内容区顶部 sticky：搜索框 + 目录抽屉按钮（移动端）。

## 3. Section Routing
- `#guide` = 首页（Guide Home）；`#guide/<slug>` = 具体章节（如 `#guide/wiki-review`、`#guide/source-verification`、`#guide/rag-evaluation`、`#guide/workflow`）。
- `resolveGuideRoute()` 从 location.hash 解析；未知 slug 回退首页。
- 章节切换通过 `location.hash = '#guide/'+slug`（push history）→ 刷新/深链/后退前进正常。
- 章节树：父级（总览可点击）+ 子级（具体页面/操作章节），`guideFlatten()` 生成有序扁平列表。

## 4. Sidebar
- `guideSidebarHtml(currentSlug)`：固定目录，父级加粗、子级缩进；当前项 `active` 高亮（含父级联动）。
- 点击目录 → `gotoGuideSection(slug)` → 路由切换，右侧只渲染该章节，滚动回顶部。

## 5. Search
- 搜索标题 + 章节内容（HTML 去标签后全文匹配）。
- 排序：标题命中 > 章节开头命中（核心主题）> 命中次数 > 子章节优先。
- 点击结果 → 直接进入对应章节（清空搜索）。
- 实测：搜索 "Mark Verified" → 第一条 = "核验 Source · 常用操作" → 点击进入 `#guide/source-verification`。

## 6. Breadcrumb
- 右侧内容顶部：`📖 使用指南 / 父章节 / 子章节`（如 使用指南 / 3. 页面说明 / Wiki Review）。

## 7. Previous / Next
- 底部「← 上一章 / 下一章 →」按 GUIDE_FLAT 顺序切换，点击直接改 hash 路由（不滚动）。

## 8. Browser History
- 章节切换 push history；`routeFromHash()` 统一处理 hashchange（guide/ 前缀 vs 普通 view）。
- 实测：wiki-review → source-verification → rag-evaluation，后退 → source-verification → wiki-review，前进 → source-verification，全部正确。

## 9. Deep Link
- 直接打开 `http://localhost:8765/#guide/source-verification` → 直接进入核验 Source 章节（active 高亮），不先显示首页。

## 10. 页面跳转
- 指南内「去 Wiki Review / 去 RAG Evaluation / 去 知识缺口 / 去 检索 Trace」仍走 `gotoView()`（现有导航，不刷新页面）。

## 11. Workflow Diagram
- 整体流程 + RAG 查询路径只在 `#guide/workflow` 独立章节显示，不再每个章节重复。

## 12. Responsive
- ≤900px：左侧目录收缩为顶部「📑 目录」按钮，点击展开抽屉（fixed 定位，可独立滚动），不挤压右侧内容。

## 13. 测试
- 更新 `test_control_center_guide.py`（11 条，适配 Docs-style 结构）
- 新增 `test_control_center_guide_navigation.py`（15 条：Guide home / section route / section render / sidebar active / prev-next / back / forward / refresh deep link / search→section / →Wiki Review / →Source / →RAG / 只渲染当前章节 / workflow / mobile）
- 更新 `test_control_center_rag_evaluation_view.py` 1 条（初始路由改用 routeFromHash）
- **401/401 全部通过**（386 + 15 新增）

## 14. 浏览器验证（真实 headless Chrome CDP，live 8765）
- 首页 #guide：打开 + 入口卡片 + 动态状态 + 全部章节 ✓
- 点击「2. 整体流程」→ 只显示流程（1 个 g-section）✓
- 点击「3. 页面说明」→ 只显示页面说明 ✓
- 点击「Wiki Review」→ 只显示 Wiki Review（draft→reviewed 步骤）✓
- 点击「Source Verification」→ 只显示核验 Source（Mark Verified + src_git_config）✓
- 点击「RAG Evaluation」→ 只显示 RAG Evaluation ✓
- 刷新 #guide/rag-evaluation → 保持章节 ✓
- 浏览器后退/前进 → 正确回到 source-verification / wiki-review ✓
- 搜索 "Mark Verified" → 第一条「核验 Source」→ 点击进入 #guide/source-verification ✓
- 深链 #guide/source-verification → 直接进入 ✓
- 无 JS 异常（仅 favicon 404）

## 15. 最终状态
```text
Guide Docs-style：PASS
Section Navigation：PASS
Search：PASS
Deep Link：PASS
Browser History：PASS
Current Section Only：PASS
Page Navigation：PASS
Browser：PASS
Regression：401/401
RAG 修改：NO
Governance 修改：NO
```
