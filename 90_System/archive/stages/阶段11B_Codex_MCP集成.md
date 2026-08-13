---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑪-B：Codex ↔ Knowledge OS MCP 正式接入

> 把 Knowledge OS 定位为**跨项目共享知识层**：项目保持独立，Codex 通过本地 MCP Server
> 调用只读 `knowledge_search`，走现有 Retrieval → Evidence → LLM Judge 安全链。

## 1. 目标

让 Codex 在任意独立项目（如无人机工程）中可直接调用 Knowledge OS 知识查询。

## 2. Project / Knowledge OS 分离

```text
D:\Projects\DroneFlightController 等（独立项目）
        ↓ Codex
D:\KnowledgeBase\Obsidian Vault\90_Systemgent\mcp_server.py（MCP）
        ↓ knowledge_search
Knowledge OS（Wiki/RAG/Evidence/Judge）
```

- 不复制 Wiki / Vector DB / RAG 到项目；不移动项目进知识库。

## 3. MCP 架构

```text
Codex（~/.codex/config.toml [mcp_servers.knowledge-os]）
  → stdio JSON-RPC（LSP 帧）
  → mcp_server.py（Python 标准库，零外部 MCP SDK/框架）
      → 仅一个 Tool：knowledge_search
          → knowledge_service.knowledge_search（只读封装）
              → 现有 retrieval → evidence → judge → answer/gap
```

- stdout 仅输出 MCP 帧（日志走 stderr），保证传输稳定。

## 4. Tool 定义

```json
{
  "name": "knowledge_search",
  "description": "Search the user's personal Knowledge OS for reliable engineering knowledge... The tool is read-only. If it returns knowledge_missing, do not claim that the Knowledge OS contains the answer.",
  "inputSchema": { "type": "object",
    "properties": { "query": {"type":"string"}, "top_k": {"type":"integer","minimum":1,"maximum":10} },
    "required": ["query"] }
}
```

- 只暴露 `knowledge_search`，不暴露 approve/reject/resolve/edit/merge/write 等管理能力。

## 5. Vault 路径

- 环境变量 `KNOWLEDGE_OS_VAULT` 指定（配置在 `[mcp_servers.knowledge-os.env]`），缺省按 mcp_server.py 自身位置反推。
- **不依赖当前工作目录**（已验证从任意 cwd 可解析）。

## 6. Read-only 边界

- MCP 只读：不写 Wiki / frontmatter / knowledge_gaps.yaml / Activity Log / Vector DB；无任何写工具。

## 7. Evidence

- 复用现有 `assess_evidence`；结果经 tools/call 原样返回（evidence: title/source/score/status）。

## 8. Judge

- 复用现有 LLM Relevance Judge（fail-closed、可开关）；MCP 调用不绕过、不二次建 LLM。

## 9. Knowledge Missing

- `knowledge_missing` 原样保留给 Codex，`answer=null`；Codex 可基于项目 + 自身知识继续分析，但须区分 `[Knowledge OS]` 与 `[Agent Reasoning]`。

## 10. Codex 调用策略

- **应调用**：STM32 / FreeRTOS / DMA / CAN / UART / SPI / PID / EKF / 传感器 / 电机控制 / 飞控原理 / 已沉淀工程知识。
- **不应调用**：当前项目代码 / 编译错误 / Git 状态 / 文件路径 / 函数实现 / 构建系统 / 临时设计。
- 详见 `90_System/agent/README.md`（Agent 使用规则）。

## 11. MCP 配置

`~/.codex/config.toml` 增量新增（保留既有 `node_repl`，不影响其他 MCP）：

```toml
[mcp_servers.knowledge-os]
command = "python"
args = ["D:\KnowledgeBase\Obsidian Vault\90_System\agent\mcp_server.py"]
startup_timeout_sec = 120

[mcp_servers.knowledge-os.env]
KNOWLEDGE_OS_VAULT = "D:\KnowledgeBase\Obsidian Vault"
HF_HUB_OFFLINE = "1"
PYTHONIOENCODING = "utf-8"
```

> 注意：需**重启 Codex** 后该 MCP Server 才会加载；当前会话不会自动出现该工具。

## 12. 无人机项目验证

- 本机不存在 `D:\Projects\DroneFlightController`（也不存在 `D:\Projects`），按任务要求**不创建虚假项目**。
- 已从**独立临时工作目录**（%TEMP%）启动 MCP Server 完成端到端验证，证明"不依赖 Codex 工作目录"成立。
- 真实无人机项目中的 Codex 调用验证留待项目实际创建后由用户执行（MCP 配置已就绪）。

## 13. 测试

- 新增 `tests/test_mcp_server.py`（9 用例，含真实 stdio 子进程握手 + tools/list）全部 PASS。
- stdio 端到端（真实 LLM）4 问题：
  - `STM32时钟树HSI/HSE/PLL怎么工作？` → **answerable**，judge=relevant(0.95) ✅
  - `WSL里怎么装Ubuntu？` → **knowledge_missing** ✅
  - `ROS2 Nav2代价地图怎么配置？` → **knowledge_missing**，judge=irrelevant(1.0) ✅（FP 仍被拒）
  - `ICM-42688-P的SPI读取应该注意什么？` → **retrieval_problem**（诚实，不编造）✅
- 原有 17/17 + 新增 MCP = **18/18 全部 PASS**。

## 14. 已知限制

- 需重启 Codex 才加载 MCP Server；本会话工具不可用（配置已就绪）。
- `mcp` 官方 SDK 未安装，采用零依赖 stdio 实现（协议合规：initialize / notifications/initialized / tools/list / tools/call / ping / resources/list / prompts/list / shutdown/exit）。
- 每次 knowledge_search 首次调用会加载本地 BGE 模型（约数秒）；LLM 回答需 DeepSeek 可用（否则 fail-closed）。
- 无真实无人机项目可做"项目内 Codex 自动调用"验证（不虚构项目）。

## 15. 后续阶段

- 阶段⑪-C 候选：真实无人机项目中的 Codex 自动调用验证；Knowledge Capture（Project → Knowledge OS 写入，需明确授权写权限）；MCP 增加可选 `knowledge_gaps` 报告（仍只读）。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
