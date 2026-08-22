"""Evaluation Baseline: solidify a verified benchmark run as the official
baseline + regression protection.

Baseline status classification (never lets JUDGE_VARIANCE become REGRESSED):
  STABLE     - no REAL_REGRESSION, core recovered queries retained
  IMPROVED   - real RECOVERED and no REAL_REGRESSION
  REGRESSED  - at least one REAL_REGRESSION
  UNVERIFIED - wiki approval / index / benchmark state incomplete

Regression Protection: compare any current run against the baseline and emit a
clear warning (never blocks).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

STATUS_STABLE = "STABLE"
STATUS_IMPROVED = "IMPROVED"
STATUS_REGRESSED = "REGRESSED"
STATUS_UNVERIFIED = "UNVERIFIED"

BASELINE_KEYS = ("baseline_id", "run_id", "established_at", "benchmark_version",
                 "query_count", "coverage", "knowledge_missing_rate", "status",
                 "recovered_queries", "regressed_queries", "real_regressions",
                 "judge_variance_count", "wiki_approval", "notes")


def classify_baseline_status(*, real_regressions: int, recovered: int,
                             core_recovered_retained: bool | None = None,
                             verified: bool = True) -> str:
    """Transparent status. JUDGE_VARIANCE never counts as REGRESSED."""
    if not verified:
        return STATUS_UNVERIFIED
    if real_regressions > 0:
        return STATUS_REGRESSED
    if recovered > 0:
        return STATUS_IMPROVED
    if core_recovered_retained is False:
        return STATUS_UNVERIFIED
    return STATUS_STABLE


def load_baseline(path: str | Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def save_baseline(path: str | Path, baseline: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_baseline(run_id: str, meta: dict, diff: dict, *, wiki_approval: dict,
                    benchmark_version: str = "1.0", path: str | Path | None = None,
                    answered_queries: list | None = None) -> dict:
    """Build a baseline from a verified run + its diff vs the previous run.

    answered_queries: query ids answered in the CURRENT (verification) run.
    """
    counts = diff.get("counts") or {}
    regression_classes = diff.get("regression_classes") or {}
    real = regression_classes.get("REAL_REGRESSION", 0)
    recovered = counts.get("recovered", 0)
    core = set(wiki_approval.get("core_recovered_queries") or [])
    retained = core <= set(answered_queries or [])
    status = classify_baseline_status(real_regressions=real, recovered=recovered,
                                      core_recovered_retained=retained,
                                      verified=bool(wiki_approval.get("approved_all")))
    baseline = {
        "baseline_id": f"bl-{run_id}",
        "run_id": run_id,
        "established_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "benchmark_version": benchmark_version,
        "query_count": meta.get("query_count"),
        "coverage": meta.get("coverage"),
        "knowledge_missing_rate": meta.get("knowledge_missing_rate"),
        "status": status,
        "recovered_queries": diff.get("recovered_queries") or [],
        "regressed_queries": diff.get("regressed_queries") or [],
        "real_regressions": real,
        "judge_variance_count": regression_classes.get("JUDGE_VARIANCE", 0),
        "wiki_approval": wiki_approval,
        "notes": "",
    }
    if path:
        save_baseline(path, baseline)
    return baseline


def regression_check(current: dict, baseline: dict) -> dict:
    """Compare a current run summary against the baseline (warning only)."""
    base_cov = baseline.get("coverage")
    cur_cov = current.get("coverage")
    delta = None
    if base_cov is not None and cur_cov is not None:
        delta = round(cur_cov - base_cov, 1)
    status = STATUS_STABLE
    if delta is not None and delta < 0:
        status = STATUS_REGRESSED
    elif delta is not None and delta > 0:
        status = STATUS_IMPROVED
    return {
        "baseline_run": baseline.get("run_id"),
        "current_run": current.get("run_id"),
        "baseline_coverage": base_cov,
        "current_coverage": cur_cov,
        "delta_pp": delta,
        "status": status,
        "warning": None if status != STATUS_REGRESSED else
                   f"当前运行（{current.get('run_id')}）低于 Baseline（{baseline.get('run_id')}）"
                   f" {delta}pp，请检查是否有知识退化。",
    }


def render_baseline_markdown(baseline: dict, check: dict | None = None) -> str:
    L = ["# Evaluation Baseline", ""]
    L.append(f"- baseline_id：`{baseline.get('baseline_id')}`")
    L.append(f"- run_id：`{baseline.get('run_id')}`")
    L.append(f"- established_at：`{baseline.get('established_at')}`")
    L.append(f"- benchmark_version：`{baseline.get('benchmark_version')}`")
    L.append(f"- query_count：{baseline.get('query_count')}")
    L.append("")
    L.append("## 指标")
    L.append("")
    L.append(f"- Answer Coverage：{baseline.get('coverage')}%")
    L.append(f"- Knowledge Missing：{baseline.get('knowledge_missing_rate')}%")
    L.append(f"- Status：{baseline.get('status')}")
    L.append(f"- Recovered Queries：{', '.join(baseline.get('recovered_queries') or []) or '无'}")
    L.append(f"- Regressed Queries：{', '.join(baseline.get('regressed_queries') or []) or '无'}")
    L.append(f"- REAL_REGRESSION：{baseline.get('real_regressions')}　"
             f"JUDGE_VARIANCE：{baseline.get('judge_variance_count')}")
    wa = baseline.get("wiki_approval") or {}
    L.append(f"- Wiki Approval：{wa.get('approved', 0)}/{wa.get('total', 0)}"
             f"（approved_all={wa.get('approved_all')}）")
    if check:
        L.append("")
        L.append("## Regression Check（当前运行 vs Baseline）")
        L.append("")
        L.append(f"- Current：{check.get('current_run')}（coverage={check.get('current_coverage')}%）")
        L.append(f"- Delta：{check.get('delta_pp')}pp")
        L.append(f"- Status：{check.get('status')}")
        if check.get("warning"):
            L.append(f"- ⚠ {check.get('warning')}")
    L.append("")
    return "\n".join(L)
