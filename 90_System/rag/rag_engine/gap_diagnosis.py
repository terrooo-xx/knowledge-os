"""Knowledge Gap Diagnosis: turn RAG Evaluation failures into clustered,
prioritized, evidence-backed gap entries + before/after diff.

Pure functions (no network / LLM / UI). Inputs are evaluation records already
produced by `scripts/evaluate_benchmark.py` (production retrieval chain).

Deliverables:
  - per-query failure kind: answered / knowledge_gap / evidence_gap /
    retrieval_gap / judge_gap / system_error
  - per-query diagnosis (trace summary with evidence)
  - gap clustering (explicit knowledge-boundary map, NOT string similarity)
  - P0/P1/P2 priority (transparent, not a composite score)
  - gap registry entries with evidence (query_ids / failure_types /
    relevant_sources / existing_wikis / retrieval_trace)
  - before/after run diff: RECOVERED / REGRESSED / UNCHANGED / NEW_FAILURE

Never fabricates knowledge: gaps with no reliable source get
recommended_action=acquire_source and are NOT auto-filled by the LLM.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_engine.evaluation import (
    FINAL_ANSWERED,
    FINAL_KNOWLEDGE_MISSING,
    FINAL_SYSTEM_ERROR,
    classify_failure,
    final_status,
)

# ---------------------------------------------------------------- failure kind

KIND_ANSWERED = "answered"
KIND_KNOWLEDGE = "knowledge_gap"
KIND_EVIDENCE = "evidence_gap"
KIND_RETRIEVAL = "retrieval_gap"
KIND_JUDGE = "judge_gap"
KIND_SYSTEM = "system_error"

KIND_LABELS = {
    KIND_ANSWERED: "已回答",
    KIND_KNOWLEDGE: "知识缺失（无可靠资料）",
    KIND_EVIDENCE: "证据不足（有候选但证据不充分）",
    KIND_RETRIEVAL: "检索缺口（预期有资料但未命中，需人工确认）",
    KIND_JUDGE: "Judge 拒绝（有候选但 LLM Judge 判定不足）",
    KIND_SYSTEM: "系统错误",
}

# 优先级建议
PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"

# 建议动作
ACTION_EXPAND = "expand_wiki"
ACTION_CREATE = "create_wiki"
ACTION_ACQUIRE = "acquire_source"
ACTION_NONE = "none"

ACTION_LABELS = {
    ACTION_EXPAND: "扩充现有 Wiki",
    ACTION_CREATE: "新建 Wiki（Draft）",
    ACTION_ACQUIRE: "获取可靠来源",
    ACTION_NONE: "暂不处理",
}

GAP_STATUS_OPEN = "open"
GAP_STATUS_RESOLVED = "resolved"


def _exec(record: dict) -> dict:
    return record.get("execution") or {}


def _judge(record: dict) -> dict:
    return record.get("judge") or {}


def _norm_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in ("true", "yes", "1")


def classify_failure_kind(record: dict) -> str:
    """5-way classification (the user-facing failure kind for gap pipeline).

    Never treats expected_* as ground truth; judge_gap is reported separately
    from evidence_gap so we never hide "Judge 拒绝" behind "knowledge missing".
    """
    status = final_status(record)
    if status == FINAL_ANSWERED:
        return KIND_ANSWERED
    if status == FINAL_SYSTEM_ERROR:
        return KIND_SYSTEM

    ex = _exec(record)
    jd = _judge(record)
    judge_rejected = bool(jd.get("executed")) and jd.get("result") == "insufficient"
    if judge_rejected:
        return KIND_JUDGE

    gate_passed = bool(ex.get("gate_passed"))
    has_candidates = int(ex.get("wiki_count") or 0) > 0 or int(ex.get("raw_count") or 0) > 0
    if gate_passed and has_candidates:
        return KIND_EVIDENCE

    if _norm_bool(record.get("expected_answerable")) is True:
        return KIND_RETRIEVAL
    return KIND_KNOWLEDGE


# ---------------------------------------------------------------- diagnosis


def diagnose_query(record: dict) -> dict:
    """Per-query minimum diagnosis (all fields come from the real trace)."""
    ex = _exec(record)
    ev = record.get("evidence") or {}
    jd = _judge(record)
    windows = record.get("evidence_windows") or []
    top = []
    for w in windows[:5]:
        top.append({
            "source": w.get("source"),
            "retrieval_score": w.get("retrieval_score"),
            "rerank_score": w.get("rerank_score"),
            "chars": len(str(w.get("text") or "")),
        })
    return {
        "query_id": record.get("query_id"),
        "query": record.get("query"),
        "expected_answerable": record.get("expected_answerable"),
        "expected_source": record.get("expected_source"),
        "category": record.get("category"),
        "query_type": record.get("query_type"),
        "initial_path": ex.get("initial_path"),
        "wiki_confidence": ex.get("wiki_confidence"),
        "gate_passed": ex.get("gate_passed"),
        "fallback_used": ex.get("fallback_used"),
        "fallback_reason": ex.get("fallback_reason"),
        "raw_ran": ex.get("raw_ran"),
        "reranker_used": ex.get("reranker_used"),
        "confidence": ex.get("confidence"),
        "wiki_count": ex.get("wiki_count"),
        "raw_count": ex.get("raw_count"),
        "evidence_sufficient": ev.get("sufficient"),
        "gap_type": ev.get("gap_type"),
        "judge_executed": jd.get("executed"),
        "judge_result": jd.get("result"),
        "final_status": final_status(record),
        "failure_type": classify_failure(record),
        "failure_kind": classify_failure_kind(record),
        "relevant_sources": sorted({str(w.get("source") or "") for w in windows if w.get("source")}),
        "top_evidence": top,
        "latency_ms": (record.get("metrics") or {}).get("total_ms"),
    }


# ---------------------------------------------------------------- clustering


def cluster_failures(records: list[dict], cluster_map: dict[str, str]) -> list[dict]:
    """Group failed records by explicit gap id (cluster_map: query_id -> gap_id).

    Clustering is a knowledge decision (human audit), not string similarity.
    """
    failed = [r for r in records if final_status(r) != FINAL_ANSWERED]
    groups: dict[str, list[dict]] = {}
    for r in failed:
        gid = cluster_map.get(r.get("query_id"))
        if not gid:
            gid = f"gap_{r.get('query_id')}"
        groups.setdefault(gid, []).append(r)
    return [{"gap_id": gid, "queries": groups[gid]} for gid in sorted(groups)]


def _count_signals(records: list[dict]) -> dict:
    return {
        "query_count": len(records),
        "knowledge_missing_count": sum(1 for r in records if final_status(r) == FINAL_KNOWLEDGE_MISSING),
        "evidence_insufficient_count": sum(1 for r in records if classify_failure_kind(r) == KIND_EVIDENCE),
        "judge_rejected_count": sum(1 for r in records if classify_failure_kind(r) == KIND_JUDGE),
        "retrieval_gap_count": sum(1 for r in records if classify_failure_kind(r) == KIND_RETRIEVAL),
        "system_error_count": sum(1 for r in records if classify_failure_kind(r) == KIND_SYSTEM),
    }


def prioritize_gap(signals: dict, source_available: bool, wiki_exists: bool,
                   recommended_action: str, override: str | None = None) -> str:
    """Transparent priority:
      P0: >=2 failed queries AND reliable source available (directly improvable)
      P1: source available, or existing wiki that needs expansion
      P2: otherwise (no reliable source / low demand)
    """
    if override:
        return override
    if signals.get("query_count", 0) >= 2 and source_available:
        return PRIORITY_P0
    if source_available or (wiki_exists and recommended_action == ACTION_EXPAND):
        return PRIORITY_P1
    return PRIORITY_P2


# ---------------------------------------------------------------- registry


def build_gap_registry(
    records: list[dict],
    cluster_map: dict[str, str],
    gap_meta: dict[str, dict],
    wiki_index: dict[str, Path] | None = None,
    source_index: dict[str, Path] | None = None,
    created: str = "",
) -> list[dict]:
    """Build gap registry entries with evidence from real records + audit meta.

    wiki_index:  vault-relative path (str) -> existing wiki Path
    source_index: vault-relative path (str) -> source Path (Inbox/10_Sources)
    """
    wiki_index = wiki_index or {}
    source_index = source_index or {}
    clusters = cluster_failures(records, cluster_map)
    out = []
    for cl in clusters:
        gid = cl["gap_id"]
        meta = gap_meta.get(gid) or {}
        queries = cl["queries"]
        signals = _count_signals(queries)
        # collect evidence from records
        query_ids = [r.get("query_id") for r in queries]
        failure_types = sorted({classify_failure(r) or FINAL_KNOWLEDGE_MISSING for r in queries})
        failure_kinds = sorted({classify_failure_kind(r) for r in queries})
        rel_sources: list[str] = []
        existing_wikis: list[str] = []
        for r in queries:
            for s in (r.get("evidence") or {}).get("sources", []):
                if s and s not in existing_wikis:
                    existing_wikis.append(s)
        rel_sources = [str(s) for s in (meta.get("sources") or [])]
        if not rel_sources:
            # 无人工指定时，尝试从已有 Wiki 反推来源
            for w in existing_wikis:
                pass  # 不自动编造来源
        wiki_target = meta.get("wiki_target") or {}
        recommended_action = meta.get("recommended_action") or _auto_action(
            bool(wiki_target.get("existing")), bool(rel_sources))
        source_available = bool(rel_sources)
        wiki_exists = bool(wiki_target.get("existing"))
        priority = prioritize_gap(
            signals, source_available, wiki_exists, recommended_action,
            override=meta.get("priority"),
        )
        entry = {
            "id": gid,
            "domain": meta.get("domain") or (queries[0].get("category") if queries else "unknown"),
            "title": meta.get("title") or gid,
            "status": GAP_STATUS_OPEN,
            "priority": priority,
            "signals": signals,
            "source_available": source_available,
            "wiki_exists": wiki_exists,
            "wiki_target": wiki_target or None,
            "recommended_action": recommended_action,
            "problem": meta.get("problem") or [],
            "sources": rel_sources,
            "evidence": {
                "query_ids": query_ids,
                "failure_types": failure_types,
                "failure_kinds": failure_kinds,
                "existing_wikis": existing_wikis,
                "retrieval_traces": {
                    r.get("query_id"): {
                        "path": (r.get("execution") or {}).get("path"),
                        "initial_path": (r.get("execution") or {}).get("initial_path"),
                        "fallback_reason": (r.get("execution") or {}).get("fallback_reason"),
                        "wiki_confidence": (r.get("execution") or {}).get("wiki_confidence"),
                        "failure": classify_failure(r),
                        "failure_kind": classify_failure_kind(r),
                    } for r in queries
                },
            },
            "before": None,
            "after": None,
            "resolved_by": None,
            "resolved_at": None,
            "created": created or "",
            "notes": meta.get("notes") or "",
        }
        out.append(entry)
    return out


def _auto_action(wiki_exists: bool, source_available: bool) -> str:
    if wiki_exists:
        return ACTION_EXPAND
    if source_available:
        return ACTION_CREATE
    return ACTION_ACQUIRE


def annotate_gaps_with_diff(gaps: list[dict], before: list[dict], after: list[dict],
                          cluster_map: dict[str, str]) -> list[dict]:
    """Fill each gap's before/after recovery status from two runs.

    before/after = {"answered": n, "total": n, "recovered": n, "remaining_failures": n}
    Auto-resolve a gap (status=resolved) only when ALL its queries are answered
    in the after run (verified improvement, not just path change).
    """
    from datetime import datetime as _dt
    bmap = {r.get("query_id"): r for r in before}
    amap = {r.get("query_id"): r for r in after}

    def _snap(qids, recs):
        qids = [q for q in qids if q in recs]
        if not qids:
            return None
        answered = sum(1 for q in qids if final_status(recs[q]) == FINAL_ANSWERED)
        return {"answered": answered, "total": len(qids),
                "remaining_failures": len(qids) - answered}

    for g in gaps:
        qids = [q for q in (g.get("evidence") or {}).get("query_ids", [])]
        before_snap = _snap(qids, bmap)
        after_snap = _snap(qids, amap)
        if before_snap and after_snap:
            delta = max(0, after_snap["answered"] - before_snap["answered"])
            before_snap["recovered"] = delta
            after_snap["recovered"] = delta
            g["before"] = before_snap
            g["after"] = after_snap
            if after_snap["remaining_failures"] == 0 and after_snap["total"] > 0:
                g["status"] = GAP_STATUS_RESOLVED
                g["resolved_by"] = "evaluation_diff"
                g["resolved_at"] = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
    return gaps


# ---------------------------------------------------------------- diff

CHANGE_RECOVERED = "RECOVERED"
CHANGE_REGRESSED = "REGRESSED"
CHANGE_UNCHANGED_ANSWERED = "UNCHANGED_ANSWERED"
CHANGE_UNCHANGED_FAILED = "UNCHANGED_FAILED"
CHANGE_NEW_ANSWERED = "NEW_ANSWERED"
CHANGE_NEW_FAILURE = "NEW_FAILURE"
CHANGE_REMOVED = "REMOVED"

REGRESSION_REAL = "REAL_REGRESSION"
REGRESSION_JUDGE_VARIANCE = "JUDGE_VARIANCE"
REGRESSION_UNKNOWN = "UNKNOWN"


def _evidence_signature(record: dict | None) -> tuple:
    """Retrieved document set (sorted unique source paths). Order/path changes
    (wiki vs raw) on the SAME documents do NOT count as evidence change."""
    wins = (record or {}).get("evidence_windows") or []
    return tuple(sorted({str(w.get("source") or "") for w in wins if w.get("source")}))


def classify_regression_change(before: dict | None, after: dict | None) -> str:
    """Classify a REGRESSED query (before answered -> after failed).

    REAL_REGRESSION: 检索命中的文档集合发生确定性变化（不同资料）
    JUDGE_VARIANCE:  命中的文档集合一致，仅 Judge 判定变化
    UNKNOWN:         缺少可比对的证据（无法判断）
    """
    b_sig = _evidence_signature(before)
    a_sig = _evidence_signature(after)
    if b_sig and a_sig:
        return REGRESSION_JUDGE_VARIANCE if b_sig == a_sig else REGRESSION_REAL
    return REGRESSION_UNKNOWN


def compare_runs(before: list[dict], after: list[dict]) -> dict:
    """Query-level before/after comparison (never only overall %)."""
    bmap = {r.get("query_id"): r for r in before}
    amap = {r.get("query_id"): r for r in after}
    all_ids = sorted(set(bmap) | set(amap))
    items: list[dict] = []
    counts = {"recovered": 0, "regressed": 0, "unchanged_answered": 0,
              "unchanged_failed": 0, "new_failure": 0, "new_answered": 0, "removed": 0}
    regression_classes = {"REAL_REGRESSION": 0, "JUDGE_VARIANCE": 0, "UNKNOWN": 0}
    for qid in all_ids:
        b = bmap.get(qid)
        a = amap.get(qid)
        bs = final_status(b) if b else None
        as_ = final_status(a) if a else None
        regression_class = None
        if b is None:
            if as_ == FINAL_ANSWERED:
                counts["new_answered"] += 1
                change = CHANGE_NEW_ANSWERED
            else:
                counts["new_failure"] += 1
                change = CHANGE_NEW_FAILURE
        elif a is None:
            counts["removed"] += 1
            change = CHANGE_REMOVED
        elif bs != FINAL_ANSWERED and as_ == FINAL_ANSWERED:
            counts["recovered"] += 1
            change = CHANGE_RECOVERED
        elif bs == FINAL_ANSWERED and as_ != FINAL_ANSWERED:
            counts["regressed"] += 1
            change = CHANGE_REGRESSED
            regression_class = classify_regression_change(b, a)
            regression_classes[regression_class] = regression_classes.get(regression_class, 0) + 1
        elif as_ == FINAL_ANSWERED:
            counts["unchanged_answered"] += 1
            change = CHANGE_UNCHANGED_ANSWERED
        else:
            counts["unchanged_failed"] += 1
            change = CHANGE_UNCHANGED_FAILED
        items.append({
            "query_id": qid,
            "query": (a or b).get("query"),
            "before_status": bs,
            "after_status": as_,
            "before_failure": classify_failure(b) if b else None,
            "after_failure": classify_failure(a) if a else None,
            "before_kind": classify_failure_kind(b) if b else None,
            "after_kind": classify_failure_kind(a) if a else None,
            "change": change,
            "change_type": change,
            "regression_class": regression_class,
            "recovered": change == CHANGE_RECOVERED,
            "regressed": change == CHANGE_REGRESSED,
        })
    recovered_ids = [i["query_id"] for i in items if i["recovered"]]
    regressed_ids = [i["query_id"] for i in items if i["regressed"]]
    # query_recovery_rate = 此前失败、重新评估后成功回答 / 此前失败且重新评估
    failed_before = [i for i in items if i["before_status"] is not None and i["before_status"] != FINAL_ANSWERED]
    qrr = round(100.0 * counts["recovered"] / len(failed_before), 1) if failed_before else None
    return {
        "counts": counts,
        "regression_classes": regression_classes,
        "total_compared": len([i for i in items if i["before_status"] is not None and i["after_status"] is not None]),
        "query_recovery_rate": qrr,
        "recovered_queries": recovered_ids,
        "regressed_queries": regressed_ids,
        "items": items,
    }


def render_diff_markdown(diff: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    c = diff["counts"]
    L = ["# RAG Evaluation Diff（Before / After）", ""]
    if meta.get("before_run"):
        L.append(f"- before_run：`{meta['before_run']}`")
    if meta.get("after_run"):
        L.append(f"- after_run：`{meta['after_run']}`")
    L.append("")
    L.append("## 汇总")
    L.append("")
    L.append(f"- Recovered：{c['recovered']}")
    L.append(f"- Unchanged：{c['unchanged_answered'] + c['unchanged_failed']}")
    L.append(f"- Regressed：{c['regressed']}")
    L.append(f"- New failures：{c['new_failure']}")
    L.append(f"- Query Recovery Rate：{diff.get('query_recovery_rate')}%"
             if diff.get("query_recovery_rate") is not None else "- Query Recovery Rate：N/A")
    L.append("")
    L.append("## 逐条变化")
    L.append("")
    L.append("| Query | Before | After | Change | Regression |")
    L.append("|---|---|---|---|---|")
    for i in diff["items"]:
        rc = i.get("regression_class") or ""
        L.append(f"| {i['query_id']} | {i['before_status'] or '—'} | {i['after_status'] or '—'} | {i['change']} | {rc} |")
    rc = diff.get("regression_classes") or {}
    if any(rc.values()):
        L.append("")
        L.append("### 回归分类（REAL_REGRESSION / JUDGE_VARIANCE / UNKNOWN）")
        L.append("")
        for k, v in rc.items():
            L.append(f"- {k}：{v}")
    L.append("")
    L.append("### Recovered")
    L.append("")
    if diff["recovered_queries"]:
        for qid in diff["recovered_queries"]:
            L.append(f"- {qid}")
    else:
        L.append("- 无")
    L.append("")
    L.append("### Regressed")
    L.append("")
    if diff["regressed_queries"]:
        for qid in diff["regressed_queries"]:
            L.append(f"- {qid}")
    else:
        L.append("- 无")
    L.append("")
    return "\n".join(L)


def render_audit_report(records: list[dict], gaps: list[dict], meta: dict | None = None) -> str:
    """Phase-1 audit report: Top failures -> classification -> gaps -> priorities."""
    meta = meta or {}
    L = ["# Evaluation → Knowledge Gap 审计", ""]
    if meta.get("run_id"):
        L.append(f"- run_id：`{meta['run_id']}`")
    L.append("")
    failed = [r for r in records if final_status(r) != FINAL_ANSWERED]
    L.append(f"## 1. Top Failure Queries（{len(failed)}）")
    L.append("")
    L.append("| Query | Final | Failure | Kind |")
    L.append("|---|---|---|---|")
    for r in failed:
        L.append(f"| {r.get('query_id')} | {final_status(r)} | {classify_failure(r)} | {classify_failure_kind(r)} |")
    L.append("")
    L.append("## 2. Failure 分类")
    L.append("")
    kinds = {}
    for r in failed:
        k = classify_failure_kind(r)
        kinds[k] = kinds.get(k, 0) + 1
    for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
        L.append(f"- {k}（{KIND_LABELS.get(k, k)}）：{c}")
    L.append("")
    L.append("## 3-5. Gap 候选（Knowledge / Evidence / Retrieval）")
    L.append("")
    for g in gaps:
        ev = g["evidence"]
        L.append(f"- **{g['id']}**（{g['title']}，{g['priority']}，{g['status']}）")
        L.append(f"  - queries：{', '.join(ev['query_ids'])}")
        L.append(f"  - failure_kinds：{', '.join(ev['failure_kinds'])}")
        L.append(f"  - source_available={g['source_available']} wiki_exists={g['wiki_exists']} "
                 f"action={g['recommended_action']}")
        L.append(f"  - sources：{', '.join(g['sources']) if g['sources'] else '（无）'}")
        if g["wiki_target"]:
            L.append(f"  - wiki_target：{g['wiki_target']}")
    L.append("")
    L.append("## 6. 已有 Wiki 但覆盖不足")
    L.append("")
    for g in gaps:
        if g["wiki_exists"]:
            L.append(f"- {g['id']}：{g['wiki_target']}")
    L.append("")
    L.append("## 7. 已有 Source 但无 Wiki")
    L.append("")
    for g in gaps:
        if g["source_available"] and not g["wiki_exists"]:
            L.append(f"- {g['id']}：{', '.join(g['sources'])}")
    L.append("")
    L.append("## 8. 完全缺资料")
    L.append("")
    for g in gaps:
        if not g["source_available"]:
            L.append(f"- {g['id']}")
    L.append("")
    L.append("## 9. Gap 聚类")
    L.append("")
    for g in gaps:
        L.append(f"- {g['id']} ← {', '.join(g['evidence']['query_ids'])}")
    L.append("")
    L.append("## 10. P0/P1/P2 优先级")
    L.append("")
    for p in ("P0", "P1", "P2"):
        sel = [g for g in gaps if g["priority"] == p]
        if sel:
            L.append(f"- {p}：{', '.join(g['id'] for g in sel)}")
    L.append("")
    L.append("## 11. 建议 Wiki Improvement Tasks")
    L.append("")
    for g in gaps:
        L.append(f"- [{g['priority']}] {g['id']} → {ACTION_LABELS.get(g['recommended_action'], g['recommended_action'])}")
        for prob in g.get("problem") or []:
            L.append(f"  - {prob}")
    L.append("")
    L.append("## 12. Golden Set 标注计划")
    L.append("")
    L.append("- 优先标注：2 wiki-first + 2 fallback + 2 knowledge_missing（见 golden.yaml）")
    L.append("")
    L.append("## 13. Before/After Benchmark 方案")
    L.append("")
    L.append("- before：`" + str(meta.get("run_id", "latest")) + "`")
    L.append("- after：补 Wiki + reindex 后重跑 evaluate_benchmark.py，用 evaluate_diff 对比")
    L.append("")
    L.append("## 14. 最小修改文件")
    L.append("")
    L.append("- 本阶段只新增诊断/注册表/测试；Wiki 修改以 draft 形式，遵守生命周期，不自动批准。")
    L.append("")
    return "\n".join(L)
