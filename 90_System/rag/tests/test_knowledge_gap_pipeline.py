"""Knowledge Gap Pipeline tests (offline): failure->gap classification,
clustering, priority, registry evidence, CC API, weekly metrics."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.gap_diagnosis import (  # noqa: E402
    KIND_EVIDENCE, KIND_JUDGE, KIND_KNOWLEDGE, KIND_RETRIEVAL,
    classify_failure_kind, cluster_failures, compare_runs,
    build_gap_registry, diagnose_query, prioritize_gap,
    render_audit_report, render_diff_markdown,
)
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402


def _rec(qid, final="knowledge_missing", gate=False, raw_count=0, wiki_count=5,
         judge_executed=False, judge_result="not_executed", expected=True,
         category="freertos", query_type="configuration", sources=None,
         path="raw", fallback=False, fb_reason=None):
    return {
        "query_id": qid, "query": qid, "category": category, "query_type": query_type,
        "expected_answerable": expected, "expected_source": "unknown",
        "execution": {"source": "raw", "path": path, "initial_path": "wiki_first",
                      "gate_passed": gate, "fallback_used": fallback,
                      "fallback_reason": fb_reason, "reranker_used": True,
                      "raw_ran": True, "wiki_count": wiki_count, "raw_count": raw_count,
                      "wiki_confidence": 0.9 if gate else 0.5, "confidence": 0.6},
        "evidence": {"sufficient": final == "answered", "gap_type": None if final == "answered" else "knowledge_missing",
                     "chunk_count": max(wiki_count, raw_count), "window_count": 2,
                     "sources": sources or ["20_Wiki/a.md"]},
        "judge": {"executed": judge_executed, "result": judge_result},
        "final": {"status": final},
        "metrics": {"total_ms": 100.0},
        "evidence_windows": [{"source": s, "retrieval_score": 0.8, "rerank_score": 0.7,
                              "text": "x" * 50} for s in (sources or ["20_Wiki/a.md"])],
    }


# ---------------------------------------------------------------- failure kind


def test_failure_kind_classification():
    assert classify_failure_kind(_rec("a", final="answered")) == "answered"
    assert classify_failure_kind(_rec("b", final="system_error")) == "system_error"
    # judge rejected -> judge_gap
    r = _rec("c", gate=True, wiki_count=5, judge_executed=True, judge_result="insufficient")
    assert classify_failure_kind(r) == KIND_JUDGE
    # gate passed + candidates + evidence insufficient (no judge) -> evidence_gap
    r2 = _rec("d", gate=True, wiki_count=5, judge_executed=False)
    assert classify_failure_kind(r2) == KIND_EVIDENCE
    # gate failed + expected answerable -> retrieval_gap
    r3 = _rec("e", gate=False, wiki_count=0, raw_count=0, expected=True)
    assert classify_failure_kind(r3) == KIND_RETRIEVAL
    # gate failed + expected not answerable -> knowledge_gap
    r4 = _rec("f", gate=False, wiki_count=0, raw_count=0, expected=False)
    assert classify_failure_kind(r4) == KIND_KNOWLEDGE


def test_diagnose_query_fields():
    d = diagnose_query(_rec("q1", sources=["20_Wiki/a.md"]))
    for key in ("query_id", "query", "expected_answerable", "initial_path",
                "wiki_confidence", "fallback_used", "fallback_reason", "confidence",
                "evidence_sufficient", "judge_result", "final_status", "failure_type",
                "failure_kind", "relevant_sources", "top_evidence"):
        assert key in d, f"missing {key}"
    assert d["relevant_sources"] == ["20_Wiki/a.md"]
    assert d["top_evidence"][0]["source"] == "20_Wiki/a.md"


# ---------------------------------------------------------------- clustering / priority


def test_clustering_groups_by_knowledge_boundary():
    records = [
        _rec("q_freertos_stack", expected=False),
        _rec("q_freertos_notify", expected=False),
        _rec("q_git", expected=False),
        _rec("ok", final="answered"),
    ]
    clusters = cluster_failures(records, {
        "q_freertos_stack": "gap_freertos", "q_freertos_notify": "gap_freertos",
        "q_git": "gap_git",
    })
    by_id = {c["gap_id"]: c for c in clusters}
    assert set(by_id) == {"gap_freertos", "gap_git"}
    assert len(by_id["gap_freertos"]["queries"]) == 2
    # answered queries are excluded
    assert all(r["final"]["status"] != "answered" for c in clusters for r in c["queries"])


def test_priority_transparent():
    assert prioritize_gap({"query_count": 2}, source_available=True, wiki_exists=True,
                          recommended_action="expand_wiki") == "P0"
    assert prioritize_gap({"query_count": 1}, source_available=True, wiki_exists=False,
                          recommended_action="create_wiki") == "P1"
    assert prioritize_gap({"query_count": 1}, source_available=False, wiki_exists=True,
                          recommended_action="expand_wiki") == "P1"
    assert prioritize_gap({"query_count": 1}, source_available=False, wiki_exists=False,
                          recommended_action="acquire_source") == "P2"
    assert prioritize_gap({"query_count": 1}, source_available=False, wiki_exists=False,
                          recommended_action="acquire_source", override="P0") == "P0"


# ---------------------------------------------------------------- registry


def test_build_gap_registry_with_evidence():
    records = [
        _rec("q_freertos_stack", expected=False, sources=["20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md"]),
        _rec("q_freertos_notify", expected=False, sources=["20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md"],
             judge_executed=True, judge_result="insufficient"),
        _rec("q_px4", expected=False, sources=[]),
        _rec("ok", final="answered"),
    ]
    cluster_map = {"q_freertos_stack": "gap_freertos", "q_freertos_notify": "gap_freertos",
                   "q_px4": "gap_px4"}
    meta = {
        "gap_freertos": {"domain": "freertos", "title": "FreeRTOS 配置与调试",
                         "wiki_target": {"existing": True, "path": "20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md"},
                         "recommended_action": "expand_wiki",
                         "sources": ["00_Inbox/x.md"], "problem": ["缺步骤"]},
        "gap_px4": {"domain": "drone", "title": "PX4 EKF",
                    "wiki_target": {"existing": False}, "recommended_action": "acquire_source"},
    }
    gaps = build_gap_registry(records, cluster_map, meta, created="2026-08-15")
    g_f = next(g for g in gaps if g["id"] == "gap_freertos")
    assert g_f["priority"] == "P0"          # 2 queries + source
    assert g_f["status"] == "open"
    assert g_f["signals"]["query_count"] == 2
    assert g_f["signals"]["judge_rejected_count"] == 1
    assert g_f["evidence"]["query_ids"] == ["q_freertos_stack", "q_freertos_notify"]
    assert "RAW_EVIDENCE_INSUFFICIENT" in g_f["evidence"]["failure_types"] or \
           g_f["evidence"]["failure_types"]
    assert g_f["evidence"]["retrieval_traces"]["q_freertos_stack"]["path"] == "raw"
    g_p = next(g for g in gaps if g["id"] == "gap_px4")
    assert g_p["priority"] == "P2"
    assert g_p["recommended_action"] == "acquire_source"
    assert g_p["source_available"] is False
    # wiki_improvement (existing + expand) has priority >= P1
    assert g_f["recommended_action"] == "expand_wiki"
    assert g_f["wiki_exists"] is True


def test_audit_report_renders_sections():
    records = [_rec("q1", expected=False), _rec("ok", final="answered")]
    gaps = build_gap_registry(records, {"q1": "gap_q1"},
                              {"gap_q1": {"domain": "x", "title": "Q1",
                                          "wiki_target": {"existing": False},
                                          "recommended_action": "acquire_source"}},
                              created="2026-08-15")
    md = render_audit_report(records, gaps, {"run_id": "eval-x"})
    for token in ("# Evaluation → Knowledge Gap 审计", "## 1. Top Failure Queries",
                  "## 2. Failure 分类", "## 9. Gap 聚类", "## 10. P0/P1/P2 优先级",
                  "## 11. 建议 Wiki Improvement Tasks", "## 8. 完全缺资料"):
        assert token in md, f"missing {token}"


# ---------------------------------------------------------------- gap diff annotation


def test_annotate_gaps_with_diff_and_auto_resolve():
    from rag_engine.gap_diagnosis import annotate_gaps_with_diff
    before = [_rec("q1", expected=False), _rec("q2", expected=False),
              _rec("ok1", final="answered")]
    after = [_rec("q1", final="answered"), _rec("q2", final="answered"),
             _rec("ok1", final="answered")]
    gaps = [{"id": "gap_a", "status": "open",
             "evidence": {"query_ids": ["q1", "q2"]}}]
    out = annotate_gaps_with_diff(gaps, before, after, {"q1": "gap_a", "q2": "gap_a"})
    assert out[0]["before"] == {"answered": 0, "total": 2, "recovered": 2, "remaining_failures": 2}
    assert out[0]["after"]["remaining_failures"] == 0
    assert out[0]["status"] == "resolved"          # 全部恢复 -> 自动 resolved
    assert out[0]["resolved_by"] == "evaluation_diff"
    # 部分恢复不 resolve
    after2 = [_rec("q1", final="answered"), _rec("q2", expected=False), _rec("ok1", final="answered")]
    gaps2 = [{"id": "gap_a", "status": "open", "evidence": {"query_ids": ["q1", "q2"]}}]
    out2 = annotate_gaps_with_diff(gaps2, before, after2, {"q1": "gap_a", "q2": "gap_a"})
    assert out2[0]["status"] == "open"
    assert out2[0]["after"]["recovered"] == 1


# ---------------------------------------------------------------- CC API


def _mk_gap_registry(tmp_path):
    reg = tmp_path / "gaps.yaml"
    reg.write_text('''- id: gap_test
  domain: freertos
  title: Test Gap
  status: open
  priority: P0
  signals:
    query_count: 2
    knowledge_missing_count: 2
    evidence_insufficient_count: 1
    judge_rejected_count: 1
  source_available: true
  wiki_exists: true
  recommended_action: expand_wiki
  sources: []
  evidence:
    query_ids: [q1, q2]
    failure_types: [RAW_EVIDENCE_INSUFFICIENT]
    failure_kinds: [evidence_gap]
    existing_wikis: [20_Wiki/a.md]
    retrieval_traces: {}
''', encoding="utf-8")
    return reg


def test_service_evaluation_gaps_and_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "GAP_REGISTRY", _mk_gap_registry(tmp_path))
    r = service.evaluation_gaps()
    assert r["ok"] is True
    assert r["open"] == 1 and r["resolved"] == 0
    assert r["source"] == "RAG Evaluation"
    d = service.evaluation_gap_detail("gap_test")
    assert d["ok"] is True and d["gap"]["priority"] == "P0"
    assert service.evaluation_gap_detail("nope")["ok"] is False


def test_service_run_gap_diagnosis_and_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "ACTIVITY_LOG", tmp_path / "activity_log.jsonl")
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "RAG Evaluation")
    monkeypatch.setattr(service, "GAP_REGISTRY", _mk_gap_registry(tmp_path))
    (tmp_path / "RAG Evaluation").mkdir(parents=True)
    (tmp_path / "RAG Evaluation" / "latest_diff.json").write_text(json.dumps({
        "before_run": "b", "after_run": "a", "counts": {"recovered": 4, "regressed": 0,
        "unchanged_answered": 21, "unchanged_failed": 3, "new_failure": 0, "new_answered": 0, "removed": 0},
        "query_recovery_rate": 50.0, "recovered_queries": ["q1"], "regressed_queries": []},
        ensure_ascii=False), encoding="utf-8")

    def fake_run(cmd, **kw):
        out = '{"ok": true, "registry": "x", "gaps": 7}' if "diagnose_gaps" in cmd[2] else \
              '{"ok": true, "counts": {"recovered": 4}}'
        return SimpleNamespace(returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    d = service.run_gap_diagnosis()
    assert d["ok"] is True
    assert d["gaps"]["open"] == 1
    df = service.evaluation_diff()
    assert df["ok"] is True and df["diff"]["counts"]["recovered"] == 4
    rd = service.run_evaluation_diff("before", "after")
    assert rd["ok"] is True and rd["diff"]["counts"]["recovered"] == 4


# ---------------------------------------------------------------- weekly metrics


def test_weekly_collect_rag_evaluation_includes_gaps_and_diff(tmp_path):
    vault = tmp_path
    (vault / "40_Outputs" / "RAG Evaluation").mkdir(parents=True)
    (vault / "40_Outputs" / "RAG Evaluation" / "latest.json").write_text(json.dumps({
        "run_id": "eval-1", "generated_at": "2026-08-15", "query_count": 28, "mode": "fast",
        "report_path": "x", "metrics": {"overall": {"answer_coverage": 71.4}}},
        ensure_ascii=False), encoding="utf-8")
    (vault / "40_Outputs" / "RAG Evaluation" / "latest_diff.json").write_text(json.dumps({
        "before_run": "b", "after_run": "a", "counts": {"recovered": 4, "regressed": 0},
        "query_recovery_rate": 50.0}, ensure_ascii=False), encoding="utf-8")
    (vault / "90_System" / "rag" / "evaluation").mkdir(parents=True)
    (vault / "90_System" / "rag" / "evaluation" / "gaps.yaml").write_text(
        "- id: gap_a\n  status: open\n- id: gap_b\n  status: resolved\n", encoding="utf-8")

    re_ = review_metrics.collect_rag_evaluation(vault)
    assert re_ is not None
    assert re_["gaps"]["open"] == 1
    assert re_["gaps"]["resolved"] == 1
    assert re_["diff"]["recovered"] == 4
    assert re_["diff"]["regressed"] == 0
