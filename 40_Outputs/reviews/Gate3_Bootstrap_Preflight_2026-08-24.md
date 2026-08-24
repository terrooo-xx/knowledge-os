# Knowledge OS Gate 3 Bootstrap Preflight

- 日期：2026-08-24
- 范围：Gate 2 Closeout 收尾 + Gate 3 Bootstrap 启动前依赖审计（**未实现 Bootstrap**）
- 依据：真实当前环境检查（非历史报告推测）

## 1. Gate 2 Closeout

- Status: PASS
- Repository: terrooo-xx/knowledge-os
- Visibility: PRIVATE
- Published Commit: 9cf811d（docs: add gate 2 publish report）
- Published Tag: baseline/rc-codex-wecom-20260820 → f9a1130（未移动）
- Gate 2 Report: 40_Outputs/reviews/Gate2_Publish_2026-08-22.md（已入库并推送到远程，gh api 确认 size=5822）
- Remote master: 9cf811d（gh api 确认）
- Working tree: CLEAN（仅 2 个 DEFER Source 未跟踪，符合预期）
- 注：本次 commit 触发 pre-commit 钩子自动更新 CHANGELOG.md（+6 行，系统设计行为），已包含在 9cf811d 中

## 2. Bootstrap Goal

```text
GitHub clone → Bootstrap → Knowledge OS READY
```

READY 判定（Bootstrap 完成后必须可验证）：
- Python 环境可用
- 依赖安装完整
- RAG 可运行（索引可重建）
- Embedding + Reranker 模型可加载（离线）
- 配置可解析（无本机硬编码阻塞）
- DEEPSEEK_API_KEY 已存在（仅检查存在性）
- MCP 可启动（knowledge profile + bridge）
- Codex 外部查询可用
- Scheduler 3 个任务已注册
- Control Center 可启动
- 健康检查通过（knowledge_os_check / rag_health_check / wiki_health_check）
- Baseline 可验证（RAG Evaluation 89.3% STABLE 可复现）

## 3. Dependency Matrix（真实检查结果）

| 组件 | 当前来源 | Git 中 | Clone 后恢复 | Bootstrap 需要 | Machine-local |
|---|---|---|---|---|---|
| Vault 文档 | Git | ✓ | ✓ | — | — |
| Wiki | Git | ✓ | ✓ | — | — |
| Projects | Git | ✓ | ✓ | — | — |
| Skills | Git | ✓ | ✓ | — | — |
| RAG 源码 | Git | ✓ | ✓ | — | — |
| RAG Tests | Git | ✓ | ✓ | — | — |
| RAG Index | runtime（90_System/rag/database/，gitignored） | ✗ | ✗ | ✓ 重建（update_index.py） | — |
| Python | C:\Python314\python.exe（3.14.6） | ✗ | ✗ | ✓ 安装 3.14.x | ✓ |
| pip dependencies | 本机 Python | ✗ | ✗ | ✓ 安装 | ✓ |
| BGE embedding 模型 | HF cache：~/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5 | ✗ | ✗ | ✓ 下载/迁移 | ✓ |
| reranker 模型 | ModelScope cache：~/.cache/modelscope/models/BAAI--bge-reranker-v2-m3（2.2GB）+ HF cache 也有 | ✗ | ✗ | ✓ 下载/迁移 | ✓ |
| reranker path | config.yaml 硬编码本机路径 | 部分（字段在 Git，值为本机路径） | 不可直接跨机 | ✓ 需配置机制 | ✓ |
| DEEPSEEK_API_KEY | Windows 用户环境（HKCU\Environment） | ✗ | ✗ | ✓ 检查存在/提示注入 | ✓ |
| Codex | 本机 CLI 0.147.0 | ✗ | ✗ | ✓ 手动安装 | ✓ |
| ~/.codex/knowledge.config.toml | 本机（profile knowledge） | ✗ | ✗ | ✓ 生成 | ✓ |
| MCP bridge | C:\Users\陶权煜\Documents\Codex\knowledge_os_mcp_bridge.py | ✗ | ✗ | ✓ 复制/生成 | ✓ |
| Windows Scheduler | 系统 3 个任务 | ✗ | ✗ | ✓ 注册（脚本在 Git） | ✓ |
| Control Center | Git 源码 + 本机 Python | 源码 ✓ | 源码 ✓ | ✓ Python + 启动 | 部分 |
| cc-connect | ~/.cc-connect + C:\cc-connect-mcp | ✗ | ✗ | 待定（可选组件） | ✓ |
| WeCom config | 本机 | ✗ | ✗ | 待定（可选组件） | ✓ |

