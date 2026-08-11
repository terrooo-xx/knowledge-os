---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑦：Knowledge OS Control Center（人机协作管理中心）

> 本阶段建立本地 Human-in-the-Loop 管理界面：把 Wiki 审核、Gap 决策等人工操作从 PowerShell
> 收敛到统一 API + UI；同时修复"高相似度但答非所问"的证据门控安全问题。
> 全部复用现有 Knowledge OS 能力（wiki_review.set_status / gaps.resolve_gap / health check），
> 未重写状态机、未重建 RAG、未动 Wiki 状态（除人工操作外）。

## 1. 当前系统分析

- Wiki：20（3 stable + 17 draft），frontmatter/source 全部有效（Wiki Health PASS=20）。
- RAG：main_vector_db 生产索引（29 文档 / 34 chunk），RAG Health PASS=8。
- Gap：knowledge_gaps.yaml 现有 3 条 pending（DMA、Obsidian Git、PX4 EKF —— 后两条为阶段⑥评估查询真实发现的缺口）。
- 人工操作此前仅能通过 CLI/PowerShell（`wiki_review.py --approve/--stabilize`、`resolve_gap`）执行。
- 已知算法缺陷：高相似但语义无关的内容被判 sufficient（阶段⑥复现："Obsidian Git 配置" 命中 CubeMX/CLion 且 conf=1.0）。

## 2. Control Center 架构

```text
Browser (localhost:8765, 单页 UI)
        │ fetch
        ▼
server.py（Python 标准库 http.server，零新依赖）
        │ JSON API
        ▼
service.py（Action 模型 + 幂等执行 + Activity Log）
        │ 复用现有函数
        ▼
rag_engine.wiki_review.set_status / rag_engine.gaps.resolve_gap /
rag_health_check.py / wiki_health_check.py / knowledge_os_check.ps1
        ▼
20_Wiki / knowledge_gaps.yaml / main_vector_db（真实数据源，无第二套存储）
```

## 3. Backend / API 设计

- 技术：Python 标准库 `http.server.ThreadingHTTPServer`（无 Flask/FastAPI/Docker，localhost 本地）。
- 启动：`python 90_System/control_center/server.py`（默认 http://127.0.0.1:8765）。
- 端点：
  - `GET /api/dashboard`：Wiki 状态计数 / Gap pending / AI 待办 / Inbox 文件 / 最近活动
  - `GET /api/actions`、`GET /api/actions/{id}`：Action 列表与详情
  - `GET /api/wikis`、`GET /api/gaps`、`GET /api/sources`、`GET /api/activity`、`GET /api/health`
  - `POST /api/actions/{id}/approve|reject|resolve|ignore|reprocess`
- API 只调用 service 层，service 层复用现有 Knowledge OS 函数，**不直接改 Markdown / 不直接操作 Vector DB**。

## 4. Action 模型

```json
{
  "id": "wiki_review:20_Wiki/03_STM32/xxx.md",
  "type": "wiki_review",
  "status": "pending",
  "created_at": "2026-08-10",
  "source": ["00_Inbox/...pdf"],
  "target": {"wiki": "...", "title": "...", "domain": "..."},
  "reason": "新 Wiki 等待人工审核",
  "evidence": {"source": [...], "content_length": 600},
  "ai_recommendation": "approve",
  "available_actions": ["approve","reject","ignore"],
  "execution_result": null
}
```

- Action 是**派生视图**（来自 frontmatter / gaps.yaml），不单独持久化 → 无第二套数据、无状态不一致。
- Gap Action：`gap:{question}`，ai_recommendation 取 `suggested_action`。

## 5. UI 页面（static/index.html，单页 7 视图）

仪表盘 / AI 待办 / Wiki Review / 知识缺口 / Source / 操作记录 / 系统健康。中文界面，点击即调 API。

## 6. Wiki Review

- 列表按 status 展示（draft 17 / reviewed 0 / stable 3），draft 可打开详情（来源 Evidence + AI 建议）。
- 操作：Approve（draft→reviewed，走 `set_status`）/ Reject / Ignore。

## 7. Knowledge Gap

- 列表显示问题/类型/状态/发现时间/AI 建议；详情显示"AI 认为它是 Gap 的原因" + 相关 Source。
- 操作：Resolve（走 `gaps.resolve_gap`，保留历史）/ Ignore / Reprocess。

