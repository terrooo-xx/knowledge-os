"""Golden Set: schema validation + manual review statistics.

Golden entries carry human ground truth (answerable / expected_source /
acceptable_paths) and manual review (answer_correct / evidence_supported /
citation_correct). These are NEVER derived from the LLM Judge.

acceptable_paths: wiki | raw | wiki_then_raw | either
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ACCEPTABLE_PATHS = ("wiki", "raw", "wiki_then_raw", "either")
REVIEW_BOOL_FIELDS = ("answerable", "answer_correct", "evidence_supported", "citation_correct")
SAMPLE_TOO_SMALL_N = 10


def load_golden(path: str | Path) -> dict:
    """Load + validate golden.yaml -> {"golden_version", "entries": [...]}."""
    p = Path(path)
    if not p.exists():
        return {"golden_version": "1.0", "entries": []}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return {"golden_version": "1.0", "entries": []}
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return {"golden_version": "1.0", "entries": []}
    return {"golden_version": str(data.get("golden_version") or "1.0"),
            "entries": data["entries"]}


def validate_golden(entries: list[dict]) -> list[str]:
    problems = []
    ids = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("id"):
            problems.append(f"entries[{i}]: missing id")
            continue
        if e["id"] in ids:
            problems.append(f"duplicate id: {e['id']}")
        ids.add(e["id"])
        gt = e.get("ground_truth") or {}
        if "answerable" not in gt:
            problems.append(f"{e['id']}: ground_truth.answerable missing")
        paths = gt.get("acceptable_paths")
        if paths is not None:
            if isinstance(paths, str):
                paths = [paths]
            for x in paths:
                if x not in ACCEPTABLE_PATHS:
                    problems.append(f"{e['id']}: bad acceptable_path {x!r}")
        rv = e.get("review") or {}
        for f in REVIEW_BOOL_FIELDS:
            v = rv.get(f)
            if v is not None and not isinstance(v, bool):
                problems.append(f"{e['id']}: review.{f} must be bool/null, got {v!r}")
    return problems


def _reviewed(entry: dict) -> bool:
    rv = entry.get("review") or {}
    return any(rv.get(f) is not None for f in REVIEW_BOOL_FIELDS)


def golden_stats(entries: list[dict]) -> dict:
    """Aggregate manual-review stats. Sample-size guard for N < 10.

    answer_correct / evidence_supported 只对「系统实际产出（可评估）」的条目计数；
    *_count 是相对总数，*_rate 是相对已评估数（避免把"未回答"当成"答错"）。
    """
    n = len(entries)
    reviewed = [e for e in entries if _reviewed(e)]
    total = len(reviewed)

    def _assessed(key):
        return [e for e in reviewed if (e.get("review") or {}).get(key) is not None]

    def _yes(key):
        return [e for e in reviewed if (e.get("review") or {}).get(key) is True]

    def _rate(key):
        a = _assessed(key)
        return round(100.0 * len(_yes(key)) / len(a), 1) if a else None

    return {
        "total": n,
        "reviewed": total,
        "reviewed_rate": round(100.0 * total / n, 1) if n else None,
        "answerable_count": len(_yes("answerable")),
        "answer_correct_count": len(_yes("answer_correct")),
        "answer_correct_assessed": len(_assessed("answer_correct")),
        "evidence_supported_count": len(_yes("evidence_supported")),
        "evidence_supported_assessed": len(_assessed("evidence_supported")),
        "citation_correct_count": len(_yes("citation_correct")),
        "citation_correct_assessed": len(_assessed("citation_correct")),
        "answer_correct_rate": _rate("answer_correct"),
        "evidence_supported_rate": _rate("evidence_supported"),
        "citation_correct_rate": _rate("citation_correct"),
        "sample_too_small": total < SAMPLE_TOO_SMALL_N,
        "sample_note": "Golden 样本过小，正确率仅作参考" if total < SAMPLE_TOO_SMALL_N else None,
    }


def get_entry(entries: list[dict], query_id: str) -> dict | None:
    for e in entries:
        if e.get("id") == query_id:
            return e
    return None
