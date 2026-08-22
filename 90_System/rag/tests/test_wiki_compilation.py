"""Wiki Compilation tests (offline): gap->wiki task, source traceability,
NEW vs EXPAND decision, draft status, schema, after-annotation."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.wiki_compilation import (  # noqa: E402
    ACTION_EXPAND, ACTION_NEW, LIKELY_FALSE, LIKELY_TRUE, LIKELY_UNKNOWN,
    annotate_compilation_with_after, decide_wiki_action, load_compilation,
    render_wiki_compilation_audit, save_compilation,
    validate_coverage_matrix, validate_requirements,
)

COMPILATION = RAG_DIR / "evaluation" / "wiki_compilation.yaml"


def _gap(**kw):
    g = {"id": "gap_x", "priority": "P0", "wiki_exists": True,
         "wiki_target": {"existing": True, "path": "20_Wiki/x.md"}}
    g.update(kw)
    # keep wiki_target.existing consistent with the wiki_exists override
    if "wiki_exists" in kw:
        g["wiki_target"]["existing"] = bool(kw["wiki_exists"])
    return g


def _req(rid, covered=True, with_source=True):
    return {"requirement_id": rid, "query": "q1", "required_fact": "fact",
            "source_location": {"title": "S", "page": "1"} if with_source else {},
            "covered": covered, "notes": ""}


def test_new_vs_expand_decision():
    assert decide_wiki_action(_gap(wiki_exists=False), "draft") == ACTION_NEW
    assert decide_wiki_action(_gap(), "draft") == ACTION_EXPAND
    # reviewed/stable wiki 不可由 AI 修改 -> 新建 draft
    assert decide_wiki_action(_gap(), "reviewed") == ACTION_NEW
    assert decide_wiki_action(_gap(), "stable") == ACTION_NEW
    # 没有 wiki_target 时新建
    assert decide_wiki_action({"id": "g", "priority": "P1", "wiki_exists": True,
                               "wiki_target": {"existing": False}}, "draft") == ACTION_NEW


def test_requirements_validation_traceability():
    # covered=true 必须可追溯
    assert validate_requirements([_req("r1", covered=True, with_source=False)])
    assert validate_requirements([_req("r1", covered=True, with_source=True)]) == []
    # covered=false 允许无来源（明确「无来源依据」）
    assert validate_requirements([_req("r1", covered=False, with_source=False)]) == []
    assert validate_requirements([_req("r1", covered="maybe")])


def test_coverage_matrix_validation_likely():
    good = [{"query_id": "q1", "before": {"final_status": "knowledge_missing"},
             "expected_after": {"likely_recoverable": LIKELY_TRUE}}]
    assert validate_coverage_matrix(good) == []
    bad = [{"query_id": "q1", "expected_after": {"likely_recoverable": "maybe"}}]
    assert validate_coverage_matrix(bad)
    assert validate_coverage_matrix([{"expected_after": {"likely_recoverable": LIKELY_FALSE}}])


def test_compilation_roundtrip_and_audit():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wiki_compilation.yaml"
        comp = {"created": "2026-08-15", "gaps": [{
            "gap_id": "gap_freertos", "priority": "P0", "title": "T",
            "wiki_tasks": [{
                "task_id": "wt_a", "title": "A", "wiki_action": ACTION_NEW,
                "wiki_target_path": "20_Wiki/a.md",
                "source": {"title": "S", "local_path": "10_Sources/a.pdf", "page": "1"},
                "query_ids": ["q1"], "requirements": [_req("r1")],
                "coverage_matrix": [{"query_id": "q1",
                                     "before": {"final_status": "knowledge_missing"},
                                     "expected_after": {"likely_recoverable": LIKELY_UNKNOWN}}],
                "missing_knowledge": []}]}]}
        save_compilation(path, comp)
        loaded = load_compilation(path)
        assert loaded["gaps"][0]["wiki_tasks"][0]["task_id"] == "wt_a"
        md = render_wiki_compilation_audit(loaded["gaps"], {"generated_at": "now"})
        for token in ("# Phase 17 Audit", "wt_a", "likely_recoverable"):
            assert token in md


def test_annotate_compilation_with_after():
    comp = {"created": "", "gaps": [{
        "gap_id": "g", "priority": "P0", "title": "T",
        "wiki_tasks": [{
            "task_id": "wt", "title": "A", "wiki_action": ACTION_NEW,
            "wiki_target_path": "20_Wiki/a.md", "source": {"title": "S"},
            "query_ids": ["q1"], "requirements": [],
            "coverage_matrix": [{"query_id": "q1",
                                 "before": {"final_status": "knowledge_missing"},
                                 "expected_after": {"likely_recoverable": LIKELY_TRUE}}],
            "missing_knowledge": []}]}]}
    diff_items = [{"query_id": "q1", "after_status": "answered", "change": "RECOVERED",
                   "recovered": True, "regression_class": None}]
    annotate_compilation_with_after(comp, diff_items)
    row = comp["gaps"][0]["wiki_tasks"][0]["coverage_matrix"][0]
    assert row["after"]["final_status"] == "answered"
    assert row["after"]["change"] == "RECOVERED"
    assert row["after"]["recovered"] is True


def test_real_compilation_plan():
    comp = load_compilation(COMPILATION)
    assert comp["gaps"]
    for g in comp["gaps"]:
        for t in g["wiki_tasks"]:
            assert t["wiki_action"] in (ACTION_NEW, ACTION_EXPAND)
            assert validate_requirements(t["requirements"]) == []
            assert validate_coverage_matrix(t["coverage_matrix"]) == []
            # draft wikis must exist with status draft + review_required
            w = Path(r"D:\KnowledgeBase\Obsidian Vault") / t["wiki_target_path"]
            if t["wiki_action"] == ACTION_NEW or t["task_id"] in ("wt_freertos_task_notification", "wt_git_config"):
                assert w.exists(), f"missing {t['wiki_target_path']}"
                fm = w.read_text(encoding="utf-8").split("---", 2)[1]
                assert any(s in fm for s in ("status: draft", "status: reviewed")), fm
                assert "review_required" in fm