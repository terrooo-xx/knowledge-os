"""Review Preflight tests: auto Judge + fingerprint cache + auto classification.

Offline only: the LLM call is injected as a monkeypatched judge function so no
network / API key is used. Covers auto-judge of new candidates, cache reuse,
change detection (wiki/source/prompt version), classification, blocking,
concurrency guard, read-only GET and dashboard counts.
"""
from __future__ import annotations

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


def _make_wiki(root, name, source=True, content_extra=""):
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True, exist_ok=True)
    wp = wiki / f"{name}.md"
    src_lines = "  - 00_Inbox/s.md\n" if source else ""
    wp.write_text(f"---\nstatus: draft\nsource:\n{src_lines}---\n# {name}\n内容一致" + content_extra + ("x" * 300), encoding="utf-8")
    if source:
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


def _mock_judge(result=None, raise_exc=None, calls=None):
    def fake(task_text, chunks, target_content, cfg, adapter=None):
        if calls is not None:
            calls.append(1)
        if raise_exc:
            raise raise_exc
        return result or {
            "status": "sufficient", "recommendation": "approve", "confidence": "high",
            "evidence_sufficiency": "sufficient", "consistency": "consistent",
            "conflicts": [], "missing_information": [], "unsupported_claims": [],
            "reasoning": "mock", "warnings": [], "error": False,
        }
    return fake


# ---------------------------------------------------------------- auto judge + cache

def test_new_candidate_auto_judged_and_cached():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            calls = []
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(calls=calls)
            try:
                r1 = service.preflight_review_candidates(limit=10)
                assert r1["judged"] == 1 and r1["more_pending"] is False
                r2 = service.preflight_review_candidates(limit=10)
                assert r2["judged"] == 0
            finally:
                rag_judge.judge_review = orig
            assert len(calls) == 1  # cached second pass -> no LLM call
            rec = service._load_review_records()["wiki_review:20_Wiki/03_STM32/W0.md"]
            assert rec["judge_status"] == "completed"
            assert rec["classification"] == "judge_passed"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_wiki_change_reruns_judge():
    with tempfile.TemporaryDirectory() as tmp:
        wp = _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            calls = []
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(calls=calls)
            try:
                service.preflight_review_candidates(limit=10)
                wp.write_text("---\nstatus: draft\nsource:\n  - 00_Inbox/s.md\n---\n# W0 changed\n改了内容" + "x" * 300, encoding="utf-8")
                service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert len(calls) == 2  # wiki changed -> rerun
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_source_change_reruns_judge():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_wiki(root, "W0")
        old = _patch(tmp)
        try:
            calls = []
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(calls=calls)
            try:
                service.preflight_review_candidates(limit=10)
                (root / "00_Inbox" / "s.md").write_text("来源内容完全变了" * 40, encoding="utf-8")
                service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert len(calls) == 2  # source changed -> rerun
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_prompt_version_change_reruns_judge():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            calls = []
            orig_judge = rag_judge.judge_review
            orig_prompt = service._prompt_fingerprint
            rag_judge.judge_review = _mock_judge(calls=calls)
            service._prompt_fingerprint = lambda: "v1"
            try:
                service.preflight_review_candidates(limit=10)
                service._prompt_fingerprint = lambda: "v2"  # prompt version changed
                service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig_judge
                service._prompt_fingerprint = orig_prompt
            assert len(calls) == 2  # version changed -> rerun
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- classification

def test_judge_passed_requires_all_conditions():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            good = {"status": "sufficient", "recommendation": "approve", "confidence": "high",
                    "evidence_sufficiency": "sufficient", "consistency": "consistent",
                    "conflicts": [], "missing_information": [], "unsupported_claims": [],
                    "reasoning": "ok", "warnings": [], "error": False}
            assert service._classify_judge(dict(good)) == "judge_passed"
            # missing one condition -> needs_review
            bad = dict(good); bad["confidence"] = "medium"
            assert service._classify_judge(bad) == "needs_review"
            bad2 = dict(good); bad2["conflicts"] = ["x"]
            assert service._classify_judge(bad2) == "needs_review"
            bad3 = dict(good); bad3["missing_information"] = ["y"]
            assert service._classify_judge(bad3) == "needs_review"
            bad4 = dict(good); bad4["warnings"] = ["w"]
            assert service._classify_judge(bad4) == "needs_review"
            bad5 = dict(good); bad5["consistency"] = "partial"
            assert service._classify_judge(bad5) == "needs_review"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_conflict_and_insufficient_needs_review():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            conflict = {"status": "conflict", "recommendation": "resolve", "confidence": "high",
                        "evidence_sufficiency": "sufficient", "consistency": "conflict",
                        "conflicts": ["Circular Mode 不一致"], "missing_information": [],
                        "unsupported_claims": [], "reasoning": "冲突", "warnings": [], "error": False}
            insufficient = {"status": "insufficient", "recommendation": "review", "confidence": "low",
                            "evidence_sufficiency": "insufficient", "consistency": "unknown",
                            "conflicts": [], "missing_information": [], "unsupported_claims": [],
                            "reasoning": "证据不足", "warnings": [], "error": False}
            assert service._classify_judge(conflict) == "needs_review"
            assert service._classify_judge(insufficient) == "needs_review"
            assert service._classify_judge({"error": True}) == "judge_failed"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_judge_failure_fail_closed_never_approve():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(raise_exc=TimeoutError("LLM timeout"))
            try:
                r = service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert r["failed"] == 1
            rec = service._load_review_records()["wiki_review:20_Wiki/03_STM32/W0.md"]
            assert rec["judge_status"] == "failed"
            assert rec["classification"] == "judge_failed"
            assert rec["result"]["recommendation"] == "review"
            assert rec["result"]["recommendation"] != "approve"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_blocked_when_no_readable_source():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "NoSrc", source=False)
        old = _patch(tmp)
        try:
            calls = []
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(calls=calls)
            try:
                r = service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert r["blocked"] == 1
            assert len(calls) == 0  # gate blocks -> no LLM call
            rec = service._load_review_records()["wiki_review:20_Wiki/03_STM32/NoSrc.md"]
            assert rec["judge_status"] == "blocked"
            assert rec["classification"] == "needs_review"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- concurrency / limits

