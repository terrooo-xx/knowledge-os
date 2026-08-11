"""Full RAG chain: retrieval + reranker + mock LLM adapter."""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = RAG_DIR.parents[1]
sys.path.insert(0, str(RAG_DIR))

from llm import create_llm
from llm.context import build_context
from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.ingest import ingest_file
from rag_engine.retrieval import answer_query
from rag_engine.vector_store import create_store

CONFIG = RAG_DIR / "tests" / "config.local.yaml"
FIXTURE = RAG_DIR / "tests" / "fixtures" / "stm32_dma.md"


def _mock_llm_answer(question: str, chunks: list[dict], cfg: dict) -> str:
    mock_cfg = {"llm": {"provider": "mock", "model": "mock"}}
    adapter = create_llm(mock_cfg)
    return adapter.generate(question, build_context(chunks))


def test_full_chain():
    cfg = resolve_paths(load_config(str(CONFIG)), VAULT_ROOT)
    raw_store = create_store(cfg, cfg["paths"]["raw_vector_db"])
    if raw_store.count() == 0:
        embedder = create_embedder(cfg)
        ingest_file(
            FIXTURE,
            cfg,
            raw_store,
            embedder,
            relative_root=FIXTURE.parent,
        )
    else:
        embedder = create_embedder(cfg)
    wiki_store = create_store(cfg, cfg["paths"]["wiki_vector_db"])

    result = answer_query(
        "STM32F405 DMA 如何搬运数据",
        cfg,
        embedder,
        raw_store,
        wiki_store,
        llm_answer=_mock_llm_answer,
    )
    assert result["source"] == "raw"
    assert result["chunks"], "retrieval returned no chunks"
    assert "rerank_score" in result["chunks"][0], "reranker did not run"
    assert result["answer"].startswith("Mock answer for: ")


if __name__ == "__main__":
    test_full_chain()
    print("PASS test_full_chain")