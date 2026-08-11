"""Control Center service tests: action building, idempotent execution, audit log."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(CTRL_DIR))

import service


def _tmp_env(tmp: str):
    root = Path(tmp)
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True)
    wp = wiki / "Test.md"
    wp.write_text(
        "---\nstatus: draft\nsource:\n  - 00_Inbox/a.pdf\n---\n# Test\n内容", encoding="utf-8"
    )
    gaps = root / "gaps.yaml"
    gaps.write_text(
        "- question: Q1\n  type: knowledge_missing\n  status: pending\n  suggested_action: create_wiki\n",
        encoding="utf-8",
    )
    return root, wp, gaps


def _patch(tmp: str):
    old_root, old_log, old_gap = service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path
    root = Path(tmp)
    service.VAULT_ROOT = root
    service.ACTIVITY_LOG = root / "activity_log.jsonl"
    service._gap_path = lambda: root / "gaps.yaml"
    return old_root, old_log, old_gap


def test_build_actions_from_real_vault():
    actions = service.build_actions()
    assert any(a["type"] == "wiki_review" and a["status"] == "pending" for a in actions)
    assert any(a["type"] == "knowledge_gap" for a in actions)
    for a in actions:
        assert a["id"] and a["available_actions"]


def test_approve_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        root, wp, gaps = _tmp_env(tmp)
        old = _patch(tmp)
        try:
            aid = "wiki_review:20_Wiki/03_STM32/Test.md"
            r1 = service.execute_action(aid, "approve")
            assert r1["ok"] and r1["result"] == "success"
            text = wp.read_text(encoding="utf-8")
            assert text.count("status: reviewed") == 1
            r2 = service.execute_action(aid, "approve")
            assert r2["result"] == "already_done"
            assert wp.read_text(encoding="utf-8").count("status: reviewed") == 1
            recs = service._activity_records()
            assert sum(1 for r in recs if r["action_id"] == aid and r["result"] == "success") == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old


def test_reject_keeps_status_and_logs():
    with tempfile.TemporaryDirectory() as tmp:
        root, wp, gaps = _tmp_env(tmp)
        old = _patch(tmp)
        try:
            aid = "wiki_review:20_Wiki/03_STM32/Test.md"
            r = service.execute_action(aid, "reject")
            assert r["ok"] and "状态保持 draft" in r["message"]
            assert "status: draft" in wp.read_text(encoding="utf-8")
            assert any(x["user_decision"] == "reject" for x in service._activity_records())
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old


def test_resolve_gap_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        root, wp, gaps = _tmp_env(tmp)
        old = _patch(tmp)
        try:
            aid = "gap:Q1"
            r1 = service.execute_action(aid, "resolve")
            assert r1["ok"] and r1["result"] == "success"
            assert "status: resolved" in gaps.read_text(encoding="utf-8")
            r2 = service.execute_action(aid, "resolve")
            assert r2["result"] == "already_done"
            assert gaps.read_text(encoding="utf-8").count("status: resolved") == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old


def test_batch_approve_requires_confirm_and_is_per_item():
    with tempfile.TemporaryDirectory() as tmp:
        root, wp, gaps = _tmp_env(tmp)
        old = _patch(tmp)
        try:
            aid = "wiki_review:20_Wiki/03_STM32/Test.md"
            # without confirm -> no-op
            r = service.batch_approve([aid], confirm=False)
            assert r["ok"] is False
            assert "status: draft" in wp.read_text(encoding="utf-8")
            # with confirm -> per-item result
            r = service.batch_approve([aid, "wiki_review:不存在.md"], confirm=True)
            assert r["ok"] is True and len(r["results"]) == 2
            assert r["results"][0]["ok"] is True and r["results"][0]["result"] == "success"
            assert r["results"][1]["ok"] is False
            assert "status: reviewed" in wp.read_text(encoding="utf-8")
            # idempotent second run
            r2 = service.batch_approve([aid], confirm=True)
            assert r2["results"][0]["result"] == "already_done"
            # one log per success
            recs = service._activity_records()
            assert sum(1 for x in recs if x["action_id"] == aid and x["result"] == "success") == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old


def test_unknown_action_errors():
    r = service.execute_action("wiki_review:不存在.md", "approve")
    assert r["ok"] is False


if __name__ == "__main__":
    for t in (
        test_build_actions_from_real_vault,
        test_approve_is_idempotent,
        test_reject_keeps_status_and_logs,
        test_resolve_gap_is_idempotent,
        test_batch_approve_requires_confirm_and_is_per_item,
        test_unknown_action_errors,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all control center tests passed")
