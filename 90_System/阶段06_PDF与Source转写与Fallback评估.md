---
type: system
status: draft
domain: 系统评估
created: 2026-08-11
updated: 2026-08-11
---

# 阶段⑥：PDF / Source 转写与 Source Fallback 评估

> 本文档是 Knowledge OS 阶段⑥的评估报告，回答三个问题：
> ① Source Pipeline（PDF→Source→Chunk→Embedding→RAG）是否可用；
> ② Wiki 不足时能否可靠执行 Source/RAG Fallback；
> ③ raw_vector_db 是否值得存在。
> 本阶段只评估与抽样验证，未批量 OCR、未重建数据库、未升级任何 Wiki 状态、未修改代码。

## 1. 评估目标

- 用实际数据确认 PDF/Source 管线的可用性与转写质量；
- 验证 Wiki→Source Fallback 的四情形（A 直接回答 / B-C 回退补充 / D 无数据→Gap）；
- 基于重复度、维护成本、查询复杂度等维度给出 raw_vector_db 取舍建议；
- 遵循最小复杂度原则，只提最小改进建议，不扩大系统。

## 2. 当前项目实际 Pipeline（以代码为准）

```text
PDF / md / txt / html --ingest.parse_file（pypdf 提取文本层）--> text
  --> chunk_text（800 字 / overlap 100）
  --> embedder（BGE-small-zh-v1.5）
  --> VectorStore（本地 JSONL）

生产路径：20_Wiki + 30_Projects --update_index.py --target main--> main_vector_db（默认查询）
可选路径：00_Inbox --ingest_rag.py --target raw--> raw_vector_db（当前为空/测试 2 chunk）
         20_Wiki --update_index.py --target wiki--> wiki_vector_db（当前为空）

查询：hybrid_query.py --store main（默认，raw_store=wiki_store=main_vector_db）
      --store raw（raw_store=raw_vector_db，wiki_store=wiki_vector_db，显式才走双库）
链路：Dense+BM25 --> reranker(BGE) --> evidence --> LLM --> Answer / Knowledge Gap
```

- PDF 处理：`rag_engine/ingest.py::parse_file` 用 pypdf `extract_text()` 仅提取文本层，无 OCR。
- 已具备原子写保护与 RAG/Wiki Health Check（阶段④）。

## 3. 33 个 PDF 盘点结果

位置：`00_Inbox/待处理文件/个人笔记/`（33 个）。

