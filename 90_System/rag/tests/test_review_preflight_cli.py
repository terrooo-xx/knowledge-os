"""Review Preflight independence tests: standalone CLI, manual API, no auto LLM.

Offline only (mock judge injected; no network / API key). Verifies:
  - CLI runs one bounded pass and delegates to the shared service
  - second CLI run reuses cache (no duplicate LLM)
  - GET dashboard / actions never call judge
  - manual API (POST /api/review/preflight) still works
  - last_preflight_run / staleness surfaced on dashboard
  - existing real review_records are preserved
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(CTRL_DIR))

import service
import rag_engine.judge as rag_judge  # noqa: F811


def _make_wiki(root, name):
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True, exist_ok=True)
    wp = wiki / f"{name}.md"
    wp.write_text("---\nstatus: draft\nsource:\n  - 00_Inbox/s.md\n---\n# " + name + "\n内容一致" + "x" * 300, encoding="utf-8")
    s = root / "00_Inbox" / "s.md"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text("来源一致内容" * 40, encoding="utf-8")
    return wp


def _patch(tmp):
    old = (service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS)
    root = Path(tmp)
    service.VAULT_ROOT = root
    service.ACTIVITY_LOG = root / "activity_log.jsonl"
    service._gap_path = lambda: root / "gaps.yaml"
    service.REVIEW_RECORDS = root / "review_records.json"
    return old


def _mock_judge(calls=None):
    def fake(task_text, chunks, target_content, cfg, adapter=None):
        if calls is not None:
            calls.append(1)
        return {"status": "sufficient", "recommendation": "approve", "confidence": "high",
                "evidence_sufficiency": "sufficient", "consistency": "consistent",
                "conflicts": [], "missing_information": [], "unsupported_claims": [],
                "reasoning": "mock", "warnings": [], "error": False}
    return fake


# ---------------------------------------------------------------- CLI

def test_cli_once_runs_and_delegates_to_service():
    import review_preflight_cli
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        old_argv = sys.argv
        try:
            sys.argv = ["review_preflight_cli.py", "--once", "--limit", "2"]
            # prove the CLI calls the shared service function
            called = []
            orig = service.preflight_review_candidates
            def spy(limit=None, trigger="manual"):
                called.append(trigger)
                return {"ok": True, "enabled": True, "trigger": trigger, "judged": 1, "reused": 0,
                        "blocked": 0, "failed": 0, "skipped_judging": 0, "pending_remaining": 0,
                        "more_pending": False, "llm_called": True, "duration_ms": 5, "details": []}
            service.preflight_review_candidates = spy
            try:
                code = review_preflight_cli.main()
            finally:
                service.preflight_review_candidates = orig
            assert code == 0
            assert called == ["cli"]  # shared service invoked with trigger=cli
        finally:
            sys.argv = old_argv
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_cli_second_run_caches_no_duplicate_llm():
    import review_preflight_cli
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        old_argv = sys.argv
        calls = []
        orig = rag_judge.judge_review
        rag_judge.judge_review = _mock_judge(calls)
        try:
            sys.argv = ["review_preflight_cli.py", "--once", "--limit", "2"]
            review_preflight_cli.main()
            first = len(calls)
            review_preflight_cli.main()
            second = len(calls)
            assert first == 1
            assert second == first  # cached -> no duplicate LLM
        finally:
            sys.argv = old_argv
            rag_judge.judge_review = orig
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- no auto LLM

def test_dashboard_and_actions_never_call_judge():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            def boom(task_text, chunks, target_content, cfg, adapter=None):
                raise AssertionError("judge must not be called from GET dashboard/actions")
            orig = rag_judge.judge_review
            rag_judge.judge_review = boom
            try:
                service.dashboard()
                service.build_actions()
                service.review_context("wiki_review:20_Wiki/03_STM32/W0.md")
            finally:
                rag_judge.judge_review = orig
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- manual API

def test_manual_preflight_api_works():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge()
            try:
                r = service.preflight_review_candidates(trigger="manual")
            finally:
                rag_judge.judge_review = orig
            assert r["ok"] is True
            assert r["judged"] == 1
            assert r["trigger"] == "manual"
            assert "reused" in r and "pending" in r and "failed" in r
            assert "llm_called" in r
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- run record / staleness

def test_last_preflight_run_and_staleness():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_wiki(root, "W0")
        old = _patch(tmp)
        try:
            # no run record -> stale
            assert service.last_preflight_run() is None
            assert service._preflight_stale() is True
            # write a fresh finished record
            service._append_log({"action_id": "", "type": "review_preflight_finished", "target": "", "actor": "cli",
                                 "trigger": "cli", "processed": 1, "judged": 1, "reused": 0,
                                 "failed": 0, "pending": 0, "duration_ms": 10})
            run = service.last_preflight_run()
            assert run is not None and run.get("type") == "review_preflight_finished"
            assert service._preflight_stale() is False  # fresh
            # stale record (older than threshold) written directly (append_log stamps now)
            stale = {"action_id": "", "type": "review_preflight_finished", "target": "", "actor": "cli",
                     "time": (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S"),
                     "trigger": "cli", "processed": 0, "judged": 0, "reused": 0,
                     "failed": 0, "pending": 0, "duration_ms": 0}
            with open(service.ACTIVITY_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(stale, ensure_ascii=False) + "\n")
            assert service._preflight_stale() is True
            d = service.dashboard()
            assert "last_preflight" in d and "preflight_stale" in d
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- real records preserved

def test_real_review_records_preserved():
    real_path = Path(r"D:\KnowledgeBase\Obsidian Vault\90_System\control_center\review_records.json")
    if not real_path.exists():
        return  # fresh environment: nothing to check
    data = json.loads(real_path.read_text(encoding="utf-8"))
    assert len(data) >= 18, f"expected >= 18 records, got {len(data)}"
    for aid, rec in data.items():
        assert rec.get("action_id") == aid
        assert rec.get("input_fingerprint"), f"record {aid} missing input_fingerprint"
        assert rec.get("judge_status") in ("completed", "failed", "blocked", "judging")


if __name__ == "__main__":
    for t in (
        test_cli_once_runs_and_delegates_to_service,
        test_cli_second_run_caches_no_duplicate_llm,
        test_dashboard_and_actions_never_call_judge,
        test_manual_preflight_api_works,
        test_last_preflight_run_and_staleness,
        test_real_review_records_preserved,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all review preflight CLI tests passed")

