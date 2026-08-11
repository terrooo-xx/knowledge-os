"""Agent Knowledge Interface tests (all offline, no real LLM / network)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
AGENT_DIR = RAG_DIR.parent / "agent"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(AGENT_DIR))

import rag_engine.retrieval as retrieval
from knowledge_service import knowledge_search
from rag_engine.vector_store import VectorStore


def _cfg(judge_enabled=False, llm_provider="none", threshold=0.78):
    return {
        "retrieval": {"wiki_first": True, "confidence_threshold": threshold, "top_k": 5,
                      "dense_weight": 0.6, "bm25_weight": 0.4},
        "reranker": {"enabled": False, "provider": "none", "top_k": 5},
        "evidence_judge": {"enabled": judge_enabled, "top_k": 5},
        "llm": {"provider": llm_provider},
        "paths": {},
    }


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _store(tmp, text, source="20_Wiki/a.md", status="stable"):
    st = VectorStore(str(Path(tmp) / "db"))
    st.add(text, {"source": source, "status": status, "document_path": source}, [1.0, 0.0, 0.0])
    return st


def _mock_llm(question, chunks, cfg):
    return "这是一个足够长的 Mock 回答，用于通过回答长度门控，并且包含必要内容。"


def test_stable_knowledge_answerable():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式", "20_Wiki/03_STM32/DMA.md")
        r = knowledge_search("STM32 DMA 怎么配置？", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store,
                             llm_answer=_mock_llm)
        assert r["status"] == "answerable"
        assert r["sufficient"] is True
        assert r["answer"] is not None
        assert r["evidence"][0]["source"] == "20_Wiki/03_STM32/DMA.md"
        assert r["source_trace"] == ["20_Wiki/03_STM32/DMA.md"]


def test_knowledge_missing():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤", "20_Wiki/03_STM32/DMA.md")
        r = knowledge_search("WSL 里怎么装 Ubuntu？", use_llm=False, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store)
        assert r["status"] == "knowledge_missing"
        assert r["sufficient"] is False
        assert r["answer"] is None
        assert r["gap"] == {"status": "pending"}


def test_judge_irrelevant_not_answerable():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "工控机采用 Ubuntu + ROS2 + Nav2 运行环境", "30_Projects/工控机.md")
        original = retrieval.judge_relevance
        retrieval.judge_relevance = lambda q, c, cfg: {
            "relevance": "irrelevant", "reason": "只提到Nav2，没有配置方法", "confidence": 0.9, "error": False}
        try:
            r = knowledge_search("ROS2 Nav2 代价地图怎么配置？", use_llm=True, cfg=_cfg(judge_enabled=True, llm_provider="deepseek"),
                                 embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        finally:
            retrieval.judge_relevance = original
        assert r["status"] == "knowledge_missing"
        assert r["sufficient"] is False
        assert r["judge"]["relevance"] == "irrelevant"


def test_evidence_fields_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "FreeRTOS 任务创建 osThreadNew", "20_Wiki/04_FreeRTOS/Task.md", status="draft")
        r = knowledge_search("FreeRTOS 任务如何创建？", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=_mock_llm)
        ev = r["evidence"][0]
        assert set(ev.keys()) >= {"title", "source", "score", "status"}
        assert ev["status"] == "draft"
        assert ev["source"] == "20_Wiki/04_FreeRTOS/Task.md"


def test_read_only_no_writes():
    gap_path = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\tests\knowledge_gaps.yaml")
    gap_before = gap_path.read_text(encoding="utf-8") if gap_path.exists() else None
    act_path = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\control_center\activity_log.jsonl")
    act_before = act_path.read_text(encoding="utf-8") if act_path.exists() else None
    wiki_path = Path(r"D:\KnowledgeBase\Obsidian Vault\20_Wiki\03_STM32\STM32-DMA-配置与使用.md")
    wiki_before = wiki_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤", "20_Wiki/03_STM32/DMA.md")
        r = knowledge_search("不存在的主题 XYZ 怎么处理？", use_llm=False, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store)
        assert r["status"] == "knowledge_missing"
    assert gap_path.read_text(encoding="utf-8") == gap_before
    assert act_path.read_text(encoding="utf-8") == act_before
    assert wiki_path.read_text(encoding="utf-8") == wiki_before


def test_llm_unavailable_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        r = knowledge_search("STM32 DMA 怎么配置？", use_llm=True, cfg=_cfg(llm_provider="none"),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=None)
        assert r["answer"] is None
        assert r["status"] in ("answerable", "knowledge_missing")


def test_llm_raises_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤：时钟、通道、模式")
        def boom(q, c, cfg):
            raise RuntimeError("LLM unavailable")
        r = knowledge_search("STM32 DMA 怎么配置？", use_llm=True, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store, llm_answer=boom)
        assert r["status"] == "error"
        assert r["sufficient"] is False
        assert r["answer"] is None


def test_malformed_query_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp, "STM32 DMA 配置步骤")
        r = knowledge_search("", use_llm=False, cfg=_cfg(),
                             embedder=FakeEmbedder(), raw_store=store, wiki_store=store)
        assert r["query"] == ""
        assert r["status"] in ("answerable", "knowledge_missing", "knowledge_insufficient", "retrieval_problem", "answer_quality_problem", "error")


if __name__ == "__main__":
    for t in (
        test_stable_knowledge_answerable,
        test_knowledge_missing,
        test_judge_irrelevant_not_answerable,
        test_evidence_fields_preserved,
        test_read_only_no_writes,
        test_llm_unavailable_fail_closed,
        test_llm_raises_fail_closed,
        test_malformed_query_fail_closed,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all agent knowledge service tests passed")