| # | 文件 | MB | 页 | 字符 | 文本层 | 疑似扫描 | 可提取性 | OCR需求 |
|---|---|---|---|---|---|---|---|---|
| 1 | CLion开发/CLion使用指南.note.pdf | 2.21 | 13 | 1908 | Yes | No | 高 | 低 |
| 2 | CPU与寄存器关系解析.note.pdf | 0.19 | 3 | 1280 | Yes | No | 中 | 中 |
| 3 | FreeRTOS/CubeMX配置/CubeMX中FreeRTOS的配置项说明.note.pdf | 0.30 | 8 | 5401 | Yes | No | 高 | 低 |
| 4 | FreeRTOS/CubeMX配置/CubeMX配置FreeRTOS.note.pdf | 0.51 | 2 | 545 | Yes | No | 中 | 中 |
| 5 | FreeRTOS/FreeRTOS任务状态.note.pdf | 0.82 | 3 | 661 | Yes | No | 中 | 中 |
| 6 | FreeRTOS/FreeRTOS优先级与抢占式调度.note.pdf | 0.15 | 2 | 692 | Yes | No | 中 | 中 |
| 7 | FreeRTOS/FreeRTOS工作框架.note.pdf | 0.21 | 3 | 1220 | Yes | No | 中 | 中 |
| 8 | STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf | 0.19 | 2 | 1521 | Yes | No | 高 | 低 |
| 9 | STM32/STM32cubeMx使用笔记/时钟树.note.pdf | 0.30 | 2 | 1436 | Yes | No | 中 | 中 |
| 10 | STM32/stm32笔记.note.pdf | 27.81 | 7 | 0 | **No** | **Yes** | 低 | **高** |
| 11 | STM32/串口通信.note.pdf | 0.28 | 3 | 372 | Yes | No | 中 | 中 |
| 12 | 个人数据库Obsidian/Git 配置.note.pdf | 0.19 | 2 | 245 | Yes | No | 低 | 高 |
| 13 | 个人数据库Obsidian/安装与配置.note.pdf | 0.57 | 2 | 47 | **No** | **Yes** | 低 | **高** |
| 14 | 无人机开发/硬件选型.note.pdf | 0.11 | 1 | 443 | Yes | No | 中 | 中 |
| 15 | 模块_芯片_硬件笔记/DC电源插座引脚说明.note.pdf | 0.51 | 1 | 383 | Yes | No | 中 | 中 |
| 16 | 模块_芯片_硬件笔记/IMU（惯性测量单元）/MPU-6050.note.pdf | 0.09 | 1 | 98 | Yes | No | 低 | 高 |
| 17 | 模块_芯片_硬件笔记/LED限流电阻选型.note.pdf | 0.10 | 1 | 216 | Yes | No | 低 | 高 |
| 18 | 模块_芯片_硬件笔记/串口使用及分类.note.pdf | 0.13 | 1 | 604 | Yes | No | 中 | 中 |
| 19 | 模块_芯片_硬件笔记/接收机/信号区分（PPM、S.Bus）.note.pdf | 0.29 | 3 | 1918 | Yes | No | 高 | 低 |
| 20 | 模块_芯片_硬件笔记/电容.note.pdf | 0.18 | 1 | 760 | Yes | No | 中 | 中 |
| 21 | 模块_芯片_硬件笔记/电机驱动/DRV8845 电机驱动.note.pdf | 0.29 | 2 | 1463 | Yes | No | 中 | 中 |
| 22 | 模块_芯片_硬件笔记/电机驱动/电机驱动选型.note.pdf | 0.15 | 2 | 983 | Yes | No | 中 | 中 |
| 23 | 模块_芯片_硬件笔记/电源/锂电池参数计算.note.pdf | 0.10 | 1 | 434 | Yes | No | 中 | 中 |
| 24 | 模块_芯片_硬件笔记/稳压（DcDc、LDO)/DC-DC（开关电源）与 LDO（线性稳压器）的选择.note.pdf | 0.20 | 2 | 673 | Yes | No | 中 | 中 |
| 25 | 模块_芯片_硬件笔记/编码器/AS5600磁编码器.note.pdf | 0.16 | 1 | 760 | Yes | No | 中 | 中 |
| 26 | 模块_芯片_硬件笔记/阻抗匹配.note.pdf | 0.28 | 2 | 968 | Yes | No | 中 | 中 |
| 27 | 移动底盘控制器_硬件搭建/功能简要.note.pdf | 0.23 | 10 | 3011 | Yes | No | 高 | 低 |
| 28 | 移动底盘控制器_硬件搭建/硬件系统框架.note.pdf | 0.20 | 5 | 3927 | Yes | No | 高 | 低 |
| 29 | 移动底盘控制器_硬件搭建/硬件选型/STM32主控选型.note.pdf | 0.20 | 6 | 1751 | Yes | No | 高 | 低 |
| 30 | 移动底盘控制器_硬件搭建/硬件选型/工控机选型.note.pdf | 0.15 | 1 | 625 | Yes | No | 中 | 中 |
| 31 | 移动底盘控制器_硬件搭建/项目适配工作场景/适配电机选型.note.pdf | 0.26 | 3 | 1717 | Yes | No | 高 | 低 |
| 32 | 移动底盘控制器_硬件搭建/项目适配工作场景/项目适配场景.note.pdf | 0.04 | 1 | 32 | **No** | No | 低 | **高** |
| 33 | 进制转换.note.pdf | 0.22 | 3 | 0 | **No** | **Yes** | 低 | **高** |

## 4. PDF 类型分类

| 类型 | 数量 | 代表 | 说明 |
|---|---|---|---|
| A. 文本型（高可提取） | 8 | CLion使用指南、CubeMX中FreeRTOS、定时器配置、PPM/S.Bus、功能简要、硬件系统框架、STM32主控选型、适配电机选型 | 文本层完整，可直接转写 |
| B. 文本型（中可提取） | 18 | CPU、时钟树、DRV8845、电容、阻抗匹配、串口等 | 文本层存在，含表格/图注，提取有少量断行噪音 |
| C. 文本极少（有层但内容少） | 3 | Git 配置(245)、MPU-6050(98)、LED限流(216) | 源 PDF 本身内容极少（与对应 Wiki 过短一致） |
| D. 无文本层 / 图片型 | 4 | stm32笔记(27.8MB)、安装与配置、项目适配场景、进制转换 | 需 OCR 才能进 RAG |

## 5. PDF → Source 测试结果

抽样（pypdf，即现有 ingest 管线）：

