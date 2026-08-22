# Phase 22-A：Control Center Source Verified + RAG Evaluation UI 修复

- 日期：2026-08-17
- 类型：Control Center 治理能力 + UI 故障修复
- 约束：不修改 RAG 算法

## 一、Source Verified 能力（新增）

- 后端：`POST /api/source_acquisition/<id>/verify` → `service.mark_source_verified()`（仅 acquired 可核验，写 verified/verified_at/verified_by，source_status 前进 verified，记录 SOURCE_VERIFIED Activity Log，不触发 Evaluation）
- 前端：Source Acquisition 卡片 + viewSources 详情显示 `✓ 已核验` / `⚠ 待人工核验` + `[Mark Verified]`（confirm 确认）
- 安全规则：只有人工确认才 verified=true；不自动 verified；Source Verified ≠ Wiki Approved
- 实际执行：src_git_config 已通过 CC 操作标记 verified（2026-08-17 17:04:12, user）

## 二、RAG Evaluation 页面故障

- 根因：前端 TDZ Bug —— `df2 = diff && diff.diff`（第 687 行）在 `const diff = await api(...)`（第 749 行）之前使用 → ReferenceError → 空白页
- 修复：diff 提前 fetch；render 加 try/catch 错误卡 + 重试；hash 路由（刷新保持视图）
- 真实验证：headless Chrome CDP 点击/刷新均 PASS（live 8765）

## 三、测试

- 新增 test_source_verified.py（8）+ test_control_center_rag_evaluation_view.py（8）
- 更新真实状态测试（baseline STABLE 89.3%、Git wiki reviewed、git source verified）
- **375/375 通过**

## 四、运维修复

- Scheduler 无限 Benchmark 循环：Wiki 批准后 manifest 未重建 → 指纹恒 modified → 每 30 分钟重复 verify
  - reindex main → 指纹干净 → skip 恢复
- 清理 Scheduler 无 API key 产生的 0.0% 伪回归 run + 恢复 latest.json（89.3%）
- Control Center 8765 已用修复代码重启

## 五、最终状态

- Git Source verified: YES；Git Wiki: reviewed
- Evaluation Required: NO；Baseline 89.3% STABLE（bl-eval-20260817T162956）
- RAG Evaluation 页面: PASS；Browser Refresh: PASS；Activity Log: PASS；Regression: 375/375
- RAG 算法修改: NO

## 六、学习记录

- 后端写 source_acquisition.yaml 用 safe_dump 会丢注释/改格式：写回后需补回文件头注释（已内置到 mark_source_verified）
- 用自动化浏览器做真实操作时，点击选择器要精确到目标行（第一次点到了表格第一行的 FreeRTOS Source），完成后要核对结果并回滚非目标副作用
- TDZ 类前端 bug（const 声明在使用之后）pytest 静态测试难发现；应补 `node --check` 语法 + 声明顺序断言（已加入 test_control_center_rag_evaluation_view.py）
