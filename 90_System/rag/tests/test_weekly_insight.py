"""AI Weekly Insight tests (Phase D2): parse, validate, hallucination rejection, cache.

Offline: mock LLM adapter; no network / API key.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))

import insight


class FakeAdapter:
    def __init__(self, raw: str, raise_exc: Exception | None = None):
        self.raw = raw
        self.raise_exc = raise_exc

    def generate(self, question: str, context: str) -> str:
        if self.raise_exc:
            raise self.raise_exc
        return self.raw


CFG = {"llm": {"provider": "deepseek", "model": {"name": "deepseek-chat"}, "timeout": 30}}


def _input(metrics_value=10):
    return {
        "period": "2026-W33",
        "metrics": {"review_pending": metrics_value, "wiki_new": 20, "judge_failed": 0},
        "health": {"score": 74, "status": "attention", "dimensions": {}},
        "wow": {"review_pending": {"available": False, "current": {"period": "2026-W33", "value": metrics_value}}},
        "four_week": {"review_pending": {"periods": ["2026-W33"], "points": []}},
        "attention": [{"level": "warning", "count": metrics_value, "label": "项需要人工审核"}],
        "evidence": [],
    }


def _metrics_like(pending=10):
    return {
        "period": "2026-W33",
        "wiki": {"wiki_total": 20, "wiki_reviewed": 4, "wiki_stable": 3, "wiki_draft": 13, "wiki_unknown": 0},
        "growth": {"new_this_week": 20, "updated_this_week": 0},
        "review": {"pending_human": pending, "judge_passed": 8, "judge_failed": 0,
                   "candidates": 18, "total": 18, "needs_review": pending},
        "gaps": {"knowledge_gaps_total": 6, "knowledge_gaps_pending": 5, "knowledge_gaps_resolved": 1},
        "projects": [],
        "stale_risk": [],
    }


def _valid_insight(metric_value=10, actions=1):
    return {
        "summary": "Review backlog is the main concern; judge failures remain zero.",
        "changes": [{"title": "Review backlog", "detail": "10 pending",
                     "evidence": [{"type": "metric", "metric": "review_pending", "current": metric_value}]}],
        "attention": [{"priority": "high", "title": "Review", "reason": "10 pending",
                       "evidence": [{"type": "metric", "metric": "review_pending", "current": metric_value}]}],
        "actions": [{"priority": "high", "action": "Process review queue", "reason": "backlog"}] * actions,
    }


# ---------------------------------------------------------------- parse

def test_parse_valid_json():
    data = insight._extract_json('{"summary": "x", "changes": [], "attention": [], "actions": []}')
    assert data and data["summary"] == "x"


def test_parse_markdown_fence():
    raw = '```json\n{"summary": "x", "changes": [], "attention": [], "actions": []}\n```'
    data = insight._extract_json(raw)
    assert data and data["summary"] == "x"


def test_parse_invalid_fail_closed():
    assert insight._extract_json("not json") is None


# ---------------------------------------------------------------- validate

def test_validate_missing_schema_field():
    ok, reason = insight.validate_insight({"summary": "x"}, _input())
    assert ok is False and "missing_field" in reason


def test_validate_hallucinated_metric_rejected():
    data = _valid_insight(metric_value=14)  # real=10, AI says 14
    ok, reason = insight.validate_insight(data, _input(metrics_value=10))
    assert ok is False
    assert "hallucinated_metric:review_pending" in reason


def test_validate_correct_metric_ok():
    data = _valid_insight(metric_value=10)
    ok, reason = insight.validate_insight(data, _input(metrics_value=10))
    assert ok is True


def test_validate_actions_limit():
    data = _valid_insight(actions=4)
    ok, reason = insight.validate_insight(data, _input())
    assert ok is False and "actions_exceed" in reason


# ---------------------------------------------------------------- generate

def test_generate_valid_available():
    r = insight.generate_insight(_metrics_like(), {}, {}, [], CFG, adapter=FakeAdapter(
        '```json\n' + __import__("json").dumps(_valid_insight(10), ensure_ascii=False) + '\n```'),
        model_label="deepseek:deepseek-chat")
    assert r["status"] == "available"
    assert r["insight"]["prompt_version"] == insight.PROMPT_VERSION


def test_generate_llm_timeout_unavailable():
    r = insight.generate_insight({}, {}, {}, [], CFG, adapter=FakeAdapter("", raise_exc=TimeoutError("timeout")))
    assert r["status"] == "unavailable"
    assert "fail-closed" in r["reason"]


def test_generate_llm_error_unavailable():
    r = insight.generate_insight({}, {}, {}, [], CFG, adapter=FakeAdapter("", raise_exc=RuntimeError("boom")))
    assert r["status"] == "unavailable"


def test_generate_hallucinated_rejected():
    r = insight.generate_insight(_metrics_like(10), {}, {}, [], CFG, adapter=FakeAdapter(
        __import__("json").dumps(_valid_insight(14), ensure_ascii=False)), model_label="deepseek:deepseek-chat")
    assert r["status"] == "unavailable"
    assert "hallucinated_metric" in r["reason"]


def test_generate_bad_json_unavailable():
    r = insight.generate_insight({}, {}, {}, [], CFG, adapter=FakeAdapter("not json"))
    assert r["status"] == "unavailable"


# ---------------------------------------------------------------- cache

def test_cache_roundtrip_and_key():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        r = {"status": "available", "prompt_version": insight.PROMPT_VERSION,
             "model": "deepseek:deepseek-chat", "insight": {"summary": "s"}}
        p = insight.save_insight("2026-W33", r, root)
        assert p.exists()
        cached = insight.load_cached_insight("2026-W33", root, "deepseek:deepseek-chat")
        assert cached is not None and cached["insight"]["summary"] == "s"
        # different model -> no cache
        assert insight.load_cached_insight("2026-W33", root, "other:model") is None
        # different prompt version -> no cache
        r2 = {"status": "available", "prompt_version": "weekly_insight_v2", "model": "deepseek:deepseek-chat",
              "insight": {}}
        insight.save_insight("2026-W34", r2, root)
        assert insight.load_cached_insight("2026-W34", root, "deepseek:deepseek-chat") is None


if __name__ == "__main__":
    for t in (
        test_parse_valid_json, test_parse_markdown_fence, test_parse_invalid_fail_closed,
        test_validate_missing_schema_field, test_validate_hallucinated_metric_rejected,
        test_validate_correct_metric_ok, test_validate_actions_limit,
        test_generate_valid_available, test_generate_llm_timeout_unavailable,
        test_generate_llm_error_unavailable, test_generate_hallucinated_rejected,
        test_generate_bad_json_unavailable, test_cache_roundtrip_and_key,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all insight tests passed")
