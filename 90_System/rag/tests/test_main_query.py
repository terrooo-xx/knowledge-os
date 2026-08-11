"""Main production index query path tests (Scheme A: --store main).

Verifies retrieval hits both Wiki and Project sources from the same main
store, evidence is sufficient, metadata carries status, and a mock LLM
produces an answer -- no real DeepSeek network required.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.retrieval import answer_query
from rag_engine.vector_store import VectorStore

CFG = {
    "retrieval": {
        "wiki_first": True,
        "confidence_threshold": 0.78,
        "top_k": 5,
        "dense_weight": 0.6,
        "bm25_weight": 0.4,
    },
    "reranker": {"enabled": False, "provider": "none", "top_k": 5},
}


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _mock_llm(question: str, chunks: list[dict], cfg: dict) -> str:
    sources = [str(c["metadata"].get("source", "")) for c in chunks]
    return "Mock answer for: " + question + " | " + ";".join(sources)


def _seed_main_store(store: VectorStore) -> None:
    store.add(
        "STM32 DMA 直接存储器访问 用于数据搬运 不占用 CPU",
        {
            "source": "20_Wiki/03_STM32/STM32-DMA-配置与使用.md",
            "status": "stable",
            "type": "wiki",
            "domain": "03_STM32",
        },
        [1.0, 0.0, 0.0],
    )
    store.add(
        "移动底盘控制器 实时运动控制 电机 PWM 驱动",
        {
            "source": "30_Projects/移动底盘控制器/功能说明.md",
            "status": "draft",
            "type": "project",
            "project": "移动底盘控制器",
        },
        [1.0, 0.0, 0.0],
    )


def test_main_store_retrieves_wiki_and_project():
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(str(Path(tmp) / "main_vector_db"))
        _seed_main_store(store)
        result = answer_query(
            "STM32 DMA 如何配置", CFG, FakeEmbedder(), store, store, llm_answer=_mock_llm
        )
        assert result["chunks"], "retrieval returned no chunks"
        sources = [str(c["metadata"].get("source")) for c in result["chunks"]]
        assert any(s.startswith("20_Wiki") for s in sources), "wiki not hit"
        assert any(s.startswith("30_Projects") for s in sources), "project not hit"
        assert result["evidence"]["sufficient"] is True
        assert result["answer"].startswith("Mock answer for:")


def test_main_store_evidence_metadata_has_status():
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(str(Path(tmp) / "main_vector_db"))
        _seed_main_store(store)
        result = answer_query(
            "DMA 配置", CFG, FakeEmbedder(), store, store, llm_answer=_mock_llm
        )
        statuses = {str(c["metadata"].get("status")) for c in result["chunks"]}
        assert "stable" in statuses
        assert "draft" in statuses


if __name__ == "__main__":
    test_main_store_retrieves_wiki_and_project()
    test_main_store_evidence_metadata_has_status()
    print("PASS test_main_store_retrieves_wiki_and_project")
    print("PASS test_main_store_evidence_metadata_has_status")
    print("all main query tests passed")
