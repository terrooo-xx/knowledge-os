# wiki_compile_agent

前置：执行本工作流前先阅读 `90_System/KNOWLEDGE_OS.md`（系统级架构、AI 权限与审核边界）。

职责：

- 输入用户问题、RAG chunks、已有 Wiki。
- 生成 `status: draft` 的 Markdown 到 `20_Wiki/<领域>/`。
- 保留来源，禁止覆盖 `reviewed` / `stable` 笔记。
- 使用双链关联已有知识。
