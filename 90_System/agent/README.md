# Knowledge OS Agent Knowledge Interface

供外部 AI Agent / Codex 查询 Knowledge OS 的**只读**知识接口。

## 定位

- 独立项目（如无人机工程）与 Knowledge OS 之间只通过本接口连接；
- Agent **不直接访问 Wiki / Vector DB**，而是经本接口走现有
  `Retrieval -> Heuristic Evidence Gate -> LLM Relevance Judge -> Sufficiency` 链路；
- 本阶段只读；写操作（WRITE / REVIEW / APPROVE / RESOLVE）留待未来阶段。

## 使用

```powershell
# CLI 查询（结构化 JSON）
python 90_System/agent/knowledge_cli.py "FreeRTOS任务优先级和抢占式调度怎么工作？"

# 离线模式（不调用 LLM，无回答/Judge）
python 90_System/agent/knowledge_cli.py "问题" --no-llm
```

代码调用：

```python
import sys
sys.path.insert(0, r"D:\KnowledgeBase\Obsidian Vault\90_Systemgent")
from knowledge_service import knowledge_search

r = knowledge_search("STM32 DMA 怎么配置？")
print(r["status"], r["answer"], r["judge"])
```

## 返回字段

- `status`：`answerable` / `knowledge_missing` / `knowledge_insufficient` / `retrieval_problem` / `answer_quality_problem` / `error`
- `answer`：有足够证据且 LLM 可用时为回答，否则 `null`
- `evidence`：`[{title, source, score, status}]`（来源可追踪）
- `sufficient`：Evidence 是否充分
- `judge`：`{relevance, confidence, reason}`（启用时）
- `gap`：`{status: "pending"}`（不足时；只读报告，不自动写入）
- `source_trace`：来源路径集合
- `reason`：Evidence 判定原因

## 安全

- 只读：不修改 Wiki / Vector DB / Gap；
- Fail Closed：LLM 不可用 / 异常 → 返回 `knowledge_missing` / `error`，绝不猜答案；
- 不绕过 Evidence 与 Judge；
- `raw_vector_db` 不作为生产 fallback。

## 未来

阶段⑪-B 将把 `knowledge_search` 包装为 MCP Tool（当前未实现）。


## MCP（Codex 正式接入，阶段⑪-B）

本地 stdio MCP Server：`90_System/agent/mcp_server.py`（Python 标准库，零外部依赖，只暴露一个只读 Tool `knowledge_search`）。

- Vault 根目录由环境变量 `KNOWLEDGE_OS_VAULT` 指定（缺省按本文件位置反推），**不依赖当前工作目录**。
- Codex 配置（`~/.codex/config.toml`）：`[mcp_servers.knowledge-os]` command=python, args=[mcp_server.py], env 含 `KNOWLEDGE_OS_VAULT`。
- 改配置后需**重启 Codex** 才会加载该 MCP Server；本会话不会自动出现该工具。

### Agent 使用规则

**应该调用 knowledge_search 的场景**（通用/长期工程知识）：

```text
STM32 / FreeRTOS / DMA / CAN / UART / SPI / PID / EKF /
传感器 / 电机控制 / 飞控原理 / 机器人控制 / 过去项目经验 / 已沉淀的工程知识
```

**不应该调用（直接读当前项目）**：

```text
当前项目代码 / 编译错误 / Git 状态 / 文件路径 / 变量定义 /
函数实现 / 构建系统 / 项目临时设计
```

**knowledge_missing 时**：可以基于当前项目 + 自身通用知识继续分析，但必须区分 `[Knowledge OS]` 与 `[Agent Reasoning]`，不得声称 Knowledge OS 包含答案。

## 安全

- MCP 接口只读：不暴露 approve/reject/resolve/edit/merge/write 等任何写工具；
- 不绕过 Evidence 与 LLM Judge；LLM 不可用 / 异常 → fail-closed 返回 `knowledge_missing` / `error`。
