"""Wiki Compilation: gap-driven Source -> Wiki compilation planning.

Turns a Knowledge Gap into:
  - knowledge requirements (required_fact + source_location, covered only if
    the source actually supports it — never LLM-filled)
  - NEW_WIKI / EXPAND_EXISTING_WIKI decision
  - query coverage matrix (before status, requirement coverage,
    expected_after.likely_recoverable = true/false/unknown)
  - source traceability (title / local_path / page / section / url)

Pure functions + YAML I/O. Nothing here writes Wiki files; the CLI does that
with status=draft + review_required=true.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ACTION_NEW = "NEW_WIKI"
ACTION_EXPAND = "EXPAND_EXISTING_WIKI"

LIKELY_TRUE = "true"
LIKELY_FALSE = "false"
LIKELY_UNKNOWN = "unknown"


def load_compilation(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"created": "", "gaps": []}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return {"created": "", "gaps": []}
    if not isinstance(data, dict):
        return {"created": "", "gaps": []}
    return {"created": data.get("created", ""), "gaps": data.get("gaps") or []}


def save_compilation(path: str | Path, compilation: dict) -> None:
    import yaml
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(compilation, allow_unicode=True, sort_keys=False), encoding="utf-8")


def decide_wiki_action(gap: dict, existing_wiki_status: str | None) -> str:
    """EXPAND when there is an editable (draft) existing wiki on the same topic;
    NEW_WIKI when none exists or the existing wiki is reviewed/stable (AI must
    not modify those) or the knowledge boundary is distinct."""
    target = gap.get("wiki_target") or {}
    wiki_exists = target.get("existing", gap.get("wiki_exists", False))
    if not wiki_exists:
        return ACTION_NEW
    if existing_wiki_status in ("draft",):
        return ACTION_EXPAND
    return ACTION_NEW  # reviewed/stable 不可由 AI 修改 -> 新建 draft


def validate_requirements(entries: list[dict]) -> list[str]:
    problems = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("requirement_id"):
            problems.append(f"requirements[{i}]: missing requirement_id")
            continue
        if e.get("covered") not in (True, False):
            problems.append(f"{e['requirement_id']}: covered 必须是 bool")
        # 只有 covered=true 的事实必须可追溯；covered=false 表示明确「无来源依据」
        if e.get("covered") is True and not (e.get("source_location") or {}).get("title"):
            problems.append(f"{e['requirement_id']}: covered=true 但缺 source_location.title（可追溯）")
    return problems


def validate_coverage_matrix(rows: list[dict]) -> list[str]:
    problems = []
    for r in rows:
        if not r.get("query_id"):
            problems.append("coverage row missing query_id")
        lr = (r.get("expected_after") or {}).get("likely_recoverable")
        if lr not in (LIKELY_TRUE, LIKELY_FALSE, LIKELY_UNKNOWN):
            problems.append(f"{r.get('query_id')}: likely_recoverable 非法 {lr!r}")
    return problems


def annotate_compilation_with_after(compilation: dict, diff_items: list[dict]) -> dict:
    """Backfill each coverage-matrix row with the after status from a diff."""
    by_id = {i.get("query_id"): i for i in diff_items or []}
    for g in compilation.get("gaps") or []:
        for t in g.get("wiki_tasks") or []:
            for row in t.get("coverage_matrix") or []:
                item = by_id.get(row.get("query_id"))
                if not item:
                    continue
                row["after"] = {
                    "final_status": item.get("after_status"),
                    "change": item.get("change"),
                    "recovered": item.get("recovered"),
                    "regression_class": item.get("regression_class"),
                }
    return compilation


def render_wiki_compilation_audit(gaps: list[dict], meta: dict | None = None) -> str:
    """Phase-17 audit report (read-only output).

    gaps: compiled entries from wiki_compile_gaps.py (gap_id / wiki_tasks).
    """
    meta = meta or {}
    L = ["# Phase 17 Audit：Source → Wiki Compilation", ""]
    if meta.get("generated_at"):
        L.append(f"- generated_at：`{meta['generated_at']}`")
    L.append("")
    L.append("## 1. P0/P1 Gap 清单")
    L.append("")
    for g in gaps:
        L.append(f"- {g.get('gap_id') or g.get('id')}（{g.get('priority')}）{g.get('title')}")
    L.append("")
    L.append("## 2-5. Gap 详情 / 失败 Query / Knowledge Requirements / Source 覆盖 / Wiki 覆盖")
    L.append("")
    for g in gaps:
        L.append(f"### {g.get('gap_id') or g.get('id')}（{g.get('priority')}）{g.get('title')}")
        tasks = g.get("wiki_tasks") or []
        if not tasks:
            L.append("- （无 Wiki 编译任务）")
            continue
        for t in tasks:
            L.append(f"#### {t.get('task_id')}：{t.get('title')}")
            L.append(f"- 决策：{t.get('wiki_action')} → {t.get('wiki_target_path')}")
            src = t.get("source") or {}
            L.append(f"- Source：{src.get('title', '?')}（local={src.get('local_path', '?')}"
                     f"{', p.' + str(src.get('page')) if src.get('page') else ''}"
                     f"{', ' + src.get('section', '') if src.get('section') else ''}）")
            L.append(f"- 覆盖 Query：{', '.join(t.get('query_ids', []))}")
            reqs = t.get("requirements") or []
            L.append("  Knowledge Requirements：")
            for r in reqs:
                sl = r.get("source_location") or {}
                L.append(f"  - [{r.get('requirement_id')}] {r.get('required_fact')} "
                         f"(covered={'YES' if r.get('covered') else 'NO'}, "
                         f"source={sl.get('title', '?')}"
                         f"{', p.' + str(sl.get('page')) if sl.get('page') else ''})")
            cm = t.get("coverage_matrix") or []
            if cm:
                L.append("  Query Coverage Matrix：")
                for row in cm:
                    lr = (row.get("expected_after") or {}).get("likely_recoverable", "unknown")
                    L.append(f"  - {row.get('query_id')}: before={row.get('before', {}).get('final_status')} "
                             f"covered={row.get('covered_count') if 'covered_count' in row else ''} "
                             f"likely_recoverable={lr}")
            if t.get("missing_knowledge"):
                L.append(f"  缺失知识点：{'; '.join(t['missing_knowledge'])}")
            if t.get("coverage_note"):
                L.append(f"  说明：{t['coverage_note']}")
            L.append("")
    L.append("## 6-7. Wiki 缺失知识点 / NEW vs EXPAND 决策")
    L.append("")
    for g in gaps:
        for t in g.get("wiki_tasks") or []:
            L.append(f"- {g.get('gap_id') or g.get('id')}/{t.get('task_id')}：{t.get('wiki_action')}　"
                     f"缺失：{'; '.join(t.get('missing_knowledge') or []) or '（无）'}")
    L.append("")
    L.append("## 8. Source Traceability 方案")
    L.append("")
    L.append("- PDF：source{title, local_path, page, section, url}；HTML：source{title, url, section/heading}。")
    L.append("- 编译后的 Wiki 正文引用 source 时附 page/section，保证人工审核可回到原文。")
    L.append("")
    L.append("## 9. likely_recoverable 判断")
    L.append("")
    for g in gaps:
        for t in g.get("wiki_tasks") or []:
            lr = (t.get("coverage_matrix") or [{}])[0].get("expected_after", {}).get("likely_recoverable", "unknown")
            L.append(f"- {t.get('task_id')}：{lr}")
    L.append("")
    L.append("## 10. 第一批 Wiki Improvement Tasks")
    L.append("")
    for g in gaps:
        for t in g.get("wiki_tasks") or []:
            L.append(f"- [{g.get('priority')}] {t.get('task_id')} → {t.get('wiki_action')}（{t.get('wiki_target_path')}）")
    L.append("")
    return "\n".join(L)
