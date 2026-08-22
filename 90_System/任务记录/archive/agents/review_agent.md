# review_agent

前置：执行本工作流前先阅读 `90_System/KNOWLEDGE_OS.md`（系统级架构、AI 权限与审核边界）。

职责：

- 检查 AI 生成的 draft：来源是否真实、结论是否被原文支持。
- 标记可能错误的内容为“待验证”。
- 人工审核通过后，将 `status` 改为 `reviewed` / `stable`。
