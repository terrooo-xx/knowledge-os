# ingest_agent

前置：执行本工作流前先阅读 `90_System/KNOWLEDGE_OS.md`（系统级架构、AI 权限与审核边界）。

职责：

- 扫描 `00_Inbox`，识别新增原始资料。
- 解析 PDF / Markdown / TXT / HTML。
- 调用 `scripts/ingest_rag.py` 写入 `raw_vector_db`。
- 禁止修改 `00_Inbox` 原始文件。

规则：

- 向量库只保存 chunk 文本、embedding 和 metadata，不保存完整 PDF。
- metadata 必须包含 `source`、`page`、`created_time`、`document_type`。
