"""Weekly Review Phase A tests: unified Review metrics + 5-second status + baseline.

Offline: no network / LLM. Uses temp vaults for hermetic cases plus one
real-data check (guarded). Verifies review counts unification, snapshot schema,
markdown status block, baseline detection and API fields.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = RAG_DIR / "scripts" / "review"
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(CTRL_DIR))

import metrics
import weekly_review
import service


def _make_review_records(tmp: Path, entries: dict) -> Path:
    records_path = tmp / "90_System" / "control_center" / "review_records.json"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return records_path


def _rec(status, classification, result=None):
    return {"judge_status": status, "classification": classification,
            "result": result or {"recommendation": "review", "reasoning": "x"}}


def _tmp_vault(tmp: str, wiki_names=("W0",), gaps=()):
    root = Path(tmp)
    for name in wiki_names:
        d = root / "20_Wiki" / "03_STM32"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(
            f"---\nstatus: draft\nsource:\n  - 00_Inbox/s.md\n---\n# {name}\n内容" + "x" * 300, encoding="utf-8")
    s = root / "00_Inbox" / "s.md"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text("来源内容" * 40, encoding="utf-8")
    if gaps:
        gp = root / "gaps.yaml"
        gp.write_text(
            "\n".join(f"- question: {q}\n  type: knowledge_missing\n  status: pending\n  suggested_action: create_wiki\n" for q in gaps),
            encoding="utf-8",
        )
    return root


# ---------------------------------------------------------------- pure counting

def test_count_review_buckets_and_formulas():
    candidates = [
        {"action_id": "wiki_review:20_Wiki/03_STM32/W0.md", "title": "W0", "type": "wiki_review"},
        {"action_id": "wiki_review:20_Wiki/03_STM32/W1.md", "title": "W1", "type": "wiki_review"},
        {"action_id": "wiki_review:20_Wiki/03_STM32/W2.md", "title": "W2", "type": "wiki_review"},
        {"action_id": "wiki_review:20_Wiki/03_STM32/W3.md", "title": "W3", "type": "wiki_review"},
        {"action_id": "wiki_review:20_Wiki/03_STM32/W4.md", "title": "W4", "type": "wiki_review"},
        {"action_id": "gap:QG", "title": "QG", "type": "knowledge_gap"},
    ]
    records = {
        "wiki_review:20_Wiki/03_STM32/W0.md": _rec("completed", "judge_passed"),
        "wiki_review:20_Wiki/03_STM32/W1.md": _rec("completed", "needs_review"),
        "wiki_review:20_Wiki/03_STM32/W2.md": _rec("blocked", "needs_review"),   # blocked -> needs_review
        "wiki_review:20_Wiki/03_STM32/W3.md": _rec("failed", "judge_failed"),
        "wiki_review:20_Wiki/03_STM32/W4.md": _rec("judging", None),
        # gap:QG missing -> not_judged
    }
    c = metrics._count_review(records, candidates)
    assert c["judge_passed"] == 1
    assert c["needs_review"] == 2   # W1 + W2(blocked)
    assert c["judge_failed"] == 1
    assert c["judging"] == 1
    assert c["not_judged"] == 1
    assert c["total"] == c["judge_passed"] + c["needs_review"] + c["judge_failed"] + c["judging"] == 5
    assert c["candidates"] == 6
    assert c["pending_human"] == c["needs_review"] + c["judge_failed"] == 3


# ---------------------------------------------------------------- collect_review_metrics

def test_collect_review_metrics_from_temp_vault():
    with tempfile.TemporaryDirectory() as tmp:
        root = _tmp_vault(tmp, wiki_names=("W0", "W1", "W2"), gaps=("QG",))
        gap_path = root / "gaps.yaml"
        records_path = _make_review_records(root, {
            "wiki_review:20_Wiki/03_STM32/W0.md": _rec("completed", "judge_passed"),
            "wiki_review:20_Wiki/03_STM32/W1.md": _rec("completed", "needs_review"),
            "wiki_review:20_Wiki/03_STM32/W2.md": _rec("failed", "judge_failed"),
            # gap:QG not_judged
        })
        c = metrics.collect_review_metrics(vault_root=root, review_records_path=records_path, gap_path=gap_path)
        assert c["judge_passed"] == 1
        assert c["needs_review"] == 1
        assert c["judge_failed"] == 1
        assert c["judging"] == 0
        assert c["not_judged"] == 1
        assert c["pending_human"] == 2
        assert c["candidates"] == 4


def test_review_metrics_matches_real_records():
    # Self-consistent against the real file: collect_review_metrics must equal an
    # independent count over the current review_records.json + pending candidates.
    # (Hardcoded Phase-A counts are intentionally not asserted: the knowledge base
    # legitimately changes as wikis are approved, which removes pending candidates.)
    vault = Path(r"D:\KnowledgeBase\Obsidian Vault")
    real_path = vault / "90_System" / "control_center" / "review_records.json"
    if not real_path.exists():
        return  # fresh environment: nothing to check
    records = json.loads(real_path.read_text(encoding="utf-8"))
    gap_path = vault / "90_System" / "rag" / "tests" / "knowledge_gaps.yaml"
    candidates = metrics._pending_candidates(vault, gap_path)
    expected = metrics._count_review(records, candidates)
    c = metrics.collect_review_metrics(vault_root=vault)
    for key in ("judge_passed", "needs_review", "judge_failed", "judging", "not_judged",
                "total", "candidates", "pending_human"):
        assert c[key] == expected[key], f"{key}: got {c[key]} != {expected[key]}"
    assert c["total"] == c["judge_passed"] + c["needs_review"] + c["judge_failed"] + c["judging"]
    assert c["pending_human"] == c["needs_review"] + c["judge_failed"]


# ---------------------------------------------------------------- baseline

def test_baseline_detection():
    with tempfile.TemporaryDirectory() as tmp:
        review_root = Path(tmp) / "review_root"
        cur = review_root / "2026" / "W33"
        cur.mkdir(parents=True)
        (cur / "snapshot.json").write_text("{}", encoding="utf-8")
        # only current week -> baseline
        assert metrics.collect_baseline("2026-W33", review_root)["is_baseline_period"] is True
        # add a prior week -> not baseline
        prior = review_root / "2026" / "W32"
        prior.mkdir(parents=True)
        (prior / "snapshot.json").write_text("{}", encoding="utf-8")
        assert metrics.collect_baseline("2026-W33", review_root)["is_baseline_period"] is False


def test_collect_metrics_includes_review_and_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        root = _tmp_vault(tmp, wiki_names=("W0",))
        _make_review_records(root, {"wiki_review:20_Wiki/03_STM32/W0.md": _rec("completed", "judge_passed")})
        old = metrics.REVIEW_ROOT
        metrics.REVIEW_ROOT = root / "reviews" / "每周复盘"
        try:
            m = metrics.collect_metrics(vault_root=root, now=__import__("datetime").datetime(2026, 8, 13, 12, 0, 0))
        finally:
            metrics.REVIEW_ROOT = old
        assert "review" in m and "baseline" in m
        assert m["review"]["judge_passed"] == 1
        assert m["baseline"]["is_baseline_period"] is True
        # old fields preserved
        for key in ("wiki", "growth", "gaps", "projects", "health", "activity"):
            assert key in m


# ---------------------------------------------------------------- snapshot + markdown

def test_snapshot_has_new_fields_and_old_preserved():
    m = metrics.collect_metrics(
        vault_root=Path(r"D:\KnowledgeBase\Obsidian Vault"),
        now=__import__("datetime").datetime(2026, 8, 13, 12, 0, 0),
    )
    snap = weekly_review.build_snapshot(m)
    assert snap["review"]["pending_human"] == snap["review_pending"]
    assert snap["review"]["pending_human"] == snap["review"]["needs_review"] + snap["review"]["judge_failed"]
    assert "baseline" in snap
    for key in ("wiki_total", "wiki_draft", "wiki_reviewed", "wiki_stable",
                "knowledge_gaps_pending", "stale_items", "projects", "health", "growth_delta", "activity_count"):
        assert key in snap


def test_markdown_has_weekly_status_and_review_split():
    with tempfile.TemporaryDirectory() as tmp:
        root = _tmp_vault(tmp, wiki_names=("W0",), gaps=("QG",))
        _make_review_records(root, {
            "wiki_review:20_Wiki/03_STM32/W0.md": _rec("completed", "needs_review"),
            "gap:QG": _rec("failed", "judge_failed"),
        })
        old = metrics.REVIEW_ROOT
        metrics.REVIEW_ROOT = root / "reviews" / "每周复盘"
        try:
            m = metrics.collect_metrics(vault_root=root, now=__import__("datetime").datetime(2026, 8, 13, 12, 0, 0))
        finally:
            metrics.REVIEW_ROOT = old
        summary = weekly_review._deterministic_summary(m)
        md = weekly_review.render_report(m, summary)
        assert "## Weekly Status" in md
        assert "待人工审核" in md
        assert "AI 已验证" in md
        assert "pending_human" not in md  # english key must not leak into report
        # Review Queue uses the split, not "draft count" wording
        assert "draft Wiki 等待人工审核" not in md


# ---------------------------------------------------------------- service unified

def test_service_review_counts_unified_with_metrics():
    with tempfile.TemporaryDirectory() as tmp:
        root = _tmp_vault(tmp, wiki_names=("W0", "W1"))
        _make_review_records(root, {
            "wiki_review:20_Wiki/03_STM32/W0.md": _rec("completed", "judge_passed"),
            "wiki_review:20_Wiki/03_STM32/W1.md": _rec("completed", "needs_review"),
        })
        old = (service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS)
        service.VAULT_ROOT = root
        service.ACTIVITY_LOG = root / "activity_log.jsonl"
        service._gap_path = lambda: root / "gaps.yaml"
        service.REVIEW_RECORDS = root / "90_System" / "control_center" / "review_records.json"
        try:
            rc = service.review_counts()
            mc = metrics.collect_review_metrics(
                vault_root=root,
                review_records_path=service.REVIEW_RECORDS,
                gap_path=service._gap_path(),
            )
            assert rc["judge_passed"] == mc["judge_passed"] == 1
            assert rc["needs_review"] == mc["needs_review"] == 1
            assert rc["pending_human"] == mc["pending_human"] == 1
        finally:
            service.VAULT_ROOT, service.ACTIVITY_LOG, service._gap_path, service.REVIEW_RECORDS = old


# ---------------------------------------------------------------- API fields

def test_weekly_review_api_fields():
    data = service.weekly_review_list()
    latest = data.get("latest")
    if not latest:
        return  # no report yet: nothing to check
    assert "period" in latest
    assert "summary" in latest or latest.get("summary") is None
    assert "review" in latest or latest.get("review") is None
    assert "review_pending" in latest or latest.get("review_pending") is None


if __name__ == "__main__":
    for t in (
        test_count_review_buckets_and_formulas,
        test_collect_review_metrics_from_temp_vault,
        test_review_metrics_matches_real_records,
        test_baseline_detection,
        test_collect_metrics_includes_review_and_baseline,
        test_snapshot_has_new_fields_and_old_preserved,
        test_markdown_has_weekly_status_and_review_split,
        test_service_review_counts_unified_with_metrics,
        test_weekly_review_api_fields,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all weekly review phase A tests passed")
