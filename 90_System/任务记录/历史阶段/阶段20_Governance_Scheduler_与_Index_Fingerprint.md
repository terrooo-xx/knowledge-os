# Phase 20：Governance Scheduler + Index Fingerprint 实施报告

- 日期：2026-08-16
- 范围：把 Phase 19 Governance 接入现有 Windows 定时任务 / Review Preflight，并增强 Index 变化检测（内容指纹）
- 原则：不创建第二个 Scheduler；不改 RAG；无知识变化绝不跑 Benchmark；API key 不进任务参数/日志

## 1. Scheduler 审计
- 复用现有 `Knowledge OS Review Preflight` 定时任务（register_review_preflight_task.ps1，默认 30 分钟，
  pythonw + review_preflight_cli.py --once --trigger scheduled，MultipleInstances=IgnoreNew）
- 实时任务查询在沙箱 Access Denied；注册脚本内容已审计（任务配置以注册脚本为准）

## 2. Review Preflight
- 职责：Wiki Review / Knowledge Gap 候选的自动 LLM Judge 预处理（不改 Wiki、不自动 approve）
- 本次在 preflight 完成后追加 Evaluation Governance（--governance）

## 3. Scheduler 接入
- `review_preflight_cli.py --governance`：preflight 完成后运行 `evaluation_governance.py --verify --json`，
  打印 Governance 状态与 exit_code；不阻断 preflight 结果
- `register_review_preflight_task.ps1` 参数追加 `--governance`（用户以管理员重跑一次即生效）
- 仍是一个治理 Scheduler（未新建第二个）

## 4. Evaluation Required
- Wiki approve / Index 内容变化（指纹）/ source 更新 / manual → required（批量合并）
- Scheduler 每次运行先检测 Index 指纹：真实变化才置 required；mtime-only / 非索引文件不触发

## 5. Index Fingerprint
- 新增 `rag_engine/index_fingerprint.py`：20_Wiki + 30_Projects 的 .md 内容 sha256 与 manifest hash 对比
- 检测 added/modified/deleted → 标记 evaluation_required(index_updated)
- 复用 `indexing.file_hash`（内容哈希，非 mtime）

## 6. 批量聚合
- 多次 approve / 多次索引变化 → 同一 required 状态（reasons 聚合、batch 计数），一次 Benchmark

## 7. 并发保护
- 跨进程文件锁 `.governance.lock`（O_EXCL 创建 + 30 分钟过期接管）
- 第二个 verify → already_running / skipped（exit 0），不重复跑 Benchmark

## 8. Failure / Retry
- Evaluation Failed → status=failed + required 保留 + baseline 不变 → 下次 Scheduler 重试
- exit codes：0=正常/无需执行/Stable/Improved；1=Regression；2=Evaluation Failed
- JUDGE_VARIANCE 不产生 Regression exit code

## 9. Control Center
- 顶栏 statusbar 显示治理状态（passed/required/regressed/failed + ⚠ 待验证）
- `/api/status` 返回 governance；RAG Evaluation 视图 Governance 卡不变

## 10. Weekly Review（8.6）
- Governance：passed　Auto Verify：ON　Evaluation Required：NO（无）　Last Check：STABLE
- 待验证时：⚠ Scheduler/Preflight 将自动运行 Benchmark + Baseline Check

## 11. Activity Log
- 新增 `governance_index_fingerprint`（Index 内容变化 → required）事件
- 原有 governance_verify / governance_finalize 事件保留，全链路可追溯

## 12. 测试结果
- 新增 test_index_fingerprint.py（6）：内容哈希、mtime-only 不触发、非索引文件忽略、added/modified/deleted、digest 稳定
- test_evaluation_governance.py +4：exit codes、指纹→required、并发锁、真实 Scenario A（--verify 无变化 no-op）
- 全量回归：**355/355 通过**（346 既有 + 9 新增）

## 13. Scenario A-F 真实验证
- A 无变化：`--verify`（含真实 index）→ skipped、无新 run、exit 0 ✅（真实执行）
- B 批准 Wiki：execute_action → required（测试模拟）✅
- C Index 变化：内容指纹 modified → required（测试）✅
- D 无语义变化：mtime 触碰 → 指纹不变、不触发（测试）✅
- E Evaluation Failure：benchmark 失败 → failed + required 保留 + baseline 不变（测试）✅
- F Concurrent：锁占用 → already_running，只跑一次（测试）✅
- 真实 Scheduler 入口：`review_preflight_cli.py --once --trigger scheduled --governance --limit 2`
  → preflight + governance（index_change.changed=false，skipped，exit 0）✅（真实执行）

## 14. 性能 / 调度影响
- 每次调度运行：preflight（有界）+ 指纹检测（读 ~35 个 .md 计算 sha256，毫秒级）+ 无变化立即退出
- 只有 required 时才跑完整 Benchmark（28 条，约 1-2 分钟）
- 指纹检测不 embedding、不重排、不调 Judge

## 15. 当前限制
- 实时 Windows 任务需管理员权限才能注册；本阶段更新注册脚本，需用户以管理员重跑一次 `register_review_preflight_task.ps1`
- 指纹为内容 hash：纯格式/换行变化也会触发 required（保守）
- Task Scheduler 环境无 DEEPSEEK_API_KEY：若触发真实 Benchmark，Judge/Answer 会优雅失败并保留 required 供下次重试（既有行为）

## 16. 下一阶段建议
- 用户以管理员重跑 `register_review_preflight_task.ps1` 使 `--governance` 生效
- 将 governance required 状态加入 CC dashboard 顶栏的持久提醒（已加入 statusbar）
- 考虑把指纹 digest 写入 evaluation_state 用于审计（本次记录 reasons 已够）

---

## 最终数字

```
Windows Scheduler 复用：YES（现有 Review Preflight 任务）
Review Preflight 集成：YES（--governance 追加调用）
Auto Verify：YES（Scheduler 每次运行自动 --verify）
Index Fingerprint：YES（内容 sha256 vs manifest，mtime 不触发）
Batch Aggregation：YES
Concurrent Protection：YES（文件锁 + already_running）
Failure Retry：YES（failed 保留 required，下次重试）
Topbar Governance：PASS
Weekly Review：PASS（Auto Verify 指示）
Activity Log：PASS（含 governance_index_fingerprint 事件）
Existing Regression：355/355（346 既有 + 9 新增）
Baseline：82.1%（bl-eval-20260816T000233）
Final Governance Status：STABLE
```