- 文本型（CLion / 时钟树 / DRV8845）：提取完整，标题/正文/参数均可读；`.note.pdf` 导出常见"字符间空格"噪音，但不影响 chunk 与检索；**无乱码、无页眉页脚污染、无页码污染**。
- 图文混合（定时器配置 / 电容）：表格提取为顺序文本行（如 LDO/DC-DC ESR 对比表），丢失二维结构但语义保留，可用于检索。
- 图片型（进制转换 / stm32笔记）：`extract_text()` 返回 0~近 0 字符 → **无法直接转写**，需 OCR（本阶段不做）。
- 结论：**29/33（88%）PDF 可直接被现有管线转写为 Source；转写质量为"可用"**（表格二维结构丢失是主要局限）。

## 6. OCR 是否必要

- 必要范围：仅 4 个无文本层 PDF（stm32笔记、安装与配置、项目适配场景、进制转换）。其中 stm32笔记 27.8MB 大文件、进制转换/安装与配置为纯扫描件。
- 不必要范围：其余 29 个有文本层。
- 建议：不为形式完整而全量 OCR；这 4 个 PDF 保留为原始 Source，待后续单独评估（可 OCR 后转 Wiki，或仅建来源索引不进 RAG）。**本阶段不实施 OCR。**

## 7. Source Metadata 追踪能力

- Wiki 摄入（main）：metadata 含 `source / source_frontmatter / document_path / document_hash / status / domain / type / updated_at` —— 可双向追踪（Wiki→源 PDF、源→Wiki）。
- raw 摄入（`ingest_rag --target raw`）：metadata 含 `source（相对 inbox 路径）/ page / document_type / created_time`，**无 document_path/document_hash/status** —— 可追溯到 PDF 路径，但无哈希/状态信息（raw 本身不参与状态机制，符合设计）。
- 阶段⑤已修正 17 篇 Wiki 的 source 路径，当前 Wiki 的 source 均可解析到存在的文件（Wiki Health PASS=20）。
- 结论：追踪能力满足需求；raw 的 source 指向 Inbox 相对路径，可定位原文件。

## 8. Source → RAG 测试结果

实测（写入可选 raw_vector_db 2 个测试 chunk，非生产 main）：

```text
ingest_rag.py --target raw --file ".../Git 配置.note.pdf"   → 1 chunk（EXIT=0）
ingest_rag.py --target raw --file ".../电容.note.pdf"       → 1 chunk（EXIT=0）

hybrid_query.py --store raw "Obsidian 的 Git 怎么配置？" --no-llm
  → source=raw，top=Git 配置.note.pdf，conf=0.543，sufficient=False，gap=knowledge_missing
```

- **Source→RAG 管线可用**：PDF 可解析、chunk、embedding、写入 raw、检索命中正确源。
- evidence 门控生效：该源文本过薄（245 字符）+ 主题词不完全匹配 → 判 insufficient → 记录 gap，**不硬答**（安全行为，符合"证据不足不编造"）。

## 9. Wiki → Source Fallback 测试结果

四情形实测（默认 main 库 + 可选 raw 库）：

| 情形 | 问题 | 结果 |
|---|---|---|
| A：Wiki 已有答案 | "电容 ESR 对 LDO 稳定性的影响？" | main 命中 `20_Wiki/02_嵌入式基础/电容选型.md`，sufficient=True ✅ |
| B/C：Wiki 不足→Source | "Obsidian 的 Git 怎么配置？" | main：命中 CubeMX配置FreeRTOS/CLion 等**无关 Wiki**，conf=1.0、sufficient=True ❌（高相似误答，见 §12-1）；`--store raw`：命中 `Git 配置.note.pdf`，但 conf=0.543 → insufficient→gap |
| D：Wiki+Source 都无 | "PX4 EKF 参数怎么调？" | main：无命中，conf=0.007，gap=knowledge_missing ✅（正确报缺口） |

- 结论：**Fallback 机制代码存在且可运行（--store raw 双库路由），但未接入默认生产路径**；默认 main 是"单库两遍检索"，不会自动回退到 Inbox Source。启用 fallback 需要：手动 ingest raw + 显式 `--store raw`；且 evidence 阈值会对薄 Source 判不足（安全）。

## 10. Gap Fallback 流程

- 证据不足时 `evidence.py` 分类：`knowledge_missing / knowledge_insufficient / retrieval_problem / answer_quality_problem`，`hybrid_query.py` 写入 `knowledge_gaps.yaml`（去重，status=pending）。
- 当前 1 条 pending（"STM32F405 DMA如何搬运数据"）已被 stable DMA Wiki 覆盖 → 阶段⑤已标记 RESOLVED_CANDIDATE，未自动 resolve。
- 结论：Gap 流程可用；无数据→Gap 的闭环已验证（情形 D）。

