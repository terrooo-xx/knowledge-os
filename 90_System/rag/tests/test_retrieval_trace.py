"""Retrieval Trace tests: structured decision-chain observability.

Offline: search_corpus / rerank / judge are monkeypatched; no network/LLM.
Verifies retrieval_trace path/fallback/reranker/judge/final + backward compat.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

import rag_engine.retrieval as retrieval
from rag_engine.vector_store import VectorStore


def _cfg(wiki_first=True, fallback=True, judge=False):
    return {
        "retrieval": {"wiki_first": wiki_first, "confidence_threshold": 0.78, "top_k": 5,
                      "dense_weight": 0.6, "bm25_weight": 0.4,
                      "wiki_fallback_on_insufficient": fallback},
        "reranker": {"enabled": True, "provider": "bge", "model": "mock-reranker", "top_k": 5},
        "evidence_judge": {"enabled": judge, "top_k": 5},
        "llm": {"provider": "deepseek", "model": "mock"},
        "chunking": {"size": 800, "overlap": 100},
        "evidence_window": {"enabled": True, "prev_chunks": 1, "next_chunks": 1,
                            "max_evidence_chars": 3000, "use_for_answer": False},
    }


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _chunk(text, score, source="doc.md"):
    return {"text": text, "metadata": {"source": source, "document_path": source}, "score": score}


class _Calls:
    def install(self, wiki_store, raw_store, wiki_chunks=None, raw_chunks=None, judge_fn=None):
        self._wiki_store = wiki_store
        self._raw_store = raw_store
        self.wiki_chunks = wiki_chunks or []
        self.raw_chunks = raw_chunks or []
        self.rerank_calls = 0

        def fake_search(query, embedder, store, bm25, cfg):
            if store is self._wiki_store:
                return list(self.wiki_chunks)
            return list(self.raw_chunks)

        def fake_rerank(query, chunks, cfg):
            self.rerank_calls += 1
            for c in chunks:
                c["rerank_score"] = c.get("rerank_score", c["score"])
            chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
            return chunks

        self._old_search = retrieval.search_corpus
        self._old_rerank = retrieval.rerank
        self._old_judge = retrieval.judge_relevance
        retrieval.search_corpus = fake_search
        retrieval.rerank = fake_rerank
        if judge_fn is not None:
            retrieval.judge_relevance = judge_fn

    def restore(self):
        retrieval.search_corpus = self._old_search
        retrieval.rerank = self._old_rerank
        retrieval.judge_relevance = self._old_judge


def _run(calls, wiki_chunks, raw_chunks, query, cfg, judge_fn=None):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            wiki_store = VectorStore(str(Path(tmp) / "w"))
            raw_store = VectorStore(str(Path(tmp) / "r"))
            for c in wiki_chunks or []:
                wiki_store.add(c["text"], c["metadata"], [1.0, 0.0, 0.0])
            for c in raw_chunks or []:
                raw_store.add(c["text"], c["metadata"], [1.0, 0.0, 0.0])
            calls.install(wiki_store, raw_store, wiki_chunks, raw_chunks, judge_fn)
            return retrieval.answer_query(query, cfg, FakeEmbedder(), raw_store, wiki_store, llm_answer=None)
    finally:
        calls.restore()


def _trace(r):
    return r.get("retrieval_trace") or {}


# ---------------------------------------------------------------- Case 1 wiki-first

def test_case1_wiki_first():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew 设置栈大小与优先级", 0.92)],
             raw_chunks=[_chunk("无关内容", 0.5)],
             query="FreeRTOS 任务如何创建？", cfg=_cfg())
    t = _trace(r)
    assert t["retrieval"]["path"] == "wiki_first"
    assert t["retrieval"]["initial_path"] == "wiki_first"
    assert t["retrieval"]["fallback_used"] is False
    assert t["candidates"]["reranked"] is False
    assert t["ranking"]["reranker_used"] is False
    assert t["ranking"]["reranker_reason"] == "wiki_first"
    assert t["answer"]["status"] == "answered"
    assert "Wiki 命中" in t["summary"]


# ---------------------------------------------------------------- Case 2 wiki insufficient -> fallback

def test_case2_wiki_insufficient_fallback():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew", 0.92)],
             raw_chunks=[_chunk("STM32 EEPROM 校验和配置：写后读回校验", 0.85)],
             query="STM32 EEPROM 校验和如何配置？", cfg=_cfg())
    t = _trace(r)
    assert t["retrieval"]["initial_path"] == "wiki_first"
    assert t["retrieval"]["path"] == "wiki_fallback"
    assert t["retrieval"]["fallback_used"] is True
    assert t["retrieval"]["fallback_reason"] == "evidence_insufficient"
    assert t["candidates"]["reranked"] is True
    assert t["ranking"]["reranker_used"] is True
    assert t["ranking"]["reranker"] == "mock-reranker"
    assert "RAW fallback" in t["summary"]


# ---------------------------------------------------------------- Case 3 wiki miss -> raw

def test_case3_wiki_miss_raw():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建", 0.5)],
             raw_chunks=[_chunk("EEPROM 校验和配置", 0.85)],
             query="EEPROM 校验和", cfg=_cfg())
    t = _trace(r)
    assert t["retrieval"]["path"] == "raw"
    assert t["retrieval"]["gate_passed"] is False
    assert t["retrieval"]["fallback_used"] is False
    assert t["ranking"]["reranker_used"] is True
    assert t["summary"].startswith("Wiki 未命中") or "Wiki 未达阈值" in t["summary"]


# ---------------------------------------------------------------- Case 4 judge rejection

def test_case4_judge_rejection_knowledge_missing():
    calls = _Calls()
    def judge_reject(q, c, cfg):
        return {"relevance": "irrelevant", "reason": "语义不足", "confidence": 0.3, "error": False}
    r = _run(calls,
             wiki_chunks=[_chunk("STM32 EEPROM 写入流程与校验配置说明", 0.92)],
             raw_chunks=[_chunk("EEPROM 校验和配置：写后读回校验", 0.85)],
             query="EEPROM 校验和如何配置？", cfg=_cfg(judge=True), judge_fn=judge_reject)
    t = _trace(r)
    assert t["judge"]["executed"] is True
    assert t["judge"]["result"] == "insufficient"
    assert t["answer"]["status"] == "knowledge_missing"
    assert "Fail-Closed" in t["summary"]


# ---------------------------------------------------------------- Case 5 wiki rerank null

def test_case5_wiki_rerank_null_not_error():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew 配置", 0.92)],
             raw_chunks=[], query="FreeRTOS 任务如何创建？", cfg=_cfg())
    assert r["chunks"][0].get("rerank_score") is None  # wiki path legitimately un-reranked
    t = _trace(r)
    assert t["ranking"]["reranker_used"] is False
    assert t["ranking"]["reranker_reason"] == "wiki_first"
    assert t["ranking"]["reranker"] is None
    assert t["judge"]["executed"] is False  # no error state


# ---------------------------------------------------------------- Case 6 window count

def test_case6_window_count_matches():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew", 0.92, source="20_Wiki/a.md")],
             raw_chunks=[_chunk("EEPROM 校验和配置", 0.85, source="00_Inbox/b.md")],
             query="FreeRTOS 任务如何创建？", cfg=_cfg())
    t = _trace(r)
    assert t["evidence"]["window_count"] == len(r["evidence_windows"]) == 1


# ---------------------------------------------------------------- Case 7 backward compat

def test_case7_backward_compat_fields_unchanged():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew", 0.92)],
             raw_chunks=[_chunk("EEPROM 校验和配置", 0.85)],
             query="FreeRTOS 任务如何创建？", cfg=_cfg())
    for key in ("source", "confidence", "chunks", "answer", "evidence", "gap_type", "judge",
                "evidence_windows", "retrieval_gate"):
        assert key in r
    g = r["retrieval_gate"]
    for key in ("wiki_first", "threshold", "wiki_confidence", "gate_passed", "fallback_used", "fallback_enabled"):
        assert key in g
    # trace is additive
    assert "retrieval_trace" in r


if __name__ == "__main__":
    for t in (
        test_case1_wiki_first, test_case2_wiki_insufficient_fallback,
        test_case3_wiki_miss_raw, test_case4_judge_rejection_knowledge_missing,
        test_case5_wiki_rerank_null_not_error, test_case6_window_count_matches,
        test_case7_backward_compat_fields_unchanged,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all retrieval trace tests passed")
