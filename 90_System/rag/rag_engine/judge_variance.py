"""Judge Variance: measure LLM Relevance Judge stability on FIXED evidence.

Never changes the judge; only observes it. For each query the retrieval /
reranker / evidence are captured ONCE (via patched judge input), then the judge
is re-run N times on the exact same chunks to classify:

    stable_sufficient / stable_insufficient / variance

Metrics (minimal):
    stable_rate = queries with identical results across repeats / tested queries
    flip_rate   = queries with at least one passed <-> rejected flip / tested queries
"""
from __future__ import annotations

STABLE_SUFFICIENT = "stable_sufficient"
STABLE_INSUFFICIENT = "stable_insufficient"
VARIANCE = "variance"


def judge_passed(result: dict) -> bool:
    """A judge result counts as passed iff relevance == 'relevant'."""
    return bool(result) and result.get("relevance") == "relevant"


def classify_variance(results: list[dict]) -> str:
    """Classify repeated judge results on identical evidence."""
    if not results:
        return "unknown"
    outcomes = {judge_passed(r) for r in results}
    if len(outcomes) == 1:
        return STABLE_SUFFICIENT if True in outcomes else STABLE_INSUFFICIENT
    return VARIANCE


def judge_variance_stats(entries: list[dict]) -> dict:
    """entries: [{"query_id", "results": [...], "classification": ...}]"""
    n = len(entries)
    stable = [e for e in entries if e.get("classification") in (STABLE_SUFFICIENT, STABLE_INSUFFICIENT)]
    flips = [e for e in entries if e.get("classification") == VARIANCE]
    stable_suff = [e for e in entries if e.get("classification") == STABLE_SUFFICIENT]
    stable_insuff = [e for e in entries if e.get("classification") == STABLE_INSUFFICIENT]
    return {
        "tested_queries": n,
        "stable_count": len(stable),
        "stable_rate": round(100.0 * len(stable) / n, 1) if n else None,
        "flip_count": len(flips),
        "flip_rate": round(100.0 * len(flips) / n, 1) if n else None,
        "stable_sufficient_count": len(stable_suff),
        "stable_insufficient_count": len(stable_insuff),
        "variance_queries": [e.get("query_id") for e in flips],
        "sample_too_small": n < 3,
        "sample_note": "Judge 重复样本 < 3，稳定率/翻转率仅作参考" if n < 3 else None,
    }


def render_variance_markdown(entries: list[dict], stats: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    L = ["# Judge Variance Report", ""]
    if meta.get("runs"):
        L.append(f"- 重复次数：{meta['runs']}")
    if meta.get("generated_at"):
        L.append(f"- generated_at：`{meta['generated_at']}`")
    L.append("")
    L.append("## 汇总")
    L.append("")
    L.append(f"- Tested Queries：{stats['tested_queries']}")
    L.append(f"- Stable Rate：{stats['stable_rate']}%")
    L.append(f"- Flip Rate：{stats['flip_rate']}%")
    if stats.get("sample_too_small"):
        L.append(f"- ⚠ {stats.get('sample_note')}")
    L.append("")
    L.append("## 逐条结果")
    L.append("")
    L.append("| Query | Run 结果 | 分类 |")
    L.append("|---|---|---|")
    for e in entries:
        outcomes = " / ".join("passed" if judge_passed(r) else "insufficient" for r in e.get("results", []))
        L.append(f"| {e.get('query_id')} | {outcomes} | {e.get('classification')} |")
    L.append("")
    L.append("## 说明")
    L.append("")
    L.append("- Retrieval / Reranker / Evidence 固定不变，仅重复执行 LLM Relevance Judge。")
    L.append("- variance 表示相同证据下 Judge 判定波动；不据此修改 Judge。")
    L.append("")
    return "\n".join(L)
