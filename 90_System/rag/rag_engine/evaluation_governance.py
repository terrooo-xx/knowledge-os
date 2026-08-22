"""Evaluation Governance: make Baseline Regression Check a standard quality gate.

State machine (reuses Activity Log / existing Evaluation / Baseline; no second
task system):

    idle -> required -> running -> passed | improved | regressed | failed

Marked `required` on knowledge changes (wiki approved / index updated /
source updated) — batched: N changes collapse into ONE required state. Manual
viewing never triggers it. A failed or regressed run NEVER overwrites the
existing baseline; only a verified STABLE/IMPROVED run re-establishes it.
JUDGE_VARIANCE is never classified as REGRESSED.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

STATUS_IDLE = "idle"
STATUS_REQUIRED = "required"
STATUS_RUNNING = "running"
STATUS_PASSED = "passed"
STATUS_IMPROVED = "improved"
STATUS_REGRESSED = "regressed"
STATUS_FAILED = "failed"
STATUSES = (STATUS_IDLE, STATUS_REQUIRED, STATUS_RUNNING,
            STATUS_PASSED, STATUS_IMPROVED, STATUS_REGRESSED, STATUS_FAILED)

REASON_WIKI_APPROVED = "wiki_approved"
REASON_INDEX_UPDATED = "index_updated"
REASON_SOURCE_UPDATED = "source_updated"
REASON_MANUAL = "manual_request"
KNOWLEDGE_REASONS = (REASON_WIKI_APPROVED, REASON_INDEX_UPDATED, REASON_SOURCE_UPDATED)


def default_state() -> dict:
    return {
        "status": STATUS_IDLE,
        "reasons": [],
        "batch": {},
        "triggered_at": None,
        "started_at": None,
        "completed_at": None,
        "run_id": None,
        "baseline_id": None,
        "check": None,
        "error": None,
    }


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return default_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default_state()
    if not isinstance(data, dict):
        return default_state()
    base = default_state()
    base.update({k: v for k, v in data.items() if k in base})
    return base


def save_state(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mark_required(state: dict, reason: str, batch_meta: dict | None = None) -> dict:
    """Accumulate a knowledge change into the required batch (one evaluation)."""
    state = dict(state)
    if reason not in KNOWLEDGE_REASONS + (REASON_MANUAL,):
        raise ValueError(f"unknown reason: {reason}")
    reasons = list(state.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    state["reasons"] = reasons
    state["batch"] = dict(state.get("batch") or {})
    if batch_meta:
        for k, v in batch_meta.items():
            state["batch"][k] = state["batch"].get(k, 0) + (v if isinstance(v, int) else 1)
    if state.get("status") not in (STATUS_RUNNING,):
        state["status"] = STATUS_REQUIRED
    if not state.get("triggered_at"):
        state["triggered_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return state


def start(state: dict) -> dict:
    state = dict(state)
    state["status"] = STATUS_RUNNING
    state["started_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    state["error"] = None
    return state


def _status_from_check(check_status: str | None) -> str:
    if check_status == "STABLE":
        return STATUS_PASSED
    if check_status == "IMPROVED":
        return STATUS_IMPROVED
    if check_status == "REGRESSED":
        return STATUS_REGRESSED
    return STATUS_FAILED


def complete(state: dict, *, run_id: str, check: dict | None, baseline_id: str | None,
             reestablish_baseline: bool = False) -> dict:
    """Finalize a run. NEVER lets REGRESSED/FAILED overwrite the baseline."""
    state = dict(state)
    state["status"] = _status_from_check((check or {}).get("status"))
    state["run_id"] = run_id
    state["completed_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    state["check"] = check
    if check is not None and check.get("status") not in ("REGRESSED", None):
        if reestablish_baseline and baseline_id:
            state["baseline_id"] = baseline_id
    state["reasons"] = []
    state["batch"] = {}
    state["triggered_at"] = None
    state["started_at"] = None
    return state


def fail(state: dict, error: str) -> dict:
    state = dict(state)
    state["status"] = STATUS_FAILED
    state["error"] = str(error)
    state["completed_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    # 保留 required reasons，允许修复后重跑（re-run failed evaluation）
    return state


def should_verify(state: dict) -> bool:
    return state.get("status") in (STATUS_REQUIRED, STATUS_FAILED)


def has_knowledge_change(state: dict) -> bool:
    return any(r in KNOWLEDGE_REASONS for r in (state.get("reasons") or []))


def render_governance_markdown(state: dict, baseline: dict | None = None) -> str:
    L = ["# Evaluation Governance State", ""]
    L.append(f"- status：`{state.get('status')}`")
    L.append(f"- reasons：{', '.join(state.get('reasons') or []) or '（无）'}")
    if state.get("triggered_at"):
        L.append(f"- triggered_at：`{state.get('triggered_at')}`")
    if state.get("run_id"):
        L.append(f"- run_id：`{state.get('run_id')}`")
    if state.get("baseline_id"):
        L.append(f"- baseline_id：`{state.get('baseline_id')}`")
    if state.get("error"):
        L.append(f"- error：{state.get('error')}")
    c = state.get("check")
    if c:
        L.append("")
        L.append("## 最近 Baseline Check")
        L.append("")
        L.append(f"- current={c.get('current_run')} coverage={c.get('current_coverage')}% "
                 f"baseline={c.get('baseline_coverage')}% delta={c.get('delta_pp')}pp status={c.get('status')}")
    if baseline:
        L.append("")
        L.append(f"## Baseline：{baseline.get('baseline_id')} coverage={baseline.get('coverage')}% status={baseline.get('status')}")
    L.append("")
    return "\n".join(L)
