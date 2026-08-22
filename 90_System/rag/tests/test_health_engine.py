"""Knowledge Health Engine tests (Phase D1): deterministic, explainable, no 0-fabrication."""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))

import health


def _m(wiki_total=20, reviewed=0, stable=0, draft=20, pending=0, failed=0, candidates=18,
       gaps_total=6, gaps_pending=0, gaps_resolved=0, stale=0, projects=None, health=None):
    return {
        "wiki": {"wiki_total": wiki_total, "wiki_reviewed": reviewed, "wiki_stable": stable,
                 "wiki_draft": draft, "wiki_unknown": 0},
        "review": {"pending_human": pending, "judge_failed": failed, "candidates": candidates,
                   "total": candidates, "judge_passed": 0},
        "gaps": {"knowledge_gaps_total": gaps_total, "knowledge_gaps_pending": gaps_pending,
                 "knowledge_gaps_resolved": gaps_resolved},
        "projects": projects if projects is not None else [],
        "stale_risk": [{}] * stale,
        "health": health if health is not None else {"status": "ok", "errors": 0, "warnings": 0},
    }


def test_healthy_gets_high_score():
    m = _m(reviewed=18, stable=2, candidates=0, pending=0, gaps_pending=0)
    m["review"]["candidates"] = 0  # no backlog at all
    h = health.calculate_health(m)
    assert h["score"] is not None and h["score"] >= 85


def test_review_backlog_lowers_score():
    base = _m(reviewed=18, stable=2, candidates=0)
    base["review"]["candidates"] = 0
    low = _m(reviewed=18, stable=2, pending=18, candidates=18)
    assert health.calculate_health(low)["score"] < health.calculate_health(base)["score"]


def test_judge_failures_lower_score():
    base = _m(reviewed=18, stable=2, candidates=0)
    base["review"]["candidates"] = 0
    bad = _m(reviewed=18, stable=2, candidates=18, failed=4)
    assert health.calculate_health(bad)["score"] < health.calculate_health(base)["score"]


def test_stale_lowers_score():
    base = _m(reviewed=18, stable=2, candidates=0)
    base["review"]["candidates"] = 0
    stale = _m(reviewed=18, stable=2, candidates=0, stale=5)
    stale["review"]["candidates"] = 0
    assert health.calculate_health(stale)["score"] < health.calculate_health(base)["score"]


def test_low_quality_lowers_score():
    high = _m(reviewed=18, stable=2, candidates=0)
    high["review"]["candidates"] = 0
    low = _m(reviewed=0, stable=0, draft=20, candidates=0)
    low["review"]["candidates"] = 0
    assert health.calculate_health(low)["score"] < health.calculate_health(high)["score"]


def test_system_errors_lower_score_significantly():
    base = _m(reviewed=18, stable=2, candidates=0)
    base["review"]["candidates"] = 0
    err = _m(reviewed=18, stable=2, candidates=0, health={"status": "error", "errors": 2, "warnings": 1})
    err["review"]["candidates"] = 0
    assert health.calculate_health(err)["score"] < health.calculate_health(base)["score"] - 20


def test_insufficient_data_score_null_not_zero():
    m = {"wiki": {}, "review": {}, "gaps": {}, "projects": [], "stale_risk": [], "health": {}}
    h = health.calculate_health(m)
    assert h["score"] is None
    assert h["status"] == "not_calculated"
    assert h["available"] is False
    assert h["reason"] == "insufficient_data"


def test_deterministic_same_input():
    m = _m(reviewed=10, stable=2, draft=8, pending=8, candidates=18, gaps_pending=4, gaps_resolved=2, stale=2)
    a = health.calculate_health(m)
    b = health.calculate_health(m)
    assert a["score"] == b["score"] == health.calculate_health(m)["score"]
    assert a["dimensions"] == b["dimensions"]


def test_build_attention():
    m = _m(pending=10, gaps_pending=5, stale=1)
    at = health.build_attention(m)
    assert any("需要人工审核" in x["label"] for x in at)
    assert any("知识缺口" in x["label"] for x in at)
    assert any("stale" in x["label"] for x in at)


def test_status_thresholds():
    assert health.status_for(95) == "excellent"
    assert health.status_for(80) == "good"
    assert health.status_for(65) == "attention"
    assert health.status_for(50) == "warning"
    assert health.status_for(20) == "critical"
    assert health.status_for(None) == "not_available"


if __name__ == "__main__":
    for t in (
        test_healthy_gets_high_score, test_review_backlog_lowers_score,
        test_judge_failures_lower_score, test_stale_lowers_score,
        test_low_quality_lowers_score, test_system_errors_lower_score_significantly,
        test_insufficient_data_score_null_not_zero, test_deterministic_same_input,
        test_build_attention, test_status_thresholds,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all health engine tests passed")
