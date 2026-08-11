"""LLM Relevance Judge tests: parse, fail-closed, integration into answer_query.

All tests are offline: the judge LLM call is mocked via monkeypatch; no real
network / API is used.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

import rag_engine.judge as judge
import rag_engine.retrieval as retrieval
from rag_engine.retrieval import answer_query
from rag_engine.vector_store import VectorStore


def _cfg(judge_enabled=True, llm_provider="deepseek"):
    return {
        "retrieval": {"wiki_first": True, "confidence_threshold": 0.78, "top_k": 5,
                      "dense_weight": 0.6, "bm25_weight": 0.4},
        "reranker": {"enabled": False, "provider": "none", "top_k": 5},
        "evidence_judge": {"enabled": judge_enabled, "top_k": 5},
        "llm": {"provider": llm_provider},
    }


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _store(tmp, text, source="20_Wiki/a.md", status="stable"):
    store = VectorStore(str(Path(tmp) / "db"))
    store.add(text, {"source": source, "status": status, "document_path": source}, [1.0, 0.0, 0.0])
    return store


def _mock_llm(question, chunks, cfg):
    return "Mock answer with enough length to pass the answer gate."


# ---------- unit: parse ----------
def test_parse_valid_relevant():
    r = judge.parse_judge_output('{"relevance": "relevant", "reason": "ok", "confidence": 0.95}')
    assert r["relevance"] == "relevant" and r["error"] is False


def test_parse_valid_irrelevant():
    r = judge.parse_judge_output('{"relevance": "irrelevant", "reason": "只提到关键词", "confidence": 0.9}')
    assert r["relevance"] == "irrelevant"


def test_parse_fenced_json():
    r = judge.parse_judge_output('```json\n{"relevance": "relevant", "reason": "x", "confidence": 0.8}\n```')
    assert r["relevance"] == "relevant"


def test_parse_invalid_json_fail_closed():
    r = judge.parse_judge_output("not json at all")
    assert r["relevance"] == "irrelevant" and r["error"] is True


def test_parse_empty_fail_closed():
    r = judge.parse_judge_output("")
    assert r["relevance"] == "irrelevant" and r["error"] is True


def test_judge_enabled_offline_false():
    assert judge.judge_enabled(_cfg(llm_provider="none")) is False
    assert judge.judge_enabled(_cfg(llm_provider="mock")) is False
    assert judge.judge_enabled(_cfg(llm_provider="deepseek")) is True
    assert judge.judge_enabled(_cfg(judge_enabled=False)) is False


# ---------- integration via answer_query (mock judge) ----------
def test_judge_relevant_keeps_sufficient():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "FreeRTOS 任务创建：osThreadNew，设置 stack_size 和 priority")
        original = retrieval.judge_relevance
        retrieval.judge_relevance = lambda q, c, cfg: {"relevance": "relevant", "reason": "ok", "confidence": 0.95, "error": False}
        try:
            result = answer_query("FreeRTOS 任务如何创建？", _cfg(), FakeEmbedder(), store, store, llm_answer=_mock_llm)
        finally:
            retrieval.judge_relevance = original
        assert result["evidence"]["sufficient"] is True
        assert result["judge"]["relevance"] == "relevant"


def test_judge_irrelevant_downgrades_to_missing():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "工控机采用 Ubuntu + ROS2 + Nav2 运行环境")
        original = retrieval.judge_relevance
        retrieval.judge_relevance = lambda q, c, cfg: {"relevance": "irrelevant", "reason": "只提到Nav2，没有配置方法", "confidence": 0.9, "error": False}
        try:
            result = answer_query("ROS2 Nav2 代价地图怎么配置？", _cfg(), FakeEmbedder(), store, store, llm_answer=_mock_llm)
        finally:
            retrieval.judge_relevance = original
        assert result["evidence"]["sufficient"] is False
        assert result["evidence"]["gap_type"] == "knowledge_missing"
        assert result["judge"]["relevance"] == "irrelevant"


def test_judge_failure_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤")
        original = retrieval.judge_relevance
        def boom(q, c, cfg):
            raise TimeoutError("LLM timeout")
        retrieval.judge_relevance = boom
        try:
            result = answer_query("STM32 DMA 怎么配置？", _cfg(), FakeEmbedder(), store, store, llm_answer=_mock_llm)
        finally:
            retrieval.judge_relevance = original
        assert result["evidence"]["sufficient"] is False
        assert result["evidence"]["gap_type"] == "knowledge_missing"


def test_judge_disabled_keeps_original_behavior():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        result = answer_query("STM32 DMA 怎么配置？", _cfg(judge_enabled=False), FakeEmbedder(), store, store, llm_answer=_mock_llm)
        assert result["evidence"]["sufficient"] is True
        assert result["judge"] is None


def test_judge_skipped_offline_no_llm():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        result = answer_query("STM32 DMA 怎么配置？", _cfg(llm_provider="none"), FakeEmbedder(), store, store, llm_answer=None)
        assert result["judge"] is None
        assert result["evidence"]["sufficient"] is True


if __name__ == "__main__":
    for t in (
        test_parse_valid_relevant, test_parse_valid_irrelevant, test_parse_fenced_json,
        test_parse_invalid_json_fail_closed, test_parse_empty_fail_closed,
        test_judge_enabled_offline_false,
        test_judge_relevant_keeps_sufficient, test_judge_irrelevant_downgrades_to_missing,
        test_judge_failure_fails_closed, test_judge_disabled_keeps_original_behavior,
        test_judge_skipped_offline_no_llm,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all judge tests passed")
