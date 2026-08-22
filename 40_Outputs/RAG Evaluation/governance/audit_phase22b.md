# Phase 22-B：Control Center 使用指南实施报告

- 日期：2026-08-17
- 范围：新增「使用指南」页面（只读操作手册 + 流程导航 + 当前状态引导）；不修改 RAG 算法、不改变治理逻辑

## 1. 审计结果（真实页面/API）

- 11 个页面：仪表盘 / AI 待办 / Wiki Review / 知识缺口 / 来源 / 活动 / 每周复盘 / 项目状态 / 系统健康 / 检索 Trace / RAG Evaluation（均有 render 分支与 API）
- Source 治理（Mark Verified）实际位于 RAG Evaluation → Source Acquisition 卡片（无独立导航页）
- 关键 API：dashboard / actions / wikis / gaps / sources / activity / weekly_review / project_status / health / query_trace / rag/evaluation(+baseline+governance+diff) / source_acquisition / golden_set / judge_variance / gaps/evaluation

## 2. 使用指南结构

- 主导航新增 `📖 使用指南`（仪表盘之后），`views`/`VIEW_LABELS` 同步
- 内容结构（GUIDE const，version 1.0 / updated 2026-08-17）：
  1. 开始使用（新手入口卡片 ×9 + 指南说明）
  2. 整体流程（Knowledge OS 流程图 + RAG 查询路径图，纯 HTML/CSS）
  3. 页面说明（页面职责表：作用/主要操作/是否修改知识）
  4. 常用操作（导入资料 / 审核批准 Wiki / 核验 Source / 处理 Gap / 运行 Evaluation）
  5. Governance 与 Evaluation Required
  6. Baseline 说明（STABLE/IMPROVED/REGRESSED/UNVERIFIED/FAILED + JUDGE_VARIANCE≠REGRESSED）
  7. 常见问题
  8. 故障排查
- 布局：顶部搜索 → 左侧目录 → 右侧正文 → 底部上一节/下一节

## 3. 页面职责说明（按代码核实）

见指南「3. 页面说明」表格；要点：Dashboard/AI 待办/Wiki Review 职责明确；Source 治理位置明确为 RAG Evaluation 卡片；Wiki 正文编辑当前通过 Markdown 文件（无在线编辑器，指南已如实说明）。

## 4. 操作流程说明

- 导入资料：00_Inbox → AI/Ingestion（自动）→ AI 待办 → Wiki Draft → Wiki Review → 人工审核/批准 → Index → Governance → Benchmark → Baseline Check
- 核验 Source：RAG Evaluation → Source Acquisition → 找到 acquired/⚠ 待人工核验（如 src_git_config）→ [Mark Verified] → 确认 → ✓ 已核验（与 Wiki Approved 独立）
- 处理 Gap：知识缺口 → 区分 Knowledge/Evidence/Retrieval/Judge/System → 详情/Source → 获取来源或补 Wiki

## 5. Knowledge OS 流程图（HTML/CSS，无图片）

Inbox → AI/Ingestion → Source/Wiki 分支 → Index → Governance Required → Benchmark → Baseline Check → STABLE/REGRESSED → Weekly Review

## 6. RAG 流程图

Query → Wiki First → Quality Gate → Wiki 足够/RAW Fallback → Reranker → Evidence → Judge → Answer / Knowledge Missing（Fail-Closed）

## 7. 动态状态引导

- 顶部「当前系统状态」7 项：Baseline / Baseline Status / Governance / Evaluation Required / 待审核 Wiki / 待核验 Source / Open P0/P1（全部来自 API，不写死）
- 「当前建议」确定性优先级：Evaluation Required → 待审核 Wiki → 待核验 Source → Open P0/P1 → 无需人工处理
- API 失败：safeApi 捕获 → 显示 —，并提示「API 不可用」，指南内容仍可读（graceful fallback）
- 实测建议：`当前建议：📝 有 9 个 Wiki 待审核 → 去 Wiki Review`（动态）

## 8. Control Center 导航

`仪表盘 → 📖 使用指南 → AI 待办 → Wiki Review → 知识缺口 → 来源 → 活动 → 每周复盘 → 项目状态 → 系统健康 → 检索 Trace → RAG Evaluation`；指南入口卡片/按钮全部跳转真实页面（gotoView）。

## 9. API / 数据来源

指南只读调用：/api/rag/evaluation/baseline、/api/rag/evaluation/governance、/api/wikis、/api/source_acquisition、/api/gaps/evaluation（safeApi + try/catch）；无 POST 写操作。

## 10. 测试

- 新增 `test_control_center_guide.py`（11 条）：页面存在 / 导航 / 内容渲染 / 目录跳转 / 页面跳转 / 流程图 / 动态状态建议 / API 失败 graceful fallback / 刷新持久 / 不修改现有页面 / node 语法检查
- **386/386 全部通过**（375 + 11 新增）

## 11. 浏览器验证（真实 headless Chrome CDP，live 8765）

| 项 | 结果 |
|---|---|
| 点击「使用指南」打开 | PASS |
| 左侧目录出现（TOC + 搜索） | PASS |
| Wiki Review 操作步骤（审核/批准/Markdown 编辑说明） | PASS |
| Source Verified 指引（Mark Verified 位置 + src_git_config + 独立说明） | PASS |
| RAG Evaluation 指引（运行 Benchmark / Wiki Hit） | PASS |
| Governance 指引（Evaluation Required 含义 + 触发/不触发 + 不浪费资源） | PASS |
| 整体流程 + RAG 查询路径图（25 box / 18 arrow） | PASS |
| 动态状态（7 卡 + 当前建议） | PASS |
| 搜索「Mark Verified」→ 目录命中 | PASS |
| 刷新 #guide 保持 | PASS |
| JS 异常 | 0（仅 favicon 404） |

## 12. 当前限制

- 指南为单页静态内容 + 动态状态；后续新增页面/操作需同步更新 GUIDE（版本号 +1）
- Wiki 正文无在线编辑器（指南已如实说明编辑方式）
- 搜索为目录级过滤（不全文高亮）

## 13. 下一阶段建议

- 指南版本化发布记录（CHANGELOG）
- 若新增在线 Wiki 编辑器，更新「常用操作 → 审核 Wiki」说明
- 可考虑把「当前建议」提升到 Dashboard 顶部（与指南共享同一逻辑）

## 最终状态

```text
Guide 页面：PASS
Workflow Diagram：PASS
Dynamic Status：PASS
Git Source Verified 指引：PASS
RAG Evaluation 指引：PASS
Browser：PASS
Regression：386/386
RAG 算法修改：NO
Governance 逻辑修改：NO
```
