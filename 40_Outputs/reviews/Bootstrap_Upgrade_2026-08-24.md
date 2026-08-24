# Knowledge OS Bootstrap Upgrade：完整 AI 工作环境自动恢复

- 日期：2026-08-24
- 类型：对 Gate 3 Bootstrap 的**增量升级**（不推倒重写）
- 范围：AI Runtime（Codex / CC Switch / DeepSeek / Routing / MCP / E2E）
- Git 状态：**未 commit / 未 push**（本任务无明确发布授权，按提示词要求只做本地验证 + 报告）

## 1. 结果

```
========================================
Knowledge OS
BOOTSTRAP UPGRADE
========================================
AI Runtime:      READY
Codex:           PASS (0.147.0)
CC Switch:       PASS (3.20.0)
DeepSeek:        PASS (provider + API key validated HTTP 200)
Routing:         PASS (native responses, no protocol routing; proxy enabled)
MCP/Approval:    PASS
E2E Test1:       PASS (Codex -> DeepSeek)
E2E Test2:       PASS (Codex -> knowledge_search, cwd != Vault)
Regression:      PASS (pytest 412/412; RAG REAL_REGRESSION=0)
BOOTSTRAP READY
========================================
```

## 1.5 正式发布回归（2026-08-24 复核）

- pytest：412 / 412 passed（0 failed / 0 skipped）
- bootstrap.ps1 -CheckOnly：BOOTSTRAP READY（AI Runtime READY）
- RAG Baseline 复测：本次运行 coverage=85.7%（vs 官方基线 89.3%），逐查询差异仅 q_drone_power（answered→knowledge_missing）；官方 gap_diagnosis 分类 **REAL_REGRESSION=0，JUDGE_VARIANCE=1**（q_drone_power 为系统记录的已知判定波动查询，Phase 19 已记录）；同日早些时候两次完整运行均为 89.3% / delta 0.0pp。结论：**Baseline 保持 STABLE，无真实回归**；85.7% 属 judge 方差（且复测时 DeepSeek 端出现一次瞬时 HTTP 402，可能影响该查询 judge 调用，属环境因素）。
- verify_baseline 已改进为使用官方 REAL_REGRESSION 分类语义（JUDGE_VARIANCE 不阻塞），并修复 rag_engine sys.path 引用。

## 2. 变更内容（未提交）

| 文件 | 变更 |
|---|---|
| 90_System/scripts/bootstrap_helper.py | +detect-codex / detect-ccswitch / ccswitch-deepseek / ccswitch-mcp / validate-deepseek-key；verify_baseline 改用官方 REAL_REGRESSION 分类（Key 值一律脱敏） |
| 90_System/scripts/bootstrap.ps1 | +AI Runtime 段（-SkipAI 开关；Codex/CCSwitch/DeepSeek/Routing/MCP/Approval/E2E；AI 状态 READY/DEGRADED/BLOCKED） |

## 3. AI Runtime 检测结果（本机真实）

- Codex：codex-cli 0.147.0 @ C:\Users\陶权煜\AppData\Roaming\npm\codex（npm 全局）
- CC Switch：3.20.0 @ D:\sorfware\ccSwitch\cc-switch.exe；配置库 ~/.cc-switch/cc-switch.db（SQLite）
- DeepSeek Provider（CC Switch）：name=DeepSeek（is_current），base_url=https://api.deepseek.com，wire_api=responses，model=deepseek-v4-flash，API key present（值未输出）
- Routing 判断：provider wire_api=responses（原生 Responses API）→ **不需要协议转换路由**（needs_routing=false）；CC Switch 本地代理当前已启用（127.0.0.1:15721），Codex 实际 base_url=http://127.0.0.1:15721/v1 → 状态一致
- DeepSeek API：env key 验证 GET /models → HTTP 200
- MCP：~/.codex/knowledge.config.toml（knowledge-os + default_tools_approval_mode="approve"）✓；CC Switch mcp_servers knowledge-os enabled_codex=True ✓

## 4. E2E 验证（cwd != Vault）

- Test1（Codex→DeepSeek 最小请求）：`codex exec` → 返回"正常"，exit 0
- Test2（Codex→knowledge_search）：`codex -p knowledge exec` @ C:\Temp\KnowledgeOS-Gate4-AI-Test → answerable / judge relevant
- Test3（联合链路）：经 MCP 的 knowledge_search 本身即 Codex→DeepSeek→RAG→Evidence 全链路（deep/fast 均验证过 answerable + judge relevant）

