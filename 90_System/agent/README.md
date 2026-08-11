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
