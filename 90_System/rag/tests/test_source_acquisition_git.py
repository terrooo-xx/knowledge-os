"""Git P1 Source Acquisition tests (offline).

Verifies the Phase 21 Git P1 loop: src_git_config is locally acquired (but
NOT verified), the official Obsidian-Git docs/README are present on disk, and
the wt_git_config compilation task is fully source-covered (plugin install /
repo init / remote / auth / auto-sync) with traceability — no hardcoded
source-limited "false" override left.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = RAG_DIR.parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.source_acquisition import (  # noqa: E402
    STATUS_ACQUIRED, load_registry, validate_registry,
)
from rag_engine.wiki_compilation import (  # noqa: E402
    LIKELY_FALSE, load_compilation, validate_coverage_matrix,
    validate_requirements,
)

REGISTRY = RAG_DIR / "evaluation" / "source_acquisition.yaml"
COMPILATION = RAG_DIR / "evaluation" / "wiki_compilation.yaml"


def _load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _git_compilation_task(compilation: dict) -> dict:
    for g in compilation.get("gaps") or []:
        if g.get("gap_id") != "gap_git_config":
            continue
        for t in g.get("wiki_tasks") or []:
            if t.get("task_id") == "wt_git_config":
                return t
    raise AssertionError("wt_git_config not found in wiki_compilation.yaml")


def test_git_source_registered_verified_by_human():
    # Phase 22-A：src_git_config 已在 Control Center 通过人工核验操作标记 verified（非自动）
    registry = load_registry(REGISTRY)
    assert validate_registry(registry) == []
    src = next(s for s in registry["sources"] if s["id"] == "src_git_config")
    assert src["gap_id"] == "gap_git_config"
    assert src["source_status"] == "verified"
    assert src["verification"]["verified"] is True
    assert src["verification"].get("verified_at")
    assert src["verification"].get("verified_by") == "user"
    # 官方文档 + README 本地已获取
    local = src["source"]["local_path"]
    related = {r["local_path"] for r in src.get("related_sources") or []}
    for p in [local, *related]:
        if not p:
            continue
        assert (VAULT_ROOT / p).exists(), f"missing local source: {p}"


def test_git_compilation_requirements_fully_covered():
    comp = load_compilation(COMPILATION)
    task = _git_compilation_task(comp)
    assert validate_requirements(task["requirements"]) == []
    assert validate_coverage_matrix(task["coverage_matrix"]) == []
    assert task["missing_knowledge"] == []
    reqs = {r["requirement_id"]: r for r in task["requirements"]}
    # 关键事实必须已覆盖且可追溯（Obsidian 同步流程不再 source-limited）
    for rid in ("git_req_3", "git_req_4", "git_req_5", "git_req_6"):
        r = reqs[rid]
        assert r["covered"] is True, rid
        assert (r.get("source_location") or {}).get("title"), rid
    assert all(r["covered"] for r in task["requirements"])
    # 覆盖矩阵 expected_after 不再是 false（薄来源限制已解除）
    row = task["coverage_matrix"][0]
    assert row["query_id"] == "q_git_config"
    assert row["expected_after"]["likely_recoverable"] != LIKELY_FALSE
    # Phase 21 真实验证：q_git_config 已恢复（after=answered/RECOVERED）
    assert row["after"]["final_status"] == "answered"
    assert row["after"]["recovered"] is True


def test_git_wiki_reviewed_with_sources():
    # 用户已在 Control Center 完成 Review（draft -> reviewed）；不得自动回到 draft
    wiki = VAULT_ROOT / "20_Wiki" / "01_计算机基础" / "Git基础配置.md"
    assert wiki.exists()
    fm = wiki.read_text(encoding="utf-8").split("---", 2)[1]
    assert any(f"status: {s}" in fm for s in ("draft", "reviewed", "stable"))
    assert "status: reviewed" in fm
    # 必须保留 Obsidian-Git 官方来源
    assert "Obsidian-Git_GettingStarted.md" in fm
    assert "Obsidian-Git_README.md" in fm


def test_script_wiki_tasks_has_no_source_limited_override():
    # 防止回归：脚本里不再硬编码 wt_git_config likely=false（薄来源覆盖已解除）
    script = _load_script_module("wiki_compile_gaps", RAG_DIR / "scripts" / "wiki_compile_gaps.py")
    tasks = script.WIKI_TASKS["gap_git_config"]
    assert tasks[0]["task_id"] == "wt_git_config"
    assert tasks[0]["source"]["local_path"].endswith("Obsidian-Git_GettingStarted.md")
    for r in tasks[0]["requirements"]:
        assert r["covered"] is True
        assert (r.get("source_location") or {}).get("title")


