# Knowledge OS Global Health Audit

## 1. Executive Summary

- Audit Date: 2026-08-22
- Vault: D:\KnowledgeBase\Obsidian Vault
- Current Commit: 86b25ae02bec3a0075d9460e06d91a7b4c3a16ff（[Wiki] docs: 新增与审核 Wiki）
- Current Tag: baseline/rc-codex-wecom-20260820（指向 242f619，用于 Remote Codex + 企业微信 系统基线）
- RAG Evaluation Baseline: bl-eval-20260817T162956（coverage 89.3%，STABLE；本次复测 eval-20260822T180123 = 89.3%，delta 0.0pp）
- 审计方式：只读优先；关键功能全部真实运行验证（pytest 回归、28 查询 Benchmark 重跑、RAG 真实查询、MCP 真实握手+调用、Codex 外部项目调用、Control Center API、任务计划核对、安全扫描）

Overall: **READY FOR GITHUB AUDIT（BLOCKER = 0）**

注意：审计提示词中“正式 Baseline = bl-eval-20260816T000233 / Coverage 82.1% / Regression 355/355”为**过期预期**。
当前官方 Baseline 已在 Phase 18 之后演进为 bl-eval-20260817T162956（89.3%），测试数为 412（Phase 22D 记录）。
本次以“当前真实状态”为准复测，并如实记录与提示词预期的差异。

## 2. Health Matrix

| Domain | Status | Evidence | Notes |
|---|---|---|---|
| Vault Architecture | PASS | knowledge_os_check.ps1：PASS=96 WARNING=3 ERROR=0；7 个核心目录齐全 | 未登记一级目录 .pytest_cache（WARNING）；.claudian 已 gitignore |
| Inbox | PASS | inbox_processor.py 真实运行：35 个文件分类（no_new_wiki/create_wiki/project_update/keep_raw） | 处理日志为运行副产物，已恢复原状 |
| Source | PASS | 10_Sources 8 个领域子目录；source_acquisition 注册表 8 条 | 3 个 PDF/HTML 未跟踪（待决定是否入库） |
| Wiki | PASS | 25 篇（stable 3 / reviewed 13 / draft 9）；wiki_health_check 25/25 PASS | frontmatter 全部合法 |
| Wiki Review | PASS | wiki_review.py --list 正常；approve/reject/resolve 写路径由单元测试真实文件写入验证；live HTTP reject 验证通过 | live approve 未执行（避免改动用户 Wiki 状态），写路径已由 test_approve_is_idempotent 等证明 |
| Index | PASS | rag_health_check 8 PASS 0 ERROR；index fingerprint 无变化（34 docs）；main_vector_db 45 chunks | 最后 sync 2026-08-13，之后无知识变更 |
| RAG | PASS | 真实查询：wiki-first gate 通过、judge relevant、evidence sufficient、answer 生成正常 | 无依据问题正确进入 gap，无编造 |
| Evidence | PASS | Evidence Window 为整 chunk 扩展（前后邻接），未发现句中硬切/残缺 | 尾部“资料来源”列表跨 chunk 边界有一处小瑕疵（WARNING） |
| LLM Judge | PASS | DeepSeek judge 真实调用：relevant + confidence 0.95 | 离线时 fail-closed 返回 irrelevant（设计正确） |
| Knowledge Gaps | PASS | 6 条（5 pending / 1 resolved）；无依据查询 → gap pending；resolve 路径测试通过 | 5 条 pending 对应已知 P2 缺口 |
| Control Center | PASS | 全新实例：/api/health 三项 OK；全部 GET API 200；live POST reject 写库成功；UI 12 个视图齐全 | 原 16:15 实例为旧代码（architecture=False），已替换 |
| Weekly Review | PASS | W34 快照+报告+insight 真实存在；dashboard period=W34、历史=[W34,W33]、trend 正常 | 见 W34 snapshot system_errors=1（瞬时）WARNING |
| Scheduler | PASS | Review Preflight（每 30 分钟，Ready，最近运行 OK）；Weekly Review（周五 18:00，Ready，最近运行 OK） | UpdateChangelog 最近一次 result=1（瞬时失败，手动运行 OK）WARNING |
| MCP | PASS | 真实启动：initialize → tools/list → knowledge_search(fast) → answerable/judge relevant；vault 由 env 解析不依赖 cwd | |
| Codex Integration | PASS | 从 C:\Temp\DroneTest（非 Vault）用 knowledge profile 真实调用 knowledge_search 成功 | 默认 approval 策略下自动取消，需配置 default_tools_approval_mode=approve（WARNING） |
| Git | PASS | HEAD 明确、working tree 与审计前一致（仅 7 项未跟踪）、无远程 | 未 commit / push |
| Governance | PASS | evaluation_state status=passed；index fingerprint 无变化；Baseline STABLE | |
| Baseline | PASS | RAG Baseline 完整复测：89.3% vs 89.3%，delta 0.0pp，STABLE；4/4 核心恢复查询保持 | rc-codex 基线外部 hash 5/8 MATCH、3 DRIFT（见 Findings） |
| Skills | PASS | project-finalization SKILL.md 具备触发条件/双模式流程/验收/异常处理/Git-Baseline-Tag 规则 | |
| Security | PASS | 301 个跟踪文件扫描 15 个命中均为误报；无 .env/secret 文件 | DEEPSEEK_API_KEY 仅存在于 Windows 用户环境，不进 Vault |
| End-to-End Flow | PASS | Inbox→分类→Source→Wiki→Review→RAG→Evidence→Gap→Control Center→Weekly Review→MCP 逐段真实验证 | |