## 4. Machine-local Dependencies（Bootstrap 必须处理，不复制进 Vault）

1. Python 3.14.6 @ C:\Python314（被 Scheduler 任务与 MCP bridge 硬编码引用）
2. pip 包：PyYAML 6.0.3 / pypdf 6.15.0 / trafilatura 2.2.0 / openai 2.53.0 / sentence-transformers 5.7.0 / torch 2.13.0 / transformers 5.14.1 / chromadb 1.5.9 / numpy 2.5.0 / scikit-learn 1.9.0
3. BGE embedding：BAAI/bge-small-zh-v1.5（HF cache）
4. BGE reranker：BAAI/bge-reranker-v2-m3（ModelScope cache 2.2GB + HF cache）
5. DEEPSEEK_API_KEY（HKCU\Environment，仅存在性检查）
6. ~/.codex/knowledge.config.toml（MCP profile）
7. C:\Users\陶权煜\Documents\Codex\knowledge_os_mcp_bridge.py
8. Windows Scheduler 3 个任务
9. cc-connect / WeCom（可选，待定）

## 5. Bootstrap Blocker Candidates

1. **Reranker 路径硬编码（YES）**：config.yaml `reranker.model = "C:/Users/陶权煜/.cache/modelscope/models/BAAI--bge-reranker-v2-m3/snapshots/master"`。load_config（config.py）**无环境变量/命令行 override 机制**；resolve_paths 只处理 paths。跨机 clone 后此路径必然不存在。Bootstrap 必须引入配置覆盖机制（如环境变量 KNOWLEDGE_OS_RERANKER_MODEL 或机器级 config overlay），但本次不改。
2. **Python 绝对路径硬编码（YES）**：Scheduler（pythonw C:\Python314）+ MCP bridge（SERVER = C:\Python314\python.exe）+ knowledge.config.toml（command = C:\Python314\python.exe）。CC launcher 与 register 脚本用 PATH 动态解析（好）。Bootstrap 需确定 Python 安装/发现策略并同步改写这些位置。
3. **依赖无 lock（YES，较轻）**：仅 requirements.txt 最小版本约束，无 lock 文件；安装结果随 pip 解析变化。Bootstrap 需固定版本或生成 lock（本次不生成）。
4. **HF_HUB_OFFLINE 未统一（WARNING）**：mcp_server.py 已 setdefault HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE；hybrid_query.py / inbox_processor.py / evaluate 等 CLI 未设置，离线首启会卡 HF 联网重试（Gate 0 实测）。Bootstrap 应统一注入。

## 6. Existing Install / Setup Assets（可直接复用）

- `90_System/scripts/knowledge_os_check.ps1`（架构健康检查，退出码 0/1）
- `90_System/rag/scripts/rag_health_check.py`（索引完整性，只读）
- `90_System/rag/scripts/wiki_health_check.py`（Wiki 完整性，只读）
- `90_System/rag/scripts/update_index.py`（索引重建）
- `90_System/control_center/start_control_center.bat`（CC 一键启动，位置无关，PATH 解析 python）
- `90_System/control_center/register_review_preflight_task.ps1`（Scheduler 注册脚本，PATH 解析 python）
- `90_System/rag/interface/mcp_server.py`（MCP server，已内置 HF_HUB_OFFLINE）
- `90_System/scripts/update_changelog.ps1`（changelog 维护）
- `90_System/rag/requirements.txt`

