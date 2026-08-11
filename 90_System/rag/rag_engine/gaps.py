"""Knowledge Gap persistence: append-only YAML registry."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

GAP_TYPES = {
    "knowledge_missing",
    "knowledge_insufficient",
    "knowledge_conflict",
    "retrieval_problem",
    "answer_quality_problem",
}


def load_gaps(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load knowledge gaps") from exc
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []


def record_gap(gap: dict, path: str) -> bool:
    gap_type = gap.get("type")
    if gap_type not in GAP_TYPES:
        raise ValueError(f"unsupported gap type: {gap_type}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    gaps = load_gaps(path)
    for existing in gaps:
        if existing.get("question") == gap.get("question") and existing.get(
            "type"
        ) == gap_type:
            return False
    gap.setdefault("status", "pending")
    gap.setdefault("priority", "medium")
    gap.setdefault(
        "detected_at", datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    gap.setdefault("suggested_action", "")
    gap.setdefault("related_sources", [])
    gap.setdefault("related_wiki", [])
    gaps.append(gap)
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to write knowledge gaps") from exc
    p.write_text(
        yaml.safe_dump(gaps, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return True


def resolve_gap(
    question: str,
    path: str,
    resolved_by: str = "",
    resolved_sources: list[str] | None = None,
) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    gaps = load_gaps(path)
    changed = False
    for gap in gaps:
        if gap.get("question") == question and gap.get("status") != "resolved":
            gap["status"] = "resolved"
            gap["resolved_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            gap["resolved_by"] = resolved_by
            gap["resolved_sources"] = resolved_sources or []
            changed = True
    if changed:
        import yaml

        p.write_text(
            yaml.safe_dump(gaps, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return changed