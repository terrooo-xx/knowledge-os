# Knowledge OS RAG 引擎

本目录是个人知识库的 RAG + LLM-Wiki 引擎，直接复用现有 Vault 目录（`00_Inbox` / `20_Wiki` / `30_Projects` / `90_System`）。

## 架构

```text
活动索引（默认路径）：
20_Wiki + 30_Projects --update_index.py（默认 --target main）--> main_vector_db

可选索引（代码已支持，当前库为空）：
00_Inbox --ingest_rag.py --target raw--> raw_vector_db
20_Wiki  --ingest_rag.py/update_index.py --target wiki--> wiki_vector_db

用户问题 --hybrid_query.py（默认 --store main）--> main_vector_db
  -> Dense + BM25 混合检索
  -> reranker
  -> evidence 评估
  -> LLM 回答 / Knowledge Gap

00_Inbox 源资料 --wiki_compile.py --action create/update/project--> 20_Wiki/<领域>/<标题>.md（status: draft）
```

## 数据流

1. 原始资料进入 `00_Inbox`（PDF / Markdown / TXT / HTML）；`inbox_processor.py` 分析分类，不修改原文。
2. 活动索引：`update_index.py`（默认 `--target main`）扫描 `20_Wiki` + `30_Projects`，chunk、embedding 后写入 `main_vector_db`，并用 `index_manifest.json` 做增量；metadata 保留 `source` / `status` / `document_path` / `document_hash` / `updated_at` 等。
3. 可选索引：`ingest_rag.py --target raw` 把 `00_Inbox` 写入 `raw_vector_db`；`--target wiki` 把 `20_Wiki` 写入 `wiki_vector_db`（当前均为空，未启用）。
4. 查询时 `hybrid_query.py`（默认 `--store main`）检索 `main_vector_db`：Dense + BM25 融合，可选 reranker，evidence 评估后由 LLM 回答；证据不足记录 Knowledge Gap。
5. 需要沉淀时用 `wiki_compile.py`（`--action create/update/project --file`）生成 `status: draft` 的知识页到 `20_Wiki/<领域>/` 或更新建议到 `90_System/任务记录/`。

## 依赖安装

首次使用前安装 Python 依赖：

```powershell
pip install -r 90_System/rag/requirements.txt
BGE embedding 与 BGE/Jina reranker 都由 sentence-transformers 加载，不依赖 FlagEmbedding。
```

## 如何添加资料

把文件放入 `00_Inbox`，用 Inbox Processor 分析分类（只读原文）：

```powershell
python 90_System/rag/scripts/inbox_processor.py
```

`main_vector_db` 由 `update_index.py` 统一维护（标准索引入口）；`ingest_rag.py` 用于可选 raw/wiki 索引，必须显式指定 `--target`：`--target raw` 建立 `00_Inbox -> raw_vector_db`，`--target wiki` 建立 `20_Wiki -> wiki_vector_db`：

```powershell
python 90_System/rag/scripts/ingest_rag.py --target raw
```

重建活动索引（`20_Wiki` + `30_Projects` -> `main_vector_db`）：

```powershell
python 90_System/rag/scripts/update_index.py
```

Reranker 默认启用（`reranker.enabled: true`），模型使用本机缓存路径，不重新下载。

## 如何运行 RAG

