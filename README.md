# Knowledge OS

> A personal engineering knowledge-base operating system: an Obsidian vault with a governed knowledge lifecycle, evidence-grounded RAG, a human-in-the-loop control center, and a cross-machine bootstrap.

个人嵌入式 / 机器人 / 无人机工程知识库操作系统。把「原始资料 → 结构化长期知识 → 可检索可回答 → 可治理可恢复」做成一条有约束、可验证的流水线。

## Why Knowledge OS?

普通 Obsidian Vault 只解决"记下来"，普通 RAG 只解决"查得到"，普通 AI Agent 只解决"帮干活"。
Knowledge OS 把三者收敛成一个**可治理、可验证、可跨机恢复**的个人知识系统，解决：

- 知识碎片化：资料进来后没有生命周期，越攒越乱。
- 知识生命周期失控：新资料、旧资料、废弃资料混在一起。
- RAG 无依据回答：模型凭外部知识编造，缺少来源约束。
- 知识更新后无法治理：改了不知道，错了不追责，回滚没依据。
- AI Agent 无法稳定访问个人知识：每次都要重新接入、重新解释。
- 跨项目知识复用困难：项目经验无法回流成长期知识。

## What It Does

- **知识生命周期**：`00_Inbox → 分类 → Source → Wiki(draft→reviewed→stable) → 审核 → 索引`，全程有约束。
- **Evidence-grounded RAG**：检索 → 证据窗口 → LLM Judge（fail-closed）→ 回答，无依据不编造。
- **Knowledge Gap 检测**：证据不足自动记录缺口，不强行作答。
- **人机协同治理**：Control Center 统一处理 Wiki 审核 / 知识缺口 / 复盘 / 健康 / RAG 评测。
- **AI Runtime**：Codex + CC Switch + DeepSeek + MCP，外部项目可直接查询知识库。
- **跨机恢复**：Bootstrap 一键从 GitHub clone 恢复运行环境。

## Core Workflow

```text
Sources
   ↓
00_Inbox
   ↓
Inbox Classification (inbox_processor.py)
   ↓
10_Sources / 20_Wiki / 30_Projects
   ↓
Review (draft → reviewed → stable, 人工确认)
   ↓
Index (update_index.py → main_vector_db)
   ↓
Retrieval → Evidence → LLM Judge
   ↓
Answer / Knowledge Gap
   ↓
Weekly Review / Governance
```

## Architecture

```text
20_Wiki + 30_Projects ──update_index.py──▶ main_vector_db（生产索引，本地 JSONL）
用户查询 ──hybrid_query / knowledge_service──▶ wiki-first → RAW fallback → Reranker
          → Evidence Window → DeepSeek Judge → Answer / Gap
外部项目 ──Codex ──MCP knowledge_search──▶ Knowledge OS（cwd 独立）
Control Center（127.0.0.1:8765）── 统一治理/操作界面
Bootstrap（bootstrap.ps1 + helper）── 跨机恢复运行环境
```

## Key Capabilities

### Knowledge Lifecycle
`00_Inbox` 收集原始资料；`inbox_processor.py` 只读分析给出分类建议；`wiki_compile.py` 只生成 `draft`；
`wiki_review.py` / Control Center 完成 `draft → reviewed → stable`（人工确认，AI 不自动升级）。

### Evidence-Grounded RAG
- 混合检索：Dense（bge-small-zh-v1.5）+ BM25 融合，权重 0.6/0.4。
- Reranker：bge-reranker-v2-m3（模型路径 machine-local，经 config.local.yaml 覆盖）。
- Evidence Window：整 chunk 邻接扩展，不句中硬切（Gate 0 专项验证无截断）。
- LLM Judge：DeepSeek relevance judge，fail-closed（不可用 → knowledge_missing，绝不编造）。
- 回答：deep 模式生成；fast / evidence_only 只返回结构化证据。

### Knowledge Gaps
证据不足 → 记录到 `knowledge_gaps.yaml`（knowledge_missing / insufficient / conflict / retrieval_problem / answer_quality_problem），
Control Center 展示，人工 resolve。不自动用外部知识补全。

### Control Center
统一治理与操作界面（127.0.0.1:8765）：Dashboard / AI 待办 / Wiki Review / Knowledge Gaps / Sources /
Activity / Weekly Review / Project Status / System Health / Retrieval Trace / RAG Evaluation / 使用指南。
启动：`90_System/control_center/start_control_center.bat`。

### Weekly Review & Governance
每周自动生成复盘（snapshot + weekly-review.md + insight.json），由 Windows 计划任务调度
（Review Preflight 每 30 分钟 / Weekly Review 周五 18:00 / UpdateChangelog 每日 23:00）。

### MCP / Codex
外部项目可通过 Codex MCP（`knowledge-os` / `knowledge_search`，mode: fast/deep/evidence_only）查询 Knowledge OS；
vault 路径由 `KNOWLEDGE_OS_VAULT` 解析，**不依赖当前工作目录**（cwd≠Vault 已验证）。

