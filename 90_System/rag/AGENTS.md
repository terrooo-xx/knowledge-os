# Knowledge OS RAG 引擎规则

## 文件规则

- `00_Inbox`：原始资料真相源，AI 禁止修改，只允许新增文件。
- `20_Wiki`：允许 AI 生成 `draft`；人工审核后改为 `reviewed`；长期有效内容改为 `stable`。
- `90_System/rag/database` 与 `90_System/rag/cache`：向量数据库和缓存，禁止提交 Git。

## AI 规则

- AI 生成知识必须保留 `sources` 来源，禁止删除人工内容。
- 禁止覆盖 `reviewed` / `stable` 笔记。
- 知识笔记使用双链 `[[笔记名]]` 关联已有 Wiki。
- 笔记状态只使用 `draft` / `reviewed` / `stable`，写在 frontmatter，不按状态建目录。

## Git 规则

- 提交范围：`20_Wiki`、`30_Projects`、`.agents`、`90_System` 中的规则与脚本、`AGENTS.md`、模板。
- 忽略范围：`database/`、`cache/`、`*.bin`、`*.index`、`__pycache__/`、`*.pyc`。

## 执行流程

1. ingest_agent：扫描 `00_Inbox`，解析并写入 `raw_vector_db`。
2. update_index：扫描 `20_Wiki`，重建 `wiki_vector_db`。
3. retrieval_agent：wiki 优先，置信度不足再查 `raw_vector_db`，混合检索 + reranker。
4. wiki_compile_agent：根据 RAG chunks 生成 `draft`。
5. review_agent：检查 AI 生成内容，标记可能错误，人工审核后改状态。

## Inbox Processor 与 Knowledge Gap

- `inbox_processor.py` 只分析并生成建议，`--apply` 才生成新 draft Wiki；禁止覆盖 `reviewed` / `stable` 笔记。
- `hybrid_query.py` 默认查 `main_vector_db`；证据不足时返回固定提示并记录 Knowledge Gap，禁止用 LLM 外部知识冒充知识库内容。
- Knowledge Gap 文件：`tests/knowledge_gaps.yaml`，支持 `knowledge_missing` / `knowledge_insufficient` / `knowledge_conflict` / `retrieval_problem` / `answer_quality_problem`。

## LLM-Wiki 编译规则

- Compiler 只生成真实 draft 文档，禁止占位符；`update_wiki` 只生成 proposal，不直接改 Wiki。
- Review CLI 控制 `draft -> reviewed -> stable`，默认禁止 `draft -> stable`。
- Incremental RAG 通过 `index_manifest.json` 只处理变化文档；draft 可入 RAG 且保留 status metadata。