def test_concurrent_judging_lock_no_duplicate():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            # pre-mark as judging with a fresh timestamp -> preflight must skip
            aid = "wiki_review:20_Wiki/03_STM32/W0.md"
            records = service._load_review_records()
            records[aid] = {"judge_status": "judging", "judging_at": service._now()}
            service._save_review_records(records)
            calls = []
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge(calls=calls)
            try:
                r = service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert r["skipped_judging"] >= 1
            assert len(calls) == 0  # lock prevents duplicate call
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_max_per_run_limit():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for i in range(5):
            _make_wiki(root, f"W{i}")
        old = _patch(tmp)
        orig = rag_judge.judge_review
        rag_judge.judge_review = _mock_judge()
        try:
            r = service.preflight_review_candidates(limit=2)
            assert r["judged"] == 2
            assert r["more_pending"] is True
            assert r["pending_remaining"] == 3
            r2 = service.preflight_review_candidates(limit=10)
            assert r2["judged"] == 3
            assert r2["more_pending"] is False
        finally:
            rag_judge.judge_review = orig
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- read-only / dashboard

def test_get_context_never_calls_llm():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            def boom(task_text, chunks, target_content, cfg, adapter=None):
                raise AssertionError("LLM must not be called from GET context")
            orig = rag_judge.judge_review
            rag_judge.judge_review = boom
            try:
                ctx = service.review_context("wiki_review:20_Wiki/03_STM32/W0.md")
                assert ctx["ok"] is True
                assert ctx["ai_judgement"]["source"] == "rule"
            finally:
                rag_judge.judge_review = orig
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_review_counts_and_dashboard():
    # dashboard surfaces unified review_counts (single source metrics.collect_review_metrics)
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge()
            try:
                service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            d = service.dashboard()
            assert d["review_counts"]["judge_passed"] == 1
            assert d["review_counts"]["pending_human"] == 0
            # dashboard == unified metrics (same function)
            mc = service.review_counts()
            assert mc["judge_passed"] == d["review_counts"]["judge_passed"] == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old




def test_failed_cooldown_no_retry_then_retry():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            aid = "wiki_review:20_Wiki/03_STM32/W0.md"
            pc = service._preflight_cfg()
            # failed record with fresh judged_at -> valid (no retry within cooldown)
            records = service._load_review_records()
            fp = service._current_fingerprints(next(a for a in service.build_actions() if a["id"] == aid))
            records[aid] = {"judge_status": "failed", "classification": "judge_failed",
                            "judged_at": service._now(), "input_fingerprint": fp[2]}
            service._save_review_records(records)
            assert service._preflight_decision(aid, records, pc) == "valid"
            # old judged_at -> retry
            records[aid]["judged_at"] = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            service._save_review_records(records)
            assert service._preflight_decision(aid, records, pc) == "needs_judge"
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


def test_cross_process_file_lock_skips_run():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wiki(Path(tmp), "W0")
        old = _patch(tmp)
        try:
            pc = service._preflight_cfg()
            assert service._acquire_preflight_file_lock(pc) is True
            try:
                calls = []
                orig = rag_judge.judge_review
                rag_judge.judge_review = _mock_judge(calls=calls)
                try:
                    r = service.preflight_review_candidates(limit=10)
                finally:
                    rag_judge.judge_review = orig
                assert r.get("skipped") is True  # lock held elsewhere -> skip
                assert len(calls) == 0          # no LLM call
            finally:
                service._release_preflight_file_lock()
            # after release -> runs normally
            orig = rag_judge.judge_review
            rag_judge.judge_review = _mock_judge()
            try:
                r2 = service.preflight_review_candidates(limit=10)
            finally:
                rag_judge.judge_review = orig
            assert r2.get("judged") == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old

if __name__ == "__main__":
    for t in (
        test_new_candidate_auto_judged_and_cached,
        test_wiki_change_reruns_judge,
        test_source_change_reruns_judge,
        test_prompt_version_change_reruns_judge,
        test_judge_passed_requires_all_conditions,
        test_conflict_and_insufficient_needs_review,
        test_judge_failure_fail_closed_never_approve,
        test_blocked_when_no_readable_source,
        test_concurrent_judging_lock_no_duplicate,
        test_max_per_run_limit,
        test_get_context_never_calls_llm,
        test_review_counts_and_dashboard,
        test_failed_cooldown_no_retry_then_retry,
        test_cross_process_file_lock_skips_run,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all review preflight tests passed")



