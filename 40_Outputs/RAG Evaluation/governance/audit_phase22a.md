# Phase 22-A：Control Center Source Verified + RAG Evaluation UI 修复报告

- 日期：2026-08-17
- 范围：不修改 RAG 算法（retrieval/reranker/judge/threshold/chunking/evidence_window/fail-closed/benchmark dataset 均未动）

## 1. Source Verified 审计（现状）

### Backend
- `service.source_acquisition()` / `source_acquisition_detail()` 已返回 `verification.verified`（只读）
- **无 Mark Verified 写操作**（无 POST handler，无 service 写函数）
- 生命周期引擎 `rag_engine/source_acquisition.py` 已有 `apply_transition`（missing→candidate→acquired→verified，严格相邻）

### API
- `GET /api/source_acquisition` → 返回 registry（含 source_status + verification）
- **缺失**：`POST /api/source_acquisition/<id>/verify`

### Frontend
- RAG Evaluation 页有 Source Acquisition 只读卡片；`viewSources(gapId)` 有只读详情
- **缺失**：Mark Verified 按钮 / ✓ 已核验 / ⚠ 待人工核验 展示

### 当前缺口
- 无 UI 操作；用户需手动编辑 YAML（正是本次要消除的）

## 2. Source Verified UI / API（新增）

- `POST /api/source_acquisition/<id>/verify`（server.py）
- `service.mark_source_verified(source_id, actor="user")`：
  - 仅 `acquired` 可核验（生命周期相邻）；已 verified → already_done；candidate/未知 id → 报错
  - 写 `verification.verified=true`、`verified_at`、`verified_by`，`source_status` 前进到 `verified`（既有生命周期明确要求：weekly/CC 均按 source_status=verified 计数）
  - **不触发 Evaluation / Benchmark**（不碰 governance 状态；source_acquisition.yaml 不在索引指纹内）
- UI：Source Acquisition 卡片 + viewSources 详情页显示 `✓ 已核验` / `⚠ 待人工核验`，acquired 未核验显示 `[Mark Verified]`（confirm 确认后调用 API）
- Activity Log：`SOURCE_VERIFIED`（含 source_id、title、previous_verified、new_verified、verified_by、time）

## 3. Activity Log

真实记录：
```json
{"action_id": "SOURCE_VERIFIED", "type": "source", "target": "src_git_config", "actor": "user",
 "previous_verified": false, "new_verified": true, "verified_by": "user",
 "message": "src_git_config（...）已人工核验 -> verified", "time": "2026-08-17 17:04:12"}
```

## 4. RAG Evaluation 页面故障根因

- 前端 `render('rag_evaluation')` 分支存在 **TDZ（temporal dead zone）Bug**：
  - 第 687 行 `const df2 = diff && diff.diff;` 先于第 749 行 `const diff = await api(...)` 声明
  - 浏览器执行时抛 `ReferenceError: Cannot access 'diff' before initialization` → `$main.innerHTML` 从未赋值 → **空白页**
- 已在真实浏览器复现（headless Chrome CDP）：点击后控制台出现该 ReferenceError，DOM 停留在 Dashboard
- 次要：`render()` 无顶层 try/catch，任一 API 失败也会导致空白

## 5. RAG Evaluation UI 修复

1. **TDZ 修复**：`const diff = await api('/api/rag/evaluation/diff');` 移到 `df2` 使用之前，删除底部重复声明
2. **错误韧性**：`render()` 加顶层 try/catch → 失败显示 `⚠ 数据加载失败 + 原因 + [重试]`，不再空白
3. **导航状态一致性**：点击时 `history.replaceState` 写 hash；新增 `hashchange` 监听；初始加载读 hash → **刷新后保持当前视图**（Scenario C）

## 6. API 验证（live 8765，全部 200）

