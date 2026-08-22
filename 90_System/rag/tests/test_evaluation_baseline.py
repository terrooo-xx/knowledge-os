"""Evaluation Baseline tests (offline): approved wiki status detection,
reindex detection, same benchmark version, recovered retention,
REAL_REGRESSION/JUDGE_VARIANCE, baseline creation/status/delta, CC API,
weekly metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = RAG_DIR / "scripts"
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(SCRIPTS_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.evaluation_baseline import (  # noqa: E402
    STATUS_IMPROVED, STATUS_REGRESSED, STATUS_STABLE, STATUS_UNVERIFIED,
    classify_baseline_status, create_baseline, load_baseline, regression_check,
    save_baseline,
)
from rag_engine.gap_diagnosis import compare_runs  # noqa: E402
import evaluation_baseline as bl_cli  # noqa: E402
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402

CORE = {"q_freertos_stack_overflow", "q_freertos_task_notification",
        "q_stm32_timer_pwm", "q_wsl_ubuntu"}


def _rec(qid, final="answered", windows=None):
    return {"query_id": qid, "final": {"status": final},
            "evidence_windows": windows if windows is not None else
            [{"source": "20_Wiki/a.md", "text": "x" * 10}]}


# ---------------------------------------------------------------- status classification


def test_baseline_status_classification():
    assert classify_baseline_status(real_regressions=0, recovered=0, core_recovered_retained=True) == STATUS_STABLE
    assert classify_baseline_status(real_regressions=0, recovered=1, core_recovered_retained=True) == STATUS_IMPROVED
    assert classify_baseline_status(real_regressions=1, recovered=0, core_recovered_retained=True) == STATUS_REGRESSED
    assert classify_baseline_status(real_regressions=0, recovered=0, verified=False) == STATUS_UNVERIFIED
    # JUDGE_VARIANCE 不会导致 REGRESSED（它不是 real_regressions）
    assert classify_baseline_status(real_regressions=0, recovered=0, core_recovered_retained=True) == STATUS_STABLE


def test_regression_check_delta_and_warning():
    base = {"run_id": "bl-1", "coverage": 82.1}
    cur = {"run_id": "r2", "coverage": 82.1}
    c = regression_check(cur, base)
    assert c["delta_pp"] == 0.0 and c["status"] == STATUS_STABLE
    c2 = regression_check({"run_id": "r3", "coverage": 78.0}, base)
    assert c2["delta_pp"] == -4.1 and c2["status"] == STATUS_REGRESSED
    assert c2["warning"]
    c3 = regression_check({"run_id": "r4", "coverage": 85.0}, base)
    assert c3["status"] == STATUS_IMPROVED


def test_create_baseline_roundtrip():
    diff = {"counts": {"recovered": 0, "regressed": 0, "new_failure": 0},
            "regression_classes": {"REAL_REGRESSION": 0, "JUDGE_VARIANCE": 1, "UNKNOWN": 0},
            "recovered_queries": [], "regressed_queries": []}
    meta = {"query_count": 28, "coverage": 82.1, "knowledge_missing_rate": 17.9}
    wa = {"approved": 4, "total": 4, "approved_all": True,
          "core_recovered_queries": list(CORE)}
    b = create_baseline("run-x", meta, diff, wiki_approval=wa, answered_queries=list(CORE))
    assert b["baseline_id"] == "bl-run-x"
    assert b["status"] == STATUS_STABLE
    assert b["coverage"] == 82.1
    assert b["real_regressions"] == 0
    assert b["judge_variance_count"] == 1


def test_baseline_unverified_when_not_approved():
    diff = {"counts": {"recovered": 0, "regressed": 0},
            "regression_classes": {"REAL_REGRESSION": 0, "JUDGE_VARIANCE": 1, "UNKNOWN": 0},
            "recovered_queries": [], "regressed_queries": []}
    wa = {"approved": 3, "total": 4, "approved_all": False,
          "core_recovered_queries": list(CORE)}
    b = create_baseline("run-x", {"coverage": 82.1}, diff, wiki_approval=wa)
    assert b["status"] == STATUS_UNVERIFIED


# ---------------------------------------------------------------- real state


def test_real_approved_wiki_status_detection():
    wa = bl_cli.wiki_approval_status()
    assert wa["total"] == 4
    assert wa["approved"] == 4          # WSL 已批准（Phase 18 Final）
    assert wa["approved_all"] is True
    assert wa["pending_wikis"] == []
    assert set(wa["core_recovered_queries"]) == CORE


def test_real_reindex_contains_four_wikis():
    db = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\rag\database\main_vector_db\records.jsonl")
    srcs = set()
    for line in db.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        s = (json.loads(line).get("metadata") or {}).get("source", "")
        if s.startswith("20_Wiki"):
            srcs.add(s)
    for name in ("栈溢出", "任务通知", "PWM", "WSL"):
        assert any(name in s for s in srcs), f"{name} not indexed"
    # 3 个已批准 Wiki 在索引中 status=reviewed
    reviewed = []
    for line in db.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        md = r.get("metadata") or {}
        if any(k in md.get("source", "") for k in ("栈溢出", "任务通知", "PWM")):
            reviewed.append(md.get("status"))
    assert all(s == "reviewed" for s in reviewed)


def test_same_benchmark_version():
    import yaml
    bench = yaml.safe_load((RAG_DIR / "evaluation" / "benchmark.yaml").read_text(encoding="utf-8"))
    assert bench.get("benchmark_version") == "1.0"
    assert len(bench["queries"]) == 29  # 28 + 1 warmup 使用量


def test_real_phase18_diff_retains_four():
    diff_path = (RAG_DIR.parent.parent / "40_Outputs" / "RAG Evaluation" / "diff" /
                 "eval-20260815T154946__eval-20260815T163659" / "evaluation_diff.json")
    data = json.loads(diff_path.read_text(encoding="utf-8"))
    d = data["diff"]
    assert d["counts"]["recovered"] == 0
    assert d["counts"]["regressed"] == 0
    assert d["counts"]["new_failure"] == 0
    answered = [i for i in d["items"] if i["query_id"] in CORE and i["after_status"] == "answered"]
    assert len(answered) == 4
    # q_drone_power 仍是 knowledge_missing（JUDGE_VARIANCE，非 REGRESSION）
    dp = next(i for i in d["items"] if i["query_id"] == "q_drone_power")
    assert dp["after_status"] == "knowledge_missing"
    assert dp["change"] in ("UNCHANGED_FAILED", "REGRESSED")


def test_real_baseline_established_stable():
    b = load_baseline(Path(r"D:\KnowledgeBase\Obsidian Vault\40_Outputs\RAG Evaluation\baseline.json"))
    assert b is not None
    assert b["coverage"] == 89.3
    assert b["status"] == STATUS_STABLE   # Phase 21 后：用户批准 Git Wiki + 复验 run -> STABLE
    assert b["run_id"] == "eval-20260817T162956"
    assert (b.get("wiki_approval") or {}).get("approved_all") is True


# ---------------------------------------------------------------- CC API / weekly


def test_service_baseline_api(tmp_path, monkeypatch):
    ev = tmp_path / "RAG Evaluation"
    ev.mkdir(parents=True)
    save_baseline(ev / "baseline.json", {
        "baseline_id": "bl-x", "run_id": "bl-run", "coverage": 82.1,
        "knowledge_missing_rate": 17.9, "status": "STABLE",
        "recovered_queries": [], "regressed_queries": [], "real_regressions": 0,
        "judge_variance_count": 0, "wiki_approval": {}, "established_at": "now",
        "benchmark_version": "1.0", "query_count": 28, "notes": ""})
    monkeypatch.setattr(service, "EVAL_ROOT", ev)
    monkeypatch.setattr(service, "evaluation_latest", lambda: {
        "latest": {"run_id": "run-x",
                   "metrics": {"overall": {"answer_coverage": 82.1, "knowledge_missing_rate": 17.9}}}})
    r = service.evaluation_baseline()
    assert r["ok"] is True
    assert r["baseline"]["coverage"] == 82.1
    assert r["check"]["delta_pp"] == 0.0
    assert r["check"]["status"] == "STABLE"


def test_weekly_metrics_include_baseline():
    re_ = review_metrics.collect_rag_evaluation()
    assert re_ is not None
    bl = re_.get("baseline")
    assert bl is not None
    assert bl["coverage"] == 89.3
    assert bl["status"] == "STABLE"
    assert bl["delta_pp"] == 0.0
    assert bl["check_status"] == "STABLE"

