"""Evaluation Diff tests (offline): before/after comparison, recovered query,
regression detection, new failures, markdown rendering, CLI wiring."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = RAG_DIR / "scripts"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from rag_engine.gap_diagnosis import compare_runs, render_diff_markdown  # noqa: E402
import evaluation_diff  # noqa: E402


def _rec(qid, final="answered", failure=None):
    return {
        "query_id": qid, "query": qid, "expected_answerable": True,
        "execution": {"source": "wiki", "path": "wiki_first", "initial_path": "wiki_first",
                      "gate_passed": final == "answered", "fallback_used": False,
                      "fallback_reason": None, "reranker_used": False, "raw_ran": False,
                      "wiki_count": 5, "raw_count": 0, "wiki_confidence": 0.9},
        "evidence": {"sufficient": final == "answered", "gap_type": None if final == "answered" else "knowledge_missing",
                     "window_count": 1},
        "judge": {"executed": final != "answered", "result": "insufficient" if final != "answered" else "passed"},
        "final": {"status": final},
        "metrics": {"total_ms": 100.0},
    }


def _recs(pairs):
    return [_rec(q, f) for q, f in pairs]


def test_compare_runs_recovered_regressed_unchanged():
    before = _recs([("q1", "knowledge_missing"), ("q2", "answered"),
                    ("q3", "knowledge_missing"), ("q4", "answered")])
    after = _recs([("q1", "answered"), ("q2", "knowledge_missing"),
                   ("q3", "knowledge_missing"), ("q4", "answered")])
    d = compare_runs(before, after)
    c = d["counts"]
    assert c["recovered"] == 1        # q1
    assert c["regressed"] == 1        # q2
    assert c["unchanged_answered"] == 1   # q4
    assert c["unchanged_failed"] == 1     # q3
    assert d["recovered_queries"] == ["q1"]
    assert d["regressed_queries"] == ["q2"]
    assert d["query_recovery_rate"] == round(100.0 / 2, 1)  # 2 failed before, 1 recovered
    assert d["total_compared"] == 4


def test_compare_runs_new_failures_and_new_answered():
    before = _recs([("q1", "answered")])
    after = _recs([("q1", "answered"), ("q2", "knowledge_missing"), ("q3", "answered")])
    d = compare_runs(before, after)
    assert d["counts"]["new_failure"] == 1    # q2
    assert d["counts"]["new_answered"] == 1   # q3
    assert d["counts"]["unchanged_answered"] == 1
    item = {i["query_id"]: i for i in d["items"]}["q2"]
    assert item["change"] == "NEW_FAILURE"
    assert item["before_status"] is None


def test_compare_runs_removed_query():
    before = _recs([("q1", "answered"), ("q2", "answered")])
    after = _recs([("q1", "answered")])
    d = compare_runs(before, after)
    assert d["counts"]["removed"] == 1
    item = d["items"][1]
    assert item["query_id"] == "q2" and item["change"] == "REMOVED"


def test_per_query_change_types_detailed():
    before = _recs([("q1", "knowledge_missing")])
    after = _recs([("q1", "answered")])
    d = compare_runs(before, after)
    item = d["items"][0]
    assert item["recovered"] is True
    assert item["regressed"] is False
    assert item["before_status"] == "knowledge_missing"
    assert item["after_status"] == "answered"
    assert item["before_failure"] is not None


def test_render_diff_markdown_sections():
    before = _recs([("q1", "knowledge_missing"), ("q2", "answered")])
    after = _recs([("q1", "answered"), ("q2", "knowledge_missing")])
    d = compare_runs(before, after)
    md = render_diff_markdown(d, {"before_run": "run-b", "after_run": "run-a"})
    for token in ("# RAG Evaluation Diff", "## 汇总", "## 逐条变化", "### Recovered",
                  "### Regressed", "before_run", "after_run"):
        assert token in md, f"missing {token}"
    assert "RECOVERED" in md and "REGRESSED" in md


def test_cli_resolve_records(monkeypatch, tmp_path):
    # _resolve_records with a direct jsonl path
    p = tmp_path / "records.jsonl"
    p.write_text(json.dumps(_rec("q1", "answered"), ensure_ascii=False) + "\n", encoding="utf-8")
    records, run_id = evaluation_diff._resolve_records(str(p))
    assert len(records) == 1
    assert run_id == tmp_path.name
