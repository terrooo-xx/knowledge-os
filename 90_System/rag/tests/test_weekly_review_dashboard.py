"""Weekly Review Dashboard tests (Phase B).

Offline / real-data checks. Verifies the dashboard aggregate is consistent with
metrics.py (review counts), real wiki distribution, knowledge_gaps.yaml, no fake
trends, no fabricated project progress, baseline handling, and the HTTP route.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(CTRL_DIR))

import metrics
import service
import server  # noqa: F401


def test_dashboard_endpoint_ok():
    d = service.weekly_review_dashboard()
    assert d["ok"] is True
    for key in ("period", "status", "knowledge", "review", "gaps", "projects", "risk", "baseline", "attention", "historical"):
        assert key in d


def test_dashboard_review_matches_metrics():
    d = service.weekly_review_dashboard()
    m = metrics.collect_review_metrics(vault_root=Path(r"D:\KnowledgeBase\Obsidian Vault"))
    assert d["review"]["judge_passed"] == m["judge_passed"]
    assert d["review"]["needs_review"] == m["needs_review"]
    assert d["review"]["judge_failed"] == m["judge_failed"]
    assert d["review"]["judging"] == m["judging"]
    assert d["review"]["pending_human"] == m["pending_human"]


def test_wiki_distribution_matches_real():
    d = service.weekly_review_dashboard()
    w = metrics.collect_wiki_stats(Path(r"D:\KnowledgeBase\Obsidian Vault"))
    dist = d["knowledge"]["status_distribution"]
    assert dist["draft"] == w["wiki_draft"]
    assert dist["reviewed"] == w["wiki_reviewed"]
    assert dist["stable"] == w["wiki_stable"]
    assert dist["unknown"] == w["wiki_unknown"]
    assert dist["draft"] + dist["reviewed"] + dist["stable"] + dist["unknown"] == w["wiki_total"]


def test_gaps_matches_yaml():
    d = service.weekly_review_dashboard()
    g = metrics.collect_gaps(Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\tests\knowledge_gaps.yaml"))
    assert d["gaps"]["pending"] == g["knowledge_gaps_pending"]
    assert d["gaps"]["total"] == g["knowledge_gaps_total"]
    assert d["gaps"]["resolved"] == g["knowledge_gaps_resolved"]


def test_projects_no_fake_progress():
    d = service.weekly_review_dashboard()
    for item in d["projects"]["items"]:
        # items expose only structured fields; progress is never fabricated
        assert "progress" not in item
        assert "phase" in item and "status" in item and "updated" in item and "blockers" in item


def test_baseline_true_no_fake_trend():
    d = service.weekly_review_dashboard()
    # W33 为基线，W34 为基线后首个正常周期（is_baseline_period=False）
    assert d["baseline"]["is_baseline_period"] is False
    assert d["status"]["baseline"] is False
    # Phase C contract: 有真实历史（W33+W34）时 has_trend=True，但 WoW/4 周仍不编造
    assert d["has_trend"] is True
    assert isinstance(d["trend"], dict)
    assert d["trend"]["wow"]["review_pending"]["available"] is False  # baseline boundary
    assert d["trend"]["four_week"]["review_pending"]["available"] is False  # <4 周
    assert d["trend"]["availability"]["has_history"] is True
    assert d["trend"]["availability"]["period_count"] >= 2
    flat = json.dumps(d, ensure_ascii=False)
    assert "↑" not in flat and "↓" not in flat  # no fabricated arrows in serialized payload


def test_http_route():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/weekly_review/dashboard", timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["period"] == "2026-W34"
    finally:
        srv.shutdown()


def test_historical_preserved_with_links():
    d = service.weekly_review_dashboard()
    assert len(d["historical"]) >= 1
    latest = d["historical"][0]
    assert latest["period"] == "2026-W34"
    assert latest.get("report_path")
    assert d["report_path"]  # View Full Weekly Review link available


if __name__ == "__main__":
    for t in (
        test_dashboard_endpoint_ok,
        test_dashboard_review_matches_metrics,
        test_wiki_distribution_matches_real,
        test_gaps_matches_yaml,
        test_projects_no_fake_progress,
        test_baseline_true_no_fake_trend,
        test_http_route,
        test_historical_preserved_with_links,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all weekly review dashboard tests passed")

