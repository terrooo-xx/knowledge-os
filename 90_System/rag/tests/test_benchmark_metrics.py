"""RAG Evaluation metrics tests (pure, offline).

Covers: benchmark/golden schema, answer coverage, wiki-first metrics, RAW
metrics, fallback recovery, knowledge_missing vs system_error split, latency
quantiles, sample-too-small, failure taxonomy, gap signals, golden manual
fields and the markdown report skeleton.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.evaluation import (  # noqa: E402
    FINAL_ANSWERED,
    FINAL_KNOWLEDGE_MISSING,
    FINAL_SYSTEM_ERROR,
    aggregate_metrics,
    build_report,
    classify_failure,
    classify_gap_signal,
    final_status,
    load_benchmark,
    load_golden,
    render_markdown,
)

BENCH = RAG_DIR / "evaluation" / "benchmark.yaml"
GOLDEN = RAG_DIR / "evaluation" / "golden.yaml"


def _rec(qid, final=FINAL_ANSWERED, source="wiki", path="wiki_first", gate=True,
         fallback=False, fb_reason=None, rerank=False, raw_ran=False,
         wiki_count=5, raw_count=0, sufficient=True, window_count=1,
         judge_executed=False, judge_result="not_executed", expected=True,
         category="freertos", query_type="concept", latency=100.0,
         expected_source="wiki"):
    return {
        "query_id": qid, "query": qid, "category": category, "query_type": query_type,
        "expected_answerable": expected, "expected_source": expected_source,
        "execution": {
            "source": source, "path": path,
            "initial_path": "wiki_first" if path != "raw" else "raw",
            "gate_passed": gate, "fallback_used": fallback, "fallback_reason": fb_reason,
            "reranker_used": rerank, "raw_ran": raw_ran, "wiki_count": wiki_count,
            "raw_count": raw_count, "wiki_confidence": 0.9 if gate else 0.5,
        },
        "evidence": {"sufficient": sufficient,
                     "gap_type": None if sufficient else "knowledge_missing",
                     "chunk_count": max(wiki_count, raw_count), "window_count": window_count},
        "judge": {"executed": judge_executed, "result": judge_result},
        "final": {"status": final},
        "metrics": {"total_ms": latency, "retrieval_ms": 10.0, "rerank_ms": 5.0,
                    "judge_ms": 20.0 if judge_executed else None, "answer_ms": None},
        "evidence_windows": [{"text": "x" * 100}] if window_count else [],
    }


# ---------------------------------------------------------------- benchmark schema


def test_benchmark_schema_valid():
    data = load_benchmark(BENCH)
    assert 20 <= len(data["queries"]) <= 30
    ids = {q["id"] for q in data["queries"]}
    assert len(ids) == len(data["queries"])
    for q in data["queries"]:
        assert q["query"].strip()
        assert q["category"]
        assert q["query_type"] in (
            "fact", "configuration", "procedure", "troubleshooting",
            "comparison", "concept", "cross_document", "unknown")
        assert q["expected_source"] in ("wiki", "wiki_or_raw", "raw", "either", "unknown")
        assert q["expected_answerable"] in (True, False, None, "unknown")
        assert q.get("expected") in ("heuristic", "manual", "unknown", None)


def test_benchmark_schema_rejects_invalid():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.yaml"
        bad.write_text("queries:\n  - id: q1\n    query: x\n", encoding="utf-8")
        try:
            load_benchmark(bad)
            assert False, "should raise"
        except ValueError as exc:
            assert "缺少字段" in str(exc) or "category" in str(exc)


def test_golden_schema():
    data = load_golden(GOLDEN)
    assert data["entries"]
    bench = load_benchmark(BENCH)
    bench_ids = {q["id"] for q in bench["queries"]}
    for e in data["entries"]:
        assert e["id"] in bench_ids
        assert isinstance(e.get("review"), dict)
        assert e["review"].get("answer_correct") in (True, False, None)


# ---------------------------------------------------------------- metrics


def test_answer_coverage_and_error_split():
    records = [_rec(f"w{i}") for i in range(5)]
    records += [_rec("km1", final=FINAL_KNOWLEDGE_MISSING, gate=True, sufficient=False,
                     judge_executed=True, judge_result="insufficient", raw_ran=True,
                     raw_count=5, source="raw", path="wiki_fallback", fallback=True,
                     fb_reason="judge_rejected", rerank=True)]
    records += [_rec("err1", final=FINAL_SYSTEM_ERROR)]
    m = aggregate_metrics(records)
    ov = m["overall"]
    assert ov["answered"] == 5
    assert ov["knowledge_missing"] == 1
    assert ov["system_error"] == 1
    assert ov["answer_coverage"] == round(100.0 * 5 / 7, 1)
    assert ov["knowledge_missing_rate"] == round(100.0 * 1 / 7, 1)
    assert ov["system_error_rate"] == round(100.0 * 1 / 7, 1)
    # system_error must never be counted as knowledge_missing
    assert sum(1 for r in records if final_status(r) == FINAL_KNOWLEDGE_MISSING) == 1


def test_wiki_metrics_and_fallback_recovery():
    records = [_rec("w1"), _rec("w2"), _rec("w3")]
    records += [_rec("f1", final=FINAL_KNOWLEDGE_MISSING, gate=True, sufficient=False,
                     source="raw", path="wiki_fallback", fallback=True,
                     fb_reason="evidence_insufficient", raw_ran=True, raw_count=5, rerank=True)]
    records += [_rec("f2", final=FINAL_KNOWLEDGE_MISSING, gate=True, sufficient=False,
                     source="raw", path="wiki_fallback", fallback=True,
                     fb_reason="evidence_insufficient", raw_ran=True, raw_count=5, rerank=True)]
    records += [_rec("f3", final=FINAL_ANSWERED, gate=True, sufficient=True,
                     source="raw", path="wiki_fallback", fallback=True,
                     fb_reason="evidence_insufficient", raw_ran=True, raw_count=5, rerank=True)]
    m = aggregate_metrics(records)
    wk = m["wiki"]
    assert wk["wiki_hit_count"] == 6          # gate passed for all 6
    assert wk["wiki_hit_rate"] == 100.0
    assert wk["wiki_gate_pass_rate"] == 100.0
    assert wk["wiki_answer_rate"] == 50.0     # w1..w3 wiki answered
    assert wk["wiki_fallback_count"] == 3
    assert wk["wiki_fallback_rate"] == 50.0
    assert wk["wiki_fallback_recovered"] == 1
    assert wk["wiki_fallback_recovery_rate"] == round(100.0 / 3, 1)
    assert wk["wiki_fallback_not_recovered"] == 2


def test_raw_metrics():
    records = [_rec("w1"), _rec("w2")]
    records += [_rec("r1", final=FINAL_ANSWERED, gate=True, sufficient=True, source="raw",
                     path="wiki_fallback", fallback=True, fb_reason="evidence_insufficient",
                     raw_ran=True, raw_count=5, rerank=True)]
    records += [_rec("r2", final=FINAL_KNOWLEDGE_MISSING, gate=False, sufficient=False,
                     source="raw", path="raw", raw_ran=True, raw_count=0,
                     expected=False, wiki_count=5)]
    m = aggregate_metrics(records)
    rw = m["raw"]
    assert rw["raw_query_count"] == 2
    assert rw["raw_query_rate"] == 50.0
    assert rw["reranker_used_count"] == 1
    assert rw["reranker_used_rate"] == 25.0
    assert rw["raw_evidence_sufficient_count"] == 1
    assert rw["raw_evidence_sufficient_rate"] == 50.0
    assert rw["raw_answer_count"] == 1
    assert rw["raw_answer_rate"] == 50.0
    assert rw["raw_knowledge_missing_count"] == 1


def test_failure_taxonomy():
    cases = [
        (_rec("a", final=FINAL_ANSWERED), None),
        (_rec("b", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="wiki_fallback",
              gate=True, fallback=True, fb_reason="judge_rejected", raw_ran=True,
              raw_count=5, judge_executed=True, judge_result="insufficient"),
         "RAW_JUDGE_REJECTED"),
        (_rec("c", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="raw", gate=False,
              raw_ran=True, raw_count=0), "RAW_RETRIEVAL_WEAK"),
        (_rec("d", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="wiki_fallback",
              gate=True, fallback=True, fb_reason="below_threshold", raw_ran=True,
              raw_count=5, sufficient=False), "RAW_EVIDENCE_INSUFFICIENT"),
        (_rec("e", final=FINAL_KNOWLEDGE_MISSING, source="wiki", path="wiki_first",
              gate=True, sufficient=False), "WIKI_EVIDENCE_INSUFFICIENT"),
        (_rec("f", final=FINAL_SYSTEM_ERROR), "SYSTEM_ERROR"),
    ]
    for rec, expected in cases:
        assert classify_failure(rec) == expected, rec["query_id"]


def test_gap_signal_classification():
    # judge rejected -> evidence_gap
    r1 = _rec("a", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="wiki_fallback",
              gate=True, fallback=True, fb_reason="judge_rejected", raw_ran=True,
              raw_count=5, judge_executed=True, judge_result="insufficient")
    assert classify_gap_signal(r1) == "evidence_gap"
    # gate failed + expected answerable -> retrieval_gap (needs manual confirm)
    r2 = _rec("b", final=FINAL_KNOWLEDGE_MISSING, gate=False, source="raw", path="raw",
              raw_ran=True, raw_count=0, expected=True)
    assert classify_gap_signal(r2) == "retrieval_gap"
    # gate failed + expected not answerable -> likely_knowledge_gap
    r3 = _rec("c", final=FINAL_KNOWLEDGE_MISSING, gate=False, source="raw", path="raw",
              raw_ran=True, raw_count=0, expected=False)
    assert classify_gap_signal(r3) == "likely_knowledge_gap"
    # answered -> answered
    assert classify_gap_signal(_rec("d")) == "answered"
    # system error -> system_error
    assert classify_gap_signal(_rec("e", final=FINAL_SYSTEM_ERROR)) == "system_error"


def test_sample_too_small_flag():
    small = aggregate_metrics([_rec("w1")])
    assert small["sample_too_small"] is True
    assert small["sample_note"]
    big = aggregate_metrics([_rec(f"w{i}") for i in range(20)])
    assert big["sample_too_small"] is False


def test_latency_quantiles():
    records = [dict(_rec(f"w{i}"), metrics={"total_ms": 100.0 + i * 10.0,
                                            "retrieval_ms": 10.0, "rerank_ms": 1.0,
                                            "judge_ms": None, "answer_ms": None})
               for i in range(10)]
    m = aggregate_metrics(records)
    q = m["latency"]["total_ms"]
    assert set(q) == {"p50", "p90", "p95"}
    assert q["p50"] == 145.0   # values 100..190, linear-interp median
    assert q["p90"] == 181.0
    assert q["p95"] == 185.5
    assert m["latency"]["mean_total_ms"] == 145.0
    empty = aggregate_metrics([])
    assert empty["latency"]["total_ms"] == {}
    assert empty["query_count"] == 0


def test_knowledge_missing_breakdown_and_top_failures():
    records = [
        _rec("k1", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="raw", gate=False,
             raw_ran=True, raw_count=0),
        _rec("k2", final=FINAL_KNOWLEDGE_MISSING, source="raw", path="wiki_fallback",
             gate=True, fallback=True, fb_reason="judge_rejected", raw_ran=True,
             raw_count=5, judge_executed=True, judge_result="insufficient"),
        _rec("w1", final=FINAL_ANSWERED),
    ]
    m = aggregate_metrics(records)
    fc = m["fail_closed"]
    assert fc["knowledge_missing_total"] == 2
    assert fc["breakdown"]["RAW_RETRIEVAL_WEAK"] == 1
    assert fc["breakdown"]["RAW_JUDGE_REJECTED"] == 1
    assert fc["judge_rejected_count"] == 1
    assert fc["top_failures"][0]["type"] == "RAW_RETRIEVAL_WEAK"
    assert fc["top_failures"][0]["examples"] == ["k1"]


def test_golden_manual_review_not_fabricated():
    # null manual fields must not count as reviewed
    records = [
        dict(_rec("w1"), manual_review={"answer_correct": None, "evidence_supported": None}),
        dict(_rec("w2"), manual_review={"answer_correct": True, "evidence_supported": True}),
        dict(_rec("w3"), manual_review={"answer_correct": False, "evidence_supported": True}),
    ]
    m = aggregate_metrics(records)
    gd = m["golden"]
    assert gd["matched_count"] == 3
    assert gd["manual_reviewed_count"] == 2
    assert gd["answer_correct_count"] == 1
    assert gd["answer_correct_rate"] == 50.0


def test_render_markdown_sections():
    records = [_rec(f"w{i}") for i in range(6)]
    records += [_rec("km1", final=FINAL_KNOWLEDGE_MISSING, gate=False, source="raw",
                     path="raw", raw_ran=True, raw_count=0, expected=False)]
    report = build_report(records, {"run_id": "eval-test", "generated_at": "now",
                                    "benchmark_version": "1.0", "mode": "fast"})
    md = render_markdown(report)
    for token in ("# RAG Evaluation Report", "## Dataset", "## Overall",
                  "## Wiki-First", "## RAW Retrieval", "## Fail-Closed",
                  "## Evidence", "## Latency", "## By Domain", "## By Query Type",
                  "## Golden Set", "## Failure Analysis", "## Knowledge Gap Signals",
                  "## Recommendations"):
        assert token in md, f"missing section: {token}"
    assert "Answer Coverage" in md
    assert "sample" not in md  # no fake trends / score


def test_no_composite_rag_score():
    records = [_rec(f"w{i}") for i in range(10)]
    m = aggregate_metrics(records)
    assert "overall_rag_score" not in m
    assert "score" not in (m.get("overall") or {})
