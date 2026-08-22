"""Review Preflight CLI: run Knowledge OS Review Preflight standalone.

Runs the same service used by the Control Center manual API
(POST /api/review/preflight) so the LLM Review Judge can complete before the
Control Center is opened. Intended to be scheduled by Windows Task Scheduler
(see register_review_preflight_task.ps1).

Usage:
  python 90_System/control_center/review_preflight_cli.py --once [--limit N] [--verbose]
  python 90_System/control_center/review_preflight_cli.py --limit 8 --trigger scheduled

Behavior:
  - one bounded pass (max `limit` or config max_per_run candidates), then exit
  - cache / fingerprint reuse: unchanged candidates are not re-judged
  - never modifies Wiki, never auto-approves
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parent
if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))

import service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Knowledge OS Review Preflight (auto LLM Judge + cache + classification)"
    )
    parser.add_argument("--config", default=str(service.RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--limit", type=int, default=None,
        help="max candidates to judge in this run (default: config review_preflight.max_per_run)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="process currently processable candidates then exit (default behavior)",
    )
    parser.add_argument(
        "--trigger", choices=["cli", "scheduled"], default="cli",
        help="trigger label recorded in the audit log",
    )
    parser.add_argument("--verbose", action="store_true", help="print per-action result detail")
    parser.add_argument(
        "--governance", action="store_true",
        help="after preflight, run evaluation_governance.py --verify "
             "(knowledge-change gate: no-op when no evaluation required)",
    )
    args = parser.parse_args()

    result = service.preflight_review_candidates(limit=args.limit, trigger=args.trigger)
    print(f"Review Preflight: trigger={result.get('trigger')} ok={result.get('ok')}")
    if result.get("skipped"):
        print("  skipped:", result.get("message"))
        return 0
    if not result.get("enabled"):
        print("  disabled (review_preflight.enabled=false)")
        return 0
    print(f"  judged={result.get('judged')} reused={result.get('reused')} "
          f"blocked={result.get('blocked')} failed={result.get('failed')} "
          f"pending={result.get('pending_remaining')} llm_called={result.get('llm_called')} "
          f"duration_ms={result.get('duration_ms')}")
    if args.verbose and result.get("details"):
        print("  details:")
        for d in result["details"]:
            print("   " + json.dumps(d, ensure_ascii=False))
    if result.get("failed"):
        print("  WARNING: some judges failed -> those candidates stay needs_review (fail-closed).")

    # ---- Evaluation Governance（知识变更质量门禁）----
    # 复用现有 evaluation_governance.py --verify：无 required 立即退出（不跑 Benchmark）
    if args.governance:
        print("Governance: running evaluation_governance.py --verify ...")
        import subprocess
        gov_cli = service.RAG_DIR / "scripts" / "evaluation_governance.py"
        try:
            proc = subprocess.run(
                [sys.executable, str(gov_cli), "--verify", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            tail = out.strip().splitlines()[-1] if out.strip() else "{}"
            try:
                import json as _json
                gov = _json.loads(tail)
            except Exception:
                gov = {"ok": False, "message": out[-400:]}
            print(f"Governance: status={ (gov.get('state') or {}).get('status') } "
                  f"skipped={gov.get('skipped')} message={gov.get('message')}")
            print(f"  exit_code={proc.returncode}（0=正常/无需执行，1=Regression，2=Evaluation Failed）")
            return proc.returncode
        except Exception as exc:
            print(f"Governance: 运行失败（不阻断 Preflight 结果）: {exc}")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