## 11. raw_vector_db 评估

| 维度 | 方案 A（Source→现有 main，不启用 raw） | 方案 B（Source→raw_vector_db，fallback） |
|---|---|---|
| 数据重复 | 低（Source 编译成 Wiki 后进 main） | **高**（同一批 PDF 既是 Wiki 来源又在 raw） |
| 查询路径复杂度 | 低（默认 main） | 中（需显式 --store raw + 双库维护） |
| 维护成本 | 低 | 中高（每次 Inbox 变动都要 ingest raw） |
| 更新成本 | 随 Wiki 审核联动 | 独立索引，易与 Wiki 版本不同步 |
| metadata 管理 | 完整（document_path/hash/status） | 只有 source 路径，无 hash/status |
| Source traceability | Wiki→源 PDF 双向可追 | 单向可追 |
| 检索质量 | Wiki 优先，质量高 | 原始文本，质量低于 Wiki |
| 是否改善 Wiki fallback | 默认无 fallback | 能回退到未沉淀 Source，但受 evidence 门控 |
| 系统复杂度 | 低 | 中 |

**推荐：A（暂不启用 raw 作为生产 fallback），raw 保留为可选工具（现状，不删除）。**
理由：
1. 当前 33 个 PDF 中约 22 个已是现有 20 篇 Wiki 的来源 → Source 与 Wiki **高度重复**，启用 raw 的边际价值低；
2. 未沉淀的 4 个图片型 PDF 无法直接进 raw（需 OCR），其余未沉淀的多为项目文档（已在 30_Projects / main）；
3. 默认 main 单索引 + Wiki 优先已能满足当前查询；启用 raw 需持续维护并引入双库一致性问题；
4. 最小复杂度原则：不为"架构看起来完整"增加一个当前无业务价值的索引。
（若未来出现大量"无需沉淀为 Wiki 的长尾原始资料"，再评估启用 B。）

## 12. 当前架构存在的问题

- **P1**：无。
- **P2**：
  1. **高相似误答**：main 对"Obsidian Git 配置"返回 CubeMX/CLion 等无关 Wiki 且 conf=1.0、sufficient=True——evidence 只看检索分数，不校验"是否真的回答了问题"，存在答非所问风险（真实复现）。
  2. **默认路径无 Source fallback**：Wiki 不足时 main 不会自动回退到 Inbox Source；fallback 需显式 `--store raw` + 手动 ingest。
  3. **图片型 PDF 不可检索**：4 个无文本层 PDF 只能人工阅读，无法进 RAG（已知，待 OCR 决策）。
  4. **表格结构丢失**：PDF 表格提取为顺序文本，二维结构丢失。
  5. raw 测试数据 2 chunk（Git配置/电容）留在 raw_vector_db，可随时清理（非生产）。

## 13. 最小改进建议

1. **evidence 语义校验**（P2-1）：在 evidence 中增加"主题词命中"之外的弱校验——如对高置信但来源全为 draft/无关领域时给出 `answer_quality` 提示，或要求 LLM 自评"是否回答了问题"。属于算法增强，列为阶段⑦候选，本阶段不改。
2. **Fallback 路由**（P2-2）：如未来启用，可在 `hybrid_query.py` 增加 `--store auto`：先 main，evidence 不足且 raw 非空时自动查 raw。本阶段不改。
3. **表格转写**：对表格型 PDF 可在转写脚本中尝试保留 Markdown 表格（现为顺序文本）；低优先。

## 14. 是否需要修改代码

**不需要。** 现有管线（pypdf 提取 → chunk → embed → main/raw 检索 → evidence → gap）已能完成全部验证；评估中发现的问题均为算法/策略增强，不属于本阶段"无法完成验证"的情形，故不改代码。

## 15. 下一阶段建议

```text
阶段⑥ PDF / Source 转写与 Fallback 评估 ← 本任务
  → 阶段⑦ Knowledge OS Control Center（人机协作界面：Wiki Review / Approve / Reject /
      Resolve Gap / Merge / Source 查看 / AI 待办 / Pipeline 状态 / 操作日志 / 人工决策）
```

阶段⑦仅作架构衔接说明，本阶段不实施。另有两项待你人工决策：① 4 个图片型 PDF 是否 OCR；② raw 测试数据是否清理。

---

*本文档由 AI 起草（2026-08-11），status: draft，待人工审核。*
