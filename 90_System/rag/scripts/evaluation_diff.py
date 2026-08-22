"""Evaluation Diff CLI: query-level before/after comparison.

Compares two RAG Evaluation runs (same benchmark) and writes:

    - 40_Outputs/RAG Evaluation/diff/<before>__<after>/evaluation_diff.json
    - 40_Outputs/RAG Evaluation/diff/<before>__<after>/evaluation_diff.md
    - 40_Outputs/RAG Evaluation/latest_diff.json   (pointer for CC / Weekly Review)

Per-query change types: RECOVERED / REGRESSED / UNCHANGED_ANSWERED /
UNCHANGED_FAILED / NEW_ANSWERED / NEW_FAILURE / REMOVED.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.gap_diagnosis import (  # noqa: E402
    annotate_gaps_with_diff, compare_runs, render_diff_markdown,
)
from rag_engine.wiki_compilation import (  # noqa: E402
    annotate_compilation_with_after, load_compilation, save_compilation,
)

EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
DEFAULT_REGISTRY = RAG_DIR / "evaluation" / "gaps.yaml"


def _resolve_records(spec: str) -> tuple[list[dict], str]:
    """spec: run_id (under EVAL_ROOT/runs) or a direct .jsonl path."""
    p = Path(spec)
    if p.exists() and p.is_file():
        run_id = p.parent.name
    else:
        run_id = spec
        p = EVAL_ROOT / "runs" / run_id / "evaluation_records.jsonl"
        if not p.exists():
            raise FileNotFoundError(f"records not found for run: {run_id}")
    records = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records, run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation Diff CLI")
    parser.add_argument("--before", required=True, help="before run_id or .jsonl path")
    parser.add_argument("--after", required=True, help="after run_id or .jsonl path")
    parser.add_argument("--out", default=str(EVAL_ROOT / "diff"))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--compilation", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    before, before_id = _resolve_records(args.before)
    after, after_id = _resolve_records(args.after)
    diff = compare_runs(before, after)

    # 更新 wiki_compilation.yaml 的 query coverage matrix（after 回填）
    comp_path = Path(args.compilation) if args.compilation else None
    if comp_path and comp_path.exists():
        try:
            comp = load_compilation(comp_path)
            comp = annotate_compilation_with_after(comp, diff["items"])
            save_compilation(comp_path, comp)
        except Exception:
            pass

    # 更新 gap 注册表 before/after（全查询恢复的 gap 自动 resolved）
    reg_path = Path(args.registry)
    if reg_path.exists():
        try:
            import yaml
            _gaps = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or []
        except Exception:
            _gaps = None
        if isinstance(_gaps, list) and _gaps:
            # cluster map 从 gaps.yaml 的 evidence.query_ids 反推
            cluster_map = {}
            for g in _gaps:
                for q in (g.get("evidence") or {}).get("query_ids", []):
                    cluster_map[q] = g["id"]
            _gaps = annotate_gaps_with_diff(_gaps, before, after, cluster_map)
            reg_path.write_text(yaml.safe_dump(_gaps, allow_unicode=True, sort_keys=False),
                                encoding="utf-8")

    out_dir = Path(args.out) / f"{before_id}__{after_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "before_run": before_id,
        "after_run": after_id,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "diff": diff,
    }
    (out_dir / "evaluation_diff.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = render_diff_markdown(diff, {"before_run": before_id, "after_run": after_id})
    (out_dir / "evaluation_diff.md").write_text(md, encoding="utf-8")

    latest = {
        "before_run": before_id,
        "after_run": after_id,
        "generated_at": payload["generated_at"],
        "counts": diff["counts"],
        "regression_classes": diff.get("regression_classes"),
        "query_recovery_rate": diff["query_recovery_rate"],
        "recovered_queries": diff["recovered_queries"],
        "regressed_queries": diff["regressed_queries"],
        "diff_path": (out_dir / "evaluation_diff.md").relative_to(VAULT_ROOT).as_posix(),
    }
    (EVAL_ROOT / "latest_diff.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"ok": True, **latest}, ensure_ascii=False, indent=2))
    else:
        c = diff["counts"]
        print(f"diff: {out_dir}")
        print(f"recovered={c['recovered']} regressed={c['regressed']} "
              f"unchanged={c['unchanged_answered'] + c['unchanged_failed']} new_failure={c['new_failure']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