## 8. AI 待办

- 聚合"现在需要用户做什么"：17 个 Wiki Review + 3 个 Gap，每项显示 AI 建议与一键操作。

## 9. Activity / Audit Log

- `90_System/control_center/activity_log.jsonl`（追加式）：时间 / action_id / 类型 / 目标 / 执行者 / AI 建议 / 用户决定 / 结果。
- 示例（集成验证写入的一条）：`CPU与寄存器.md / wiki_review / reject / 状态保持 draft`。
- 幂等：approve 二次点击 → `already_done` 且不重复写日志；resolve 同理。

## 10. Health

- `/api/health` 直接调用现有检查：rag_health_check（ERROR=0 PASS=8）、wiki_health_check（E=0 W=0）、knowledge_os_check.ps1（汇总 PASS=98 WARNING=3 ERROR=0），只读、不重实现。

## 11. Evidence Gate 改进（高相似误答修复）

- 修改 `rag_engine/evidence.py::assess_evidence`：当 `top_score >= threshold` 时新增**主题词覆盖门控**——查询中的显著词（英文/技术词，如 Git/Obsidian）若在所有检索 chunk 中均缺失，则降级为 `knowledge_missing`，不再"高相似即 sufficient"。
- 实测：`"Obsidian 的 Git 怎么配置？"` → 修复前 sufficient=True（答非所问）→ 修复后 sufficient=False、gap=knowledge_missing（reason 列出缺失主题词 git, obsidian）。
- 纯中文查询无显著词，门控跳过，保持原行为（不误伤）。
- 3 篇 stable Wiki 查询回归不受影响（主题词均在 Wiki 中）。

## 12. 已完成的代码修改

| 文件 | 修改 | 风险 | 测试 |
|---|---|---|---|
| `90_System/rag/rag_engine/evidence.py` | 高相似主题词覆盖门控 | 中（检索判定） | test_evidence_gaps 新增 3 用例 PASS |
| `90_System/rag/tests/test_evidence_gaps.py` | 新增门控用例 | - | PASS |
| `90_System/rag/tests/test_main_query.py` | fixture 补 STM32（门控后真实化） | - | PASS |
| `90_System/control_center/service.py`（新） | Action 模型/幂等执行/Activity Log/Health 聚合 | 低 | test_control_center PASS |
| `90_System/control_center/server.py`（新） | stdlib HTTP API + 静态页 | 低 | 端点实测 PASS |
| `90_System/control_center/static/index.html`（新） | 7 视图单页 UI | 低 | HTTP 200 PASS |
| `90_System/control_center/activity_log.jsonl`（运行时生成） | 审计日志 | 低 | 实测 PASS |

## 13. 测试结果

15/15 测试文件全部 PASS（含新增 `test_control_center.py` 5 用例 + evidence 门控 3 用例）。服务端点实测：dashboard/actions(20)/wikis/gaps(3)/sources(33)/activity/health 全部正常；POST approve/reject/resolve/ignore 链路验证通过（真实 reject 一次写入审计日志且 Wiki 状态保持 draft，验证"UI→API→现有函数→真实数据"闭环且不越权）。

## 14. 未完成事项

- Control Center 第一版未含：多用户/权限、复杂工作流引擎、移动端、Merge/Edit 完整实现（API 预留 reprocess/merge 命名，未做）。
- Evidence Gate 仅覆盖"英文/技术词缺失"场景；纯中文问题的语义相关性仍依赖分数（后续可用 LLM 相关性打分增强）。
- 4 个图片型 PDF 未 OCR（阶段⑥决策待定）。
- 审计日志含 1 条集成验证产生的 reject 记录（actor=integration-test），可清理。
- 3 条 pending Gap（含阶段⑥新发现的 Git/PX4）待你决策。

## 15. 下一阶段建议

- 阶段⑧候选：① Evidence Gate 增加 LLM 相关性二次判断或中文语义校验；② Merge/Edit 动作落地；③ Wiki 批量审核工作流（把阶段⑤的 15 篇 APPROVE 建议接入 UI 批量批准）；④ Inbox→Wiki 自动管线可视化。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
