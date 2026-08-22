"""RAG Evaluation integration tests (runner + Control Center + Weekly Review).

All offline: the production knowledge_search is mocked; no network / LLM / real
retrieval is executed. Verifies the runner calls the production path, records
are persisted, CC service endpoints read runs, and weekly review references the
latest evaluation summary.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAG_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = RAG_DIR / "scripts"
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(SCRIPTS_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

import evaluate_benchmark as eb  # noqa: E402
import knowledge_service  # noqa: E402
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402
import weekly_review  # noqa: E402


def _trace(path="wiki_first", initial="wiki_first", gate=True, fb=False, fb_reason=None,
           rerank=False, wiki_count=5, raw_count=0, window=1, sufficient=True,
           gap_type=None, judge_executed=False, judge_result="not_executed"):
    return {
        "retrieval": {
            "path": path, "initial_path": initial, "gate_passed": gate,
            "fallback_used": fb, "fallback_reason": fb_reason,
            "wiki_confidence": 0.9 if gate else 0.4,
        },
        "candidates": {"wiki_count": wiki_count, "raw_count": raw_count, "reranked": rerank},
        "ranking": {"reranker_used": rerank, "reranker_reason": "raw_path" if rerank else "wiki_first",
                    "reranker": "bge" if rerank else None, "top_k": 5},
        "evidence": {"window_count": window, "sufficient": sufficient, "gap_type": gap_type},
        "judge": {"executed": judge_executed, "result": judge_result},
        "answer": {"status": "answered" if sufficient else "knowledge_missing"},
        "summary": "Wiki 命中 → 已回答" if sufficient else "Wiki 命中 → Evidence 不足 → Fail-Closed",
    }


def _fake_search(query, **kw):
    """Deterministic fake production knowledge_search (offline)."""
    mode = kw.get("mode", "fast")
    if "missing" in query or "低功耗" in query:
        return {
            "query": query, "mode": mode, "status": "knowledge_missing",
            "answer": None, "evidence": [], "sufficient": False, "judge": None,
            "gap": {"status": "pending"}, "source_trace": [], "reason": "缺少主题词",
            "evidence_windows": [],
            "retrieval_trace": _trace(path="raw", initial="wiki_first", gate=False,
                                      fb=True, fb_reason="below_threshold", rerank=True,
                                      wiki_count=5, raw_count=0, window=0, sufficient=False,
                                      gap_type="knowledge_missing"),
            "retrieval_gate": {"gate_passed": False, "fallback_used": True,
                               "fallback_reason": "below_threshold"},
        }
    return {
        "query": query, "mode": mode, "status": "answerable",
        "answer": "mock 回答（足够长以满足长度门控，包含必要内容。）",
        "evidence": [{"title": "Wiki", "source": "20_Wiki/a.md", "score": 0.9, "status": "stable"}],
        "sufficient": True, "judge": {"relevance": "relevant", "confidence": 0.9, "error": False},
        "gap": None, "source_trace": ["20_Wiki/a.md"], "reason": "证据充分",
        "evidence_windows": [{"text": "window", "hit_chunk_ids": [0], "retrieval_score": 0.9,
                              "rerank_score": 0.9, "source": "20_Wiki/a.md",
                              "context_start_chunk": 0, "context_end_chunk": 0}],
        "retrieval_trace": _trace(),
        "retrieval_gate": {"gate_passed": True, "fallback_used": False, "fallback_reason": None},
    }


def _args(limit=None, mode="fast", warmup=1, no_llm=False, benchmark=None, golden=None, out=None, config=None, json_out=False, dry_run=False):
    return SimpleNamespace(
        benchmark=benchmark or str(RAG_DIR / "evaluation" / "benchmark.yaml"),
        golden=golden or str(RAG_DIR / "evaluation" / "golden.yaml"),
        config=config or str(RAG_DIR / "config.yaml"),
        out=out or str(Path(tempfile.gettempdir()) / "eval-out"),
        limit=limit, mode=mode, warmup=warmup, no_llm=no_llm, json=json_out, dry_run=dry_run,
    )


# ---------------------------------------------------------------- runner


def test_runner_calls_production_path_and_builds_records(monkeypatch):
    monkeypatch.setattr(knowledge_service, "knowledge_search", _fake_search)
    args = _args(limit=12, warmup=1)
    run = eb.run_benchmark(args)
    records = run["records"]
    assert len(records) == 11  # limit=12, warmup=1 query excluded
    assert run["meta"]["warmup_count"] == 1
    answered = [r for r in records if r["final"]["status"] == "answered"]
    missing = [r for r in records if r["final"]["status"] == "knowledge_missing"]
    assert answered and missing
    for r in records:
        assert r["retrieval_trace"]
        assert r["retrieval_gate"]
        assert r["metrics"]["total_ms"] >= 0
        assert r["query_id"]
    # golden lookup attached where id exists
    golden_ids = {"q_freertos_scheduler", "q_stm32_usart"}
    for r in records:
        if r["query_id"] in golden_ids:
            assert r["manual_review"] is not None


def test_runner_system_error_record(monkeypatch):
    def boom(query, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(knowledge_service, "knowledge_search", boom)
    args = _args(limit=3, warmup=0)
    run = eb.run_benchmark(args)
    for r in run["records"]:
        assert r["final"]["status"] == "system_error"
        assert r["failure_type"] == "SYSTEM_ERROR"
        assert r["gap_signal"] == "system_error"


def test_persist_writes_files(tmp_path):
    records = [{
        "query_id": "q1", "query": "Q1", "category": "freertos", "query_type": "concept",
        "expected_answerable": True, "execution": {"source": "wiki", "path": "wiki_first",
        "initial_path": "wiki_first", "gate_passed": True, "fallback_used": False,
        "fallback_reason": None, "reranker_used": False, "raw_ran": False,
        "wiki_count": 5, "raw_count": 0},
        "evidence": {"sufficient": True, "gap_type": None, "window_count": 1},
        "judge": {"executed": False, "result": "not_executed"},
        "final": {"status": "answered"}, "metrics": {"total_ms": 10.0},
        "manual_review": None, "evidence_windows": [{"text": "x"}],
    }]
    meta = {"run_id": "eval-test", "generated_at": "2026-08-14T00:00:00",
            "benchmark_version": "1.0", "query_count": 1, "mode": "fast", "warmup_count": 0,
            "model_config": {"llm": "none"}}
    run = {"run_id": "eval-test", "meta": meta,
           "report": eb.build_report(records, meta), "records": records}
    out_root = tmp_path / "RAG Evaluation"
    latest = eb.persist(run, out_root)
    run_dir = out_root / "runs" / "eval-test"
    assert (run_dir / "meta.json").exists()
    assert (run_dir / "evaluation_records.jsonl").exists()
    assert (run_dir / "evaluation_report.json").exists()
    assert (run_dir / "evaluation_report.md").exists()
    assert (out_root / "latest.json").exists()
    assert latest["run_id"] == "eval-test"
    assert latest["metrics"]["overall"]["answer_coverage"] == 100.0
    assert "RAG Evaluation Report" in (run_dir / "evaluation_report.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- Control Center service


def _mk_eval_root(tmp_path):
    root = tmp_path / "RAG Evaluation"
    run_dir = root / "runs" / "eval-001"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({
        "run_id": "eval-001", "generated_at": "2026-08-14T10:00:00",
        "query_count": 10, "mode": "fast"}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "evaluation_report.json").write_text(json.dumps({
        "meta": {"run_id": "eval-001"}, "metrics": {"query_count": 10}}, ensure_ascii=False), encoding="utf-8")
    (root / "latest.json").write_text(json.dumps({
        "run_id": "eval-001", "generated_at": "2026-08-14T10:00:00",
        "query_count": 10, "mode": "fast",
        "metrics": {"overall": {"answer_coverage": 60.0}}}, ensure_ascii=False), encoding="utf-8")
    return root


def test_service_evaluation_latest_runs_report(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVAL_ROOT", _mk_eval_root(tmp_path))
    d = service.evaluation_latest()
    assert d["ok"] is True
    assert d["latest"]["run_id"] == "eval-001"
    assert d["runs"][0]["run_id"] == "eval-001"
    rep = service.evaluation_report("eval-001")
    assert rep["ok"] is True
    assert rep["report"]["metrics"]["query_count"] == 10
    assert service.evaluation_report("nope")["ok"] is False


def test_service_run_evaluation_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVAL_ROOT", _mk_eval_root(tmp_path))
    monkeypatch.setattr(service, "ACTIVITY_LOG", tmp_path / "activity_log.jsonl")

    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    r = service.run_evaluation(limit=5, mode="fast")
    assert r["ok"] is True
    assert r["latest"]["run_id"] == "eval-001"
    assert (tmp_path / "activity_log.jsonl").exists()

    def fake_run_fail(cmd, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(service.subprocess, "run", fake_run_fail)
    r2 = service.run_evaluation(limit=5, mode="fast")
    assert r2["ok"] is False
    assert "boom" in r2["message"]


# ---------------------------------------------------------------- Weekly Review


def test_metrics_collect_rag_evaluation(tmp_path):
    root = tmp_path / "40_Outputs" / "RAG Evaluation"
    root.mkdir(parents=True)
    (root / "latest.json").write_text(json.dumps({
        "run_id": "eval-001", "generated_at": "2026-08-14T10:00:00", "query_count": 29,
        "mode": "fast", "report_path": "40_Outputs/RAG Evaluation/runs/eval-001/evaluation_report.md",
        "metrics": {"overall": {"answer_coverage": 72.4, "knowledge_missing_rate": 20.7,
                                "system_error": 0},
                    "wiki": {"wiki_hit_rate": 100.0, "wiki_fallback_rate": 30.0,
                             "wiki_fallback_recovery_rate": 40.0},
                    "raw": {"raw_answer_rate": 30.0, "raw_evidence_sufficient_rate": 40.0},
                    "evidence": {"avg_window_count": 1.2},
                    "latency": {"total_ms": {"p50": 1200.0, "p95": 5400.0}},
                    "fail_closed": {"top_failures": [{"type": "RAW_EVIDENCE_INSUFFICIENT", "count": 3, "rate": 10.3}]},
                    "gap_signals": {"likely_knowledge_gap": 3, "evidence_gap": 4, "retrieval_gap": 1}}},
        ensure_ascii=False), encoding="utf-8")
    re_ = review_metrics.collect_rag_evaluation(tmp_path)
    assert re_ is not None
    assert re_["run_id"] == "eval-001"
    assert re_["metrics"]["answer_coverage"] == 72.4
    assert re_["metrics"]["p95_total_ms"] == 5400.0
    assert re_["metrics"]["top_failures"][0]["type"] == "RAW_EVIDENCE_INSUFFICIENT"
    # missing file -> None (weekly review stays intact)
    assert review_metrics.collect_rag_evaluation(tmp_path / "empty") is None


def test_weekly_report_includes_rag_quality_section():
    m = {
        "period": "2026-W33", "generated_at": "2026-08-14T10:00:00",
        "wiki": {"wiki_total": 20, "wiki_draft": 13, "wiki_reviewed": 4, "wiki_stable": 3,
                 "wiki_unknown": 0, "review_pending": 10},
        "growth": {"new_this_week": 20, "updated_this_week": 0, "new_items": [], "updated_items": []},
        "gaps": {"knowledge_gaps_pending": 5, "knowledge_gaps_total": 6, "pending_gaps": []},
        "projects": [], "stale_risk": [], "activity": [], "review": {"pending_human": 10, "judge_passed": 8, "judge_failed": 0, "judging": 0, "needs_review": 10, "items": []},
        "health": {"status": "ok", "errors": 0, "warnings": 0, "rag": {"ok": True, "summary": "PASS=1"}, "wiki": {"ok": True, "error": 0, "warning": 0}, "architecture": {"ok": True, "summary": "ok"}},
        "rag_evaluation": {
            "run_id": "eval-001", "generated_at": "2026-08-14T10:00:00", "query_count": 29,
            "mode": "fast",
            "metrics": {"answer_coverage": 72.4, "knowledge_missing_rate": 20.7, "system_error": 0,
                        "wiki_hit_rate": 100.0, "wiki_fallback_rate": 30.0,
                        "wiki_fallback_recovery_rate": 40.0, "raw_answer_rate": 30.0,
                        "raw_evidence_sufficient_rate": 40.0, "avg_window_count": 1.2,
                        "p50_total_ms": 1200.0, "p95_total_ms": 5400.0,
                        "top_failures": [{"type": "RAW_EVIDENCE_INSUFFICIENT", "count": 3, "rate": 10.3}],
                        "gap_signals": {"likely_knowledge_gap": 3, "evidence_gap": 4, "retrieval_gap": 1}},
        },
    }
    md = weekly_review.render_report(m, "摘要")
    assert "## 8.6 RAG Quality" in md
    assert "Answer Coverage：72.4%" in md
    assert "Knowledge Missing：20.7%" in md
    assert "Fallback Recovery：40.0%" in md
    assert "RAW_EVIDENCE_INSUFFICIENT" in md
    assert "Retrieval Gap：1" in md


def test_weekly_report_without_eval_is_graceful():
    m = {
        "period": "2026-W33", "generated_at": "x",
        "wiki": {"wiki_total": 20, "wiki_draft": 13, "wiki_reviewed": 4, "wiki_stable": 3,
                 "wiki_unknown": 0, "review_pending": 10},
        "growth": {"new_this_week": 0, "updated_this_week": 0, "new_items": [], "updated_items": []},
        "gaps": {"knowledge_gaps_pending": 0, "knowledge_gaps_total": 0, "pending_gaps": []},
        "projects": [], "stale_risk": [], "activity": [], "review": {"pending_human": 10, "judge_passed": 8, "judge_failed": 0, "judging": 0, "needs_review": 10, "items": []},
        "health": {"status": "ok", "errors": 0, "warnings": 0, "rag": {"ok": True, "summary": "PASS=1"}, "wiki": {"ok": True, "error": 0, "warning": 0}, "architecture": {"ok": True, "summary": "ok"}},
        "rag_evaluation": None,
    }
    md = weekly_review.render_report(m, "摘要")
    assert "## 8.6 RAG Quality" in md
    assert "暂无 RAG Evaluation 数据" in md


def test_metrics_collect_includes_rag_evaluation_key():
    m = review_metrics.collect_metrics(vault_root=Path(r"D:\KnowledgeBase\Obsidian Vault"))
    assert "rag_evaluation" in m
