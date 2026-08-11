"""Performance optimization tests: reranker singleton, fast/deep modes, timeout.

All offline: LLM and models are mocked / injected.
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
AGENT_DIR = RAG_DIR.parent / "agent"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(AGENT_DIR))

import rag_engine.rerank as rerank
from knowledge_service import knowledge_search
from rag_engine.vector_store import VectorStore


# ---------- Reranker singleton ----------
def test_reranker_singleton_reuses_model():
    fake_st = types.ModuleType("sentence_transformers")
    class FakeCE:
        instances = []
        def __init__(self, name):
            FakeCE.instances.append(name)
        def predict(self, pairs):
            return [1.0] * len(pairs)
    fake_st.CrossEncoder = FakeCE
    saved = sys.modules.get("sentence_transformers")
    sys.modules["sentence_transformers"] = fake_st
    try:
        rerank._reranker_model = None
        rerank._reranker_provider = None
        rerank._reranker_model_name = None
        m1 = rerank._get_reranker("bge", "model-x")
        m2 = rerank._get_reranker("bge", "model-x")
        assert m1 is m2, "same (provider, model) must reuse the instance"
        assert len(FakeCE.instances) == 1, "model must be created once"
        m3 = rerank._get_reranker("bge", "model-y")
        assert len(FakeCE.instances) == 2, "different model creates a new instance"
    finally:
        if saved is not None:
            sys.modules["sentence_transformers"] = saved
        rerank._reranker_model = None
        rerank._reranker_provider = None
        rerank._reranker_model_name = None


# ---------- Fast / Deep / evidence_only ----------
def _cfg(judge_enabled=False, llm_provider="none"):
    return {
        "retrieval": {"wiki_first": True, "confidence_threshold": 0.78, "top_k": 5,
                      "dense_weight": 0.6, "bm25_weight": 0.4},
        "reranker": {"enabled": False, "provider": "none", "top_k": 5},
        "evidence_judge": {"enabled": judge_enabled, "top_k": 5},
        "llm": {"provider": llm_provider},
        "paths": {},
    }


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _store(tmp, text, source="20_Wiki/a.md"):
    st = VectorStore(str(Path(tmp) / "db"))
    st.add(text, {"source": source, "status": "stable", "document_path": source}, [1.0, 0.0, 0.0])
    return st


def _mock_llm(q, chunks, cfg):
    return "Mock answer that is long enough to pass the answer quality gate." + "内容" * 5


def test_deep_mode_generates_answer():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        r = knowledge_search("STM32 DMA 怎么配置？", mode="deep", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        assert r["status"] == "answerable"
        assert r["answer"] is not None
        assert r["mode"] == "deep"


def test_fast_mode_no_answer_keeps_judge_and_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式", "20_Wiki/03_STM32/DMA.md")
        r = knowledge_search("STM32 DMA 怎么配置？", mode="fast", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        assert r["status"] == "answerable"
        assert r["answer"] is None, "fast mode must not generate a long answer"
        assert r["evidence"][0]["source"] == "20_Wiki/03_STM32/DMA.md"
        assert r["sufficient"] is True


def test_evidence_only_mode_equivalent_to_fast():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "FreeRTOS 任务创建 osThreadNew")
        r = knowledge_search("FreeRTOS 任务如何创建？", mode="evidence_only", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        assert r["answer"] is None
        assert r["evidence"]
        assert r["mode"] == "evidence_only"


def test_fast_mode_knowledge_missing_and_judge_reject():
    import rag_engine.retrieval as retrieval
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "工控机采用 Ubuntu + ROS2 + Nav2 运行环境", "30_Projects/x.md")
        original = retrieval.judge_relevance
        retrieval.judge_relevance = lambda q, c, cfg: {"relevance": "irrelevant", "reason": "无配置方法",
                                                       "confidence": 0.9, "error": False}
        try:
            r = knowledge_search("ROS2 Nav2 代价地图怎么配置？", mode="fast", use_llm=True,
                                 cfg=_cfg(judge_enabled=True, llm_provider="deepseek"),
                                 embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        finally:
            retrieval.judge_relevance = original
        assert r["status"] == "knowledge_missing"
        assert r["judge"]["relevance"] == "irrelevant"
        assert r["answer"] is None


# ---------- Timeout ----------
def test_answer_timeout_preserves_evidence():
    import openai
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式", "20_Wiki/03_STM32/DMA.md")
        def boom(q, chunks, cfg):
            raise openai.APITimeoutError(request=None)
        r = knowledge_search("STM32 DMA 怎么配置？", mode="deep", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=boom)
        assert r["status"] == "answer_generation_timeout"
        assert r["answer"] is None
        assert r["evidence"], "evidence must be preserved on answer timeout"
        assert r["sufficient"] is True


def test_answer_generation_error_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        def boom(q, chunks, cfg):
            raise RuntimeError("boom")
        r = knowledge_search("STM32 DMA 怎么配置？", mode="deep", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=boom)
        assert r["status"] == "error"
        assert r["sufficient"] is False
        assert r["answer"] is None


# ---------- Read-only ----------
def test_optimized_modes_are_read_only():
    gap_path = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\tests\knowledge_gaps.yaml")
    gap_before = gap_path.read_text(encoding="utf-8")
    act_path = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\control_center\activity_log.jsonl")
    act_before = act_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤")
        for mode in ("fast", "evidence_only", "deep"):
            knowledge_search("不存在的主题 QQQ 怎么处理？", mode=mode, use_llm=False, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=None)
    assert gap_path.read_text(encoding="utf-8") == gap_before
    assert act_path.read_text(encoding="utf-8") == act_before


if __name__ == "__main__":
    for t in (
        test_reranker_singleton_reuses_model,
        test_deep_mode_generates_answer,
        test_fast_mode_no_answer_keeps_judge_and_evidence,
        test_evidence_only_mode_equivalent_to_fast,
        test_fast_mode_knowledge_missing_and_judge_reject,
        test_answer_timeout_preserves_evidence,
        test_answer_generation_error_fail_closed,
        test_optimized_modes_are_read_only,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all performance optimization tests passed")