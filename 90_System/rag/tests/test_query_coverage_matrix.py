"""Query Coverage Matrix tests (offline): structure, likely_recoverable
semantics, before/after rows from the real compilation plan."""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.wiki_compilation import LIKELY_FALSE, LIKELY_TRUE, LIKELY_UNKNOWN, load_compilation

COMPILATION = RAG_DIR / "evaluation" / "wiki_compilation.yaml"


def _rows():
    return [
        {"query_id": "q1", "before": {"final_status": "knowledge_missing", "source": "raw"},
         "requirements": {"r1": "covered", "r2": "covered"},
         "expected_after": {"likely_recoverable": LIKELY_TRUE}},
        {"query_id": "q2", "before": {"final_status": "knowledge_missing", "source": "raw"},
         "requirements": {"r1": "missing"},
         "expected_after": {"likely_recoverable": LIKELY_FALSE}},
    ]


def test_matrix_fields_present():
    rows = _rows()
    for r in rows:
        assert r["query_id"]
        assert r["before"]["final_status"] == "knowledge_missing"
        assert r["requirements"]
        assert r["expected_after"]["likely_recoverable"] in (LIKELY_TRUE, LIKELY_FALSE, LIKELY_UNKNOWN)


def test_likely_true_requires_covered():
    # likely=true 应基于需求覆盖；covered=missing 时不应标 true
    rows = _rows()
    for r in rows:
        if r["expected_after"]["likely_recoverable"] == LIKELY_TRUE:
            assert all(v == "covered" for v in r["requirements"].values())
        if r["expected_after"]["likely_recoverable"] == LIKELY_FALSE:
            assert any(v == "missing" for v in r["requirements"].values())


def test_real_coverage_matrix_after_backfill():
    comp = load_compilation(COMPILATION)
    rows = [row for g in comp["gaps"] for t in g["wiki_tasks"]
            for row in t.get("coverage_matrix") or []]
    assert rows
    # Phase 21 后：git P1 已恢复，应回填 after=RECOVERED；已覆盖任务 query 均为 answered
    recovered = [r for r in rows if (r.get("after") or {}).get("change") == "RECOVERED"]
    assert recovered, "coverage matrix 应已由 evaluation_diff 回填 after"
    by_q = {r["query_id"]: r for r in rows}
    assert by_q["q_freertos_stack_overflow"]["after"]["final_status"] == "answered"
    assert by_q["q_freertos_task_notification"]["after"]["final_status"] == "answered"
    assert by_q["q_stm32_timer_pwm"]["after"]["final_status"] == "answered"
    # Phase 21：git P1 不再 source-limited，已恢复为 answered
    assert by_q["q_git_config"]["after"]["final_status"] == "answered"
    assert by_q["q_git_config"]["after"]["recovered"] is True

