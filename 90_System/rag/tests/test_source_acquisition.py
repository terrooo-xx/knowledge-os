"""Source Acquisition tests (offline): registry schema, status transitions,
P0/P1 gap -> source task linkage, CC API, weekly metrics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.source_acquisition import (  # noqa: E402
    STATUS_ACQUIRED, STATUS_CANDIDATE, STATUS_MISSING, STATUS_VERIFIED,
    gaps_source_summary, load_registry, p0_p1_missing, save_registry,
    transition_status, validate_registry, apply_transition,
)
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402


def _entry(**kw):
    e = {
        "id": kw.get("id", "src_x"), "gap_id": kw.get("gap_id", "gap_x"),
        "title": "T", "priority": kw.get("priority", "P0"),
        "source_status": kw.get("source_status", STATUS_MISSING),
        "source_type": "official_docs",
        "source": {"title": "S", "url": "https://example.com", "local_path": None,
                   "authority": "A", "date": None},
        "verification": {"verified": False, "reviewer": "", "notes": ""},
        "sufficiency": {f: "unknown" for f in
                        ("source_relevance", "source_authority", "source_completeness",
                         "source_recency", "source_extractability")},
        "reason": "reason",
    }
    e.update(kw)
    return e


def test_registry_roundtrip_and_validation():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source_acquisition.yaml"
        reg = {"created": "2026-08-15", "sources": [_entry()]}
        save_registry(path, reg)
        loaded = load_registry(path)
        assert loaded["sources"][0]["id"] == "src_x"
        assert validate_registry(loaded) == []
        bad = {"created": "", "sources": [_entry(source_status="fake")]}
        assert validate_registry(bad)


def test_status_transitions_monotonic():
    assert transition_status(STATUS_MISSING, STATUS_CANDIDATE)
    assert transition_status(STATUS_CANDIDATE, STATUS_ACQUIRED)
    assert transition_status(STATUS_ACQUIRED, STATUS_VERIFIED)
    assert not transition_status(STATUS_MISSING, STATUS_VERIFIED)   # 不能跳过
    assert not transition_status(STATUS_ACQUIRED, STATUS_CANDIDATE)  # 不能回退
    e = apply_transition(_entry(), STATUS_CANDIDATE)
    assert e["source_status"] == STATUS_CANDIDATE
    try:
        apply_transition(_entry(), STATUS_VERIFIED)
        assert False, "should raise (skip acquired)"
    except ValueError:
        pass
    v = apply_transition(_entry(source_status=STATUS_ACQUIRED), STATUS_VERIFIED, reviewer="r")
    assert v["verification"]["verified"] is True
    assert v["verification"]["reviewer"] == "r"


def test_p0_p1_gap_to_source_task_linkage():
    gaps = [
        {"id": "gap_p0", "priority": "P0"},
        {"id": "gap_p1", "priority": "P1"},
        {"id": "gap_p2", "priority": "P2"},
    ]
    sources = [
        _entry(id="s0", gap_id="gap_p0", source_status=STATUS_ACQUIRED),
        _entry(id="s1", gap_id="gap_p1", source_status=STATUS_MISSING),
    ]
    summary = gaps_source_summary(gaps, sources)
    assert summary["gap_p0"]["source_status"] == STATUS_ACQUIRED
    assert summary["gap_p1"]["source_status"] == STATUS_MISSING
    assert summary["gap_p2"]["source_status"] == STATUS_MISSING  # 无任务 -> missing
    missing = p0_p1_missing(gaps, sources)
    assert missing == ["gap_p1"]  # P0 有 acquired，P1 缺，P2 不计


def test_weekly_metrics_include_sources(tmp_path):
    vault = tmp_path
    (vault / "40_Outputs" / "RAG Evaluation").mkdir(parents=True)
    (vault / "40_Outputs" / "RAG Evaluation" / "latest.json").write_text(
        '{"metrics": {"overall": {"answer_coverage": 71.4}}}', encoding="utf-8")
    (vault / "90_System" / "rag" / "evaluation").mkdir(parents=True)
    (vault / "90_System" / "rag" / "evaluation" / "gaps.yaml").write_text(
        "- id: gap_p0\n  priority: P0\n  status: open\n", encoding="utf-8")
    (vault / "90_System" / "rag" / "evaluation" / "source_acquisition.yaml").write_text('''created: "2026-08-15"
sources:
  - id: s0
    gap_id: gap_p0
    priority: P0
    source_status: verified
    source_type: official_docs
    source: {}
    verification: {}
    sufficiency: {}
    reason: r
''', encoding="utf-8")
    re_ = review_metrics.collect_rag_evaluation(vault)
    assert re_ is not None
    assert re_["sources"]["verified"] == 1
    assert re_["sources"]["p0_p1_missing"] == []


# ---------------------------------------------------------------- CC API


def test_service_source_acquisition_api(tmp_path, monkeypatch):
    reg = tmp_path / "source_acquisition.yaml"
    reg.write_text('''created: "2026-08-15"
sources:
  - id: s0
    gap_id: gap_p0
    title: T
    priority: P0
    source_status: candidate
    source_type: official_docs
    source: {title: S, url: "https://x", local_path: null, authority: A, date: null}
    verification: {verified: false, reviewer: "", notes: ""}
    sufficiency: {source_relevance: high, source_authority: high, source_completeness: unknown, source_recency: unknown, source_extractability: unknown}
    reason: r
''', encoding="utf-8")
    monkeypatch.setattr(service, "SOURCE_REGISTRY", reg)
    monkeypatch.setattr(service, "_load_gap_registry", lambda: [{"id": "gap_p0", "priority": "P0"}])
    r = service.source_acquisition()
    assert r["ok"] is True and r["source_count"] == 1
    assert r["per_gap"]["gap_p0"]["source_status"] == "candidate"
    d = service.source_acquisition_detail("s0")
    assert d["ok"] is True and d["source"]["priority"] == "P0"
    assert service.source_acquisition_detail("nope")["ok"] is False
