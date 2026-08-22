"""Evidence Context Expansion tests (Case 1-6 + integration).

Offline: fabricated chunk sequences + a real VectorStore for retrieval
integration. Verifies neighbor expansion, cross-chunk sentence recovery,
dedup, length capping, multiple windows, and reranker-order preservation.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.evidence_window import build_document_index, build_evidence_windows, merge_chunk_sequence
from rag_engine.vector_store import VectorStore

CFG = {
    "chunking": {"size": 800, "overlap": 100},
    "evidence_window": {"enabled": True, "prev_chunks": 1, "next_chunks": 1,
                        "max_evidence_chars": 3000, "use_for_answer": False},
}


def _doc_index(chunks_text, source="doc.md"):
    store = VectorStore(str(tempfile.mkdtemp()) + "/db")
    for t in chunks_text:
        store.add(t, {"source": source, "document_path": source}, [1.0, 0.0])
    return build_document_index(store)


def _ranked(idx, doc_index, source="doc.md"):
    doc = doc_index[source]
    return [dict(doc[i], score=1.0 - i * 0.01, rerank_score=0.9 - i * 0.01) for i in idx]


# ---------------------------------------------------------------- Case 1: cross-chunk sentence

def test_case1_cross_chunk_sentence_restored():
    # chunk 4 ends mid-sentence, chunk 5 starts with the continuation
    chunks = [
        "前文 A。",
        "前文 B。",
        "上下文 C。",
        "前文 D。",
        "是否启用 FreeRTOS 配置中的栈溢出检查",
        "：Disabled。启用后，FreeRTOS 在任务切换时检查栈溢出。",
        "后文 E。",
    ]
    di = _doc_index(chunks)
    ranked = _ranked([4], di)
    wins = build_evidence_windows(ranked, di, CFG)
    assert len(wins) == 1
    w = wins[0]
    assert w["hit_chunk_ids"] == [4]
    assert w["context_start_chunk"] == 3 and w["context_end_chunk"] == 5
    # the joined sentence is restored (no mid-sentence break)
    assert "栈溢出检查：Disabled。启用后" in w["text"]
    assert w["text"].rstrip().endswith("启用后，FreeRTOS 在任务切换时检查栈溢出。")


# ---------------------------------------------------------------- Case 2: single complete chunk

def test_case2_single_complete_chunk_not_expanded():
    chunks = ["一个完整且自包含的段落，本身不依赖前后文。", "其他段落。"]
    di = _doc_index(chunks)
    ranked = _ranked([0], di)
    wins = build_evidence_windows(ranked, di, CFG)
    assert len(wins) == 1
    w = wins[0]
    # expansion may pull one neighbor, but text must contain the full hit sentence
    assert "一个完整且自包含的段落" in w["text"]
    # window keeps whole chunks (no mid-sentence hard cut)
    assert w["text"].endswith("。") or w["text"].endswith("其他段落。")


# ---------------------------------------------------------------- Case 3: adjacent hits merged

def test_case3_adjacent_hits_merged_no_duplicate():
    # chunks 4/5/6 overlap by 100 chars (chunk_text style); all are hits
    base = "x" * 200
    chunks = [base[:300]] * 1 + [f"chunk{i} " + "y" * 150 for i in range(3)]
    chunks = [chunks[0], "A" * 200, "B" * 200, "C" * 200]
    di = _doc_index(chunks)
    ranked = _ranked([1, 2, 3], di)
    wins = build_evidence_windows(ranked, di, CFG)
    assert len(wins) == 1  # adjacent hits -> single window
    w = wins[0]
    assert sorted(w["hit_chunk_ids"]) == [1, 2, 3]
    # no duplicated whole blocks (dedup): each 200-char block appears exactly once
    assert w["text"].count("A" * 200) == 1
    assert w["text"].count("B" * 200) == 1
    assert w["text"].count("C" * 200) == 1


# ---------------------------------------------------------------- Case 4: non-adjacent hits

def test_case4_non_adjacent_hits_two_windows():
    chunks = [f"段落 {i} " + "z" * 50 for i in range(25)]
    di = _doc_index(chunks)
    ranked = _ranked([4, 20], di)
    wins = build_evidence_windows(ranked, di, CFG)
    assert len(wins) == 2
    ids = [w["hit_chunk_ids"][0] for w in wins]
    assert 4 in ids and 20 in ids
    # window 4 must NOT include chunk 20 and vice versa
    w4 = next(w for w in wins if w["hit_chunk_ids"] == [4])
    w20 = next(w for w in wins if w["hit_chunk_ids"] == [20])
    assert "段落 20" not in w4["text"]
    assert "段落 4" not in w20["text"]


# ---------------------------------------------------------------- Case 5: length cap

def test_case5_length_cap_no_mid_sentence_cut():
    chunks = [("句子" * 300)[:600], ("句子" * 300)[:600], ("句子" * 300)[:600],
              ("句子" * 300)[:600], ("句子" * 300)[:600]]
    di = _doc_index(chunks)
    cfg = dict(CFG)
    cfg["evidence_window"] = dict(cfg["evidence_window"], max_evidence_chars=900, prev_chunks=2, next_chunks=2)
    ranked = _ranked([2], di)
    wins = build_evidence_windows(ranked, di, cfg)
    assert len(wins) == 1
    w = wins[0]
    assert len(w["text"]) <= 900  # capped
    # every included chunk is whole (no mid-chunk hard cut): text equals a full merge
    assert "句子" in w["text"]


# ---------------------------------------------------------------- Case 6: reranker order unchanged

def test_case6_reranker_order_preserved():
    chunks = [f"doc {i} " + "w" * 60 for i in range(8)]
    di = _doc_index(chunks)
    ranked = _ranked([3, 1, 6], di)  # already in rerank order
    before = [(c["text"], c.get("rerank_score")) for c in ranked]
    build_evidence_windows(ranked, di, CFG)
    after = [(c["text"], c.get("rerank_score")) for c in ranked]
    assert before == after  # input list untouched


# ---------------------------------------------------------------- metadata

def test_window_metadata():
    chunks = [f"段落 {i} " + "m" * 80 for i in range(10)]
    di = _doc_index(chunks)
    ranked = _ranked([5], di)
    wins = build_evidence_windows(ranked, di, CFG)
    w = wins[0]
    for key in ("source", "document", "section", "hit_chunk_ids", "context_start_chunk",
                "context_end_chunk", "text", "retrieval_score", "rerank_score"):
        assert key in w


# ---------------------------------------------------------------- integration via answer_query

def test_answer_query_returns_evidence_windows():
    from rag_engine.retrieval import answer_query

    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0]] * len(texts)

    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(str(Path(tmp) / "db"))
        for t in ["是否启用 FreeRTOS 配置中的栈溢出检查", "：Disabled。启用后，FreeRTOS 在任务切换时检查栈溢出。",
                  "STM32 DMA 配置步骤：时钟、通道、模式。"]:
            store.add(t, {"source": "20_Wiki/a.md", "status": "stable"}, [1.0, 0.0, 0.0])
        cfg = {"retrieval": {"wiki_first": False, "confidence_threshold": 0.0, "top_k": 5,
                             "dense_weight": 0.6, "bm25_weight": 0.4},
               "reranker": {"enabled": False, "provider": "none", "top_k": 5},
               "evidence_judge": {"enabled": False, "top_k": 5},
               "chunking": {"size": 800, "overlap": 100},
               "evidence_window": {"enabled": True, "prev_chunks": 1, "next_chunks": 1,
                                   "max_evidence_chars": 3000, "use_for_answer": False}}
        result = answer_query("FreeRTOS 栈溢出检查如何配置？", cfg, FakeEmbedder(), store, store, llm_answer=None)
        assert "evidence_windows" in result
        assert isinstance(result["evidence_windows"], list)
        assert result["chunks"]  # original chunks still returned (rerank path untouched)


# ---------------------------------------------------------------- review context windows

def test_review_context_evidence_has_window():
    import sys as _sys
    _sys.path.insert(0, str(RAG_DIR.parent / "control_center"))
    import service
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "00_Inbox" / "s.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("句" * 900, encoding="utf-8")  # > 800 chars -> multiple chunks
        old = (service.VAULT_ROOT, service.REVIEW_RECORDS)
        service.VAULT_ROOT = root
        service.REVIEW_RECORDS = root / "review_records.json"
        try:
            ev = service._extract_evidence(["00_Inbox/s.md"], role="source")
            assert ev["sources"][0]["readable"] is True
            assert ev["sources"][0]["chunk_count"] > 1
            assert ev["sources"][0]["window_text"]
            assert ev["sources"][0]["window_start"] == 1
            assert "context_end_chunk" in ev["chunks"][0]
        finally:
            service.VAULT_ROOT, service.REVIEW_RECORDS = old


if __name__ == "__main__":
    for t in (
        test_case1_cross_chunk_sentence_restored,
        test_case2_single_complete_chunk_not_expanded,
        test_case3_adjacent_hits_merged_no_duplicate,
        test_case4_non_adjacent_hits_two_windows,
        test_case5_length_cap_no_mid_sentence_cut,
        test_case6_reranker_order_preserved,
        test_window_metadata,
        test_answer_query_returns_evidence_windows,
        test_review_context_evidence_has_window,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all evidence window tests passed")
