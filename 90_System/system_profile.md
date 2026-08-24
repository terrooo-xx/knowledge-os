---
type: system-profile
status: authoritative-current
schema_version: 1
generated_at: 2026-08-25
source_commit: 82e7383149ac7156596c6f6fafd90e3f8b2a2b79
source_tag: baseline/rc-codex-wecom-20260820
rag_baseline: bl-eval-20260817T162956
freshness_policy: update-on-system-change
---

# Knowledge OS System Profile

> 本文档回答：**Knowledge OS 现在是什么？**（当前系统状态快照 / AI 快速上下文入口）
> 不是 `KNOWLEDGE_OS.md`（应是什么/架构宪法）的替代品，也不是 README 或任务记录的替代品。
> 更新机制：`90_System/scripts/system_profile_generator.py --update` 刷新动态字段；稳定描述人工维护。
> 新鲜度：`system_profile_generator.py --check`（对比 `source_commit` 与 `git HEAD` → STALE / CURRENT）。

## 1. System Identity

Knowledge OS 是一个**个人嵌入式 / 机器人 / 无人机工程知识库操作系统**：
把「原始资料 → 结构化长期知识 → 可检索可回答 → 可治理可恢复」做成一条有约束、可验证的流水线。
它不是普通 Obsidian Vault（多了知识生命周期治理 + RAG + 审计），不是普通 RAG 服务（多了人机协同 Control Center、
LLM Judge、Knowledge Gap、Baseline/Governance），也不是普通 AI Agent（多了知识库自身的治理规则与 Bootstrap 恢复机制）。

- 解决：个人工程知识长期积累的「进来一堆资料 → 变成可查、可信、可复现的知识资产」问题。
- 核心用户：本人（嵌入式 / 飞控 / 移动底盘 / ROS2 方向的工程师）。
- 核心工作方式：Inbox 收集 → 分类 → Source/Wiki 沉淀 → 人工审核 → 索引 → RAG 问答 → 周复盘 → 版本治理。

## 2. Current Version

- 当前 HEAD：`82e7383`（feat: upgrade bootstrap with codex cc-switch deepseek）
- 正式 Tag：`baseline/rc-codex-wecom-20260820` → f9a1130（未变）
- 远程：`origin = https://github.com/terrooo-xx/knowledge-os`（PRIVATE，分支 master）
- RAG Baseline：`bl-eval-20260817T162956`（coverage 89.3%，STABLE）
- Phase：Phase 3 ACTIVE（Git/Baseline/Tag 治理实施中；CLOSED 需人工确认）

## 3. Current Git State

- HEAD：82e7383149ac7156596c6f6fafd90e3f8b2a2b79
- Branch：master（唯一）
- Remote：origin（GitHub Private，terrooo-xx/knowledge-os）
- Tag：baseline/rc-codex-wecom-20260820 → f9a1130
- Working tree：一般干净；预期未跟踪项为 2 个 DEFER Source + 待入库审计报告
- 发布链路：Gate 0→1→1C→2→2C→3→Bootstrap Upgrade 全部 PASS

## 4. Current Phase

Phase 3：ACTIVE（阶段14~22D 已完成入库；Git/Baseline/Tag 治理实施中）。
阶段 23+ 按用户明确任务推进；Phase CLOSED 仅人工确认。

## 5. Architecture Snapshot

```text
00_Inbox（原始资料）
  → inbox_processor.py（分类建议）
  → 10_Sources（长期证据）/ 20_Wiki（LLM-Wiki，draft→reviewed→stable）/ 30_Projects（项目六类文档）
  → update_index.py → main_vector_db（20_Wiki + 30_Projects 合并，生产索引）
  → hybrid_query / knowledge_service（检索 → 证据 → LLM Judge → 回答 / Knowledge Gap）
  → Control Center（人机协同：Dashboard/Review/Gaps/Eval…） + Weekly Review（周复盘）
  → 版本治理（Commit/Baseline/Tag/Phase）+ Bootstrap（跨机恢复）
外部：Codex ↔ MCP（knowledge-os）↔ Knowledge OS；CC Switch + DeepSeek（AI Runtime）
```

## 6. Directory Model

| 目录 | 职责 | Git |
|---|---|---|
| 00_Inbox | 原始资料入口（含 待处理文件/个人笔记 私人 PDF，gitignored） | 仅 .gitkeep + 2 个已处理 md |
| 10_Sources | 长期来源/证据（官方文档为主） | 5 个正式 Source 已纳入 |
| 20_Wiki | 结构化知识（frontmatter status） | ✓ |
| 30_Projects | 项目六类文档（architecture/modules/interfaces/decisions/tasks/problems） | ✓ |
| 40_Outputs | 输出/复盘/审计证据 | 正式证据 ✓；运行产物 gitignored |
| 90_System | 系统规范/KNOWLEDGE_OS.md/rag/control_center/scripts/任务记录/templates/prompts | 核心资产 ✓ |
| .agents/skills | 正式 Skill（4 个） | ✓ |
| .obsidian | Obsidian 配置 + realclaudian 插件 | 配置 ✓ |

