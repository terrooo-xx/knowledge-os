"""Source Acquisition: registry + status transitions + sufficiency review.

Ties Knowledge Gaps (gaps.yaml) to source acquisition tasks and their status.
Pure functions + YAML I/O; never fabricates source URLs as verified.

Status lifecycle:
    missing -> candidate -> acquired -> verified
  (acquired = 本地已获取；verified = 人工核验内容且可用于 Stable Wiki)

Source types (priority order per phase spec):
    official_docs > datasheet > reference_manual > project_docs >
    trusted_tutorial > unknown
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

STATUS_MISSING = "missing"
STATUS_CANDIDATE = "candidate"
STATUS_ACQUIRED = "acquired"
STATUS_VERIFIED = "verified"
SOURCE_STATUSES = (STATUS_MISSING, STATUS_CANDIDATE, STATUS_ACQUIRED, STATUS_VERIFIED)

SOURCE_TYPES = ("official_docs", "datasheet", "reference_manual", "project_docs",
                "trusted_tutorial", "unknown")

SUFFICIENCY_LEVELS = ("high", "medium", "low", "unknown")

SUFFICIENCY_FIELDS = ("source_relevance", "source_authority", "source_completeness",
                      "source_recency", "source_extractability")


def load_registry(path: str | Path) -> dict:
    """Load source_acquisition.yaml -> {"created", "sources": [...]}."""
    p = Path(path)
    if not p.exists():
        return {"created": "", "sources": []}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return {"created": "", "sources": []}
    if not isinstance(data, dict):
        return {"created": "", "sources": []}
    sources = data.get("sources") or []
    return {"created": data.get("created", ""), "sources": sources if isinstance(sources, list) else []}


def save_registry(path: str | Path, registry: dict) -> None:
    import yaml
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")


def validate_registry(registry: dict) -> list[str]:
    """Return a list of problems (empty == valid)."""
    problems = []
    ids = set()
    for i, s in enumerate(registry.get("sources") or []):
        if not isinstance(s, dict) or not s.get("id"):
            problems.append(f"sources[{i}]: missing id")
            continue
        if s["id"] in ids:
            problems.append(f"duplicate source id: {s['id']}")
        ids.add(s["id"])
        if s.get("source_status") not in SOURCE_STATUSES:
            problems.append(f"{s['id']}: bad source_status {s.get('source_status')!r}")
        if s.get("source_type") not in SOURCE_TYPES:
            problems.append(f"{s['id']}: bad source_type {s.get('source_type')!r}")
        for f in SUFFICIENCY_FIELDS:
            v = (s.get("sufficiency") or {}).get(f)
            if v is not None and v not in SUFFICIENCY_LEVELS:
                problems.append(f"{s['id']}: bad {f}={v!r}")
    return problems


def transition_status(current: str, target: str) -> bool:
    """Allow only strictly-adjacent forward transitions in the lifecycle
    (missing -> candidate -> acquired -> verified; no skipping, no rollback)."""
    order = {s: i for i, s in enumerate(SOURCE_STATUSES)}
    cur, tgt = order.get(current, -1), order.get(target, -1)
    if cur < 0 or tgt < 0:
        return False
    return tgt == cur + 1


def apply_transition(entry: dict, target: str, reviewer: str = "") -> dict:
    """Return a new entry with status moved forward (validated)."""
    entry = dict(entry)
    if not transition_status(entry.get("source_status", STATUS_MISSING), target):
        raise ValueError(
            f"invalid transition {entry.get('source_status')!r} -> {target!r} "
            f"(must be monotonic missing<candidate<acquired<verified)")
    entry["source_status"] = target
    if target == STATUS_VERIFIED:
        entry.setdefault("verification", {})["verified"] = True
        entry["verification"]["reviewer"] = reviewer
    return entry


def gaps_source_summary(gaps: list[dict], sources: list[dict]) -> dict:
    """Per-gap source status (first/highest status among its source tasks)."""
    order = {s: i for i, s in enumerate(SOURCE_STATUSES)}
    by_gap: dict[str, list[dict]] = {}
    for s in sources:
        by_gap.setdefault(s.get("gap_id"), []).append(s)
    out = {}
    for g in gaps:
        gid = g.get("id")
        tasks = by_gap.get(gid, [])
        if not tasks:
            out[gid] = {"source_status": STATUS_MISSING, "source_tasks": 0}
            continue
        best = max(tasks, key=lambda t: order.get(t.get("source_status"), -1))
        out[gid] = {
            "source_status": best.get("source_status"),
            "source_tasks": len(tasks),
            "candidates": [t.get("id") for t in tasks],
        }
    return out


def p0_p1_missing(gaps: list[dict], sources: list[dict]) -> list[str]:
    """Gap ids (P0/P1) whose sources are all missing/absent."""
    summary = gaps_source_summary(gaps, sources)
    out = []
    for g in gaps:
        if g.get("priority") not in ("P0", "P1"):
            continue
        st = summary.get(g.get("id"), {}).get("source_status")
        if not st or st == STATUS_MISSING:
            out.append(g.get("id"))
    return out