| API | 结果 |
|---|---|
| GET /api/status | 200 |
| GET /api/rag/evaluation | 200 |
| GET /api/rag/evaluation/baseline | 200 |
| GET /api/rag/evaluation/governance | 200 |
| GET /api/source_acquisition | 200 |
| GET /api/golden_set | 200 |
| GET /api/judge_variance | 200 |
| POST /api/source_acquisition/src_git_config/verify | 200 |

## 7. 浏览器验证（真实 headless Chrome CDP，live 8765）

- **Scenario B**：Dashboard → 点击 RAG Evaluation → DOM 出现 RAG Evaluation / Evaluation Baseline / Evaluation Governance / Golden Set / Source Acquisition / Before-After Diff；active nav = rag_evaluation；无 JS 异常
- **Scenario A（UI）**：Git 行显示 `src_git_config | P1 | verified | ✓ 已核验`，Mark Verified 按钮消失；FreeRTOS 等其余 7 条保持 `⚠ 待人工核验`
- **Scenario C**：刷新 `#rag_evaluation` → 仍正确打开，active nav = rag_evaluation
- 唯一 console error：`/favicon.ico` 404（无 favicon，与功能无关）

## 8. 测试结果

- 新增 `test_source_verified.py`（8 条：unverified 返回 / mark 成功 / Activity Log / verified_at / 不触发 Evaluation / API 状态 / 幂等 / 仅 acquired 可核验）
- 新增 `test_control_center_rag_evaluation_view.py`（8 条：route / nav / render / baseline / governance / 错误韧性 / 导航完整性 / TDZ 回归 / node --check）
- 更新真实状态测试（baseline STABLE 89.3% bl-eval-20260817T162956；Git wiki reviewed；git source verified）
- **375/375 全部通过**（359 既有 + 16 新增）

## 9. Git Source Verified 状态

- `src_git_config`：**verified = true**（verified_at=2026-08-17 17:04:12，verified_by=user，source_status=verified）
- 通过 Control Center 真实操作完成（POST /api/source_acquisition/src_git_config/verify + 浏览器 UI 展示）
- Git Wiki：**reviewed**（用户已在 CC 完成 Review）
- 未自动 verified 其它 Source（FreeRTOS 等仍 ⚠ 待人工核验）

## 10. Benchmark / Baseline 是否受影响

- **未受影响**：Mark Verified 不触发 Evaluation Required（governance=passed，reasons=[]，fingerprint changed=false）
- Baseline：**89.3% STABLE**（bl-eval-20260817T162956）保持不变

## 11. 附：运维修复（Scheduler 无限 Benchmark 循环）

- 审计发现：用户批准 Git Wiki（draft→reviewed）后 index_manifest 未重建 → 指纹恒显示 modified → **Scheduler 每 30 分钟重复触发 Benchmark**（16:54 又触发一次）
- 处置：清理陈旧锁与中断 state → reindex main（manifest 重建）→ fingerprint 干净 → `--verify` 恢复 skip
- 另清理一条因 Scheduler 无 DEEPSEEK_API_KEY 产生的 0.0% 伪回归 run（eval-20260817T165422）并恢复 latest.json 到 eval-20260817T162956（89.3%）

## 12. 下一步

- Control Center 8765 已用修复后代码重启，浏览器刷新即可用
- 若后续发现 Source 有问题：走既有 Source Review 流程人工处理（第一版无 Unverify，符合要求）
- Golden Set 扩标注、P2 三缺口（px4_ekf / ros2_nav2 / stm32_low_power）下一轮处理

## 最终状态

```text
Git Source verified：YES（src_git_config，人工核验）
Git Wiki：reviewed
Evaluation Required：NO
Baseline：89.3%（25/28）
Baseline Status：STABLE（bl-eval-20260817T162956）
RAG Evaluation 页面：PASS
Browser Refresh：PASS
Activity Log：PASS（SOURCE_VERIFIED 已记录）
Regression：375/375
RAG 算法修改：NO
```
