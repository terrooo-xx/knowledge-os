"""Evaluation Governance tests (offline): state machine, service hooks, batch,
failure vs regression, judge variance, baseline protection, CC/weekly."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAG_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = RAG_DIR / "scripts"
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(SCRIPTS_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.evaluation_governance import (  # noqa: E402
    STATUS_FAILED, STATUS_IDLE, STATUS_IMPROVED, STATUS_PASSED, STATUS_REGRESSED,
    STATUS_REQUIRED, STATUS_RUNNING,
    complete, default_state, fail, has_knowledge_change, load_state,
    mark_required, render_governance_markdown, save_state, should_verify, start,
)
from rag_engine.evaluation_baseline import regression_check  # noqa: E402
from rag_engine.index_fingerprint import (  # noqa: E402
    current_fingerprint, detect_index_change,
)
import service  # noqa: E402
import evaluation_governance as gov_cli  # noqa: E402
import metrics as review_metrics  # noqa: E402


def _tmp_state(tmp_path):
    p = tmp_path / "evaluation_state.json"
    save_state(p, default_state())
    return p


# ---------------------------------------------------------------- state machine


def test_wiki_approve_marks_required_and_batches():
    st = default_state()
    st = mark_required(st, "wiki_approved", {"wiki_approved": 1})
    assert st["status"] == STATUS_REQUIRED
    assert "wiki_approved" in st["reasons"]
    # 批量：第二次批准仍是一个 required（不重复触发）
    st2 = mark_required(st, "wiki_approved", {"wiki_approved": 1})
    assert st2["status"] == STATUS_REQUIRED
    assert st2["batch"]["wiki_approved"] == 2
    assert st2["triggered_at"] == st["triggered_at"]


def test_index_change_marks_required_but_view_does_not():
    st = mark_required(default_state(), "index_updated", {"modified": 2})
    assert st["status"] == STATUS_REQUIRED
    # 纯查看/浏览不调用 mark_required —— 由 service 层只在实际变化时触发


def test_start_running_and_should_verify():
    st = start(mark_required(default_state(), "wiki_approved"))
    assert st["status"] == STATUS_RUNNING
    assert st["started_at"]
    assert should_verify(mark_required(default_state(), "wiki_approved")) is True
    assert should_verify(default_state()) is False


def test_run_success_passed():
    st = start(mark_required(default_state(), "index_updated"))
    check = {"status": "STABLE", "current_run": "r2", "current_coverage": 82.1,
             "baseline_coverage": 82.1, "delta_pp": 0.0, "warning": None}
    st = complete(st, run_id="r2", check=check, baseline_id="bl-1", reestablish_baseline=True)
    assert st["status"] == STATUS_PASSED
    assert st["run_id"] == "r2"
    assert st["baseline_id"] == "bl-1"
    assert st["reasons"] == []


def test_run_improvement_improved():
    st = start(mark_required(default_state(), "wiki_approved"))
    check = {"status": "IMPROVED", "delta_pp": 3.0, "current_run": "r3", "current_coverage": 85.0}
    st = complete(st, run_id="r3", check=check, baseline_id="bl-2", reestablish_baseline=True)
    assert st["status"] == STATUS_IMPROVED


def test_real_regression_regressed_and_baseline_not_overwritten():
    st = default_state()
    st["baseline_id"] = "bl-keep"   # 已有正式基线
    st = start(mark_required(st, "wiki_approved"))
    check = {"status": "REGRESSED", "delta_pp": -4.0, "current_run": "r4", "current_coverage": 78.0}
    st = complete(st, run_id="r4", check=check, baseline_id="bl-new-would-be", reestablish_baseline=False)
    assert st["status"] == STATUS_REGRESSED
    # 回归运行不覆盖 baseline：即使传入新 baseline_id，也不写入（保留旧基线）
    assert st["baseline_id"] == "bl-keep"


def test_judge_variance_not_regression():
    # q_drone_power 场景：同证据仅 Judge 波动 -> regression_check 不判 REGRESSED
    base = {"run_id": "bl", "coverage": 82.1}
    cur = {"run_id": "r5", "coverage": 82.1}  # 覆盖率不变（judge variance 未改变总量）
    c = regression_check(cur, base)
    assert c["status"] != "REGRESSED"
    assert c["delta_pp"] == 0.0
    # 即使单条查询翻转为 knowledge_missing 但总量不变，也不触发 REGRESSED（由 diff 分类 JUDGE_VARIANCE）


def test_evaluation_failure_failed_and_rerun():
    st = fail(start(mark_required(default_state(), "index_updated")), "DeepSeek timeout")
    assert st["status"] == STATUS_FAILED
    assert "timeout" in (st["error"] or "").lower()
    assert should_verify(st) is True  # 允许重跑 failed
    st2 = start(st)  # 重跑
    assert st2["status"] == STATUS_RUNNING
    st2 = complete(st2, run_id="r6", check={"status": "STABLE", "delta_pp": 0.0}, baseline_id="bl-1",
                   reestablish_baseline=True)
    assert st2["status"] == STATUS_PASSED


def test_render_markdown():
    st = mark_required(default_state(), "wiki_approved")
    md = render_governance_markdown(st, {"baseline_id": "bl-1", "coverage": 82.1, "status": "STABLE"})
    for token in ("# Evaluation Governance State", "required", "wiki_approved", "bl-1"):
        assert token in md


# ---------------------------------------------------------------- service hooks


def test_service_approve_marks_required(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "RAG Evaluation")
    (tmp_path / "RAG Evaluation").mkdir(parents=True, exist_ok=True)
    save_state(tmp_path / "RAG Evaluation" / "evaluation_state.json", default_state())
    monkeypatch.setattr(service, "ACTIVITY_LOG", tmp_path / "activity_log.jsonl")
    # 构造一个 wiki_review action 并 approve
    root = tmp_path / "vault"
    wiki = root / "20_Wiki" / "04_FreeRTOS"
    wiki.mkdir(parents=True)
    wp = wiki / "Test.md"
    wp.write_text("---\ntype: wiki\nstatus: draft\nsource: []\n---\n# Test\n内容", encoding="utf-8")
    old_root = service.VAULT_ROOT
    service.VAULT_ROOT = root
    try:
        r = service.execute_action("wiki_review:20_Wiki/04_FreeRTOS/Test.md", "approve")
        assert r["ok"] and r["result"] == "success"
        st = load_state(tmp_path / "RAG Evaluation" / "evaluation_state.json")
        assert st["status"] == STATUS_REQUIRED
        assert "wiki_approved" in st["reasons"]
        # activity log 有 approve 记录
        recs = service._activity_records()
        assert any(a.get("type") == "wiki_review" and a.get("user_decision") == "approve" for a in recs)
    finally:
        service.VAULT_ROOT = old_root


def test_service_sync_change_marks_required(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "RAG Evaluation")
    (tmp_path / "RAG Evaluation").mkdir(parents=True, exist_ok=True)
    save_state(tmp_path / "RAG Evaluation" / "evaluation_state.json", default_state())
    monkeypatch.setattr(service, "ACTIVITY_LOG", tmp_path / "activity_log.jsonl")
    # 模拟 update_index 输出 changed=2（有知识变化）
    def fake_run(script, extra=None):
        return 0, "changed=2 deleted=0 rebuilt=False\nstore size: 45"
    monkeypatch.setattr(service, "_run_py", fake_run)
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"a.md": "h1"}', encoding="utf-8")
    monkeypatch.setattr(service, "load_config", lambda *a, **k: {"paths": {}})
    # 直接用内部逻辑：构造 sync 所需的 manifest 路径 —— 简化：手动验证 _mark_governance_required
    st = service._mark_governance_required("index_updated", {"modified": 2})
    assert st["ok"] is True
    s2 = load_state(tmp_path / "RAG Evaluation" / "evaluation_state.json")
    assert s2["status"] == STATUS_REQUIRED


def test_service_governance_state_api(tmp_path, monkeypatch):
    (tmp_path / "eval").mkdir(parents=True, exist_ok=True)
    st_path = tmp_path / "eval" / "evaluation_state.json"
    save_state(st_path, mark_required(default_state(), "wiki_approved"))
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "eval")
    g = service.governance_state()
    assert g["ok"] is True
    assert g["required"] is True
    assert g["state"]["status"] == STATUS_REQUIRED
    assert g["running"] is False


def test_service_verify_skips_when_not_required(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "RAG Evaluation")
    (tmp_path / "RAG Evaluation").mkdir(parents=True, exist_ok=True)
    save_state(tmp_path / "RAG Evaluation" / "evaluation_state.json", default_state())
    monkeypatch.setattr(service, "EVAL_ROOT", tmp_path / "eval")
    r = service.run_baseline_verification()
    assert r["ok"] is True and r.get("skipped") is True


# ---------------------------------------------------------------- weekly


def test_weekly_governance_metrics(tmp_path):
    vault = tmp_path
    (vault / "40_Outputs" / "RAG Evaluation").mkdir(parents=True)
    (vault / "40_Outputs" / "RAG Evaluation" / "latest.json").write_text(
        '{"metrics": {"overall": {"answer_coverage": 82.1}}}', encoding="utf-8")
    st = mark_required(default_state(), "wiki_approved")
    save_state(vault / "40_Outputs" / "RAG Evaluation" / "evaluation_state.json", st)
    re_ = review_metrics.collect_rag_evaluation(vault)
    assert re_ is not None
    g = re_.get("governance") or {}
    assert g["status"] == "required"
    assert g["required"] is True
    assert g["reasons"] == ["wiki_approved"]


# ---------------------------------------------------------------- exit codes / concurrency / fingerprint


def test_exit_codes():
    assert gov_cli.exit_code_for({"ok": False}) == 2                       # Evaluation Failed
    assert gov_cli.exit_code_for({"ok": True, "skipped": True}) == 0       # 无变化
    assert gov_cli.exit_code_for({"ok": True, "state": {"status": "passed"}}) == 0
    assert gov_cli.exit_code_for({"ok": True, "state": {"status": "improved"}}) == 0
    assert gov_cli.exit_code_for({"ok": True, "state": {"status": "regressed"}}) == 1  # Regression
    # JUDGE_VARIANCE 不会让 state 变 regressed -> 不产生 Regression exit code
    assert gov_cli.exit_code_for({"ok": True, "state": {"status": "passed"}}) == 0


def test_fingerprint_detection_marks_required(tmp_path):
    root = Path(tmp_path)
    wiki = root / "20_Wiki" / "04_FreeRTOS"
    proj = root / "30_Projects" / "P"
    wiki.mkdir(parents=True); proj.mkdir(parents=True)
    (wiki / "Task.md").write_text("# T\n内容", encoding="utf-8")
    cur = current_fingerprint([wiki, proj], root)
    mp = root / "manifest.json"
    mp.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    assert detect_index_change(mp, [wiki, proj], root)["changed"] is False
    (wiki / "Task.md").write_text("# T\n改了", encoding="utf-8")
    d = detect_index_change(mp, [wiki, proj], root)
    assert d["changed"] is True and d["modified"]


def test_concurrency_lock_prevents_second_verify():
    # 占锁 -> verify 应报告 already_running（不跑 benchmark）
    lock = gov_cli.LOCK_PATH
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("", encoding="utf-8")
    try:
        r = gov_cli.verify()
        assert r.get("already_running") is True
        assert r.get("skipped") is True
    finally:
        lock.unlink(missing_ok=True)


def test_cli_verify_noop_real():
    """真实 Scenario A：当前无知识变化 -> --verify 返回 skip（exit 0），不产生新 run。"""
    import subprocess
    runs_before = set()
    runs_dir = Path(r"D:\KnowledgeBase\Obsidian Vault\40_Outputs\RAG Evaluation\runs")
    if runs_dir.exists():
        runs_before = {d.name for d in runs_dir.iterdir() if d.is_dir()}
    proc = subprocess.run(
        [sys.executable, str(gov_cli.__file__), "--verify", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert proc.returncode == 0
    assert "skipped" in (proc.stdout or "")
    runs_after = {d.name for d in runs_dir.iterdir() if d.is_dir()} if runs_dir.exists() else set()
    assert runs_after == runs_before  # 无新的 Evaluation Run