## 7. Knowledge Lifecycle（真实存在）

Inbox → Classification（inbox_processor，只读建议）→ Source（10_Sources）→ Wiki（wiki_compile 仅 draft）→ Review（wiki_review / Control Center：draft→reviewed→stable，人工确认）→ Index（update_index 增量，index_manifest）→ Retrieval（wiki-first + RAW fallback）→ Evidence（evidence_window 整 chunk 扩展）→ LLM Judge（fail-closed）→ Answer / Knowledge Gap → Weekly Review + Governance。

## 8. RAG Architecture

- ingestion：parse_file（pdf/md/txt/html）→ chunk（800 字，overlap 100）
- embedding：BAAI/bge-small-zh-v1.5（HF 缓存，默认离线 HF_HUB_OFFLINE=1）
- store：本地 JSONL 向量库（main_vector_db；raw/wiki 可选）
- retrieval：wiki-first 门控（阈值 0.78）+ wiki_fallback_on_insufficient + RAW fallback（dense 0.6 + BM25 0.4 融合）
- reranker：BAAI/bge-reranker-v2-m3（路径经 config.local.yaml machine-local 覆盖；默认离线）
- evidence：assess_evidence + evidence_window（邻接 chunk 整块扩展，3000 字上限，不句中硬切）
- judge：DeepSeek relevance judge（fail-closed；不可用→knowledge_missing）
- answer：deep 模式 LLM 生成；fast/evidence_only 仅返回结构化证据
- gaps：tests/knowledge_gaps.yaml（knowledge_missing/insufficient/conflict/retrieval_problem/answer_quality_problem）
- evaluation：evaluate_benchmark.py（28 查询）+ golden set + baseline regression（REAL_REGRESSION=0 为门禁；JUDGE_VARIANCE 不阻塞）

## 9. Evidence & Answering

- Evidence Window：完整 chunk 邻接扩展，无句中截断（Gate 0 专项验证通过）
- fail-closed：LLM 不可用/异常 → knowledge_missing，绝不编造
- 无依据问题 → Knowledge Gap（pending），不自动用外部知识补全

## 10. Knowledge Gaps

- 当前：5 pending / 1 resolved（tests/knowledge_gaps.yaml）
- 流程：RAG 证据不足 → gap 记录 → Control Center 展示 → resolve（人工）
- evaluation/gaps.yaml 为治理注册表（source acquisition 关联）

## 11. Control Center

