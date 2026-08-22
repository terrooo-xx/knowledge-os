"""Wiki-First / RAW Retrieval path tests.

Offline: search_corpus / rerank are monkeypatched to control scores
deterministically; real VectorStore instances provide count()/all().
Verifies the Wiki quality gate + RAW fallback + fail-closed + reranker coverage.
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
        "reranker": {"enabled": True, "provider": "bge", "model": "mock", "top_k": 5},
        "evidence_judge": {"enabled": judge, "top_k": 5},
        "llm": {"provider": "deepseek", "model": "mock"},
        "chunking": {"size": 800, "overlap": 100},
        "evidence_window": {"enabled": True, "prev_chunks": 1, "next_chunks": 1,
                            "max_evidence_chars": 3000, "use_for_answer": False},
    }


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def _store(tmp):
    return VectorStore(str(Path(tmp) / "db"))


def _chunk(text, score, source="doc.md", rerank=None):
    c = {"text": text, "metadata": {"source": source, "document_path": source}, "score": score}
    if rerank is not None:
        c["rerank_score"] = rerank
    return c


class _Calls:
    def __init__(self):
        self.rerank_calls = 0
        self.wiki_search = None
        self.raw_search = None

    def install(self, wiki_store, raw_store, wiki_chunks=None, raw_chunks=None):
        self._wiki_store = wiki_store
        self._raw_store = raw_store
        self.wiki_chunks = wiki_chunks or []
        self.raw_chunks = raw_chunks or []

        def fake_search(query, embedder, store, bm25, cfg):
            if store is self._wiki_store:
                self.wiki_search = query
                return list(self.wiki_chunks)
            self.raw_search = query
            return list(self.raw_chunks)

        def fake_rerank(query, chunks, cfg):
            self.rerank_calls += 1
            for c in chunks:
                c["rerank_score"] = c.get("rerank_score", c["score"])
            chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
            return chunks

        self._old_search = retrieval.search_corpus
        self._old_rerank = retrieval.rerank
        retrieval.search_corpus = fake_search
        retrieval.rerank = fake_rerank

    def restore(self):
        retrieval.search_corpus = self._old_search
        retrieval.rerank = self._old_rerank


def _run(calls, wiki_chunks, raw_chunks, query, cfg):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            wiki_store = _store(tmp)
            raw_store = _store(tmp)
            wiki_store.add("dummy wiki", {"source": "w"}, [1.0, 0.0, 0.0])
            raw_store.add("dummy raw", {"source": "r"}, [1.0, 0.0, 0.0])
            # 让窗口构建能按文档索引到这些 chunk
            for c in wiki_chunks or []:
                wiki_store.add(c["text"], c["metadata"], [1.0, 0.0, 0.0])
            for c in raw_chunks or []:
                raw_store.add(c["text"], c["metadata"], [1.0, 0.0, 0.0])
            calls.install(wiki_store, raw_store, wiki_chunks, raw_chunks)
            return retrieval.answer_query(query, cfg, FakeEmbedder(), raw_store, wiki_store, llm_answer=None)
    finally:
        calls.restore()


# ---------------------------------------------------------------- 1 wiki hit

def test_wiki_hit_wiki_first():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew 设置栈大小与优先级", 0.92)],
             raw_chunks=[_chunk("不相关内容", 0.5)],
             query="FreeRTOS 任务如何创建？", cfg=_cfg())
    assert r["source"] == "wiki"
    assert r["retrieval_gate"]["gate_passed"] is True
    assert r["retrieval_gate"]["fallback_used"] is False
    assert calls.rerank_calls == 0          # wiki path must NOT rerank
    assert r["chunks"][0]["text"].startswith("FreeRTOS 任务创建")


# ---------------------------------------------------------------- 2 wiki miss

def test_wiki_miss_goes_raw_with_rerank():
    calls = _Calls()
    raw = _chunk("STM32 EEPROM 校验和配置：写后读回校验", 0.7)
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建", 0.55)],
             raw_chunks=[raw],
             query="STM32 EEPROM 校验和如何配置？", cfg=_cfg())
    assert r["source"] == "raw"
    assert r["retrieval_gate"]["gate_passed"] is False
    assert calls.rerank_calls == 1          # RAW path reranks


# ---------------------------------------------------------------- 3 wiki weak -> raw fallback

def test_wiki_weak_evidence_falls_back_to_raw():
    calls = _Calls()
    wiki = _chunk("FreeRTOS 任务创建：osThreadNew", 0.92)  # high score but missing query tokens
    raw = _chunk("STM32 EEPROM 校验和配置：写后读回校验", 0.85)
    r = _run(calls,
             wiki_chunks=[wiki],
             raw_chunks=[raw],
             query="STM32 EEPROM 校验和如何配置？", cfg=_cfg())
    assert r["retrieval_gate"]["gate_passed"] is True
    assert r["retrieval_gate"]["fallback_used"] is True  # 真优先，非命中即终止
    assert r["source"] == "raw"
    assert calls.rerank_calls == 1
    assert "EEPROM" in r["chunks"][0]["text"]


# ---------------------------------------------------------------- 4 multiple wiki ordering

def test_multiple_wiki_results_ordered_by_fusion():
    calls = _Calls()
    a = _chunk("FreeRTOS 任务创建：osThreadNew 参数说明与用法", 0.89)
    b = _chunk("FreeRTOS 调度：抢占式优先级", 0.73)
    c = _chunk("FreeRTOS 队列：xQueueSend", 0.66)
    r = _run(calls, wiki_chunks=[a, b, c], raw_chunks=[], query="FreeRTOS 任务如何创建？", cfg=_cfg())
    assert r["source"] == "wiki"
    scores = [ch["score"] for ch in r["chunks"]]
    assert scores == sorted(scores, reverse=True)  # fusion order preserved


# ---------------------------------------------------------------- 5/6 reranker coverage

def test_raw_reranker_regression_and_wiki_no_rerank():
    calls = _Calls()
    wiki = _chunk("FreeRTOS 任务创建：osThreadNew", 0.92)
    raw = _chunk("STM32 EEPROM 校验和配置", 0.85)
    # wiki hit (sufficient) -> no rerank
    _run(calls, wiki_chunks=[wiki], raw_chunks=[raw], query="FreeRTOS 任务如何创建？", cfg=_cfg())
    assert calls.rerank_calls == 0
    # wiki miss -> rerank once
    calls.rerank_calls = 0
    _run(calls, wiki_chunks=[_chunk("无关", 0.4)], raw_chunks=[raw], query="EEPROM 校验和", cfg=_cfg())
    assert calls.rerank_calls == 1


# ---------------------------------------------------------------- 7 evidence window both paths

def test_evidence_window_covers_wiki_and_raw():
    calls = _Calls()
    # wiki sufficient -> window from wiki store
    r1 = _run(calls, wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew", 0.92, source="20_Wiki/a.md")],
              raw_chunks=[], query="FreeRTOS 任务如何创建？", cfg=_cfg())
    assert r1["source"] == "wiki" and len(r1["evidence_windows"]) == 1
    assert r1["evidence_windows"][0]["source"] == "20_Wiki/a.md"
    # raw path -> window from raw store
    r2 = _run(calls, wiki_chunks=[_chunk("无关", 0.4)], raw_chunks=[_chunk("EEPROM 校验和配置", 0.85, source="00_Inbox/b.md")],
              query="EEPROM 校验和", cfg=_cfg())
    assert r2["source"] == "raw" and len(r2["evidence_windows"]) == 1
    assert r2["evidence_windows"][0]["source"] == "00_Inbox/b.md"


# ---------------------------------------------------------------- 8 judge unchanged

def test_judge_still_runs_and_fail_closed():
    calls = _Calls()
    orig = retrieval.judge_relevance
    # 确定性证据充分（wiki 含 EEPROM token）→ 仅 LLM Judge 判 irrelevant → 触发 RAW fallback
    judge_results = iter([
        {"relevance": "irrelevant", "reason": "wiki 语义不足", "confidence": 0.3, "error": False},
        {"relevance": "relevant", "reason": "raw 语义充分", "confidence": 0.9, "error": False},
    ])
    retrieval.judge_relevance = lambda q, c, cfg: next(judge_results)
    try:
        r = _run(calls,
                 wiki_chunks=[_chunk("STM32 EEPROM 写入流程与校验配置说明", 0.92)],
                 raw_chunks=[_chunk("EEPROM 校验和配置：写后读回校验", 0.85)],
                 query="EEPROM 校验和如何配置？", cfg=_cfg(judge=True))
    finally:
        retrieval.judge_relevance = orig
    # 第一阶段确定性证据充分（未在 Phase1 fallback），Judge 判 wiki 不足 → Phase3 fallback
    assert r["retrieval_gate"]["fallback_used"] is True
    assert r["source"] == "raw"
    assert r["evidence"]["sufficient"] is True
    assert r["judge"]["relevance"] == "relevant"


def test_judge_failure_fails_closed_unchanged():
    from rag_engine import judge as judge_mod  # noqa: F401
    calls = _Calls()
    orig = retrieval.judge_relevance
    def boom(q, c, cfg):
        raise TimeoutError("LLM timeout")
    retrieval.judge_relevance = boom
    try:
        r = _run(calls, wiki_chunks=[_chunk("FreeRTOS 任务创建", 0.92)], raw_chunks=[],
                 query="FreeRTOS 任务如何创建？", cfg=_cfg(judge=True))
    finally:
        retrieval.judge_relevance = orig
    assert r["evidence"]["sufficient"] is False
    assert r["evidence"]["gap_type"] == "knowledge_missing"


# ---------------------------------------------------------------- 9 fail-closed

def test_insufficient_no_fabricated_answer():
    calls = _Calls()
    # query 含 wiki 缺失的 ASCII token（EEPROM）→ 确定性证据不足 → 回退 RAW；RAW 为空 → 不可回答
    r = _run(calls, wiki_chunks=[_chunk("FreeRTOS 任务创建", 0.92)], raw_chunks=[],
             query="STM32 EEPROM 校验和如何配置？", cfg=_cfg())
    assert r["retrieval_gate"]["fallback_used"] is True
    assert r["evidence"]["sufficient"] is False
    assert r["answer"] is None


# ---------------------------------------------------------------- 10 fallback can be disabled

def test_fallback_disabled_keeps_wiki_hit_and_terminate():
    calls = _Calls()
    r = _run(calls,
             wiki_chunks=[_chunk("FreeRTOS 任务创建：osThreadNew", 0.92)],
             raw_chunks=[_chunk("EEPROM 校验和配置", 0.85)],
             query="STM32 EEPROM 校验和如何配置？", cfg=_cfg(fallback=False))
    # gate passes but evidence insufficient; fallback disabled -> stays wiki (旧行为)
    assert r["retrieval_gate"]["gate_passed"] is True
    assert r["retrieval_gate"]["fallback_used"] is False
    assert r["source"] == "wiki"
    assert r["evidence"]["sufficient"] is False
    assert calls.rerank_calls == 0


if __name__ == "__main__":
    for t in (
        test_wiki_hit_wiki_first, test_wiki_miss_goes_raw_with_rerank,
        test_wiki_weak_evidence_falls_back_to_raw, test_multiple_wiki_results_ordered_by_fusion,
        test_raw_reranker_regression_and_wiki_no_rerank,
        test_evidence_window_covers_wiki_and_raw, test_judge_still_runs_and_fail_closed,
        test_judge_failure_fails_closed_unchanged, test_insufficient_no_fabricated_answer,
        test_fallback_disabled_keeps_wiki_hit_and_terminate,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all retrieval path tests passed")
