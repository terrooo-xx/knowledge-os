# 知识库变更记录

## 2026-08-11

### 新增
- .agents/agents/ingest_agent.md
- .agents/agents/retrieval_agent.md
- .agents/agents/review_agent.md
- .agents/agents/wiki_compile_agent.md
- 30_Projects/移动底盘控制器/硬件选型/STM32主控选型.md
- 30_Projects/移动底盘控制器/硬件选型/工控机选型.md
- 30_Projects/移动底盘控制器/项目适配/适配电机选型.md
- 30_Projects/移动底盘控制器/项目适配/项目适配场景.md
- 90_System/control_center/activity_log.jsonl
- 90_System/control_center/server.py
- 90_System/control_center/service.py
- 90_System/control_center/static/index.html
- 90_System/rag/AGENTS.md
- 90_System/rag/README.md
- 90_System/rag/config.yaml
- 90_System/rag/llm/__init__.py
- 90_System/rag/llm/base_adapter.py
- 90_System/rag/llm/context.py
- 90_System/rag/llm/deepseek_adapter.py
- 90_System/rag/llm/mock_adapter.py
- 90_System/rag/llm/ollama_adapter.py
- 90_System/rag/llm/openai_adapter.py
- 90_System/rag/llm/prompt.py
- 90_System/rag/prompts/relevance_judge.md
- 90_System/rag/rag_engine/__init__.py
- 90_System/rag/rag_engine/atomic_io.py
- 90_System/rag/rag_engine/bm25.py
- 90_System/rag/rag_engine/config.py
- 90_System/rag/rag_engine/embeddings.py
- 90_System/rag/rag_engine/evidence.py
- 90_System/rag/rag_engine/gaps.py
- 90_System/rag/rag_engine/inbox_classifier.py
- 90_System/rag/rag_engine/indexing.py
- 90_System/rag/rag_engine/ingest.py
- 90_System/rag/rag_engine/judge.py
- 90_System/rag/rag_engine/llm.py
- 90_System/rag/rag_engine/rerank.py
- 90_System/rag/rag_engine/retrieval.py
- 90_System/rag/rag_engine/vector_store.py
- 90_System/rag/rag_engine/wiki.py
- 90_System/rag/rag_engine/wiki_compiler.py
- 90_System/rag/rag_engine/wiki_review.py
- 90_System/rag/requirements.txt
- 90_System/rag/scripts/hybrid_query.py
- 90_System/rag/scripts/inbox_processor.py
- 90_System/rag/scripts/ingest_rag.py
- 90_System/rag/scripts/rag_health_check.py
- 90_System/rag/scripts/reranker.py
- 90_System/rag/scripts/update_index.py
- 90_System/rag/scripts/wiki_compile.py
- 90_System/rag/scripts/wiki_health_check.py
- 90_System/rag/scripts/wiki_review.py
- 90_System/rag/tests/config.local.yaml
- 90_System/rag/tests/fixtures/stm32_dma.md
- 90_System/rag/tests/knowledge_gaps.yaml
- 90_System/rag/tests/test_atomic_write.py
- 90_System/rag/tests/test_cli_contract.py
- 90_System/rag/tests/test_control_center.py
- 90_System/rag/tests/test_evidence_gaps.py
- 90_System/rag/tests/test_full_chain.py
- 90_System/rag/tests/test_inbox_processor.py
- 90_System/rag/tests/test_incremental_rag.py
- 90_System/rag/tests/test_judge.py
- 90_System/rag/tests/test_llm.py
- 90_System/rag/tests/test_main_query.py
- 90_System/rag/tests/test_paths.py
- 90_System/rag/tests/test_rag_health.py
- 90_System/rag/tests/test_review.py
- 90_System/rag/tests/test_smoke.py
- 90_System/rag/tests/test_wiki_compiler.py
- 90_System/rag/tests/test_wiki_health.py
- 90_System/任务记录/Wiki更新建议_20260810_003.md
- 90_System/任务记录/inbox_processor_log.md
- 90_System/任务记录/本次PDF知识导入分析.md
- 90_System/阶段06_PDF与Source转写与Fallback评估.md
- 90_System/阶段07_Knowledge_OS_Control_Center.md
- 90_System/阶段08_Knowledge_OS_稳定化与闭环验证.md
- 90_System/阶段09_Evidence_Intelligence与知识回答安全增强.md
- 90_System/阶段10_Knowledge_OS_v1.0基线与生产运行验证.md
- 90_System/control_center/create_desktop_shortcut.bat
- 90_System/control_center/start_control_center.bat
- 90_System/阶段10.5_Control_Center启动体验优化.md
- 90_System/control_center/launch_test.cmd
- 90_System/control_center/launcher_test.log
- 90_System/control_center/test2.log

