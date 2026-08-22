"""Judge Variance tests (offline): repeated-result capture, stable/variance
classification, stats, CC API, weekly metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.judge_variance import (  # noqa: E402
    STABLE_INSUFFICIENT, STABLE_SUFFICIENT, VARIANCE,
    classify_variance, judge_passed, judge_variance_stats,
    render_variance_markdown,
)
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402


def _judge(relevance, confidence=0.9):
    return {"relevance": relevance, "confidence": confidence}


def test_judge_passed_semantics():
    assert judge_passed(_judge("relevant")) is True
    assert judge_passed(_judge("irrelevant")) is False
    assert judge_passed({}) is False
    assert judge_passed(None) is False


def test_classify_variance():
    assert classify_variance([_judge("relevant"), _judge("relevant"), _judge("relevant")]) == STABLE_SUFFICIENT
    assert classify_variance([_judge("irrelevant"), _judge("irrelevant")]) == STABLE_INSUFFICIENT
    assert classify_variance([_judge("relevant"), _judge("irrelevant"), _judge("relevant")]) == VARIANCE
    assert classify_variance([]) == "unknown"


def test_variance_stats():
    entries = [
        {"query_id": "a", "results": [_judge("relevant")] * 3, "classification": STABLE_SUFFICIENT},
        {"query_id": "b", "results": [_judge("irrelevant")] * 3, "classification": STABLE_INSUFFICIENT},
        {"query_id": "c", "results": [_judge("relevant"), _judge("irrelevant")], "classification": VARIANCE},
    ]
    s = judge_variance_stats(entries)
    assert s["tested_queries"] == 3
    assert s["stable_count"] == 2
    assert s["stable_rate"] == round(100.0 * 2 / 3, 1)
    assert s["flip_count"] == 1
    assert s["flip_rate"] == round(100.0 * 1 / 3, 1)
    assert s["variance_queries"] == ["c"]
    assert s["sample_too_small"] is False  # n >= 3


def test_variance_stats_sample_too_small():
    s = judge_variance_stats([{"query_id": "a", "results": [], "classification": STABLE_SUFFICIENT}])
    assert s["sample_too_small"] is True


def test_render_variance_markdown():
    entries = [
        {"query_id": "q1", "results": [_judge("relevant")] * 3, "classification": STABLE_SUFFICIENT},
        {"query_id": "q2", "results": [_judge("irrelevant")] * 3, "classification": STABLE_INSUFFICIENT},
    ]
    stats = judge_variance_stats(entries)
    md = render_variance_markdown(entries, stats, {"runs": 3})
    for token in ("# Judge Variance Report", "Stable Rate", "Flip Rate", "q1", "q2"):
        assert token in md


def test_service_judge_variance_api(tmp_path, monkeypatch):
    ev = tmp_path / "RAG Evaluation"
    ev.mkdir(parents=True)
    (ev / "latest_judge_variance.json").write_text(json.dumps({
        "run_id": "jv-1", "runs": 3,
        "stats": {"tested_queries": 3, "stable_rate": 66.7, "flip_rate": 33.3,
                  "stable_sufficient_count": 1, "stable_insufficient_count": 1,
                  "flip_count": 1, "sample_too_small": False},
        "entries": [{"query_id": "q1", "results": [], "classification": "variance"}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(service, "EVAL_ROOT", ev)
    r = service.judge_variance()
    assert r["ok"] is True
    assert r["judge_variance"]["stats"]["flip_rate"] == 33.3
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "none")
    assert service.judge_variance()["judge_variance"] is None


def test_weekly_metrics_include_judge_variance(tmp_path):
    vault = tmp_path
    (vault / "40_Outputs" / "RAG Evaluation").mkdir(parents=True)
    (vault / "40_Outputs" / "RAG Evaluation" / "latest.json").write_text(
        '{"metrics": {"overall": {}}}', encoding="utf-8")
    (vault / "40_Outputs" / "RAG Evaluation" / "latest_judge_variance.json").write_text(json.dumps({
        "stats": {"tested_queries": 6, "stable_rate": 100.0, "flip_rate": 0.0,
                  "sample_too_small": False}}, ensure_ascii=False), encoding="utf-8")
    re_ = review_metrics.collect_rag_evaluation(vault)
    assert re_ is not None
    assert re_["judge_variance"]["flip_rate"] == 0.0
    assert re_["judge_variance"]["stable_rate"] == 100.0