## 3. Baseline Comparison

Expected（提示词，已过期）:
- 355/355（测试回归，实际为 Phase 22D 的 412）
- 82.1%（bl-eval-20260816T000233，Phase 18 基线）
- STABLE

Actual（本次真实复测）:
- 测试回归：412 收集，**408 通过 / 4 失败**（4 项为 weekly-review 测试硬编码 2026-W33，实际数据已到 W34，属测试数据过期，非功能回归）
- RAG Benchmark 重跑：eval-20260822T180123，coverage **89.3%**（25/28），system_error=0
- Baseline Check：current=89.3% vs baseline=89.3%，delta=0.0pp，**STABLE**；4/4 核心恢复查询（FreeRTOS 栈溢出/任务通知/STM32 PWM/WSL）全部 answered

Difference:
- 覆盖率为 89.3%（较提示词 82.1% 提升 7.2pp，因为 Phase 18 后 4 个 Source-backed Wiki 获批并恢复查询）
- 测试数为 412（较提示词 355 增加，因为 Phase 19~22 新增了 Evaluation/Governance/Control Center 测试）

Status: STABLE（无回归；4 项失败为测试日期数据过期，需更新断言）

## 4. Blockers

- 无（BLOCKER = 0）

## 5. Warnings

1. **[测试维护] pytest 4 失败**：test_weekly_review_dashboard.py（3）+ test_weekly_review_trends.py（1）硬编码“2026-W33 为最新周期”。实际 W34 快照已于 2026-08-22 生成，dashboard 正确返回 W34。需把断言从 W33 更新为 W34（更新测试数据，不是放宽标准）。
2. **[配置] Codex MCP 审批策略**：`~/.codex/knowledge.config.toml` 缺少 `default_tools_approval_mode = "approve"`。在 approval_policy=never 的自动化场景（codex exec / cc-connect WeCom）下，knowledge_search 工具调用会被自动取消（user cancelled MCP tool call）。已用 `-c mcp_servers.knowledge-os.default_tools_approval_mode="approve"` 实测通过。交互式使用时用户批准即可。建议加这一行。
3. **[数据] W34 快照 health=error（errors=1）**：生成时刻（16:08，与 Review Preflight 并发）架构检查瞬时失败被固化进快照；当前实时 health=0 error。Control Center 仍显示 error。建议重新生成 W34 快照或接受该瞬时记录。
4. **[测试卫生] weekly-review 测试污染运行时**：测试运行在真实 activity_log.jsonl 写入了 5 条 period=2099-W01 的运行记录（gitignored 运行时数据，不影响发布，但污染 dashboard runs 列表）。
5. **[环境] HF hub 联网重试**：hybrid_query.py / inbox_processor.py 未设置 HF_HUB_OFFLINE，离线时模型加载每个配置文件重试 5 次（约 2 分钟延迟）；mcp_server.py 已设置。建议 CLI 脚本统一设置（Bootstrap 相关）。
6. **[调度] UpdateChangelog 任务最近 result=1**：16:08:06 与 Weekly Review 并发时失败；手动运行 exit 0。建议确认是否为并发 git 冲突。
7. **[基线] rc-codex-wecom-20260820 外部 hash 3 项漂移**：codex config.toml 漂移已在基线文档记录（Codex App 重写）；workspace_bindings.json 与 start-cc-connect.ps1 与基线记录差 1-2 个字符，需人工确认是基线文档抄录错误还是文件改动（此基线明确 machine-local、不承诺跨机可复现）。
8. **[索引] raw_vector_db 仅 2 条记录**：raw 检索对多数问题返回无关结果（期望行为，wiki-first 为生产路径；raw 为可选）。
9. **[进程] 旧 Control Center 实例**：审计前有 16:15 启动的旧代码实例（架构检查返回 False），已替换为当前代码新实例（127.0.0.1:8765 运行中）。建议以后用 start_control_center.bat 统一管理，避免多实例。
10. **[文档] `.pytest_cache` 未登记**：knowledge_os_check 提示未登记一级目录，建议加入 .gitignore 或 KNOWLEDGE_OS.md 登记。
11. **[UI] weekly dashboard automation.status=unknown**：自动化状态未填充（小 UX 数据缺口）。

## 6. Findings