### 修改
- 90_System/KNOWLEDGE_OS.md

### 提交
- 提交 c121a31：Knowledge OS v1.0 baseline

## 2026-08-10 LLM-Wiki MVP

## 2026-08-10

### 新增
- 20_Wiki/01_计算机基础/CPU与寄存器.md
- 20_Wiki/02_嵌入式基础/AS5600磁编码器.md
- 20_Wiki/02_嵌入式基础/CLion嵌入式开发环境.md
- 20_Wiki/02_嵌入式基础/DC-DC与LDO选择.md
- 20_Wiki/02_嵌入式基础/DC电源插座引脚.md
- 20_Wiki/02_嵌入式基础/DRV8845电机驱动.md
- 20_Wiki/02_嵌入式基础/LED限流电阻选型.md
- 20_Wiki/02_嵌入式基础/MPU-6050惯性测量单元.md
- 20_Wiki/02_嵌入式基础/电容选型.md
- 20_Wiki/02_嵌入式基础/电机驱动选型.md
- 20_Wiki/02_嵌入式基础/锂电池参数计算.md
- 20_Wiki/02_嵌入式基础/阻抗匹配.md
- 20_Wiki/03_STM32/STM32 USART配置与使用.md
- 20_Wiki/03_STM32/STM32CubeMX定时器配置.md
- 20_Wiki/03_STM32/STM32时钟树.md
- 20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md
- 20_Wiki/04_FreeRTOS/FreeRTOS任务调度与状态.md
- 20_Wiki/05_通信协议/PPM与S.Bus接收机信号.md
- 20_Wiki/05_通信协议/串口通信协议基础.md
- 30_Projects/无人机飞控/硬件选型.md
- 30_Projects/移动底盘控制器/功能说明.md
- 30_Projects/移动底盘控制器/硬件系统框架.md
- 30_Projects/移动底盘控制器/硬件选型/
- 30_Projects/移动底盘控制器/项目适配/
- 90_System/prompts/rag_answer.md
- 90_System/任务记录/
- 个人笔记/
- 00_Inbox/待处理文件/FreeRTOS任务通知补充资料.md
- 00_Inbox/待处理文件/STM32_DMA资料.md
- 00_Inbox/待处理文件/个人笔记/
- 20_Wiki/03_STM32/STM32-DMA-配置与使用.md
- 90_System/KNOWLEDGE_OS.md
- 90_System/archive/嵌入式课程设计/
- 90_System/prompts/wiki_compile.md

### 修改
- .agents/skills/knowledge-compiler/SKILL.md
- .agents/skills/project-doc-maintainer/SKILL.md
- .agents/skills/weekly-review/SKILL.md
- 30_Projects/无人机飞控/00_项目索引.md
- 30_Projects/移动底盘控制器/00_项目索引.md

## 2026-08-08

### 新增
- 新增 Knowledge OS RAG 引擎（`90_System/rag/`）：资料入库、索引更新、混合检索、重排序、Wiki 编译脚本及冒烟测试。
- 新增 RAG 引擎说明与配置（`90_System/rag/README.md`、`config.yaml`、`requirements.txt`、`AGENTS.md`）。
- 新增 Agent 定义（`.agents/agents/`）：ingest、retrieval、review、wiki_compile 四个工作流。

### 修改
- `AGENTS.md`：新增 Knowledge OS 规则；Wiki 状态字段由 `verified` / `deprecated` 调整为 `reviewed` / `stable`。
- `README.md`：新增 Knowledge OS 使用说明。
- `.gitignore`：排除 RAG 数据库与缓存、`__pycache__`、`*.pyc`。

## 2026-08-07

### 新增
- 新增 `interfaces.md`（空文件，待补充内容）。

## 2026-08-03

### 新增
- 初始化知识库目录结构。
- 创建知识库维护规则。
- 创建基础模板。
- 创建 Codex Skills。
