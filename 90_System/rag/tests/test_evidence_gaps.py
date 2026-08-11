"""Evidence Assessment and Knowledge Gap tests."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.evidence import assess_evidence
from rag_engine.gaps import record_gap

CFG = {"retrieval": {"confidence_threshold": 0.78}}


def _chunk(score, text, source="20_Wiki/a.md", status="draft"):
    return {
        "score": score,
        "rerank_score": score,
        "text": text,
        "metadata": {"source": source, "status": status},
    }


def test_knowledge_missing():
    evidence = assess_evidence("STM32F405 DMA如何搬运数据？", [], CFG)
    assert evidence["sufficient"] is False
    assert evidence["gap_type"] == "knowledge_missing"


def test_knowledge_insufficient():
    evidence = assess_evidence(
        "FreeRTOS 消息队列底层实现",
        [_chunk(0.5, "FreeRTOS 任务状态概述")],
        CFG,
    )
    assert evidence["gap_type"] == "knowledge_insufficient"


def test_retrieval_problem():
    evidence = assess_evidence(
        "CubeMX 如何配置 FreeRTOS",
        [_chunk(0.5, "CubeMX 配置 FreeRTOS 的入口", status="stable")],
        CFG,
    )
    assert evidence["gap_type"] == "retrieval_problem"


def test_answer_quality_problem():
    evidence = assess_evidence(
        "STM32 USART 如何配置",
        [_chunk(0.95, "STM32 USART 配置步骤完整说明")],
        CFG,
        answer="嗯",
    )
    assert evidence["gap_type"] == "answer_quality_problem"


def test_high_similarity_but_unrelated_is_insufficient():
    # Query topic terms (Obsidian, Git) are absent from the high-score chunk.
    evidence = assess_evidence(
        "Obsidian 的 Git 怎么配置？",
        [_chunk(0.98, "CLion 和 CubeMX 的工程配置步骤", status="stable")],
        CFG,
    )
    assert evidence["sufficient"] is False
    assert evidence["gap_type"] == "knowledge_missing"
    assert "主题词" in evidence["reason"]


def test_high_similarity_with_topic_coverage_is_sufficient():
    evidence = assess_evidence(
        "STM32 DMA 如何配置",
        [_chunk(0.95, "STM32 DMA 配置步骤：时钟、通道、模式", status="stable")],
        CFG,
        answer="先使能 DMA 和通道时钟，再配置数据方向、地址与传输模式。",
    )
    assert evidence["sufficient"] is True


def test_chinese_only_query_unaffected():
    # No ASCII topic tokens -> gate skipped, keeps previous behavior.
    evidence = assess_evidence(
        "电容怎么选型",
        [_chunk(0.95, "电容选型看 ESR 和耐压", status="draft")],
        CFG,
        answer="主要看输出侧 ESR 要求，传统 LDO 需要中等 ESR 配钽电容。",
    )
    assert evidence["sufficient"] is True


def test_sufficient():
    evidence = assess_evidence(
        "STM32 USART 如何配置",
        [_chunk(0.95, "STM32 USART 配置步骤完整说明")],
        CFG,
        answer="配置步骤：异步模式、PA9/PA10、中断。",
    )
    assert evidence["sufficient"] is True
    assert evidence["gap_type"] is None


def test_gap_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "gaps.yaml")
        gap = {
            "question": "STM32F405 DMA如何搬运数据？",
            "topic": "STM32/DMA",
            "type": "knowledge_missing",
            "suggested_action": "create_wiki",
        }
        assert record_gap(gap, path) is True
        assert record_gap(gap, path) is False
        from rag_engine.gaps import load_gaps

        assert len(load_gaps(path)) == 1



def test_gap_resolve_keeps_history():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "gaps.yaml")
        gap = {
            "question": "STM32F405 DMA如何搬运数据？",
            "topic": "STM32/DMA",
            "type": "knowledge_missing",
        }
        record_gap(gap, path)
        from rag_engine.gaps import load_gaps, resolve_gap

        assert resolve_gap(
            "STM32F405 DMA如何搬运数据？",
            path,
            resolved_by="test",
            resolved_sources=["20_Wiki/03_STM32/DMA.md"],
        ) is True
        gaps = load_gaps(path)
        assert gaps[0]["status"] == "resolved"
        assert gaps[0]["resolved_at"]
        assert gaps[0]["resolved_sources"] == ["20_Wiki/03_STM32/DMA.md"]

if __name__ == "__main__":
    for test in (
        test_knowledge_missing,
        test_knowledge_insufficient,
        test_high_similarity_but_unrelated_is_insufficient,
        test_high_similarity_with_topic_coverage_is_sufficient,
        test_chinese_only_query_unaffected,
        test_retrieval_problem,
        test_answer_quality_problem,
        test_sufficient,
        test_gap_dedup,
        test_gap_resolve_keeps_history,
    ):
        test()
        print(f"PASS {test.__name__}")
    print("all evidence/gap tests passed")