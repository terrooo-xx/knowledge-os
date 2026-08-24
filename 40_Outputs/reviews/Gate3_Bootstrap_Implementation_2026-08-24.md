# Knowledge OS Gate 3：Bootstrap 实施报告

- 日期：2026-08-24
- 提交：873b7a5（[Phase 3] feat: Knowledge OS Bootstrap (Gate 3)，已 push origin/master）
- 前置：Gate 0~2 Closeout 全部 PASS；Gate 3 Preflight PASS WITH WARNINGS

## 1. 结论

```
========================================
Knowledge OS
GATE 3 IMPLEMENTATION
========================================
Bootstrap Dependencies: RESOLVED
Bootstrap Blockers:      0
Bootstrap Verification:  BOOTSTRAP READY
========================================
```

本机完整运行 `bootstrap.ps1`（含 Baseline Verification）结果：

```
 Python           : PASS
 Dependencies     : PASS
 Models           : PASS
 Secrets          : PASS
 Index            : PASS
 Scheduler        : PASS
 Codex/MCP        : PASS
 Control Center   : PASS
 Health Check     : PASS
 Baseline Verify  : PASS  (coverage=89.3% vs bl-eval-20260817T162956, delta=0.0pp)
----------------------------------------------
 BOOTSTRAP READY
```

## 2. 交付物（已提交 Git）

| 文件 | 说明 |
|---|---|
| 90_System/scripts/bootstrap.ps1 | PowerShell 主脚本（-CheckOnly / -Skip* / -CreateVenv） |
| 90_System/scripts/bootstrap_helper.py | Python helper（12 个子命令，UTF-8 输出） |
| 90_System/scripts/templates/mcp_bridge_template.py | MCP bridge 模板（Bootstrap 实例化到 machine-local） |
| 90_System/rag/requirements-lock.txt | 已验证核心依赖锁定版本 |
| 90_System/rag/rag_engine/config.py | 支持 config.local.yaml + env 覆盖 |
| 90_System/rag/config.yaml | reranker.model 改为可移植默认（BAAI/bge-reranker-v2-m3） |
| 90_System/rag/rag_engine/embeddings.py | 默认 HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE |
| 90_System/rag/rag_engine/rerank.py | 同上（统一离线默认） |
| .gitignore | +90_System/.venv/、config.local.yaml、.bootstrap_state.json |

## 3. Preflight 4 个跨机问题解决情况

| 问题 | 解决方式 | 状态 |
|---|---|---|
| 1. reranker 路径硬编码 | config.yaml 改可移植默认；新增 config.local.yaml 机器级覆盖（gitignored）+ `KNOWLEDGE_OS_RERANKER_MODEL` env 覆盖；Bootstrap 自动发现模型并写入 config.local.yaml | ✅ |
| 2. Python 绝对路径硬编码 | Bootstrap 自动发现（venv → py -3.14 → PATH），记录 machine-local 解释器；Scheduler/bridge/Codex 配置使用该解释器；用户环境变量 KNOWLEDGE_OS_PYTHON 供 weekly-review 解析 | ✅ |
| 3. 依赖无 lock | 新增 requirements-lock.txt（已验证核心版本，torch 2.13 / sentence-transformers 5.7 / openai 2.53 等）；requirements.txt 仍为直接依赖源 | ✅ |
| 4. HF_HUB_OFFLINE 未统一 | embeddings.py / rerank.py 模块级 setdefault 离线；Bootstrap 下载阶段显式置空走 online；本机验证离线加载无重试卡顿 | ✅ |

## 4. 关键设计

- **配置优先级**：DEFAULTS < config.yaml < config.local.yaml < env KNOWLEDGE_OS_RERANKER_MODEL
- **模型发现**：embedding（HF cache 完整校验 model.safetensors）+ reranker（ModelScope `snapshots/<rev>` 优先，其次 HF cache，最后模型名）；本机 reranker 仅 ModelScope 完整（2.27GB），已正确写入 config.local.yaml
- **venv 策略**：优先复用已验证解释器（本机 C:\Python314）；新机无有效解释器时创建 90_System/.venv 并安装 requirements-lock.txt（-CreateVenv 强制）
- **Scheduler**：检查 3 个任务存在性，缺失才注册，不重复创建；最近运行全部 result=0
- **Codex/MCP**：knowledge.config.toml + bridge 由 Bootstrap 生成/校验（machine-local，不进 Git），保留 default_tools_approval_mode="approve"
- **Health vs Baseline 分离**：Health Check = 运行时健康；Baseline Verification = RAG benchmark 复测覆盖率对比官方基线

## 5. 验证记录（本机真实执行）

1. `bootstrap.ps1 -CheckOnly`：全 PASS → BOOTSTRAP READY
2. `bootstrap.ps1`（完整，含 Baseline）：全 PASS；Baseline coverage=89.3% vs 89.3%（delta 0.0pp）
3. MCP：cwd=C:\Temp\DroneTest（非 Vault）→ initialize/tools/list/knowledge_search(fast) → answerable / judge relevant
4. Codex：`codex -p knowledge exec`（cwd≠Vault）→ knowledge_search 返回 answerable / judge relevant（confidence 0.95）
5. 测试套件：412/412 passed（Bootstrap 代码改动无回归）
6. RAG raw 路径 reranker 加载验证：CrossEncoder 从 ModelScope 加载成功

## 6. Machine-local 变更（本机，均不进 Git）

- 90_System/rag/config.local.yaml（reranker 指向本机 ModelScope 路径，正斜杠）
- 90_System/scripts/.bootstrap_state.json（Bootstrap 状态）
- 用户环境变量 KNOWLEDGE_OS_PYTHON = C:\Python314\python.exe
- ~/.codex/knowledge.config.toml（已存在，校验通过）
- Documents/Codex/knowledge_os_mcp_bridge.py（已存在，校验通过）

## 7. 边界遵守

- ✅ 未修改 Wiki/Source/Baseline 数值/Tag/Git 历史；未创建新 Tag；未 gc
- ✅ 未把 machine-local 配置复制进 Vault（config.local.yaml/state 均 gitignored）
- ✅ Secret 仅检查存在性，未输出/保存
- ✅ 未部署第二台真实电脑；未删除旧环境
- ✅ Bootstrap 职责：恢复运行环境，不改变知识内容

## 8. 使用方式（新电脑）

```powershell
git clone https://github.com/terrooo-xx/knowledge-os.git
cd knowledge-os
powershell -ExecutionPolicy Bypass -File 90_System\scripts\bootstrap.ps1
# 可选：
#   -CheckOnly          只读审计
#   -CreateVenv         强制创建 90_System/.venv
#   -SkipModels / -SkipScheduler / -SkipCodex / -SkipIndex / -SkipBaseline / -SkipDeps
```

## 9. 遗留建议（不阻塞）

- 新机器首次运行若模型缺失，Bootstrap 会 FAIL Models 并提示联网下载/恢复模型缓存（未实现自动下载，避免不可控网络行为）。
- requirements-lock.txt 为"已验证核心版本"而非完整传递闭包；如要完整锁定，在新机 venv 内 `pip freeze > requirements-lock.txt` 替换。
- `gh` 不在 PATH（本机），建议加入 PATH 便于 Gate 4 等后续操作。
