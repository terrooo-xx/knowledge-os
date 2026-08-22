"""Evaluation Diff classification tests (offline): REAL_REGRESSION /
JUDGE_VARIANCE / UNKNOWN, recovered, unchanged, new failure."""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.gap_diagnosis import (  # noqa: E402
    CHANGE_NEW_FAILURE, CHANGE_RECOVERED, CHANGE_REGRESSED, CHANGE_UNCHANGED_ANSWERED,
    CHANGE_UNCHANGED_FAILED, REGRESSION_JUDGE_VARIANCE, REGRESSION_REAL, REGRESSION_UNKNOWN,
    classify_regression_change, compare_runs,
)


def _rec(qid, final="answered", windows=None):
    return {
        "query_id": qid, "query": qid, "expected_answerable": True,
        "execution": {"source": "wiki", "path": "wiki_first", "initial_path": "wiki_first",
                      "gate_passed": final == "answered", "fallback_used": False,
                      "fallback_reason": None, "reranker_used": False, "raw_ran": False,
                      "wiki_count": 5, "raw_count": 0, "wiki_confidence": 0.9},
        "evidence": {"sufficient": final == "answered",
                     "gap_type": None if final == "answered" else "knowledge_missing", "window_count": 1},
        "judge": {"executed": final != "answered",
                  "result": "insufficient" if final != "answered" else "passed"},
        "final": {"status": final}, "metrics": {"total_ms": 100.0},
        "evidence_windows": [{"source": "20_Wiki/a.md", "text": "x" * 10}] if windows is None else windows,
    }


def _win(source, text="x" * 10):
    return {"source": source, "text": text}


def test_regression_class_judge_variance_same_docs():
    # 相同文档集合（顺序/路径不同）-> JUDGE_VARIANCE
    before = _rec("q1", "answered", windows=[_win("a"), _win("b"), _win("c")])
    after = _rec("q1", "knowledge_missing", windows=[_win("c"), _win("b"), _win("a")])
    assert classify_regression_change(before, after) == REGRESSION_JUDGE_VARIANCE


def test_regression_class_real_regression_different_docs():
    before = _rec("q1", "answered", windows=[_win("a"), _win("b")])
    after = _rec("q1", "knowledge_missing", windows=[_win("a"), _win("d")])
    assert classify_regression_change(before, after) == REGRESSION_REAL


def test_regression_class_unknown_no_evidence():
    assert classify_regression_change(_rec("q1"), None) == REGRESSION_UNKNOWN
    assert classify_regression_change(None, _rec("q1")) == REGRESSION_UNKNOWN
    assert classify_regression_change(_rec("q1", windows=[]), _rec("q2", windows=[])) == REGRESSION_UNKNOWN


def test_compare_runs_classifies_regressed():
    before = [_rec("q1", "answered"), _rec("q2", "answered", windows=[_win("a"), _win("b")])]
    after = [_rec("q1", "answered"), _rec("q2", "knowledge_missing", windows=[_win("b"), _win("a")])]
    d = compare_runs(before, after)
    item = next(i for i in d["items"] if i["query_id"] == "q2")
    assert item["change"] == CHANGE_REGRESSED
    assert item["regression_class"] == REGRESSION_JUDGE_VARIANCE
    assert d["regression_classes"]["JUDGE_VARIANCE"] == 1
    assert d["regression_classes"]["REAL_REGRESSION"] == 0


def test_compare_runs_real_regression_aggregate():
    before = [_rec("q1", "answered", windows=[_win("a")])]
    after = [_rec("q1", "knowledge_missing", windows=[_win("z")])]
    d = compare_runs(before, after)
    assert d["regression_classes"]["REAL_REGRESSION"] == 1
    assert d["regression_classes"]["JUDGE_VARIANCE"] == 0


def test_recovered_unchanged_new_failure_labels():
    before = [_rec("q1", "knowledge_missing"), _rec("q2", "answered"), _rec("q3", "answered")]
    after = [_rec("q1", "answered"), _rec("q2", "answered"),
             _rec("q3", "knowledge_missing"), _rec("q4", "knowledge_missing")]
    d = compare_runs(before, after)
    by_id = {i["query_id"]: i for i in d["items"]}
    assert by_id["q1"]["change"] == CHANGE_RECOVERED
    assert by_id["q2"]["change"] == CHANGE_UNCHANGED_ANSWERED
    assert by_id["q3"]["change"] == CHANGE_REGRESSED
    assert by_id["q4"]["change"] == CHANGE_NEW_FAILURE
    assert by_id["q4"]["regression_class"] is None
    assert d["counts"]["recovered"] == 1
    assert d["counts"]["new_failure"] == 1