## 7. Reranker Path Problem

- 当前字段：`config.yaml reranker.model = C:/Users/陶权煜/.cache/modelscope/.../snapshots/master`
- 使用代码：`rerank.py:_get_reranker(provider, reranker_cfg["model"])` → 直接作为模型路径/名称传给 sentence-transformers
- 环境变量 override：**无**（load_config 不读 env）
- 命令行 override：**无**（hybrid_query.py --config 只换整个文件）
- 更合理机制：环境变量覆盖（如 `KNOWLEDGE_OS_RERANKER_MODEL`）或 machine-local config overlay（gitignored），Bootstrap 阶段实现
- 注意：模型同时存在于 HF cache（`models--BAAI--bge-reranker-v2-m3`），也可用模型名 `BAAI/bge-reranker-v2-m3` + HF_HUB_OFFLINE 从 HF cache 加载

## 8. Python / Dependencies

- Python：C:\Python314\python.exe（3.14.6）——Bootstrap requirement: Python 3.14.x（sentence-transformers 5.7 / torch 2.13 等已在此版本验证）
- 硬编码引用位置：Scheduler 2 处（Review Preflight pythonw；register 脚本动态解析）、MCP bridge 1 处、knowledge.config.toml 1 处
- requirements.txt：PyYAML / pypdf / trafilatura / openai / sentence-transformers（chromadb 可选）
- 无 requirements-lock / pyproject → Bootstrap 待解决项

## 9. Models

| 模型 | 用途 | 来源 | 缓存位置 | 离线加载 |
|---|---|---|---|---|
| BAAI/bge-small-zh-v1.5 | embedding | HF | ~/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5 | 需 HF_HUB_OFFLINE=1 |
| BAAI/bge-reranker-v2-m3 | reranker | ModelScope（config 指向）+ HF 亦有 | ~/.cache/modelscope/models/BAAI--bge-reranker-v2-m3（2.2GB）；HF hub 亦有 | 需 HF_HUB_OFFLINE=1 |

模型版本未在配置中固定为 hash（ModelScope snapshots/master）；Bootstrap 应固定或记录下载来源。

## 10. DeepSeek

- 读取位置：`90_System/rag/llm/deepseek_adapter.py` → `os.environ.get("DEEPSEEK_API_KEY")`（仅环境变量）
- MCP bridge 额外从 HKCU\Environment 恢复用户级变量注入 server 子进程
- 原则：Secret 永不进 Git；Bootstrap 只检查存在性；缺失时提示用户设置；日志不打印 key
- 当前：已存在（仅记录存在性，不输出值）

## 11. Codex / MCP

- Codex CLI：0.147.0（cc-connect 使用的 npm 版本）
- knowledge.config.toml 结构：`[mcp_servers.knowledge-os]` command=C:\Python314\python.exe, args=[bridge], startup_timeout=120, **default_tools_approval_mode="approve"**（Gate 0 实测的自动化依赖，必须保留）, env.KNOWLEDGE_OS_VAULT
- MCP bridge（Documents/Codex/knowledge_os_mcp_bridge.py）→ 内部 spawn 90_System/rag/interface/mcp_server.py
- bridge 职责：NDJSON↔Content-Length 适配 + HKCU 环境继承（恢复 DEEPSEEK_API_KEY）+ HF_HUB_OFFLINE
- Bootstrap 需生成：bridge 文件 + knowledge.config.toml（machine-local，非 Git 资产）

## 12. Scheduler（3 个任务，当前真实状态）

| 任务 | Trigger | Executable | 参数 | 工作目录 | 用户 |
|---|---|---|---|---|---|
| Knowledge OS Review Preflight | 每 30 分钟 | C:\Python314\pythonw.exe | review_preflight_cli.py --once --trigger scheduled --governance | D:\KnowledgeBase\Obsidian Vault | 陶权煜 |
| Knowledge OS Weekly Review | 每周五 18:00 | powershell.exe | -File ...\run_weekly_review.ps1 | D:\KnowledgeBase\Obsidian Vault | 陶权煜 |
| KnowledgeBase-UpdateChangelog | 每日 23:00 | powershell.exe | -File ...\update_changelog.ps1 | 无 | 陶权煜 |

