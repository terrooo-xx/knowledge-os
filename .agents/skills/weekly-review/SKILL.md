---
name: weekly-review
description: 定期复盘知识库质量并生成周期报告（Weekly Review）。用于检查 00_Inbox、20_Wiki 和 30_Projects 中的未处理资料、重复内容、失效链接、过时风险、知识缺口与项目状态，生成 weekly-review.md 与 snapshot.json，并由 Control Center 统一查看。
---

# weekly-review

## 何时执行

- 自动：Windows 计划任务 `Knowledge OS Weekly Review`，默认每周五 18:00（配置见 `90_System/rag/config.yaml` 的 `weekly_review` 段：`enabled / weekday / time / stale_threshold_days`）。
- 手动：
  - `python 90_System/rag/scripts/review/weekly_review.py [--week YYYY-WNN] [--force]`
  - 或 Control Center「📝 生成本周复盘」按钮。
- 幂等：同一周重复执行不会产生重复文件，只更新同一 `YYYY/WNN/` 下的两个文件（无 `--force` 时跳过已存在周）。

## 输入数据来源

- `20_Wiki/**/*.md`：frontmatter（status / created / updated / review_required / confidence / source）
- `30_Projects/<项目>/00_项目索引.md`：frontmatter 项目状态（status / phase / progress / next_step / blockers / updated）
- `90_System/rag/tests/knowledge_gaps.yaml`：知识缺口
- Git 历史：活动与变更
- `90_System/control_center/activity_log.jsonl`、`90_System/任务记录/inbox_processor_log.md`：活动来源
- 健康检查（复用，不重复实现）：`rag_health_check.py` / `wiki_health_check.py` / `knowledge_os_check.ps1`

## 报告目录结构

```text
40_Outputs/reviews/每周复盘/YYYY/WNN/
    weekly-review.md      # 人读
    snapshot.json         # 机器读（Control Center / 趋势）
```

## 输出文件

- `weekly-review.md`：11 个固定章节（本周摘要 / Knowledge Growth / Wiki 状态 / Knowledge Gaps / Project Status / Review Queue / Stale Risk / Activity / System Health / 本周建议 / 待验证事项）。
- `snapshot.json`：结构化快照，字段见 `weekly_review.py` 的 `build_snapshot()`。

## LLM 可以做什么

- 知识缺口分析（基于证据）
- 趋势解释
- 自然语言摘要（数据必须来自确定性统计）
- 本周建议

## LLM 不可以做什么

- 统计 Wiki 数量、项目进度、Health Score、Git 数量、Review 数量、Stale 数量（必须由 `metrics.py` 程序计算）
- **禁止猜测项目进度**：无结构化 `progress` 字段时输出 `Project status source insufficient`，不得推断百分比
- **禁止重复实现系统健康检查**：Health 必须复用 `rag_health_check.py` / `wiki_health_check.py` / `knowledge_os_check.ps1`
- **禁止制造无证据的知识缺口**：无来源支撑的缺口必须标记“待验证”
- 禁止把“Stale Risk（复查风险）”表述为绝对意义上的“知识已过期”
- 不直接删除文件、不修改 Wiki 正文、不移动已有日志/报告

## 确定性统计入口

```text
90_System/rag/scripts/review/metrics.py     # collect_metrics()：事实统计
90_System/rag/scripts/review/weekly_review.py  # 报告/快照生成
```

## 检查范围（人工复盘时）

- `00_Inbox` 未处理资料
- 重复或近义笔记
- 失效内部链接
- 缺少来源的技术结论
- 长期 `draft` / 过时风险
- 项目文档与 Wiki 冲突
- 项目问题记录中可回流的经验