"""Review Judge tests: real LLM Review Judge wiring into Review Task.

Offline only: the LLM call is injected as a fake adapter / monkeypatched judge
function; no network and no real API key is used. Covers structured parsing,
consistent / conflict / missing / insufficient semantics, fail-closed on LLM
failure, persistence to review records, and read-only GET context.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(CTRL_DIR))

import rag_engine.judge as judge
import service
import rag_engine.judge as rag_judge  # noqa: F811  (module attr is patched for service tests)


class FakeAdapter:
    """Injected LLM adapter returning a canned review JSON."""

    def __init__(self, raw: str, raise_exc: Exception | None = None):
        self.raw = raw
        self.raise_exc = raise_exc

    def generate(self, question: str, context: str) -> str:
        if self.raise_exc:
            raise self.raise_exc
        return self.raw


CFG = {"llm": {"provider": "deepseek", "model": {"name": "deepseek-chat"}, "timeout": 30}}


def _run(raw: str, raise_exc: Exception | None = None) -> dict:
    return judge.judge_review(
        "审核任务：Wiki Review",
        [{"source": "00_Inbox/a.md", "content": "DMA direction = Peripheral to Memory"}],
        "# DMA\nDMA direction = Peripheral to Memory",
        CFG,
        adapter=FakeAdapter(raw, raise_exc),
    )


# ---------------------------------------------------------------- parse

def test_parse_review_valid():
    raw = ('{"status":"sufficient","recommendation":"approve","confidence":"high",'
           '"evidence_sufficiency":"sufficient","consistency":"consistent",'
           '"conflicts":[],"missing_information":[],"unsupported_claims":[],'
           '"reasoning":"来源与 Wiki 一致","warnings":[]}')
    r = judge.parse_review_judgement(raw)
    assert r["status"] == "sufficient"
    assert r["recommendation"] == "approve"
    assert r["consistency"] == "consistent"
    assert r["error"] is False


def test_parse_review_invalid_fail_closed():
    r = judge.parse_review_judgement("not json at all")
    assert r["error"] is True
    assert r["status"] == "uncertain"
    assert r["recommendation"] == "review"


def test_parse_review_bad_enum_fail_closed():
    raw = '{"status":"sufficient","recommendation":"approve_now","confidence":"high","consistency":"consistent"}'
    r = judge.parse_review_judgement(raw)
    assert r["error"] is True
    assert r["recommendation"] == "review"


# ---------------------------------------------------------------- semantics

def test_judge_consistent_approve():
    raw = ('{"status":"sufficient","recommendation":"approve","confidence":"high",'
           '"evidence_sufficiency":"sufficient","consistency":"consistent","conflicts":[],'
           '"missing_information":[],"unsupported_claims":[],"reasoning":"完全一致"}')
    r = _run(raw)
    assert r["consistency"] == "consistent"
    assert r["recommendation"] == "approve"
    assert r["error"] is False


def test_judge_conflict_resolve():
    raw = ('{"status":"conflict","recommendation":"resolve","confidence":"high",'
           '"evidence_sufficiency":"sufficient","consistency":"conflict",'
           '"conflicts":["Circular Mode: 来源 Enable vs Wiki Disable"],'
           '"missing_information":[],"unsupported_claims":[],"reasoning":"冲突"}')
    r = _run(raw)
    assert r["consistency"] == "conflict"
    assert r["recommendation"] in ("resolve", "review")


def test_judge_missing_information_not_approve():
    raw = ('{"status":"insufficient","recommendation":"review","confidence":"medium",'
           '"evidence_sufficiency":"partial","consistency":"partial",'
           '"conflicts":[],"missing_information":["Wiki 缺少 DMA circular mode 限制"],'
           '"unsupported_claims":[],"reasoning":"存在缺失"}')
    r = _run(raw)
    assert r["missing_information"] != []
    assert r["recommendation"] != "approve"


def test_judge_insufficient_evidence_review():
    raw = ('{"status":"insufficient","recommendation":"review","confidence":"low",'
           '"evidence_sufficiency":"insufficient","consistency":"unknown","conflicts":[],'
           '"missing_information":[],"unsupported_claims":[],"reasoning":"证据不足"}')
    r = _run(raw)
    assert r["evidence_sufficiency"] == "insufficient"
    assert r["recommendation"] == "review"


def test_judge_llm_failure_fail_closed():
    r = _run("", raise_exc=TimeoutError("LLM timeout"))
    assert r["error"] is True
    assert r["status"] == "uncertain"
    assert r["recommendation"] == "review"
    assert r["recommendation"] != "approve"


def test_build_review_context_has_both_sections():
    ctx = judge.build_review_context(
        [{"source": "a.md", "content": "证据"}],
        "# Wiki\n正文",
    )
    assert "SOURCE EVIDENCE" in ctx
    assert "CURRENT WIKI" in ctx
    assert "证据" in ctx
    assert "正文" in ctx


# ---------------------------------------------------------------- persistence

def _tmp_env(tmp: str):
    root = Path(tmp)
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True)
    wp = wiki / "Test.md"
    wp.write_text(
        "---\nstatus: draft\nsource:\n  - 00_Inbox/a.md\n---\n# Test\n" + "DMA direction = Peripheral to Memory\n" + "x" * 300,
        encoding="utf-8",
    )
    src = root / "00_Inbox" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("DMA direction = Peripheral to Memory. 完整说明。", encoding="utf-8")
    return root, wp


def _patch(tmp: str):
    old = (service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS)
    root = Path(tmp)
    service.VAULT_ROOT = root
    service.ACTIVITY_LOG = root / "activity_log.jsonl"
    service._gap_path = lambda: root / "gaps.yaml"
    service.REVIEW_RECORDS = root / "review_records.json"
    return old


def test_rule_fallback_when_no_judge():
    with tempfile.TemporaryDirectory() as tmp:
        _tmp_env(tmp)
        old = _patch(tmp)
        try:
            ctx = service.review_context("wiki_review:20_Wiki/03_STM32/Test.md")
            j = ctx["ai_judgement"]
            assert j["source"] == "rule"
            assert j["derived"] is True
            assert j["judge_available"] is False
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_judge_persist_and_context_reads():
    with tempfile.TemporaryDirectory() as tmp:
        _tmp_env(tmp)
        old = _patch(tmp)
        aid = "wiki_review:20_Wiki/03_STM32/Test.md"
        try:
            def fake(task_text, chunks, target_content, cfg, adapter=None):
                return {"status": "conflict", "recommendation": "resolve", "confidence": "high",
                        "evidence_sufficiency": "sufficient", "consistency": "conflict",
                        "conflicts": ["Circular Mode 不一致"], "missing_information": [],
                        "unsupported_claims": [], "reasoning": "来源与 Wiki 冲突", "warnings": [], "error": False}

            orig = rag_judge.judge_review
            rag_judge.judge_review = fake
            try:
                r = service.run_review_judge(aid)
            finally:
                rag_judge.judge_review = orig
            assert r["ok"] is True and r["judge_status"] == "completed"
            recs = service._load_review_records()
            assert aid in recs
            assert recs[aid]["source_refs"] == ["00_Inbox/a.md"]
            assert recs[aid]["judge_model"].startswith("deepseek:")
            # context now shows the LLM judge
            j = service.review_context(aid)["ai_judgement"]
            assert j["source"] == "llm_judge"
            assert j["consistency"] == "conflict"
            assert j["recommendation"] == "resolve"
            assert j["review_reason"]
            assert j["rule_recommendation"] is not None  # rule kept as auxiliary
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_judge_failure_persists_failed_and_no_approve():
    with tempfile.TemporaryDirectory() as tmp:
        _tmp_env(tmp)
        old = _patch(tmp)
        aid = "wiki_review:20_Wiki/03_STM32/Test.md"
        try:
            def boom(task_text, chunks, target_content, cfg, adapter=None):
                raise TimeoutError("LLM timeout")

            orig = rag_judge.judge_review
            rag_judge.judge_review = boom
            try:
                r = service.run_review_judge(aid)
            finally:
                rag_judge.judge_review = orig
            assert r["ok"] is True and r["judge_status"] == "failed"
            j = service.review_context(aid)["ai_judgement"]
            assert j["source"] == "llm_judge"
            assert j["judge_status"] == "failed"
            assert j["recommendation"] == "review"
            assert j["recommendation"] != "approve"
            assert "AI Judge 未能完成" in j["review_reason"]
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_context_get_is_read_only():
    with tempfile.TemporaryDirectory() as tmp:
        root, wp = _tmp_env(tmp)
        old = _patch(tmp)
        aid = "wiki_review:20_Wiki/03_STM32/Test.md"
        try:
            before = wp.read_text(encoding="utf-8")
            service.review_context(aid)
            after = wp.read_text(encoding="utf-8")
            assert before == after
            assert service._load_review_records() == {}  # no review state written
            assert service._activity_records() == []    # no activity written
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_unknown_action_judge_errors():
    r = service.run_review_judge("wiki_review:不存在.md")
    assert r["ok"] is False



def test_gap_judge_persist():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gaps = root / "gaps.yaml"
        gaps.write_text(
            "- question: QG\n  type: knowledge_missing\n  status: pending\n  suggested_action: create_wiki\n"
            "  related_wiki:\n  - 20_Wiki/03_STM32/Test.md\n",
            encoding="utf-8",
        )
        wiki = root / "20_Wiki" / "03_STM32"
        wiki.mkdir(parents=True)
        wp = wiki / "Test.md"
        wp.write_text("---\nstatus: draft\n---\n# Test\n已有知识", encoding="utf-8")
        old = _patch(tmp)
        try:
            aid = "gap:QG"
            def fake(task_text, chunks, target_content, cfg, adapter=None):
                assert target_content is None
                return {"status": "insufficient", "recommendation": "review", "confidence": "medium",
                        "evidence_sufficiency": "insufficient", "consistency": "unknown",
                        "conflicts": [], "missing_information": [], "unsupported_claims": [],
                        "reasoning": "缺口真实存在", "warnings": [], "error": False}
            orig = rag_judge.judge_review
            rag_judge.judge_review = fake
            try:
                r = service.run_review_judge(aid)
            finally:
                rag_judge.judge_review = orig
            assert r["ok"] is True and r["judge_status"] == "completed"
            rec = service._load_review_records()[aid]
            assert rec["type"] == "knowledge_gap"
            j = service.review_context(aid)["ai_judgement"]
            assert j["source"] == "llm_judge"
            assert j["evidence_sufficiency"] == "insufficient"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old

if __name__ == "__main__":
    for t in (
        test_parse_review_valid,
        test_parse_review_invalid_fail_closed,
        test_parse_review_bad_enum_fail_closed,
        test_judge_consistent_approve,
        test_judge_conflict_resolve,
        test_judge_missing_information_not_approve,
        test_judge_insufficient_evidence_review,
        test_judge_llm_failure_fail_closed,
        test_build_review_context_has_both_sections,
        test_rule_fallback_when_no_judge,
        test_judge_persist_and_context_reads,
        test_judge_failure_persists_failed_and_no_approve,
        test_context_get_is_read_only,
        test_unknown_action_judge_errors,
        test_gap_judge_persist,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all review judge tests passed")

