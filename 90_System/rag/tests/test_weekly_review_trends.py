"""Weekly Review trends tests (Phase C): snapshots reader, WoW, 4-week, baseline.

Offline: uses temp snapshot fixtures (never writes real Outputs). Corrupt /
temp files ignored; missing fields tolerated; no fabricated history.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(CTRL_DIR))

import metrics


def _snap(period, wiki_total=20, new=0, updated=0, review_pending=0, gaps_pending=0,
          stale=0, baseline=False, judge_passed=0, judge_failed=0):
    return {
        "period": period,
        "wiki_total": wiki_total,
        "growth_delta": {"new_wiki": new, "updated_wiki": updated},
        "review_pending": review_pending,
        "review": {"judge_passed": judge_passed, "judge_failed": judge_failed},
        "knowledge_gaps_pending": gaps_pending, "knowledge_gaps_total": gaps_pending,
        "stale_items": [{}] * stale,
        "baseline": {"is_baseline_period": baseline, "note": "x"},
    }


def _write(root: Path, period: str, data: dict, corrupt: bool = False):
    d = root / period[:4] / ("W" + period[-2:])
    d.mkdir(parents=True, exist_ok=True)
    if corrupt:
        (d / "snapshot.json").write_text("{not json", encoding="utf-8")
    else:
        (d / "snapshot.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _trends(*weeks):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for w in weeks:
            _write(root, w["period"], w["data"])
        snaps = metrics.collect_weekly_snapshots(root)
        return metrics.build_weekly_trends(snaps), snaps


# ---------------------------------------------------------------- reader

def test_snapshot_iso_sort_w9_w10_w11():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for p in ("2025-W9", "2025-W10", "2025-W11"):
            _write(root, p, _snap(p))
        snaps = metrics.collect_weekly_snapshots(root)
        assert [s["period"] for s in snaps] == ["2025-W9", "2025-W10", "2025-W11"]


def test_snapshot_ignores_corrupt_and_temp():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root, "2026-W33", _snap("2026-W33"))
        _write(root, "2026-W32", {"period": "2026-W32"}, corrupt=True)  # corrupt -> ignored
        tmp = root / "2026" / "W31" / "snapshot.json.tmp"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("{}", encoding="utf-8")  # temp -> ignored
        snaps = metrics.collect_weekly_snapshots(root)
        assert [s["period"] for s in snaps] == ["2026-W33"]


def test_missing_fields_no_crash():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root, "2026-W33", {"period": "2026-W33"})  # minimal, missing everything
        t, _ = _trends()
        # rebuild with the temp root
        t = metrics.build_weekly_trends(metrics.collect_weekly_snapshots(root))
        assert t["wow"]["review_pending"]["available"] is False
        assert t["wow"]["review_pending"]["reason"] in ("baseline_current", "missing_data", "no_previous")


# ---------------------------------------------------------------- WoW

def test_wow_stock_delta():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", review_pending=8, baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", review_pending=10)},
        {"period": "2026-W35", "data": _snap("2026-W35", review_pending=10)},
    )
    w = t["wow"]["review_pending"]
    assert w["available"] is True
    assert w["current"]["value"] == 10 and w["previous"]["value"] == 10
    assert w["delta"] == 0 and w["direction"] == "flat"


def test_wow_flow_percent():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", new=4, baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", new=6)},
    )
    # W34's previous is baseline -> not comparable; use W33+W34+W35 to compare W35 vs W34
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", new=4, baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", new=6)},
        {"period": "2026-W35", "data": _snap("2026-W35", new=9)},
    )
    w = t["wow"]["wiki_new"]
    assert w["available"] is True
    assert w["delta"] == 3 and w["delta_percent"] == 50.0
    assert w["direction"] == "up" and w["health_effect"] == "positive"


def test_wow_prev_zero_percent_null():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", new=0, baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", new=0)},
        {"period": "2026-W35", "data": _snap("2026-W35", new=5)},
    )
    w = t["wow"]["wiki_new"]  # W35 vs W34: prev=0 -> percent null
    assert w["available"] is True
    assert w["delta"] == 5
    assert w["delta_percent"] is None


def test_single_snapshot_not_available():
    t, _ = _trends({"period": "2026-W33", "data": _snap("2026-W33", baseline=True)})
    assert t["availability"]["has_history"] is False
    assert t["wow"]["review_pending"]["available"] is False


# ---------------------------------------------------------------- baseline

def test_baseline_boundary_w34_not_available():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", review_pending=9)},
    )
    assert t["wow"]["review_pending"]["available"] is False
    assert t["wow"]["review_pending"]["reason"] == "baseline_boundary"


def test_w35_comparable_after_baseline():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", review_pending=9)},
        {"period": "2026-W35", "data": _snap("2026-W35", review_pending=3)},
    )
    assert t["wow"]["review_pending"]["available"] is True
    assert t["wow"]["review_pending"]["previous"]["period"] == "2026-W34"
    assert t["wow"]["review_pending"]["delta"] == -6


def test_four_week_only_real_no_zeros():
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", new=20, baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", new=4)},
        {"period": "2026-W35", "data": _snap("2026-W35", new=6)},
    )
    fw = t["four_week"]["wiki_new"]
    # baseline W33 excluded -> only W34, W35 (real values, no zero fill)
    assert fw["available"] is True
    assert [p["period"] for p in fw["points"]] == ["2026-W34", "2026-W35"]
    assert all(p["value"] is not None and p["value"] != 0 for p in fw["points"])
    # latest WoW includes per-period mapping
    assert t["wow_by_period"]["review_pending"]["2026-W34"]["available"] is False
    assert t["wow_by_period"]["review_pending"]["2026-W35"]["available"] is True


def test_wow_health_effect_semantics():
    # review_pending up = negative; wiki_new up = positive
    t, _ = _trends(
        {"period": "2026-W33", "data": _snap("2026-W33", baseline=True)},
        {"period": "2026-W34", "data": _snap("2026-W34", review_pending=5, new=2)},
        {"period": "2026-W35", "data": _snap("2026-W35", review_pending=8, new=4)},
    )
    assert t["wow"]["review_pending"]["health_effect"] == "negative"  # pending up = bad
    assert t["wow"]["wiki_new"]["health_effect"] == "positive"        # new up = good


# ---------------------------------------------------------------- dashboard integration

def test_dashboard_trend_structure():
    import service  # noqa: F401  (needs control_center on path)
    d = service.weekly_review_dashboard()
    assert "trend" in d and "wow" in d["trend"] and "four_week" in d["trend"]
    assert "wow_by_period" in d["trend"] and "availability" in d["trend"]
    # real env: only W33 baseline -> no fake history
    assert d["has_trend"] is False
    assert d["trend"]["wow"]["review_pending"]["available"] is False


if __name__ == "__main__":
    for t in (
        test_snapshot_iso_sort_w9_w10_w11,
        test_snapshot_ignores_corrupt_and_temp,
        test_missing_fields_no_crash,
        test_wow_stock_delta,
        test_wow_flow_percent,
        test_wow_prev_zero_percent_null,
        test_single_snapshot_not_available,
        test_baseline_boundary_w34_not_available,
        test_w35_comparable_after_baseline,
        test_four_week_only_real_no_zeros,
        test_wow_health_effect_semantics,
        test_dashboard_trend_structure,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all weekly review trends tests passed")

