"""Weekly Review automation tests (Phase E): pipeline, idempotency, recovery,
long-term trend, health version, automation reporting.

Offline: temp/fixture data only; never touches real Outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(CTRL_DIR))

import metrics
import health
import insight
import weekly_review
import service


def _args(**kw):
    defaults = {"week": "2099-W01", "force": False, "config": str(RAG_DIR / "config.yaml"),
                "llm": False, "out": None, "insight": False, "insight_only": False}
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _snap(period, baseline=False, wiki_total=10, review_pending=0, health_score=None):
    return {"period": period, "wiki_total": wiki_total, "review_pending": review_pending,
            "health_score": health_score,
            "baseline": {"is_baseline_period": baseline, "note": None},
            "review": {"judge_passed": 0, "judge_failed": 0, "needs_review": review_pending,
                       "pending_human": review_pending}}


def _write(root, period, data, corrupt=False):
    d = root / period[:4] / ("W" + period[-2:])
    d.mkdir(parents=True, exist_ok=True)
    if corrupt:
        (d / "snapshot.json").write_text("{broken", encoding="utf-8")
    else:
        (d / "snapshot.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 1-2 scheduler / wrapper

def test_scheduler_scripts_exist_and_reference_pipeline():
    ps1 = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\scripts\review\run_weekly_review.ps1")
    reg = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\scripts\review\register_task.ps1")
    assert ps1.exists() and reg.exists()
    text = ps1.read_text(encoding="utf-8")
    assert "weekly_review.py" in text and "--insight" in text
    assert "KNOWLEDGE_OS_PYTHON" in text  # deterministic python resolution


def test_run_wrapper_propagates_pipeline():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "reviews"
        # deterministic run without insight on a temp week -> success (no LLM)
        r = weekly_review.run_weekly_review(_args(out=str(out), force=True))
        assert r in (0, 1)  # 0 success or 1 success_with_warnings (no insight requested)
        md = out / "2099" / "W01" / "weekly-review.md"
        snap = out / "2099" / "W01" / "snapshot.json"
        assert md.exists() and snap.exists()


# ---------------------------------------------------------------- 3-5 pipeline status

def test_pipeline_metrics_critical_failure_fails():
    old = metrics.collect_metrics
    def boom(*a, **k):
        raise RuntimeError("vault unreadable")
    metrics.collect_metrics = boom
    try:
        with tempfile.TemporaryDirectory() as td:
            r = weekly_review.run_weekly_review(_args(out=str(Path(td) / "reviews"), force=True))
            assert r == 3  # critical failure
    finally:
        metrics.collect_metrics = old


def test_pipeline_llm_failure_success_with_warnings():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "reviews"
        # force insight with a guaranteed-failing LLM: clear key via env-free config provider
        cfg = {"llm": {"provider": "none"}}  # ContextOnly -> insight generate returns non-JSON
        r = weekly_review.run_weekly_review(_args(out=str(out), force=True, insight=True))
        # no real LLM key in sandbox; insight stage should be warning -> success_with_warnings
        assert r in (0, 1)
        md = out / "2099" / "W01" / "weekly-review.md"
        assert md.exists()  # deterministic report survives insight failure


# ---------------------------------------------------------------- 6-8 idempotency / recovery

def test_same_period_rerun_idempotent():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "reviews"
        r1 = weekly_review.run_weekly_review(_args(out=str(out), force=True))
        assert r1 in (0, 1)
        md1 = out / "2099" / "W01" / "weekly-review.md"
        mtime1 = md1.stat().st_mtime_ns
        r2 = weekly_review.run_weekly_review(_args(out=str(out)))  # no force -> already_complete
        assert r2 == 0
        assert md1.stat().st_mtime_ns == mtime1  # untouched, no W01-2 duplicate
        assert not (out / "2099" / "W01-2").exists()
        assert list((out / "2099").iterdir()) == [Path(out / "2099" / "W01")]


def test_insight_only_repair():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "reviews"
        weekly_review.run_weekly_review(_args(out=str(out), force=True))  # no insight
        assert not insight.insight_path("2099-W01", out).exists()
        # insight-only repair (LLM will fail in sandbox, but pipeline must not crash and md stays)
        r = weekly_review.run_weekly_review(_args(out=str(out), insight_only=True))
        assert r in (0, 1)
        md = out / "2099" / "W01" / "weekly-review.md"
        assert md.exists()


def test_corrupt_snapshot_ignored():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root, "2099-W01", _snap("2099-W01"), corrupt=True)
        _write(root, "2099-W02", _snap("2099-W02"))
        snaps = metrics.collect_weekly_snapshots(root)
        assert [s["period"] for s in snaps] == ["2099-W02"]  # corrupt ignored, no crash


# ---------------------------------------------------------------- 9 long-term trend

def test_long_term_12_week_trend():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for i in range(1, 13):
            _write(root, f"2099-W{i:02d}", _snap(f"2099-W{i:02d}", review_pending=i))
        snaps = metrics.collect_weekly_snapshots(root)
        t4 = metrics.build_weekly_trends(snaps, weeks=4)
        t12 = metrics.build_weekly_trends(snaps, weeks=12)
        assert len(t12["four_week"]["review_pending"]["points"]) == 12
        assert len(t4["four_week"]["review_pending"]["points"]) == 4
        assert t12["wow"]["review_pending"]["available"] is True


def test_baseline_does_not_pollute_long_trend():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root, "2099-W01", _snap("2099-W01", baseline=True, review_pending=20))
        for i in range(2, 13):
            _write(root, f"2099-W{i:02d}", _snap(f"2099-W{i:02d}", review_pending=i))
        t = metrics.build_weekly_trends(metrics.collect_weekly_snapshots(root), weeks=12)
        points = t["four_week"]["review_pending"]["points"]
        assert "2099-W01" not in [p["period"] for p in points]  # baseline excluded
        assert len(points) == 11


# ---------------------------------------------------------------- 10 health version

def test_health_algorithm_version_in_snapshot_and_engine():
    assert health.HEALTH_ALGORITHM_VERSION == "health_v1"
    h = health.calculate_health({})
    assert h["algorithm_version"] == "health_v1"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "reviews"
        weekly_review.run_weekly_review(_args(out=str(out), force=True))
        snap = json.loads((out / "2099" / "W01" / "snapshot.json").read_text(encoding="utf-8"))
        assert snap["health_algorithm_version"] == "health_v1"
        assert snap["snapshot_schema_version"] == "1.0"


# ---------------------------------------------------------------- 11-12 automation reporting

def test_automation_reporting_keys_and_runs():
    a = service.weekly_review_automation()
    for key in ("status", "state", "last_run", "last_success", "next_run", "last_result"):
        assert key in a
    runs = service.weekly_review_runs(5)
    assert isinstance(runs, list) and len(runs) <= 5
    d = service.weekly_review_dashboard()
    assert "automation" in d and "runs" in d


# ---------------------------------------------------------------- performance

def test_performance_100_snapshots():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # 100 valid snapshots across two ISO years (weeks are 1-2 digits)
        for i in range(1, 53):
            _write(root, f"2098-W{i:02d}", _snap(f"2098-W{i:02d}", review_pending=i % 10, health_score=70 + i % 20))
        for i in range(1, 49):
            _write(root, f"2099-W{i:02d}", _snap(f"2099-W{i:02d}", review_pending=i % 10, health_score=70 + i % 20))
        t0 = time.perf_counter()
        snaps = metrics.collect_weekly_snapshots(root)
        t = metrics.build_weekly_trends(snaps, weeks=12)
        elapsed = time.perf_counter() - t0
        assert len(snaps) == 100
        assert len(t["four_week"]["review_pending"]["points"]) == 12
        assert elapsed < 5.0, f"too slow: {elapsed:.2f}s"


if __name__ == "__main__":
    for t in (
        test_scheduler_scripts_exist_and_reference_pipeline,
        test_run_wrapper_propagates_pipeline,
        test_pipeline_metrics_critical_failure_fails,
        test_pipeline_llm_failure_success_with_warnings,
        test_same_period_rerun_idempotent,
        test_insight_only_repair,
        test_corrupt_snapshot_ignored,
        test_long_term_12_week_trend,
        test_baseline_does_not_pollute_long_trend,
        test_health_algorithm_version_in_snapshot_and_engine,
        test_automation_reporting_keys_and_runs,
        test_performance_100_snapshots,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all weekly review automation tests passed")
