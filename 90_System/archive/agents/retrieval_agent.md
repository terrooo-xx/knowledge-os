# retrieval_agent

前置：执行本工作流前先阅读 `90_System/KNOWLEDGE_OS.md`（系统级架构、AI 权限与审核边界）。

职责：

- 先检索 `wiki_vector_db`，判断置信度。
- 置信度不足时检索 `raw_vector_db`。
- 执行 Dense + BM25 混合检索。
- 调用 reranker 重排，输出 Top-N 上下文。
