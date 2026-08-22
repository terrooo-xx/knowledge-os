"""Review Context tests: read-only audit workbench assembly for pending actions.

Covers wiki_review / knowledge_gap contexts, missing-data resilience and the
no-mutation guarantee (context building never changes Wiki / gap / log state).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(CTRL_DIR))

import service


def _first_action(action_type: str) -> dict:
    for a in service.build_actions():
        if a["type"] == action_type:
            return a
    raise AssertionError(f"no pending {action_type} action in real vault")


def _tmp_review_env(tmp: str):
    """Hermetic env: one draft wiki + one pending gap, no judge records."""
    root = Path(tmp)
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True)
    wp = wiki / "Test.md"
    wp.write_text(
        "---\nstatus: draft\nsource:\n  - 00_Inbox/a.md\n---\n# Test\n" + "内容一致" + "x" * 300,
        encoding="utf-8",
    )
    src = root / "00_Inbox" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("来源内容一致" * 40, encoding="utf-8")
    gaps = root / "gaps.yaml"
    gaps.write_text(
        "- question: QG\n  type: knowledge_missing\n  status: pending\n  suggested_action: create_wiki\n"
        "  related_wiki:\n  - 20_Wiki/03_STM32/Test.md\n",
        encoding="utf-8",
    )
    old = (service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS)
    service.VAULT_ROOT = root
    service.ACTIVITY_LOG = root / "activity_log.jsonl"
    service._gap_path = lambda: root / "gaps.yaml"
    service.REVIEW_RECORDS = root / "review_records.json"
    return old


def test_wiki_review_context_has_all_sections():
    with tempfile.TemporaryDirectory() as tmp:
        old = _tmp_review_env(tmp)
        try:
            action = next(a for a in service.build_actions() if a["type"] == "wiki_review")
            ctx = service.review_context(action["id"])
            assert ctx["ok"] is True
            assert ctx["task"]["type"] == "wiki_review"
            assert ctx["task"]["id"] == action["id"]
            assert ctx["ai_judgement"]["recommendation"] == action["ai_recommendation"]
            assert ctx["ai_judgement"]["source"] == "rule"  # no judge record -> rule fallback
            assert isinstance(ctx["ai_judgement"]["warnings"], list)
            assert ctx["target_content"] is not None
            assert ctx["target_content"]["path"] == action["target"]["wiki"]
            assert ctx["ai_suggestion"]["action"] in ("approve", "reject", "review")
            assert ctx["actions"] == action["available_actions"]
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_gap_context_has_related_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        old = _tmp_review_env(tmp)
        try:
            action = next(a for a in service.build_actions() if a["type"] == "knowledge_gap")
            ctx = service.review_context(action["id"])
            assert ctx["ok"] is True
            assert ctx["task"]["type"] == "knowledge_gap"
            assert ctx["ai_judgement"]["evidence_sufficiency"] == "insufficient"
            assert ctx["ai_judgement"]["source"] == "rule"  # no judge record -> rule fallback
            assert isinstance(ctx["evidence"]["sources"], list)
            assert isinstance(ctx["ai_suggestion"]["changes"], list)
            assert ctx["target_content"] is None  # gaps have no target wiki
            assert ctx["actions"] == action["available_actions"]
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_missing_source_is_resilient():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wiki = root / "20_Wiki" / "03_STM32"
        wiki.mkdir(parents=True)
        wp = wiki / "NoSource.md"
        wp.write_text(
            "---\nstatus: draft\nsource:\n  - 00_Inbox/不存在.md\n---\n# NoSource\n内容不够长不足三百字符的测试草稿内容。",
            encoding="utf-8",
        )
        old_root, old_log, old_gap = service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path
        service.VAULT_ROOT = root
        service.ACTIVITY_LOG = root / "activity_log.jsonl"
        service._gap_path = lambda: root / "gaps.yaml"
        try:
            ctx = service.review_context("wiki_review:20_Wiki/03_STM32/NoSource.md")
            assert ctx["ok"] is True
            assert ctx["ai_judgement"]["evidence_sufficiency"] == "insufficient"
            assert any("来源文件不可读" in w for w in ctx["ai_judgement"]["warnings"])
            assert ctx["target_content"]["content"]  # wiki body still shown
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old_root, old_log, old_gap


def test_missing_data_does_not_crash():
    # a wiki with no source field at all
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wiki = root / "20_Wiki" / "03_STM32"
        wiki.mkdir(parents=True)
        wp = wiki / "NoMeta.md"
        wp.write_text("---\nstatus: draft\n---\n# NoMeta\n" + "内容" * 200, encoding="utf-8")
        old_root, old_log, old_gap = service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path
        service.VAULT_ROOT = root
        service.ACTIVITY_LOG = root / "activity_log.jsonl"
        service._gap_path = lambda: root / "gaps.yaml"
        try:
            ctx = service.review_context("wiki_review:20_Wiki/03_STM32/NoMeta.md")
            assert ctx["ok"] is True
            assert ctx["evidence"]["sources"] == []
            assert ctx["ai_judgement"]["evidence_sufficiency"] == "insufficient"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path = old_root, old_log, old_gap


def test_review_context_is_read_only():
    action = _first_action("wiki_review")
    wp = Path(service.VAULT_ROOT) / action["target"]["wiki"]
    before = wp.read_text(encoding="utf-8")
    log_before = [r for r in service._activity_records()]
    service.review_context(action["id"])
    after = wp.read_text(encoding="utf-8")
    log_after = [r for r in service._activity_records()]
    assert before == after
    assert log_before == log_after


def test_unknown_action_returns_error():
    ctx = service.review_context("wiki_review:不存在.md")
    assert ctx["ok"] is False


if __name__ == "__main__":
    for t in (
        test_wiki_review_context_has_all_sections,
        test_gap_context_has_related_evidence,
        test_missing_source_is_resilient,
        test_missing_data_does_not_crash,
        test_review_context_is_read_only,
        test_unknown_action_returns_error,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all review context tests passed")