默认 `llm.provider: deepseek`，调用 DeepSeek API 前先设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY="你的密钥"
```

只有 `--no-llm` 模式不调用任何 LLM。

## LLM Adapter

`90_System/rag/llm/` 提供统一 `generate(question, context)` 接口：

- `deepseek_adapter.py`：DeepSeek API，读取 `DEEPSEEK_API_KEY`
- `openai_adapter.py`：OpenAI 或任意 OpenAI 兼容端点
- `ollama_adapter.py`：Ollama 本地服务
- `mock_adapter.py`：离线测试用

RAG 核心只调用 `llm.answer()`，不感知具体 provider。Prompt 模板位于 `90_System/rag/prompts/rag_answer.md`，包含 System 角色、`{{context}}` 和 `{{question}}` 占位符。

## 如何运行 RAG

```powershell
python 90_System/rag/scripts/hybrid_query.py "STM32F405 的 DMA 怎么配置"
```

不调用 LLM（只输出检索上下文）：

```powershell
python 90_System/rag/scripts/hybrid_query.py "问题" --no-llm
```

## 如何生成 Wiki

基于 `00_Inbox` 源资料编译 draft（需要 LLM provider）：

```powershell
python 90_System/rag/scripts/wiki_compile.py --action create --file "00_Inbox/待处理文件/xxx.md" --domain 03_STM32
```

- `--action create`：生成 `status: draft` Wiki 到 `20_Wiki/<领域>/`，禁止覆盖 `reviewed / stable`。
- `--action update`：为已有 Wiki 生成更新建议到 `90_System/任务记录/`，不直接改 Wiki。
- `--action project`：为 `30_Projects` 生成项目文档 draft。
- 说明：旧接口 `--question / --chunks` 与 `hybrid_query.py --compile-wiki` 均已移除；`wiki_compile.py` 是唯一正式 Wiki 编译入口。

## Obsidian 集成

- Wiki 状态用 frontmatter：`draft` -> `reviewed` -> `stable`，不建状态目录。
- 禁止覆盖 `reviewed` / `stable` 笔记；已存在的 draft 需加 `--force` 才能更新。
- 笔记之间使用双链 `[[笔记名]]`。

## 配置

- `config.yaml`：embedding（`openai` / `bge`）、store（`local` / `chroma`）、retrieval 权重、reranker、llm、wiki 默认领域。LLM 支持 `none` / `deepseek` / `openai` / `openai_compatible` / `ollama` / `mock`；API Key 一律从环境变量读取，不写入配置或知识库。
- API Key 从环境变量读取（`OPENAI_API_KEY`），不写入知识库。
- `database/` 和 `cache/` 已加入 `.gitignore`。


## Inbox Processor

`scripts/inbox_processor.py` 扫描 `00_Inbox`，提取文本并自动分类：

- `create_wiki`：知识库没有对应 Wiki，建议新建 draft。
- `update_wiki`：已有 Wiki 可能缺少新内容，只生成更新建议，不覆盖。
- `project_update`：内容属于具体项目，建议进入 `30_Projects`。
- `no_new_wiki`：与已有 Wiki 高度重复，记录 `matched_wiki` 与相似度。
- `keep_raw`：无法提取文本（如图片型 PDF）或不需要整理，保留原始资料。

默认只分析并写入 `90_System/任务记录/inbox_processor_log.md`，不移动、删除、覆盖原始文件。`--apply` 才会为 `create_wiki` 生成 `status: draft` 的新 Wiki。

## Knowledge Gap

查询流程增加 Evidence Assessment：`query → retrieval → reranker → evidence → answer / knowledge_gap`。

当证据不足时不会让 DeepSeek 用外部知识补全，而是返回“当前知识库没有足够资料支持这个问题”，并记录到 `tests/knowledge_gaps.yaml`：

- `knowledge_missing`：缺少主题词对应知识
- `knowledge_insufficient`：有相关内容但不足以回答
- `knowledge_conflict`：存在矛盾信息
- `retrieval_problem`：知识存在但检索未命中
- `answer_quality_problem`：检索正确但回答不完整

## Evidence Assessment

`rag_engine/evidence.py` 根据 chunk 数量、Reranker 最高分、Wiki `status`、来源数量与主题词命中情况判断是否足以回答。查询结果包含 `evidence` 和 `gap_type` 字段，供后续来源追溯和可信度控制使用。


## LLM-Wiki Compiler

`scripts/wiki_compile.py` 提供真实 Wiki 编译（不是占位符）：

- `--action create`：根据 Inbox 资料生成完整 `status: draft` Wiki，frontmatter 含 `source / confidence / review_required`，禁止覆盖 `reviewed / stable`。
- `--action update`：生成 Wiki 更新建议到 `90_System/任务记录/Wiki更新建议_*.md`，只产出 proposal，不直接修改 Wiki。
- `--action project`：为 `30_Projects` 对应项目生成项目文档 draft。

`scripts/wiki_review.py` 管理状态流转：

- `--list` / `--show`：查看 Wiki 与状态。
- `--approve`：`draft -> reviewed`。
- `--stabilize`：`reviewed -> stable`。
- 默认禁止 `draft -> stable`，只有显式 `--force` 才允许。

## Incremental RAG

`scripts/update_index.py --target main` 使用 `database/index_manifest.json` 记录文档 `sha256 / chunk 数 / 索引时间`：

- `--changed`：只处理新增、修改、删除的文档，不重新 embedding 未变化文档。
- `--file xxx.md`：只处理单个文档。
- 删除文档会同步清理对应 chunks；draft 允许进入 RAG，metadata 保留 `status / source / document_hash / updated_at`。

## RAG 数据恢复流程

发现数据库损坏（如 `records.jsonl` / `index_manifest.json` 出现 NUL 字节、JSON 解析失败、manifest 与 records 不一致）：

```text
发现损坏
  → 停止写入（不要继续 update_index / ingest_rag）
  → 备份当前损坏文件（改名保留，如 .corrupt-<日期>）
  → 验证备份可读
  → 全量 rebuild：python 90_System/rag/scripts/update_index.py
  → 健康检查：python 90_System/rag/scripts/rag_health_check.py
  → 查询验证：python 90_System/rag/scripts/hybrid_query.py "问题"
```

注意事项：

- `rag_health_check.py` / `wiki_health_check.py` 默认**只读**，只发现问题并报告，不自动修复。
- 运行会写数据库的脚本时，不要用 `Select-Object -First` / `head` / `tail` 等管道截断方式提前终止进程——写入中途被杀会留下半写入/全 NUL 文件（本项目历史事故原因）。
- 索引写入已使用原子替换（临时文件 → 校验 → `os.replace`），异常退出时旧文件保持可用。

## 技术取舍

- 不引入 LangChain / LlamaIndex：个人库管线很短，直接适配器更轻、更容易读。
- 默认本地 JSONL 向量库，支持切换 Chroma；Qdrant 可通过相同 store 接口扩展。
- BM25 为纯 Python 实现，支持专业术语、芯片型号、函数名的关键词精确匹配。
