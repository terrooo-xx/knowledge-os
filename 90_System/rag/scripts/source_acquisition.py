"""Source Acquisition CLI: validate + audit the source_acquisition.yaml registry.

Usage:
    python source_acquisition.py [--registry PATH] [--gaps PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

import yaml  # noqa: E402
from rag_engine.source_acquisition import (  # noqa: E402
    SOURCE_STATUSES, gaps_source_summary, load_registry, p0_p1_missing,
    validate_registry,
)

DEFAULT_REGISTRY = RAG_DIR / "evaluation" / "source_acquisition.yaml"
DEFAULT_GAPS = RAG_DIR / "evaluation" / "gaps.yaml"


def audit(registry: dict, gaps: list) -> dict:
    problems = validate_registry(registry)
    summary = gaps_source_summary(gaps, registry["sources"])
    p0_p1_missing_ids = p0_p1_missing(gaps, registry["sources"])
    status_counts = {}
    for s in registry["sources"]:
        st = s.get("source_status")
        status_counts[st] = status_counts.get(st, 0) + 1
    by_priority = {}
    for s in registry["sources"]:
        p = s.get("priority") or "?"
        by_priority.setdefault(p, []).append(s.get("id"))
    return {
        "ok": not problems,
        "problems": problems,
        "source_count": len(registry["sources"]),
        "status_counts": status_counts,
        "per_gap": summary,
        "p0_p1_source_missing": p0_p1_missing_ids,
        "by_priority": by_priority,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Source Acquisition audit CLI")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--gaps", default=str(DEFAULT_GAPS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    gaps = yaml.safe_load(Path(args.gaps).read_text(encoding="utf-8")) or [] if Path(args.gaps).exists() else []
    result = audit(registry, gaps)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"sources: {result['source_count']}")
        print(f"status: {result['status_counts']}")
        print(f"P0/P1 source missing: {result['p0_p1_source_missing']}")
        if result["problems"]:
            print("PROBLEMS:")
            for p in result["problems"]:
                print(f"  - {p}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
