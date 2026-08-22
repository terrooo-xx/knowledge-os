"""Wiki Benchmark Validation tests (offline): before/after diff, RECOVERED /
REAL_REGRESSION / JUDGE_VARIANCE preservation, golden regression flag,
reindex metadata, CC API, weekly metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.gap_diagnosis import compare_runs  # noqa: E402
from rag_engine.wiki_compilation import load_compilation  # noqa: E402
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402

DIFF = RAG_DIR.parent.parent / "40_Outputs" / "RAG Evaluation" / "diff" / \
       "eval-20260814T232719__eval-20260815T154946" / "evaluation_diff.json"


def _rec(qid, final="answered", windows=None):
    return {"query_id": qid, "final": {"status": final},
            "evidence_windows": windows if windows is not None else
            [{"source": "20_Wiki/a.md", "text": "x" * 10}]}


def test_recovered_classification():
    before = [_rec("q1", "knowledge_missing")]
    after = [_rec("q1", "answered")]
    d = compare_runs(before, after)
    assert d["counts"]["recovered"] == 1
    assert d["items"][0]["change"] == "RECOVERED"


def test_regression_class_preserved_for_drone_power():
    # q_drone_power：同文档集合，仅 Judge 翻转 -> JUDGE_VARIANCE
    wins = [{"source": s, "text": "t"} for s in ("a", "b", "c")]
    before = [_rec("q1", "answered", wins)]
    after = [_rec("q1", "knowledge_missing", list(reversed(wins)))]
    d = compare_runs(before, after)
    assert d["items"][0]["change"] == "REGRESSED"
    assert d["items"][0]["regression_class"] == "JUDGE_VARIANCE"


def test_real_phase17_diff_counts():
    data = json.loads(DIFF.read_text(encoding="utf-8"))
    diff = data["diff"]
    assert diff["counts"]["recovered"] == 4
    assert diff["counts"]["regressed"] == 1
    assert diff["counts"]["new_failure"] == 0
    # q_drone_power 保持 JUDGE_VARIANCE，不当作 REAL_REGRESSION
    dp = next(i for i in diff["items"] if i["query_id"] == "q_drone_power")
    assert dp["regression_class"] == "JUDGE_VARIANCE"
    assert diff["regression_classes"]["REAL_REGRESSION"] == 0
    # 恢复的 query 确实是阶段17 Wiki 涉及的
    recovered = {i["query_id"] for i in diff["items"] if i["change"] == "RECOVERED"}
    assert {"q_freertos_stack_overflow", "q_freertos_task_notification",
            "q_stm32_timer_pwm", "q_wsl_ubuntu"} <= recovered


def test_golden_regression_flagged():
    from rag_engine.golden_set import get_entry, load_golden
    golden = load_golden(RAG_DIR / "evaluation" / "golden.yaml")
    e = get_entry(golden["entries"], "q_freertos_stack_overflow")
    assert e is not None
    assert (e.get("review") or {}).get("review_required") is True  # 状态变化 -> 需人工复核


def test_reindex_metadata_chunk_growth():
    # 阶段15: 34 chunks -> 阶段17: 43 chunks（+9）
    db = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\database\main_vector_db\records.jsonl")
    count = sum(1 for line in db.read_text(encoding="utf-8").splitlines() if line.strip())
    assert count > 36
    assert count >= 43


def test_service_gaps_show_source_status_and_resolved():
    r = service.evaluation_gaps()
    assert r["ok"] is True
    resolved = [g for g in r["gaps"] if g.get("status") == "resolved"]
    assert any(g["id"] == "gap_freertos_config_debug" for g in resolved)
    open_p0 = [g for g in r["gaps"] if g.get("status") == "open" and g.get("priority") == "P0"]
    assert open_p0 == []
    # source status 已关联
    assert all("source_status" in g for g in r["gaps"])


def test_weekly_metrics_include_recovery():
    re_ = review_metrics.collect_rag_evaluation()
    assert re_ is not None
    d = re_.get("diff") or {}
    # 最新 diff = Phase 21 验证 run（git P1 + drone_power 恢复，0 regressed）
    assert d.get("recovered") == 2
    assert d.get("regressed") == 0
    g = re_.get("gaps") or {}
    assert g.get("open") == 3
    assert g.get("resolved") == 4
    bl = re_.get("baseline") or {}
    assert bl.get("status") == "STABLE"
