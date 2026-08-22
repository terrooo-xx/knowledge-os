# Phase 20 Audit：Scheduler + Index Fingerprint

- 日期：2026-08-16
- 方式：只读审计（实施前）

## 1. 当前 Windows Scheduler
- 任务名：`Knowledge OS Review Preflight`（由 register_review_preflight_task.ps1 注册）
- 命令：`pythonw.exe review_preflight_cli.py --once --trigger scheduled`（WorkingDirectory=VaultRoot）
- 周期：config.yaml `review_preflight.schedule_minutes`（默认 30 分钟），Once + RepetitionInterval
- Settings：MultipleInstances=IgnoreNew、ExecutionTimeLimit=10min、StartWhenAvailable
- 实时任务查询在沙箱内 Access Denied（需管理员）；注册脚本内容已审计
- 注：Task Scheduler 环境无 DEEPSEEK_API_KEY（既有已验收行为：LLM 不可用则优雅降级）

## 2. Review Preflight
- `review_preflight_cli.py --once`：单次有界 pass（max_per_run），LLM Judge + cache + classification
- 职责：Wiki Review / Knowledge Gap 候选的自动 LLM Judge 预处理；不改 Wiki、不自动 approve
- 与 Evaluation/Governance 无连接

## 3. Evaluation Governance（Phase 19）
- `evaluation_governance.py --verify`：required/failed 时跑 Benchmark + Baseline Check
- 状态文件 evaluation_state.json；无并发锁；无 exit code 约定（0/1 仅 ok/not ok）
- 无 Index 变化自动检测（依赖 sync_kb 手动触发）

## 4. 当前 Index Change Detection
- `sync_kb`：manifest key 集合前后对比 + update_index "changed" 输出 → 变化后手动标记 required
- 依赖先执行 sync；Governance 本身不检测索引

## 5. 当前 Index Manifest
- `database/index_manifest.json`：{rel_path: {hash: sha256(file bytes), chunks, indexed_at}}
- hash 为内容哈希（非 mtime）——天然支持"mtime 触碰不触发"

## 6. 可复用机制
- `indexing.file_hash`（sha256 bytes）——指纹算法
- manifest.json——内容指纹载体
- `evaluation_governance.py`（状态机 + verify）
- `review_preflight_cli.py` / 注册脚本（现有 Scheduler 入口）
- activity_log、CC、weekly

## 7. 缺失连接
- Governance --verify 不检测 Index 变化（无自动发现）
- 无并发保护（两进程可同时跑 Benchmark）
- 无 exit code 约定（Scheduler 无法识别 failed/regressed）
- Review Preflight 不调用 Governance
- CC 顶栏无 Governance 状态；Weekly 无 Auto Verify 指示

## 8. Scheduler 接入位置
- 在现有 `review_preflight_cli.py` 增加 `--governance`：preflight 完成后调用 `evaluation_governance.py --verify`
- 注册脚本参数追加 `--governance`；不新建第二个 Scheduler

## 9. Fingerprint 最小设计
- `index_fingerprint.py`：对 20_Wiki + 30_Projects 的 .md 计算 sha256 内容指纹，与 manifest hash 对比
- 变化（added/modified/deleted）→ 标记 evaluation_required(index_updated)
- mtime-only / 非索引文件 → 不触发

## 10. 并发与失败策略
- 跨进程文件锁（O_EXCL + 30 分钟过期接管）→ 同一时间只跑一个 Benchmark
- Evaluation Failed → 状态 failed + required 保留 + baseline 不变 → 下次重试
- 无变化 → 立即退出（exit 0），不跑 Benchmark/Judge/Reranker

## 11. 最小修改文件
- 新增：`rag_engine/index_fingerprint.py`、`tests/test_index_fingerprint.py`
- 修改：`scripts/evaluation_governance.py`（指纹检测+锁+exit code）、`review_preflight_cli.py`（--governance）、
  `register_review_preflight_task.ps1`（--governance）、`service.py`（cc_status 治理）、`index.html`（顶栏）、
  `metrics.py`/`weekly_review.py`（Auto Verify）、`tests/test_evaluation_governance.py`

## 12. 风险
- 指纹基于文件内容 hash：语义不变但格式变化（如换行）会触发 required（保守，可接受）
- Task Scheduler 实时任务需管理员权限才能注册；本阶段更新注册脚本，用户需管理员重跑一次
- API key 仅在环境变量，不进任务参数/日志