- 最近运行：Preflight 08-24 16:29:53 result=0；Weekly 08-22 16:08:06 result=0；Changelog 08-22 23:00:01 result=0（全部成功）
- Bootstrap 必须写入：Python 绝对路径（若新机不同需更新）；任务参数
- 建议动态发现：Python 路径（参考 register 脚本的 Get-Command python 逻辑）

## 13. Control Center

- 启动：start_control_center.bat（位置无关，从脚本位置推导 VAULT_ROOT；python 从 PATH 解析；curl 健康探测；自带打开浏览器）
- 端口：8765（server.py PORT=8765；HEALTH_URL /api/health）
- 依赖：stdlib only（http.server）+ 复用 RAG 引擎（同 Python 环境）
- 工作目录：Vault 根
- 存在 launcher：start_control_center.bat + create_desktop_shortcut.bat
- 机器路径依赖：launcher 本身位置无关（好）；不依赖特定用户路径
- Bootstrap 注意：不要生成只能在当前用户路径运行的 launcher；应沿用位置无关模式

## 14. Bootstrap 边界

Bootstrap 应负责：
- 运行环境（Python/依赖/模型）
- 环境变量检查（DEEPSEEK_API_KEY 存在性）
- 配置覆盖机制（reranker 路径等 machine-local 项）
- 索引重建（update_index.py）
- MCP（bridge + knowledge.config.toml 生成）
- Scheduler 注册
- Health Check 执行与 READY 判定
- Baseline 验证（RAG Evaluation 复测）

Bootstrap 不应自动：
- 上传私人资料 / 修改 Wiki 状态 / Approve Wiki / 修改知识内容
- 改变 Baseline / 重写 Git 历史 / 创建 GitHub Repository / 自动 commit
- 暴露 Secret / 把 machine-local 配置复制进 Vault

## 15. Bootstrap 模式建议

- 推荐：**PowerShell 主脚本 + Python helper 混合**
  - PowerShell：环境探测、Scheduler 注册、模型缓存迁移提示、CC 启动、health check 编排（复用 90_System/scripts/knowledge_os_check.ps1）
  - Python helper：pip 依赖安装/校验、config overlay 生成、索引重建、RAG 验证（复用现有 scripts）
- 理由：现有工具已按 PS + Python 分工（register_review_preflight_task.ps1、update_changelog.ps1、run_weekly_review.ps1 均为 PS 壳 + Python 核心）；避免第二套平行安装系统
- 复用 90_System/scripts/，不新建平行体系

## 16. 验证机制

- Bootstrap 最终调用：`knowledge_os_check.ps1`（架构+健康）+ `rag_health_check.py`（索引）+ `wiki_health_check.py`（Wiki）→ 输出 `BOOTSTRAP READY`
- 区分：
  - Health Check = 运行时健康（进程/索引/配置可用）
  - Baseline Verification = 版本/行为恢复正确（RAG Evaluation 复测 coverage ≈ 89.3%，Baseline bl-eval-20260817T162956 STABLE 可复现）
- 两者不能混为一谈；Bootstrap 报告需分别输出

## 17. 结论

```
GATE 3 BOOTSTRAP PREFLIGHT = PASS WITH WARNINGS
```

- Bootstrap 依赖：IDENTIFIED（Dependency Matrix 完成）
- Bootstrap Blocker Candidates：
  1. reranker 模型路径硬编码（无 env/CLI override）—— Bootstrap 必须引入覆盖机制
  2. Python 绝对路径硬编码（Scheduler/bridge/Codex config）
  3. 依赖无 lock 文件
  4. HF_HUB_OFFLINE 未统一（WARNING）
- 均为"Bootstrap 设计输入"，不阻塞启动 Gate 3（Bootstrap 设计时处理）
- NO BOOTSTRAP IMPLEMENTATION YET
