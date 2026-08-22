# Phase 21：Git P1 Source Acquisition + Governance 闭环（Baseline 89.3% IMPROVED）

- 日期：2026-08-16
- 类型：知识治理（真实 Source → Wiki → Review → Benchmark → Baseline 闭环）
- 关联：Phase 20（Scheduler + Governance）完成确认

## 一、目标

1. 只读确认真实 Windows Task Scheduler 已加载 `--governance`（Phase 20 最终闭环）
2. 处理 `gap_git_config` P1 source-limited：Source Acquisition → Wiki Draft → Reindex → Governance Benchmark → Baseline Check
3. 审计剩余 P2 Knowledge Gap 排序与 Golden Set 覆盖

## 二、Part A：Scheduler / Governance 确认（COMPLETE）

- 实际 Action 含 `--governance`（`review_preflight_cli.py --once --trigger scheduled --governance`）
- 真实执行 Preflight + Governance exit 0；无变化 → `governance_skip`（index_change=false）
- 未新增 Evaluation Run；Baseline 当时仍 82.1% STABLE

## 三、Part B：Git P1 闭环

### Source Acquisition
- 获取官方 Obsidian-Git Getting Started 原文（raw markdown，8,242 B）+ 官方仓库 README（7,752 B）
- source_acquisition.yaml：`src_git_config` → acquired（verified=false）；P0/P1 Source Missing = 0

### Wiki（draft + review_required，未 approve）
- Git基础配置.md 扩充：插件安装 / Initialize new repo / Push origin / Clone（.git URL）/ Edit remotes / Commit-and-sync / 认证（PAT 最小权限）
- 边界：只覆盖 Obsidian-Git 配置流程，不扩展完整 Git 教程

### Reindex
- 36 → 45 chunks；index_manifest 重建

### Governance Benchmark（真实 DeepSeek Judge）
- run：`eval-20260816T135103`；Coverage 82.1% → **89.3%（25/28）**
- Recovered：`q_git_config`、`q_drone_power`；Regressed：0；REAL_REGRESSION：0
- Baseline Check：**IMPROVED** → 基线重建 `bl-eval-20260816T135103`
- 基线保护实测：沙箱内网络受限导致 0.0% fail-closed 运行被正确判 REGRESSED 且未覆盖基线

## 四、P2 排序（下一轮）

1. gap_px4_ekf（官方 PX4 文档，公开易取，knowledge_gap）
2. gap_ros2_nav2（官方 Nav2 文档，公开易取，evidence_gap）
3. gap_stm32_low_power（AN4621 L4 专用，PDF 获取成本中等）

## 五、Golden Set

- 当前 6 条；建议扩至 8~10（+Git P1 已恢复、+已恢复 Query、+evidence-insufficient、+wiki-first）
- 必须人工标注，本阶段未自动填写

## 六、Regression

- 359/359 通过（新增 test_source_acquisition_git.py 4 条；真实状态测试随验证结果更新）

## 七、验收

- ✅ Phase 20 = COMPLETE（Scheduler 实际带 --governance、无变化跳过、无新 run）
- ✅ Git P1 闭环：Source acquired → Wiki draft → Reindex → Benchmark IMPROVED → Baseline 重建
- ✅ q_git_config RECOVERED；无回归；未修改 RAG 算法
- ✅ Control Center / Weekly Review 数据同源正确（open P0/P1=0，git source acquired）

## 八、待人工

- Git基础配置.md review（draft → reviewed/stable）
- Git Source verified 核验
- Golden Set 扩标注
- P2 三缺口按同一流程处理

## 九、学习记录

- 沙箱内无法访问 LLM API：生产 Benchmark/Governance 验证必须在有网络权限的环境执行；沙箱运行会 fail-closed 产生 0.0% 伪回归（Governance 正确拒绝覆盖基线，但仍应避免）
- wiki_compile_gaps.py 重新生成会丢弃 coverage_matrix 的 after 回填；重新生成后需用最新 diff 重新 annotate
- 运行 test_cli_verify_noop_real 这类"真实状态"测试前，须确保无未验证的知识变化（否则会意外触发真实 Benchmark）