- 提示词基线数字过期（见 §3）。
- Evidence 专项：历史“chunk 残缺/句子切断”问题已解决——evidence_window.py 采用整 chunk 邻接扩展 + overlap 去重 + 3000 字上限整 chunk 裁剪，不句中硬切。抽样 4 组证据（wiki-first/raw/多长度）均完整；仅发现“资料来源”列表跨 chunk 边界的小瑕疵（如 `- STM32 DMA 测试资料` 被截断）。
- RAG 全链路（deep/fast/evidence_only/raw/unanswerable）均真实验证；fail-closed 在无网时按设计工作（judge=Connection error → knowledge_missing）。
- MCP 三层（server → bridge → Codex）均真实验证：bridge 使用 NDJSON↔Content-Length 适配 + HKCU 用户环境继承（恢复 DEEPSEEK_API_KEY）；直接 NDJSON 驱动调用 9.7s 完成。
- Codex 外部查询从 C:\Temp\DroneTest（非 Vault cwd）成功，证明不依赖 cwd，vault 由 KNOWLEDGE_OS_VAULT 解析。

## 7. External Runtime Dependencies

| 依赖 | 状态 | 说明 |
|---|---|---|
| Python | C:\Python314\python.exe 3.14.6 | 计划任务与 bridge 均使用该绝对路径 |
| pip 依赖 | yaml/requests/openai/sentence-transformers 等已装 | 通过 import 验证 |
| BGE 模型 | HF 本地缓存 + reranker modelscope 缓存 | 已缓存，离线可加载（需 HF_HUB_OFFLINE） |
| DeepSeek API | DEEPSEEK_API_KEY 存于 Windows 用户环境（HKCU） | bridge 从注册表恢复；Vault 不存密钥 |
| Windows 任务计划 | 3 个任务（见 §2 Scheduler） | 绝对路径均为 D:\KnowledgeBase\Obsidian Vault |
| Codex MCP | ~/.codex/knowledge.config.toml（profile: knowledge） | 指向 Documents\Codex\knowledge_os_mcp_bridge.py → 90_System\rag\interface\mcp_server.py |
| cc-connect | ~/.cc-connect + C:\cc-connect-mcp | 本机运行（Remote Codex + 企业微信），本次未深入测试 |

## 8. Evidence Truncation Verification

- 方法：真实运行 retrieval，抽查 wiki-first main / raw store 两类路径、长/短文档，检查证据窗口开头/结尾是否句子切断。
- 结果：未发现明显截断。窗口由完整 chunk 组成（合并时按真实 overlap 去重，不硬切）；结尾多为文档“资料来源”列表（自然结束），非残缺。
- 唯一瑕疵：个别文档“来源”列表跨 chunk 边界（如 STM32-DMA 配置与使用.md 的 `- STM32 DMA 测试资料`），属 chunk 边界小瑕疵，不影响内容完整性。
- 结论：**PASS（无 BLOCKER 级截断）**

## 9. End-to-End Validation

逐段真实验证：
- 资料导入：00_Inbox 35 个文件存在（待处理）
- Inbox 分类：inbox_processor.py 真实运行，35 个文件全部分类
- Source：10_Sources 目录与 source_acquisition 注册表正常
- Wiki：25 篇，状态合法
- Review：wiki_review CLI 正常；approve/reject/resolve 写路径测试通过 + live reject
- Reindex：index fingerprint 无变化（无需重建）；rag_health 8 PASS
- RAG 查询：wiki-first → gate → evidence → judge → answer 全链路真实通过
- Evidence：完整无截断
- Knowledge Gap：无依据查询正确进入 pending gap
- Control Center：API + UI 正常
- Weekly Review：W34 真实生成
- MCP：真实握手 + knowledge_search 通过
- Codex 外部：C:\Temp\DroneTest 真实调用通过（需 approval 配置）

## 10. Final Decision

```
=====================================
Knowledge OS
GLOBAL HEALTH AUDIT
GATE 0 = PASS
=====================================

READY FOR GITHUB AUDIT
```

## 建议在 Gate 1 前处理的必办项（都不影响本次 BLOCKER=0 结论）

1. 更新 4 个 weekly-review 测试的周期断言（W33 → W34），使回归套件恢复 412/412。
2. 在 `~/.codex/knowledge.config.toml` 的 `[mcp_servers.knowledge-os]` 增加 `default_tools_approval_mode = "approve"`（自动化 Codex 外部查询必需）。
3. 人工确认 rc-codex-wecom-20260820 基线中 workspace_bindings.json / start-cc-connect.ps1 两个 hash 是否为文档抄录错误。
4. （可选）重新生成 W34 weekly review 快照以清除瞬时 system_errors=1 记录。

## 任务边界遵守

- 未创建 GitHub Repository / 未 push / 未改 remote / 未开发 Bootstrap / 未重构。
- 未修改任何 Wiki/源码/配置/测试；审计产生的 inbox_processor_log 副产物已还原；未 commit。
- 测试套件按原样运行并如实记录结果，未修改测试标准。