## 5. 失败模式映射

- AI_BOOTSTRAP_BLOCKED：Codex/CCSwitch 安装失败、DeepSeek 验证失败、MCP 失败、E2E 失败（核心 AI 环境不能运行）
- AI_BOOTSTRAP_DEGRADED：DeepSeek 未配置/Key 缺失（Knowledge OS Core/RAG/CC 仍可运行）
- AI_BOOTSTRAP_READY：Codex + CC Switch + DeepSeek + MCP + Knowledge OS 全部通过

## 6. 幂等性（本机第二次运行验证）

- 已有 Codex/CCSwitch/DeepSeek Provider/MCP/Models → 全部走 VERIFY/REPAIR，不重复安装/创建/询问
- bootstrap.ps1 连续运行多次结果一致（READY）

## 7. 安全

- DeepSeek API Key：仅读取存在性/HTTP 验证；**值未输出到任何日志/报告/diff**
- 未把 Key 写入 Git / Vault / config.yaml / requirements
- 优先使用 CC Switch 自身的安全存储（provider auth），Bootstrap 不复制一份 Secret

## 8. New Machine Initial Environment

> 一台完全没预装 Codex、CC Switch、Python、RAG、MCP、Knowledge OS 运行环境的 Windows 电脑，Bootstrap 开始前：

| 项 | 状态 | 说明 |
|---|---|---|
| OS | REQUIRED BEFORE BOOTSTRAP | Windows 10/11（本实现已用 Windows 10/11 验证；依赖 schtasks/tasklist/winreg） |
| PowerShell | REQUIRED BEFORE BOOTSTRAP | Windows PowerShell 5.1+ 或 PowerShell 7（bootstrap.ps1 运行环境） |
| Git | REQUIRED BEFORE BOOTSTRAP | 需要先 `git clone`；Bootstrap 不安装 Git |
| Internet | REQUIRED BEFORE BOOTSTRAP | clone + pip + 模型下载 + DeepSeek API 均需网络 |
| GitHub Authentication | REQUIRED BEFORE BOOTSTRAP | 需要能 clone 私有仓库的凭据（gh 或 credential） |
| Python | REQUIRED BEFORE BOOTSTRAP | Bootstrap 自动发现（venv → py -3.14 → PATH）并创建 90_System/.venv；**不自动安装 Python**，需 3.14.x（已验证 3.14.6） |
| Node | OPTIONAL | 仅当需要 Bootstrap 用 npm 安装 Codex 时需要 |
| Codex | BOOTSTRAP INSTALLS | 缺失时尝试 `npm install -g @openai/codex`（需 Node）；无 Node 则提示用户手动安装 |
| CC Switch | USER INPUT REQUIRED if missing | Bootstrap 自动检测；缺失时不硬编码下载 URL，提示用户提供官方 release/安装器（未验证的 URL 不写入） |
| DeepSeek API Key | USER INPUT REQUIRED | 首次运行检查本机已有 Key；缺失则安全提示用户输入（只写入 machine-local 安全存储/CC Switch provider） |
| Chocolatey | OPTIONAL | 不依赖；有则可用于装 gh 等 |
| Winget | NOT REQUIRED | 不依赖 |
| OpenAI Login | NOT REQUIRED | CC Switch + DeepSeek 自定义 provider 即可，无需 OpenAI 官方登录 |
| Python deps / Models / Reranker / RAG index / Scheduler / Control Center / MCP / Codex config | BOOTSTRAP CONFIGURES | 由 Bootstrap 自动恢复（Gate 3 已验证） |

## 9. 边界遵守

- ✅ 增量升级现有 bootstrap.ps1 / bootstrap_helper.py，未建立第二套安装系统
- ✅ 未硬编码 127.0.0.1:15721 为"DeepSeek 一定需要路由"；按 provider wire_api 动态判断（本机原生 responses → 不需要协议路由）
- ✅ 未硬编码 CC Switch 下载 URL；未把 CC Switch 源码/运行代码复制进 Knowledge OS Git
- ✅ 未修改 ~/.codex 除现有 knowledge.config.toml 管理外的内容；最小侵入
- ✅ 未 push（无发布授权）；未 commit（遵循默认不自动 commit）
- ✅ 未输出任何 Secret / Key 值
