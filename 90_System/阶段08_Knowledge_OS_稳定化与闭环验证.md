---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑧：Knowledge OS 稳定化与真实数据闭环验证

> 本阶段不新增功能，验证 Knowledge OS 文档=代码=目录一致、Control Center 真实数据
> Human-in-the-Loop 闭环可用、Evidence Gate 足够安全，并清理测试残留。

## 1. 阶段目标

1. 文档/代码/目录/Control Center 状态保持一致；
2. 用真实数据验证"Control Center → 人工决策 → Knowledge OS"完整闭环；
3. 验证 Evidence Gate 安全性（FP/FN）；
4. 使系统可进入长期运行，不继续改架构。

## 2. 当前系统状态（阶段⑧完成后）

- Wiki：20（3 stable + 1 reviewed + 16 draft）——本阶段真实 Approve 1 篇（CPU与寄存器：draft→reviewed）。
- Gap：3 条 → 2 条 pending（本阶段真实 Resolve 1 条：DMA，已保留历史）。
- Control Center：已实现（阶段⑦），Dashboard/待办/Review/Gap/Source/Activity/Health 全可用。
- RAG：main_vector_db 生产索引，RAG Health PASS=8。

## 3. KNOWLEDGE_OS.md 同步结果

- 第二、五、七、二十三、二十四章更新：
  - 登记 `90_System/control_center/`（目录职责表 + 结构地图）；
  - 登记 `control_center/server.py` / `service.py` / `activity_log.jsonl` / 阶段06/07/08 报告（重要文件表）；
  - Control Center 状态由 **PLANNED（未实现）→ ACTIVE（阶段⑦ MVP 已实现）**，如实描述能力与边界（不虚构 Merge/Edit/OCR/raw 生产化）。
- 阶段⑦新增文件归属：control_center/ 属 90_System（系统层），activity_log.jsonl 属 control_center（审计日志），阶段报告属 90_System 系统文档。

## 4. 测试数据清理结果

- `activity_log.jsonl` 中原有 1 条 `actor=integration-test / reject`（阶段⑦集成验证残留）——已按"只清理 test 记录"删除（该条是唯一 test 记录，无真实记录被误删，日志未整体清空；随后写入的均为真实操作）。
- 本阶段真实操作产生的 3 条记录保留。

## 5. Wiki Review 真实闭环

**测试 A（Approve，CPU与寄存器）**：阶段⑤ APPROVE 候选、内容完整、source 存在。
```text
Control Center → POST /api/actions/wiki_review:.../approve
  → service.execute_action → wiki_review.set_status(path,"reviewed")
  → frontmatter: status: draft → reviewed ✅
  → 第二次调用 → already_done（不重复修改）✅
```
**测试 B（Reject，MPU-6050）**：阶段⑤ INSUFFICIENT_SOURCE（内容过薄），确实不宜批准。
```text
POST .../reject → 记录决定，状态保持 draft ✅（拒绝后不被错误升级）
```

## 6. Knowledge Gap 真实闭环

选择 DMA Gap（"STM32F405 DMA如何搬运数据？"，已被 stable `STM32-DMA-配置与使用` 覆盖 → 确实可 Resolve）：
```text
Control Center → POST /api/actions/gap:.../resolve
  → service.execute_action → gaps.resolve_gap（保留历史）
  → knowledge_gaps.yaml: status: resolved + resolved_at/by/sources ✅
  → 第二次调用 → already_done ✅
```
未删除 Gap 历史、未伪造状态、未创建重复 Wiki。Git / PX4 两条 Gap 保持 pending（真实未解决，不强行 Resolve）。

## 7. Action 幂等性

- Approve 连续两次：第一次 success，第二次 already_done；frontmatter 只改一次。
- Resolve 连续两次：第一次 success，第二次 already_done；gaps.yaml 只写一次 resolved。
- 均不产生重复副作用、不重复写审计日志。

## 8. Activity Log

真实操作已记录（3 条，含 timestamp/type/target/actor/AI 建议/用户决定/result）：
```text
[2026-08-11 15:45:11] knowledge_gap | STM32F405 DMA如何搬运数据？ | AI:create_wiki | User:resolve | success
[2026-08-11 15:45:11] wiki_review   | MPU-6050惯性测量单元.md     | AI:approve  | User:reject  | success
[2026-08-11 15:45:11] wiki_review   | CPU与寄存器.md              | AI:approve  | User:approve | success
```

## 9. Evidence Gate 回归测试

