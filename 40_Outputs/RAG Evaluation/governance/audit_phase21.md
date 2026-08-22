# Phase 21 Audit：Git P1 Source Acquisition + Governance 闭环

- 日期：2026-08-16
- 方式：真实执行（Scheduler 只读确认 + Source 获取 + Wiki Draft + Reindex + Governance Benchmark + Baseline Check）
- 结论：**Phase 20 = COMPLETE**；Git P1 已闭环；Baseline 82.1% STABLE → **89.3% IMPROVED**

---

## 1. Windows Scheduler 实时状态（只读，真实注册结果）

- 任务名：`Knowledge OS Review Preflight`（Folder: `\`，Host: LAPTOP-38EP70CA）
- 状态：`Ready` / `Enabled`
- **实际 Action**：
  `C:\Python314\pythonw.exe "D:\KnowledgeBase\Obsidian Vault\90_System\control_center\review_preflight_cli.py" --once --trigger scheduled --governance`
- 工作目录：`D:\KnowledgeBase\Obsidian Vault`
- 运行账户：陶权煜（Interactive only）
- Last Run：2026/8/16 13:29:52（Result=0）；Next Run：13:59:52（每 30 分钟）
- **Governance 参数：YES**（`--governance` 已加载）

## 2. Governance Auto Verify 实际状态

- 真实执行 `review_preflight_cli.py --once --trigger scheduled --governance --limit 2` → exit 0
- Activity Log 证据：
  - `governance_verify running`（reasons=['index_updated']）→ `improved`（delta=+7.2pp，run=eval-20260816T135103）
  - `governance_skip`（index_change=false）多次：Scheduler 每 30 分钟无变化自动跳过
- 当前 state：`improved`；required=False；last_check=IMPROVED

## 3. 无变化场景验证

- Index fingerprint changed = **false**（无新增/修改/删除）
- Evaluation Required = **NO**；无新增 Evaluation Run；无新增 Judge/Reranker 调用
- 本次 Phase 21 实测：Scheduler 在 13:53 / 13:54 两次 `governance_skip`（index_change=false）

## 4. Git P1 Gap（gap_git_config）

- 失败 Query：`q_git_config = "Obsidian 的 Git 怎么配置？"`（RAW_JUDGE_REJECTED / wiki_fallback / evidence_gap）
- 当前 Wiki（改进前）：Git基础配置.md（822 字，coverage=partial）
  - 覆盖：user.name/user.email、.git 识别
  - 不覆盖：Obsidian 仓库同步流程（插件/远程/自动 commit-push）
- 知识边界判断：Query 实际涉及 **Obsidian-Git**，不是完整 Git 教程 → 只补 Obsidian-Git 配置流程，不扩展巨型教程

## 5. Git Source 状态（真实）

| 来源 | 类型 | 本地文件 | 状态 |
|---|---|---|---|
| Obsidian-Git Getting Started（官方插件文档，raw markdown） | trusted_tutorial | 10_Sources/工具链/Obsidian-Git_GettingStarted.md（8,242 B） | acquired |
| Obsidian-Git README（官方仓库） | trusted_tutorial | 10_Sources/工具链/Obsidian-Git_README.md（7,752 B） | acquired |
| Git 配置.note.pdf（个人笔记，薄来源） | trusted_tutorial | 00_Inbox/…/Git 配置.note.pdf（245 字） | acquired |

- `verified = false`（未人工核验，不标 verified）
- P0/P1 Source Missing = **0**（src_git_config 已 acquired）
- 注：GettingStarted 页面为 JS 渲染，已通过 Obsidian Publish 的 raw markdown 访问端点获取原文（非伪造 URL）

## 6. Git Knowledge Requirements（wt_git_config）

- git_req_1 user.name/user.email 身份配置 → covered（薄 PDF）
- git_req_2 识别仓库（.git 文件夹）→ covered（薄 PDF）
- git_req_3 Obsidian-Git 插件安装与启用 → covered（Getting Started）
- git_req_4 仓库初始化与远程配置（Initialize new repo / Push origin / Clone / Edit remotes）→ covered（Getting Started）
- git_req_5 自动 commit-and-sync（定时同步、启动自动 pull）→ covered（README）
- git_req_6 认证（桌面 HTTPS/SSH；GitHub PAT 最小权限）→ covered（Getting Started + README）
- missing_knowledge = **[]**；likely_recoverable = true（不再硬编码 false）

## 7. P2 Gap 排序（3 个 open，均 source_available=False / candidate）

1. **gap_px4_ekf**（P2 #1）：knowledge_gap（无证据）；官方 PX4 EKF2 调参文档公开可获取、直接命中；获取成本低
2. **gap_ros2_nav2**（P2 #2）：evidence_gap（0.8058 被拒）；官方 Nav2 costmap 配置文档公开可获取；获取成本低
3. **gap_stm32_low_power**（P2 #3）：judge_gap（0.6171 被拒）；AN4621 为 L4 系列应用笔记、PDF 获取成本中等、与通用查询边界略有错位

排序依据：同 query_count=1 → 可靠 Source 可获取性 + 获取成本 + 边界清晰度；不做复杂总分。

## 8. Golden Set 当前覆盖（人工标注，无虚假标注）

- 6 条：q_freertos_scheduler、q_stm32_usart、q_freertos_stack_overflow、q_stm32_low_power、q_px4_ekf、q_drone_power
- answer_correct 已评估 2/2（均 true）；evidence_supported 3/6；其余 answer_correct=null（未人工判断）
- 建议扩至 8~10：+ q_git_config（Git P1，已恢复）、+ q_wsl_ubuntu 或 q_freertos_stack_overflow（已恢复）、+ 一个 evidence-insufficient、+ 一个 wiki-first
- **必须人工标注**（answerable / answer_correct / evidence_supported / expected_source / acceptable_paths）；未人工判断保持 null；本阶段未自动填写

## 9. 最小下一步实施范围

- Git P1 已在本阶段闭环（Source → Wiki Draft → Reindex → Governance Benchmark → Baseline Check）
- 下一步（非本阶段）：P2 #1 gap_px4_ekf 走同一流程；Golden Set 人工扩标注

---

# Phase 21 验证结果（Git Source / Wiki 改进后）

## Reindex
- Before 36 chunks → After **45 chunks**（Git基础配置.md 扩充后重新索引；manifest rebuilt）

## Benchmark
- run：`eval-20260816T135103`（28 queries，mode=fast，real LLM judge）
- Coverage：82.1%（23/28）→ **89.3%（25/28）**（+7.2pp）

## Query-level Diff（eval-20260816T000233 → eval-20260816T135103）
- **Recovered：2** → `q_git_config`（wiki_first，conf=0.9842，judge passed）、`q_drone_power`（wiki_first，judge passed，原 JUDGE_VARIANCE 案例现稳定回答）
- Regressed：0；New failures：0；REAL_REGRESSION：0；JUDGE_VARIANCE：0
- Query Recovery Rate：40%（2/5 此前失败）

## Governance 自动触发与 Baseline Check
- 指纹检测：index_modified=1（Git基础配置.md）→ mark_required(index_updated)
- `evaluation_governance.py --verify`：自动跑 Benchmark → regression_check → **IMPROVED**
- Baseline 重建：`bl-eval-20260816T135103`（89.3%，IMPROVED）
- 说明：首次沙箱内 verify 因网络受限全部 fail-closed（0.0%）→ Governance 正确判 REGRESSED 且**未覆盖基线**；在真实网络环境重跑后 IMPROVED 并重建基线（基线保护机制真实生效）

## Control Center / Weekly Review（读取同源数据，已确认）
- RAG Evaluation：coverage 89.3%、Governance improved、Evaluation Required NO
- Knowledge Gaps：open=3（全 P2）、resolved=4；open P0/P1 = **0**
- Source Acquisition：P0/P1 missing=0；git=acquired（verified=false）
- Weekly：diff recovered=2 / regressed=0；baseline IMPROVED

## Regression
- **359/359** 全部通过（355 既有 + 4 新增 test_source_acquisition_git.py；2 个真实状态测试随 Phase 21 已验证结果更新）

## 验收对照
- ✅ 实际 Task Scheduler 已带 --governance
- ✅ Review Preflight 真正调用 Governance
- ✅ 无知识变化时不跑 Benchmark（governance_skip 实测）
- ✅ Baseline 由 82.1% STABLE 提升为 89.3% IMPROVED（Git P1 恢复，符合治理预期）
- ✅ Git P1 准确诊断 + Source 状态真实（acquired，verified=false）
- ✅ P2 明确优先级
- ✅ Golden Set 无虚假标注（本阶段未自动填写）
- ✅ 未修改 RAG 算法（retrieval/reranker/judge/threshold/chunking/evidence_window/fail-closed 均未动）

## 新增 / 修改文件
- 新增：10_Sources/工具链/Obsidian-Git_GettingStarted.md、Obsidian-Git_README.md（上一阶段已下载，本阶段登记）
- 新增：90_System/rag/tests/test_source_acquisition_git.py
- 修改：90_System/rag/evaluation/source_acquisition.yaml（src_git_config → acquired + related_sources）
- 修改：90_System/rag/scripts/wiki_compile_gaps.py（wt_git_config 需求补齐 + 移除 source-limited 硬编码）
- 修改：90_System/rag/evaluation/wiki_compilation.yaml（重新生成 + after 回填）
- 修改：20_Wiki/01_计算机基础/Git基础配置.md（扩充 Obsidian-Git 配置流程，draft + review_required）
- 修改：40_Outputs/RAG Evaluation/*（evaluation_state.json、baseline.json、latest.json、latest_diff.json、runs/、diff/）
- 修改：90_System/rag/evaluation/gaps.yaml（gap_git_config → resolved，evaluation_diff 自动）
- 修改：90_System/rag/tests/test_query_coverage_matrix.py、test_evaluation_baseline.py、test_wiki_benchmark_validation.py（随已验证结果更新）

## 待人工确认
- Git基础配置.md 保持 draft + review_required，**未自动 approve**
- Git Source verified=false（人工核验后再标 verified）
- Golden Set 扩标注（8~10 条）需人工判断
- P2（px4_ekf / ros2_nav2 / stm32_low_power）下一轮按同一流程处理
