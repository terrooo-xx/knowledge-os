"""Evaluation Baseline CLI (Phase 18).

Establishes / checks the official Evaluation Baseline after wiki approval.

    python evaluation_baseline.py --establish --run <run_id> --prev <phase17_run_id>
    python evaluation_baseline.py --check --run <run_id>

Outputs: 40_Outputs/RAG Evaluation/baseline.json (+ baselines/<id>.json)
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

from rag_engine.evaluation_baseline import (  # noqa: E402
    create_baseline, load_baseline, regression_check, render_baseline_markdown,
    save_baseline,
)
from rag_engine.gap_diagnosis import compare_runs  # noqa: E402

EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
BASELINE_PATH = EVAL_ROOT / "baseline.json"
BASELINES_DIR = EVAL_ROOT / "baselines"

# Phase 17 批准的 4 个 Source-backed Wiki 及其恢复的 Query
CORE_WIKIS = {
    "20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md": "q_freertos_stack_overflow",
    "20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md": "q_freertos_task_notification",
    "20_Wiki/03_STM32/STM32定时器PWM输出.md": "q_stm32_timer_pwm",
    "20_Wiki/01_计算机基础/WSL安装Ubuntu.md": "q_wsl_ubuntu",
}


def wiki_approval_status() -> dict:
    approved = []
    pending = []
    for rel, qid in CORE_WIKIS.items():
        p = VAULT_ROOT / rel
        status = None
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if text.startswith("---"):
                fm = text.split("---", 2)[1]
                for line in fm.splitlines():
                    if line.strip().startswith("status:"):
                        status = line.split(":", 1)[1].strip()
        if status == "reviewed":
            approved.append(qid)
        else:
            pending.append(qid)
    total = len(CORE_WIKIS)
    return {"approved": len(approved), "total": total,
            "approved_all": len(approved) == total,
            "approved_queries": approved, "pending_wikis": pending,
            "core_recovered_queries": list(CORE_WIKIS.values())}


def _load_records(run_id: str) -> list[dict]:
    p = EVAL_ROOT / "runs" / run_id / "evaluation_records.jsonl"
    if not p.exists():
        raise FileNotFoundError(f"records not found: {p}")
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _run_meta(run_id: str) -> dict:
    p = EVAL_ROOT / "runs" / run_id / "meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _diff(before: str, after: str) -> dict:
    diff_path = EVAL_ROOT / "diff" / f"{before}__{after}" / "evaluation_diff.json"
    if diff_path.exists():
        try:
            return json.loads(diff_path.read_text(encoding="utf-8"))["diff"]
        except Exception:
            pass
    return compare_runs(_load_records(before), _load_records(after))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation Baseline CLI")
    parser.add_argument("--establish", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", required=True, help="current verification run id")
    parser.add_argument("--prev", default=None, help="previous run id (for establish)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    meta = _run_meta(args.run)
    wa = wiki_approval_status()

    if args.establish:
        prev = args.prev
        if not prev:
            print("--establish 需要 --prev（被比较的上一 run）", file=sys.stderr)
            return 2
        diff = _diff(prev, args.run)
        cov = None
        km = None
        try:
            report = json.loads((EVAL_ROOT / "runs" / args.run / "evaluation_report.json")
                                .read_text(encoding="utf-8"))
            ov = report["metrics"]["overall"]
            cov = ov.get("answer_coverage")
            km = ov.get("knowledge_missing_rate")
        except Exception:
            pass
        answered_queries = [r["query_id"] for r in _load_records(args.run)
                            if (r.get("final") or {}).get("status") == "answered"]
        baseline = create_baseline(
            args.run, {"query_count": meta.get("query_count"), "coverage": cov,
                       "knowledge_missing_rate": km},
            diff, wiki_approval=wa,
            benchmark_version=str(meta.get("benchmark_version") or "1.0"),
            answered_queries=answered_queries,
        )
        save_baseline(BASELINE_PATH, baseline)
        bl_dir = BASELINES_DIR
        bl_dir.mkdir(parents=True, exist_ok=True)
        save_basename = bl_dir / f"{baseline['baseline_id']}.json"
        save_baseline(save_basename, baseline)
        (EVAL_ROOT / "baseline.md").write_text(
            render_baseline_markdown(baseline), encoding="utf-8")
        if args.json:
            print(json.dumps({"ok": True, "baseline": baseline}, ensure_ascii=False, indent=2))
        else:
            print(f"baseline established: {baseline['baseline_id']} "
                  f"coverage={baseline['coverage']}% status={baseline['status']}")
        return 0

    if args.check:
        baseline = load_baseline(BASELINE_PATH)
        if not baseline:
            print("no baseline established yet", file=sys.stderr)
            return 1
        cov = None
        try:
            report = json.loads((EVAL_ROOT / "runs" / args.run / "evaluation_report.json")
                                .read_text(encoding="utf-8"))
            cov = report["metrics"]["overall"].get("answer_coverage")
        except Exception:
            pass
        check = regression_check({"run_id": args.run, "coverage": cov}, baseline)
        if args.json:
            print(json.dumps({"ok": True, "baseline": baseline, "check": check},
                             ensure_ascii=False, indent=2))
        else:
            print(f"baseline={baseline['run_id']}({baseline['coverage']}%) "
                  f"current={args.run}({cov}%) delta={check['delta_pp']}pp "
                  f"status={check['status']}")
        return 0

    print("需要 --establish 或 --check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