| 类别 | 查询 | 预期 | 结果 |
|---|---|---|---|
| A 明确存在 | STM32 DMA 怎么配置？ | sufficient | ✅ sufficient（DMA stable） |
| A 明确存在 | FreeRTOS 任务调度优先级怎么设置？ | sufficient | ✅ sufficient |
| A 明确存在 | TTL 串口和 RS232 有什么区别？ | sufficient | ✅ sufficient |
| B 不存在 | PX4 EKF 卡尔曼滤波参数怎么调？ | missing | ✅ knowledge_missing |
| B 不存在 | ROS2 Nav2 代价地图怎么配置？ | missing | ❌ FP（见下） |
| C 高相似错主题 | Obsidian 的 Git 怎么配置？ | missing | ✅ knowledge_missing（修复生效） |
| C 高相似错主题 | WSL 里怎么装 Ubuntu？ | missing | ✅ knowledge_missing |
| D 纯中文 | 电容选型要注意什么？ | sufficient | ✅ sufficient |
| D 纯中文 | 锂电池怎么算放电时间？ | sufficient | ✅ sufficient |

## 10. False Positive / False Negative

- 样本：9 个真实查询 → **OK=8，FP=1，FN=0**。
- FP 案例：`ROS2 Nav2 代价地图怎么配置？` 命中 `30_Projects/移动底盘控制器/硬件选型/工控机选型.md` 且 sufficient=True——因为查询词 ROS2/Nav2 出现在检索片段中（底盘文档含 ROS2 环境），但**并未回答"代价地图配置"**。属主题词门控边界（"词出现"≠"问题被回答"）。
- 结论：FP 已大幅下降（Obsidian Git / WSL 两类已修复），残留 1 例为多词覆盖边界；FN=0（未牺牲召回）。

## 11. LLM Relevance Judge 是否必要

- 必要性：**建议作为阶段⑨候选，本阶段不实现**。现有"相似度 + 主题词覆盖"已解决已知误答，但无法排除"词出现但主题不符"的残余 FP。
- 最小设计（仅设计）：在 `answer_query` 中、heuristic 门控通过后，可选调用 LLM 对 top-k chunk 做二分类 `RELEVANT/IRRELEVANT`；全部 IRRELEVANT → 降级 knowledge_missing；任一批次 RELEVANT → 维持 sufficient。要求：离线可回退（LLM 不可用时用当前行为）、不引入新依赖、仅对英文/技术词已覆盖但置信度高的问题触发（控制成本）。

## 12. Control Center 状态一致性

- 仪表盘与真实状态一致：Approve/Reject/Resolve 后 dashboard 显示 draft=16、reviewed=1、stable=3、gaps_pending=2，与 frontmatter / knowledge_gaps.yaml 完全一致。
- 无"UI 显示 Approved 但 frontmatter 仍是 draft"类分裂——Action 是派生视图，实时读取真实数据。

## 13. API / Service 权限边界

- 全部写操作：UI → API → `service.execute_action` → 现有 `wiki_review.set_status` / `gaps.resolve_gap`。
- 无 UI 直接改 Markdown、无直接操作 Vector DB、无复制第二套状态逻辑（代码审查 + 单元测试确认）。

## 14. 系统健康

```text
knowledge_os_check：ERROR=0，WARNING=3（不变），PASS=98
rag_health（main）：ERROR=0，PASS=8，INFO=1
wiki_health：ERROR=0，WARNING=0，PASS=20
```
阶段⑧未引入任何新 ERROR/WARNING（与阶段⑦相比仅 Wiki 状态 INFO 变化：reviewed 0→1）。

## 15. 修复的问题

1. KNOWLEDGE_OS.md 文档漂移：Control Center 由"规划中"更正为"已实现"，登记 control_center/ 目录与文件、阶段06/07/08 报告。
2. 阶段⑦测试残留：activity_log.jsonl 的 integration-test 记录已清理。
3. 无新增稳定性 Bug（幂等、API、Activity、Health 均正常）。

## 16. 当前未解决的问题

- 残余 FP 1 例（多词覆盖边界，LLM Judge 建议阶段⑨评估）。
- MPU-6050：source 内容不足，待阶段⑥/⑨补资料后重审。
- 2 条 pending Gap（Obsidian Git、PX4 EKF）真实未解决。
- 4 个图片型 PDF 未 OCR（既定不做）。
- raw_vector_db 未生产化；Merge/Edit/多用户/工作流引擎未实现（既定不做）。
- Control Center 尚未纳入 Git 提交（全部未跟踪，未 commit）。

## 17. 阶段⑨建议

1. **LLM Relevance Judge**（FP 残余问题）最小化实现 + 回归；
2. **批量人工批准工作流**：把阶段⑤ 15 篇 APPROVE 建议接入 UI 批量 Approve；
3. Wiki 全文搜索/来源追踪增强（Source 页面已具备基础）；
4. 将已稳定部分纳入首次 Git commit（需你批准）。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