### AI Runtime
```text
Codex ← CC Switch ← DeepSeek（deepseek-v4-flash / pro）
       └── knowledge-os MCP（approval=approve，自动化不取消）
```
CC Switch 管理 provider；DeepSeek 原生 Responses API（wire_api=responses，无需协议路由）；
本地代理按需启用（127.0.0.1:15721）。**Bootstrap 自动安装 Codex；CC Switch 缺失时需用户提供官方安装器。**

### Bootstrap
`90_System/scripts/bootstrap.ps1` 一键恢复：Python venv → 依赖（requirements-lock）→ 模型 → Reranker →
RAG 索引 → Codex 配置 → DeepSeek/MCP → Scheduler → Control Center → Health Check → Baseline Verification。
幂等（重复执行为 VERIFY/REPAIR）；`-CheckOnly` 只读审计。

## Quick Start

```powershell
git clone https://github.com/terrooo-xx/knowledge-os.git
cd knowledge-os
powershell -ExecutionPolicy Bypass -File 90_System/scripts/bootstrap.ps1
```

## New Machine Setup

Bootstrap 前**必须预装**：Windows 10/11、PowerShell 5.1+、Git、GitHub 认证、Python 3.14.x。
**用户提供**：DeepSeek API Key（CC Switch 缺失时还需其官方安装器）。
**Bootstrap 自动**：venv / 依赖 / 模型 / Reranker / RAG 索引 / Codex（npm）/ MCP / approval / Scheduler / Control Center。
完整矩阵见 [`90_System/system_profile.md`](90_System/system_profile.md)（第 16 章）。

## Project Structure

```text
00_Inbox/     Raw intake（私人资料 gitignored）
10_Sources/   Source materials / evidence
20_Wiki/      Curated knowledge（frontmatter status）
30_Projects/  Project context（六类文档）
40_Outputs/   Reviews, reports, audit evidence
90_System/    Knowledge OS runtime & governance
  ├─ KNOWLEDGE_OS.md        架构宪法（应是什么）
  ├─ system_profile.md      当前系统快照（现在是什么）
  ├─ rag/                   RAG 引擎 + 评测 + 测试
  ├─ control_center/        治理/操作界面
  └─ scripts/               bootstrap / 工具
.agents/skills/             AI 可复用工作流（4 个 Skill）
```

## Verification

- 测试：`412/412 passed`（pytest）。
- RAG Baseline：`bl-eval-20260817T162956`（当前验证基线，coverage 89.3%，STABLE；Regression 以 REAL_REGRESSION=0 为门禁）。
- Health Check：`rag_health_check.py` / `wiki_health_check.py` / `knowledge_os_check.ps1`。
- Bootstrap：`bootstrap.ps1 -CheckOnly` → BOOTSTRAP READY。
- MCP E2E：`knowledge_search` answerable / judge relevant（cwd≠Vault）。

> 数字为当前验证状态，不构成准确率保证。

## Configuration

- `90_System/rag/config.yaml`：RAG 配置（可移植默认）。
- `90_System/rag/config.local.yaml`（gitignored）：machine-local 覆盖（Bootstrap 生成）。
- 环境变量：`DEEPSEEK_API_KEY`（machine-local，绝不进 Git）。
- `~/.codex/knowledge.config.toml`：MCP profile（machine-local）。

## Documentation

- `AGENTS.md`：AI 操作规则（上下文加载 / 权限 / 验证 / Git 治理）。
- [`90_System/KNOWLEDGE_OS.md`](90_System/KNOWLEDGE_OS.md)：架构宪法。
- [`90_System/system_profile.md`](90_System/system_profile.md)：当前系统全貌（版本绑定，`system_profile_generator.py --check` 验证新鲜度）。
- `90_System/rag/README.md`：RAG 引擎说明。
- `40_Outputs/reviews/`：Gate 0~3 / Bootstrap / 治理报告。

## Current Status

- Core runtime：validated（412/412，RAG Baseline STABLE）。
- Bootstrap：READY（本机验证 BOOTSTRAP READY）。
- GitHub：private repository（terrooo-xx/knowledge-os，master）。
- AI runtime：validated（Codex 0.147.0 + CC Switch 3.20.0 + DeepSeek）。
- MCP integration：validated（cwd≠Vault）。
- Phase：Phase 3 ACTIVE（Git / Baseline / Tag 治理实施中）。

## Limitations

- 需要 Python 3.14.x（Bootstrap 不自动安装 Python）。
- CC Switch 缺失时需用户提供官方安装器（不硬编码下载 URL）。
- DeepSeek API Key 需用户输入，且账户需有余额。
- Codex 经 npm 安装需 Node.js。
- 部分网络环境直连 github.com 可能异常（临时 resolve 绕行，不写入配置）。
- `raw_vector_db` 为可选检索路径，记录较少（非生产默认）。
- 私人资料（00_Inbox 个人笔记 PDF）gitignored，不进入 GitHub。