- 位置：90_System/control_center（server.py，端口 8765，stdlib）
- 视图：Dashboard / AI 待办 / Wiki Review / Knowledge Gaps / Sources / Activity / Weekly Review / Project Status / System Health / Retrieval Trace / RAG Evaluation / 使用指南
- 核心 API：/api/health、/api/dashboard、/api/actions（approve/reject/resolve）、/api/weekly_review/*、/api/rag/evaluation/*、/api/source_acquisition/*、/api/gaps/*、/api/query/trace
- 启动：start_control_center.bat（位置无关，PATH 解析 python）

## 12. Weekly Review & Scheduler

- Weekly Review：review/metrics.py + weekly_review.py（snapshot.json + weekly-review.md + insight.json）→ 40_Outputs/reviews/每周复盘/YYYY/Www/
- Scheduler（Windows 任务计划，3 个）：
  - Knowledge OS Review Preflight（每 30 分钟）
  - Knowledge OS Weekly Review（每周五 18:00）
  - KnowledgeBase-UpdateChangelog（每日 23:00）

## 13. MCP / Codex

- 外部项目 → Codex（`-p knowledge`）→ MCP `knowledge-os`（knowledge_search，fast/deep/evidence_only）→ Knowledge OS
- 配置：~/.codex/knowledge.config.toml（machine-local，approval=approve）；bridge 由模板动态生成（Documents/Codex/knowledge_os_mcp_bridge.py）
- cwd 独立：vault 由 KNOWLEDGE_OS_VAULT 解析，不依赖当前工作目录（Gate 2/3 已验证 cwd≠Vault）

## 14. AI Runtime

- Codex CLI：0.147.0（npm 全局 + WindowsApps）
- CC Switch：3.20.0（本地代理 127.0.0.1:15721；DeepSeek provider wire_api=responses 原生，无需协议路由）
- DeepSeek：api.deepseek.com，model deepseek-v4-flash / deepseek-v4-pro；API Key 仅 machine-local（env + CC Switch provider 安全存储）
- 状态：AI Runtime READY（bootstrap 验证）

## 15. Bootstrap

- 脚本：90_System/scripts/bootstrap.ps1 + bootstrap_helper.py + templates/mcp_bridge_template.py + requirements-lock.txt
- 自动安装：Codex（npm，需 Node）
- 自动配置：venv（90_System/.venv，gitignored）、deps（requirements-lock）、models（检测）、reranker（config.local.yaml）、RAG index、Codex config、DeepSeek provider（读/验）、MCP、approval、scheduler、Control Center
- 用户提供：GitHub 认证、DeepSeek API Key、CC Switch 官方安装器（若缺失）、Python 3.14.x（必须预装）
- 模式：-CheckOnly / -Skip* / -CreateVenv；幂等（VERIFY/REPAIR）
- 本机状态：BOOTSTRAP READY（全部 PASS，含 AI Runtime）

## 16. Current New Machine Environment

（Gate 4 前置，见 40_Outputs/reviews/Bootstrap_Upgrade_Release_2026-08-24.md 正式矩阵）
必须预装：Windows 10/11、PowerShell 5.1+、Git、GitHub 认证、Python 3.14.x。
用户提供：DeepSeek API Key（CC Switch 缺失时其官方安装器）。
Bootstrap 自动：venv/deps/models/reranker/index/Codex/MCP/approval/scheduler/Control Center。
不需要：OpenAI 官方登录、Winget、Chocolatey（可选）。

## 17. Git Governance

- Commit/Baseline/Tag/Phase/Summary 唯一权威：KNOWLEDGE_OS.md 第二十八章
- commit 格式 `[<phase|project>] <type>: <摘要>`；禁止 git add -A；精确文件清单
- 正式里程碑 Tag：`baseline/<baseline_id>`；不为每个 commit/run 建 tag
- 禁止自动 commit/push（除非任务明确授权）；当前仓库有 remote（origin）
- 运行时/派生文件禁止作为正式成果提交（.gitignore 已覆盖）

## 18. Baseline & Verification

- RAG Baseline：bl-eval-20260817T162956（89.3%，STABLE；Gate 0/2/3 多次复现，最新复测 REAL_REGRESSION=0）
- Verification：pytest 412/412；rag_health_check / wiki_health_check / knowledge_os_check.ps1；bootstrap -CheckOnly → BOOTSTRAP READY
- Health Check ≠ Baseline Verification（运行时健康 vs 行为复现），两者分开判定

## 19. External Dependencies

GitHub（私有仓库）、DeepSeek API、Codex CLI、CC Switch、Git、Python、pip（pypi）、HuggingFace/ModelScope（模型下载）

## 20. Machine-local Dependencies

Python 3.14.x；BGE embedding/reranker 模型缓存；DeepSeek API Key（env + CC Switch）；~/.codex（knowledge.config.toml）；CC Switch 配置（~/.cc-switch）；Windows Scheduler；MCP bridge（Documents/Codex）；config.local.yaml（gitignored）。
（不记录真实用户路径细节；Bootstrap 负责发现/恢复。）

## 21. Known Limitations

- 需要 Python 3.14.x（Bootstrap 不自动安装）
- CC Switch 缺失时需用户提供官方安装器（不硬编码下载 URL）
- DeepSeek API Key 需用户输入（且账户需有余额；曾出现瞬时 HTTP 402）
- Codex 经 npm 安装需 Node；github.com 直连 DNS 可能异常（用 http.curloptResolve 临时绕行，不写入配置）
- raw_vector_db 记录很少（可选路径，非生产）
- q_drone_power 为已知 judge 方差查询（JUDGE_VARIANCE，不影响 Baseline）

## 22. Current Health Summary

- pytest：412/412 passed
- rag_health_check：ERROR=0 WARNING=0 PASS=8
- wiki_health_check：25/25 PASS
- bootstrap：BOOTSTRAP READY（Python/Deps/Models/Secrets/Index/Scheduler/Codex-MCP/AI Runtime/CC/Baseline 全 PASS）
- Control Center：127.0.0.1:8765 可访问
- MCP：knowledge_search answerable / judge relevant（cwd 独立）

## 23. Source References

- 架构宪法：90_System/KNOWLEDGE_OS.md
- RAG 引擎：90_System/rag/README.md + AGENTS.md
- 控制中心：90_System/control_center/
- Bootstrap：90_System/scripts/bootstrap.ps1 + bootstrap_helper.py
- 治理报告：40_Outputs/reviews/（Gate0~3、Bootstrap Upgrade、Bootstrap Upgrade Release）
- AI 操作规则：AGENTS.md


<!-- DYNAMIC-START -->
## 附：自动刷新动态字段（由 system_profile_generator.py --update 覆盖此区块）

- source_commit: `82e7383149ac7156596c6f6fafd90e3f8b2a2b79`
- source_tag: `baseline/rc-codex-wecom-20260820`
- generated_at: 2026-08-25 00:09:03
- rag_baseline: `bl-eval-20260817T162956` coverage=89.3% status=STABLE
- bootstrap_state: BOOTSTRAP READY (mode=full)
- rag_health: ERROR=0 WARNING=0 PASS=8 INFO=1
- wiki: draft=9, reviewed=13, stable=3, unknown=0
<!-- DYNAMIC-END -->

