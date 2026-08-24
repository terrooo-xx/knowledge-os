# Knowledge OS Bootstrap Upgrade：正式发布报告（Gate 4 前置确认）

- 日期：2026-08-24
- Commit：**82e7383**（feat: upgrade bootstrap with codex cc-switch deepseek）
- Push：873b7a5..82e7383 → origin/master（已确认远程 master = 82e7383）
- 远程文件：bootstrap.ps1（21771B）/ bootstrap_helper.py（23440B）/ Bootstrap_Upgrade_2026-08-24.md（6973B）均已确认存在
- Tag：baseline/rc-codex-wecom-20260820 → f9a1130 **UNCHANGED**

## 1. 发布前复核与回归

| 检查 | 结果 |
|---|---|
| Push Candidate | 仅 3 个升级文件（helper/ps1/报告）+ 系统自动 CHANGELOG 条目（与历次 commit 一致的既有行为） |
| Secret 扫描（3 文件） | Real Secret = 0（无 API Key / token / auth header / 私钥 / 凭据值） |
| pytest | **412 / 412 passed**（0 failed / 0 skipped） |
| bootstrap.ps1 -CheckOnly | **BOOTSTRAP READY**（AI Runtime READY） |
| RAG Baseline 复测 | 本次 coverage=85.7%（vs 89.3%），差异仅 q_drone_power；官方分类 **REAL_REGRESSION=0, JUDGE_VARIANCE=1**（q_drone_power 为系统已知判定波动查询）；同日两次完整运行曾复现 89.3%/delta 0.0pp。Baseline 保持 STABLE，无真实回归 |
| machine-local | config.local.yaml / .bootstrap_state.json / venv / 模型缓存 / 日志 / Secret 均未进入候选（已 gitignore 验证） |

> 说明：复测期间 DeepSeek 上游出现一次瞬时 HTTP 402（账户当前余额 9.66 CNY、直连 API 200、CC Switch 代理无限额设置、最近代理日志 200），判断为瞬时环境因素，已如实记录；不影响发布。

## 2. Gate 4 新电脑初始环境（正式冻结，以真实实现为准）

| 项目 | Gate 4 开始前要求 | Bootstrap 行为 |
|---|---|---|
| Windows | 必须（10/11，已用 Windows 11 验证） | 不安装 |
| PowerShell | 必须（Windows PowerShell 5.1+ 或 PS7） | 不安装 |
| Git | 必须 | 不安装（当前实现不自动装 Git） |
| GitHub 私库认证 | 必须 | 用户完成（gh 或 credential） |
| Python 3.14.x | 必须 | Bootstrap 不安装，自动发现（venv → py -3.14 → PATH） |
| Python venv | 不需要 | Bootstrap 创建（90_System/.venv） |
| Python dependencies | 不需要 | Bootstrap 安装（requirements-lock.txt） |
| BGE models | 不需要 | Bootstrap 检测；缺失时提示准备/联网下载 |
| Reranker | 不需要 | Bootstrap 检测并写入 config.local.yaml |
| Codex | 当前实现自动安装（npm，需 Node） | Bootstrap 安装（`npm i -g @openai/codex`） |
| Node | 仅当 Bootstrap 用 npm 装 Codex 时需要 | 记录实际要求（本机 node v24.16.0） |
| CC Switch | 缺失时需用户提供官方安装器 | 用户输入（Bootstrap 不硬编码未验证 URL） |
| DeepSeek API Key | 用户提供 | Bootstrap 检查存在性/验证；写入 machine-local 安全存储（CC Switch provider） |
| MCP | 不需要 | Bootstrap 配置（knowledge.config.toml + bridge） |
| Codex config | 不需要 | Bootstrap 配置（approval=approve，最小侵入） |
| Scheduler | 不需要 | Bootstrap 注册/修复 3 个任务 |
| Control Center | 不需要 | Bootstrap 检查/复用 launcher |
| Knowledge OS Index | 不需要 | Bootstrap 重建（update_index.py） |
| cc-connect | 当前实现不自动安装 | 可选，用户自行安装（不在核心链路） |
| OpenAI 官方登录 | 不需要 | CC Switch + DeepSeek 自定义 provider 即可 |

## 3. Bootstrap 能力边界（明确区分）

### Bootstrap 自动安装
- Codex（npm，需 Node；缺失时尝试安装）

### Bootstrap 自动配置
- Python venv / Python dependencies（requirements-lock）/ BGE models（检测）/ Reranker（config.local.yaml）/ RAG Index（重建）/ Codex config / DeepSeek Provider（读取+验证；缺失时引导用户在 CC Switch UI 创建）/ MCP（knowledge.config.toml + bridge）/ Approval（approve）/ Scheduler（3 任务）/ Control Center（检查+launcher）

### 用户仍需要提供/处理
- GitHub 私库认证
- DeepSeek API Key（machine-local，仅写 CC Switch provider 安全存储）
- 若 CC Switch 缺失：官方安装器（Bootstrap 不硬编码下载 URL）
- 若 Codex 缺失且无 Node：手动安装 Codex

## 4. 结论

```
========================================
Knowledge OS
BOOTSTRAP UPGRADE RELEASE
========================================

Release:
PASS (commit 82e7383 pushed)

GitHub master:
82e7383

Existing Tag:
baseline/rc-codex-wecom-20260820
UNCHANGED

Gate 4:
READY TO START
========================================
```

## 5. 边界遵守

- ✅ 未创建/修改 Tag；未修改 Baseline 数值；未改 Wiki/Source；未改 machine-local 文件提交
- ✅ 未提交 config.local.yaml / .bootstrap_state.json / venv / 模型缓存 / 日志 / 任何 Secret
- ✅ 未开始 Gate 4（未在第二台电脑 clone/运行）
- ✅ 未输出任何 DeepSeek API Key / token / 凭据值
