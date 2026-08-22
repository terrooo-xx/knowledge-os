"""Knowledge OS deterministic metrics layer (no LLM, no speculation).

This module only computes factual statistics from the Vault:

  - Wiki counts by frontmatter status
  - Wiki growth (created / updated within an ISO week)
  - Knowledge gaps (from knowledge_gaps.yaml)
  - Project status (from 30_Projects/<project>/00_项目索引.md frontmatter)
  - Stale risk (explicit signals: review_required / low confidence / not
    updated within the configured threshold; reported as risk, never as fact)
  - System health (reuses existing health check scripts as single source)
  - Unified activity timeline (control_center log / inbox_processor_log /
    git history / wiki frontmatter)

It never writes files and never guesses numbers.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

RAG_DIR = Path(__file__).resolve().parents[2]
VAULT_ROOT = Path(__file__).resolve().parents[4]
REVIEW_ROOT = VAULT_ROOT / "40_Outputs" / "reviews" / "每周复盘"
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths  # noqa: E402
from rag_engine.gaps import load_gaps  # noqa: E402

VALID_PROJECT_STATUS = {
    "planning", "active", "blocked", "paused", "completed", "archived",
}


def load_config_public(config_path: str | None = None) -> dict:
    """Load RAG config (weekly_review section included)."""
    return load_config(config_path or str(RAG_DIR / "config.yaml"))


# ---------------------------------------------------------------- helpers

def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        import yaml
        data = yaml.safe_load(text[3:end])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"Z$", "", s)
    s = re.sub(r"[+-]\d{2}:\d{2}$", "", s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19].strip(), fmt)
        except ValueError:
            continue
    return None


def current_iso_week(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"


def iso_week_range(period: str) -> tuple[datetime, datetime]:
    """Return (week_start_monday, week_end_exclusive) for 'YYYY-WNN' (local)."""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", period or "")
    if not m:
        raise ValueError(f"invalid period: {period!r} (expected YYYY-WNN)")
    year, week = int(m.group(1)), int(m.group(2))
    jan4 = date(year, 1, 4)
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    start = week1_monday + timedelta(weeks=week - 1)
    return (
        datetime.combine(start, datetime.min.time()),
        datetime.combine(start + timedelta(days=7), datetime.min.time()),
    )


def _norm_ts(ts: Any) -> str:
    """Normalize a timestamp to 'YYYY-MM-DD HH:MM:SS' for sorting."""
    if not ts:
        return ""
    return str(ts).replace("T", " ")[:19]


# ---------------------------------------------------------------- wiki

def collect_wiki_stats(vault_root: Path) -> dict:
    status_count: dict[str, int] = {}
    wikis = []
    wiki_root = vault_root / "20_Wiki"
    for p in sorted(wiki_root.rglob("*.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(vault_root).as_posix()
        fm = _parse_frontmatter(p)
        status = fm.get("status") or "unknown"
        status_count[status] = status_count.get(status, 0) + 1
        sources = fm.get("source") or []
        if not isinstance(sources, list):
            sources = [sources]
        wikis.append({
            "path": rel,
            "title": fm.get("title") or p.stem,
            "domain": fm.get("domain", ""),
            "status": status,
            "created": _parse_date(fm.get("created")),
            "updated": _parse_date(fm.get("updated")),
            "review_required": bool(fm.get("review_required", False)),
            "confidence": str(fm.get("confidence") or "").lower(),
            "sources": [str(s) for s in sources if str(s).strip()],
        })
    return {
        "wiki_total": len(wikis),
        "wiki_draft": status_count.get("draft", 0),
        "wiki_reviewed": status_count.get("reviewed", 0),
        "wiki_stable": status_count.get("stable", 0),
        "wiki_unknown": status_count.get("unknown", 0),
        "review_pending": status_count.get("draft", 0),
        "wikis": wikis,
    }


def collect_growth(wikis: list[dict], start: datetime, end: datetime) -> dict:
    new_items, updated_items = [], []
    for w in wikis:
        if w["created"] and start <= w["created"] < end:
            new_items.append(w["path"])
        elif w["updated"] and start <= w["updated"] < end:
            updated_items.append(w["path"])
    return {
        "new_this_week": len(new_items),
        "updated_this_week": len(updated_items),
        "new_items": new_items,
        "updated_items": updated_items,
    }


# ---------------------------------------------------------------- gaps

def collect_gaps(gap_path: Path) -> dict:
    gaps = load_gaps(str(gap_path)) if gap_path.exists() else []
    pending = [g for g in gaps if g.get("status") == "pending"]
    resolved = [g for g in gaps if g.get("status") == "resolved"]
    return {
        "knowledge_gaps_total": len(gaps),
        "knowledge_gaps_pending": len(pending),
        "knowledge_gaps_resolved": len(resolved),
        "gaps": gaps,
        "pending_gaps": pending,
    }


# ---------------------------------------------------------------- projects

def collect_project_status(vault_root: Path) -> list[dict]:
    projects = []
    for idx in sorted((vault_root / "30_Projects").glob("*/00_项目索引.md")):
        fm = _parse_frontmatter(idx)
        name = fm.get("project") or idx.parent.name
        status = fm.get("status")
        if status not in VALID_PROJECT_STATUS:
            status = str(status) if status else None
        progress = fm.get("progress")
        if progress is None or str(progress).strip() == "":
            progress = None
        else:
            try:
                progress = int(progress)
            except (TypeError, ValueError):
                progress = None
        projects.append({
            "name": name,
            "status": status,
            "phase": fm.get("phase"),
            "progress": progress,
            "next_step": fm.get("next_step"),
            "blockers": fm.get("blockers") or [],
            "updated": str(fm.get("updated") or ""),
            "index_path": idx.relative_to(vault_root).as_posix(),
        })
    return projects


# ---------------------------------------------------------------- stale risk

def collect_stale_risk(
    wikis: list[dict],
    stale_threshold_days: int,
    now: datetime | None = None,
) -> list[dict]:
    now = now or datetime.now()
    threshold = timedelta(days=int(stale_threshold_days))
    risks = []
    for w in wikis:
        factors = []
        if w["review_required"]:
            factors.append("review_required")
        if w["confidence"] == "low":
            factors.append("low_confidence")
        if w["updated"] and (now - w["updated"]) >= threshold:
            factors.append(f"not_updated_{int(stale_threshold_days)}d")
        if factors:
            risks.append({
                "path": w["path"],
                "title": w["title"],
                "status": w["status"],
                "updated": w["updated"].strftime("%Y-%m-%d") if w["updated"] else None,
                "review_required": w["review_required"],
                "confidence": w["confidence"],
                "risk_factors": factors,
            })
    return risks


# ---------------------------------------------------------------- health

def _run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:
        return -1, str(exc)


def collect_health(vault_root: Path) -> dict:
    """Reuse existing health check scripts (single source of truth)."""
    rag_dir = vault_root / "90_System" / "rag"
    result: dict[str, Any] = {}

    code, out = _run([sys.executable, str(rag_dir / "scripts" / "rag_health_check.py")])
    m = re.search(r"RAG_HEALTH_SUMMARY (ERROR=\d+ WARNING=\d+ PASS=\d+ INFO=\d+)", out)
    result["rag"] = {
        "ok": code == 0,
        "summary": m.group(1) if m else (out.strip()[:200] or "no output"),
    }

    code, out = _run([sys.executable, str(rag_dir / "scripts" / "wiki_health_check.py")])
    err = re.search(r"ERROR\s*=\s*(\d+)", out)
    warn = re.search(r"WARNING\s*=\s*(\d+)", out)
    result["wiki"] = {
        "ok": code == 0,
        "error": int(err.group(1)) if err else None,
        "warning": int(warn.group(1)) if warn else None,
    }

    ps1 = vault_root / "90_System" / "scripts" / "knowledge_os_check.ps1"
    code, out = _run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
        timeout=120,
    )
    summary = ""
    for line in out.splitlines():
        if "汇总" in line or ("ERROR" in line and "=" in line):
            summary = line.strip()
    result["architecture"] = {
        "ok": code == 0,
        "summary": summary or (out.strip()[:300] or "no output"),
    }

    errors = sum(1 for k in ("rag", "wiki", "architecture") if not result[k]["ok"])
    warnings = int(result["wiki"].get("warning") or 0)
    result["status"] = "error" if errors else ("warning" if warnings else "ok")
    result["errors"] = errors
    result["warnings"] = warnings
    return result


# ---------------------------------------------------------------- activity

def _read_activity_log(vault_root: Path) -> list[dict]:
    log = vault_root / "90_System" / "control_center" / "activity_log.jsonl"
    out = []
    if not log.exists():
        return out
    with open(log, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            atype = rec.get("type", "unknown")
            out.append({
                "timestamp": _norm_ts(rec.get("time")),
                "type": "review" if atype == "wiki_review" else atype,
                "source": "control_center",
                "object": rec.get("target", ""),
                "summary": rec.get("message", ""),
            })
    return out


def _read_inbox_log(vault_root: Path) -> list[dict]:
    log = vault_root / "90_System" / "任务记录" / "inbox_processor_log.md"
    out = []
    if not log.exists():
        return out
    current_ts: str | None = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
        if m:
            current_ts = m.group(1)
            continue
        if current_ts and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5 and cells[0] not in ("", "原始文件"):
                out.append({
                    "timestamp": current_ts,
                    "type": "inbox_processed",
                    "source": "inbox_processor",
                    "object": cells[0],
                    "summary": f"{cells[1]} {cells[2]} -> {cells[3]}",
                })
    return out


def _read_git_activity(vault_root: Path, since: datetime) -> list[dict]:
    cmd = [
        "git", "-C", str(vault_root), "log",
        f"--since={since.strftime('%Y-%m-%dT%H:%M:%S')}",
        "--date=iso", "--pretty=format:%H|%ad|%s",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        out = proc.stdout or ""
    except Exception:
        return []
    entries = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            entries.append({
                "timestamp": _norm_ts(parts[1]),
                "type": "git_change",
                "source": "git",
                "object": parts[0][:8],
                "summary": parts[2],
            })
    return entries


def collect_activity(
    vault_root: Path,
    since: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    since = since or (datetime.now() - timedelta(days=30))
    entries: list[dict] = []
    entries += _read_activity_log(vault_root)
    entries += _read_inbox_log(vault_root)
    entries += _read_git_activity(vault_root, since)

    wikis = collect_wiki_stats(vault_root)["wikis"]
    for w in wikis:
        if w["created"] and since <= w["created"]:
            entries.append({
                "timestamp": _norm_ts(w["created"]),
                "type": "wiki_created",
                "source": "frontmatter",
                "object": w["path"],
                "summary": f"新增 Wiki（{w['domain'] or '未分类'}）",
            })
        if w["updated"] and since <= w["updated"]:
            if not w["created"] or (w["updated"] - w["created"]) > timedelta(seconds=1):
                entries.append({
                    "timestamp": _norm_ts(w["updated"]),
                    "type": "wiki_updated",
                    "source": "frontmatter",
                    "object": w["path"],
                    "summary": f"更新 Wiki（review_required={str(w['review_required']).lower()}）",
                })

    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries[:limit]




# ---------------------------------------------------------------- review metrics (unified)

REVIEW_RECORDS_REL = "90_System/control_center/review_records.json"


def _short_review_reason(rec: dict | None) -> str:
    """Short human reason for a review candidate, derived only from stored data."""
    if not rec:
        return "尚未运行 LLM Judge"
    status = rec.get("judge_status")
    res = rec.get("result") or {}
    if status == "completed":
        if rec.get("classification") == "judge_passed":
            return "AI 已验证（consistent / sufficient）"
        parts = []
        consistency = res.get("consistency")
        if consistency == "conflict":
            parts.append("冲突")
        elif consistency == "partial":
            parts.append("部分一致")
        sufficiency = res.get("evidence_sufficiency")
        if sufficiency == "insufficient":
            parts.append("证据不足")
        elif sufficiency == "partial":
            parts.append("证据部分支持")
        if res.get("missing_information"):
            parts.append(f"缺失 {len(res['missing_information'])} 项")
        if res.get("unsupported_claims"):
            parts.append(f"来源不支持 {len(res['unsupported_claims'])} 项")
        if res.get("warnings"):
            parts.append(f"警告 {len(res['warnings'])} 项")
        return "；".join(parts) if parts else "AI 判断需人工复核"
    if status == "failed":
        return "AI Judge 失败（fail-closed，需人工审核）"
    if status == "blocked":
        return "无法进行 LLM Judge（" + str(rec.get("reason") or "缺少可读来源或目标") + "）"
    if status == "judging":
        return "AI Judge 运行中"
    return "尚未运行 LLM Judge"


def _pending_candidates(vault_root: Path, gap_path: Path) -> list[dict]:
    """Current review candidates: draft wikis + pending gaps (same set as CC build_actions)."""
    candidates = []
    for w in collect_wiki_stats(vault_root)["wikis"]:
        if w["status"] == "draft":
            candidates.append({
                "action_id": "wiki_review:" + w["path"],
                "title": w["title"],
                "type": "wiki_review",
            })
    for g in collect_gaps(gap_path).get("pending_gaps", []):
        q = str(g.get("question", ""))
        candidates.append({"action_id": "gap:" + q, "title": q, "type": "knowledge_gap"})
    return candidates


def _count_review(records: dict, candidates: list[dict]) -> dict:
    """Pure counting shared by Weekly Review and Control Center."""
    counts = {"judge_passed": 0, "needs_review": 0, "judge_failed": 0, "judging": 0, "not_judged": 0}
    items = []
    for c in candidates:
        rec = records.get(c["action_id"]) or {}
        status = rec.get("judge_status")
        cls = rec.get("classification")
        if status == "judging":
            counts["judging"] += 1
        elif cls == "judge_passed":
            counts["judge_passed"] += 1
        elif status == "failed" or cls == "judge_failed":
            counts["judge_failed"] += 1
        elif status == "blocked" or cls == "needs_review":
            counts["needs_review"] += 1
        else:
            counts["not_judged"] += 1
        res = rec.get("result") or {}
        items.append({
            "action_id": c["action_id"],
            "title": c["title"],
            "type": c["type"],
            "judge_status": status,
            "classification": cls,
            "recommendation": res.get("recommendation"),
            "reason": _short_review_reason(rec),
        })
    counts["total"] = counts["judge_passed"] + counts["needs_review"] + counts["judge_failed"] + counts["judging"]
    counts["candidates"] = counts["total"] + counts["not_judged"]
    counts["pending_human"] = counts["needs_review"] + counts["judge_failed"]
    counts["human_review_total"] = counts["pending_human"] + counts["not_judged"]
    counts["items"] = items
    return counts


def collect_review_metrics(
    vault_root: Path | None = None,
    review_records_path: Path | None = None,
    gap_path: Path | None = None,
    config_path: str | None = None,
) -> dict:
    """Unified Review metrics (single source for Weekly Review and Control Center).

    pending_human = needs_review + judge_failed (never draft count).
    not_judged is the explicit "unknown" bucket (preflight has not processed it).
    """
    vault_root = vault_root or VAULT_ROOT
    cfg = load_config(config_path or str(RAG_DIR / "config.yaml"))
    resolved = resolve_paths(cfg, vault_root)
    gap_path = gap_path or Path(resolved["paths"]["knowledge_gaps"])
    review_records_path = review_records_path or (vault_root / REVIEW_RECORDS_REL)
    records: dict = {}
    if Path(review_records_path).exists():
        try:
            data = json.loads(Path(review_records_path).read_text(encoding="utf-8"))
            records = data if isinstance(data, dict) else {}
        except Exception:
            records = {}
    return _count_review(records, _pending_candidates(vault_root, gap_path))


# ---------------------------------------------------------------- baseline / trend

def _has_prior_snapshot(period: str, review_root: Path) -> bool:
    """True if any other week's snapshot exists besides the given period."""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", period or "")
    if not m:
        return False
    week_label = f"W{int(m.group(2)):02d}"
    if not review_root.exists():
        return False
    for snap in review_root.rglob("snapshot.json"):
        if snap.parent.name == week_label:
            continue
        return True
    return False


def collect_baseline(period: str, review_root: Path | None = None) -> dict:
    review_root = review_root or REVIEW_ROOT
    is_baseline = not _has_prior_snapshot(period, review_root)
    return {
        "is_baseline_period": is_baseline,
        "note": "初始化基线，暂不作为正常周增长趋势使用" if is_baseline else None,
    }



# ---------------------------------------------------------------- historical trends (Phase C)

TREND_INDICATORS: dict[str, dict] = {
    "wiki_new": {"type": "flow", "health_when_up": "positive", "label": "New Wiki",
                 "extract": lambda s: _snap_val(s, ["growth_delta", "new_wiki"], None)},
    "wiki_updated": {"type": "flow", "health_when_up": "positive", "label": "Updated Wiki",
                     "extract": lambda s: _snap_val(s, ["growth_delta", "updated_wiki"], None)},
    "wiki_total": {"type": "stock", "health_when_up": "positive", "label": "Wiki Total",
                   "extract": lambda s: _snap_val(s, ["wiki_total"], None)},
    "review_pending": {"type": "stock", "health_when_up": "negative", "label": "Review Pending",
                       "extract": lambda s: _snap_val(s, ["review_pending"], None)},
    "judge_passed": {"type": "flow", "health_when_up": "positive", "label": "AI Passed",
                     "extract": lambda s: _snap_val(s, ["review", "judge_passed"], None)},
    "judge_failed": {"type": "flow", "health_when_up": "negative", "label": "Judge Failed",
                     "extract": lambda s: _snap_val(s, ["review", "judge_failed"], None)},
    "gaps_pending": {"type": "stock", "health_when_up": "negative", "label": "Gaps Pending",
                     "extract": lambda s: _snap_val(s, ["knowledge_gaps_pending"], None)},
    "gaps_resolved": {"type": "flow", "health_when_up": "positive", "label": "Gaps Resolved",
                      "extract": lambda s: _snap_gaps_resolved(s)},
    "stale": {"type": "stock", "health_when_up": "negative", "label": "Stale",
              "extract": lambda s: _snap_stale_count(s)},
    "projects_active": {"type": "stock", "health_when_up": "neutral", "label": "Active Projects",
                        "extract": lambda s: _snap_projects_count(s, "active")},
    "projects_planning": {"type": "stock", "health_when_up": "neutral", "label": "Planning Projects",
                          "extract": lambda s: _snap_projects_count(s, "planning")},
    "projects_blocked": {"type": "stock", "health_when_up": "negative", "label": "Blocked Projects",
                         "extract": lambda s: _snap_projects_count(s, "blocked")},
    "health_score": {"type": "stock", "health_when_up": "positive", "label": "Health Score",
                     "extract": lambda s: _snap_val(s, ["health_score"], None)},
}


def _snap_val(snapshot: dict, path: list[str], default=None):
    node = snapshot
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
        if node is None:
            return default
    return node if node is not None else default


def _snap_stale_count(snapshot: dict) -> int:
    return len(_snap_val(snapshot, ["stale_items"], []) or [])


def _snap_projects_count(snapshot: dict, status: str) -> int:
    projects = _snap_val(snapshot, ["projects"], []) or []
    return sum(1 for pr in projects if pr.get("status") == status)


def _snap_gaps_resolved(snapshot: dict):
    total = _snap_val(snapshot, ["knowledge_gaps_total"], None)
    pending = _snap_val(snapshot, ["knowledge_gaps_pending"], None)
    if total is None or pending is None:
        return None
    return total - pending


def _snap_is_baseline(snapshot: dict) -> bool:
    return bool((snapshot.get("baseline") or {}).get("is_baseline_period", False))


def _iso_week_key(period: str) -> tuple[int, int]:
    m = re.match(r"^(\d{4})-W(\d{1,2})$", str(period or ""))
    if not m:
        return (9999, 0)
    return (int(m.group(1)), int(m.group(2)))


def collect_weekly_snapshots(review_root: Path | None = None) -> list[dict]:
    """Read all weekly snapshot.json under the review root (deterministic).

    Sorted by ISO week (numeric, not string). Corrupt / temp files are ignored.
    Never modifies history. Missing fields are tolerated by callers.
    """
    review_root = review_root or REVIEW_ROOT
    out = []
    if not review_root.exists():
        return out
    for snap in review_root.rglob("snapshot.json"):
        parts = [part.lower() for part in snap.parts]
        if any(part.startswith(".") or ".tmp" in part for part in parts):
            continue  # ignore temp / hidden
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        period = str(data.get("period") or "")
        if not re.match(r"^\d{4}-W\d{1,2}$", period):
            continue
        out.append({"period": period, "snapshot": data, "path": str(snap)})
    out.sort(key=lambda s: _iso_week_key(s["period"]))
    return out


def compute_wow(name: str, spec: dict, current_period: str | None, current_value,
                prev_period: str | None, prev_value, current_baseline: bool, prev_baseline: bool) -> dict:
    """Week-over-week for one indicator. Never fabricates a previous value."""
    base = {
        "metric": name, "label": spec["label"], "type": spec["type"],
        "current": {"period": current_period, "value": current_value},
        "previous": None, "delta": None, "delta_percent": None,
        "direction": "neutral", "health_effect": "neutral",
        "available": False, "reason": None,
    }
    if current_baseline:
        base["reason"] = "baseline_current"
        return base
    if prev_period is None:
        base["reason"] = "no_previous"
        return base
    if prev_baseline:
        base["reason"] = "baseline_boundary"
        return base
    if current_value is None or prev_value is None:
        base["reason"] = "missing_data"
        return base
    base["previous"] = {"period": prev_period, "value": prev_value}
    delta = current_value - prev_value
    base["delta"] = delta
    if prev_value != 0:
        base["delta_percent"] = round((delta / prev_value) * 100, 1)
    base["direction"] = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    base["health_effect"] = _health_effect(spec["health_when_up"], base["direction"])
    base["available"] = True
    return base


def _health_effect(up_meaning: str, direction: str) -> str:
    if direction == "flat" or up_meaning == "neutral":
        return "neutral"
    if direction == "up":
        return up_meaning
    return "positive" if up_meaning == "negative" else "negative"


def build_weekly_trends(snapshots: list[dict], weeks: int = 4) -> dict:
    """Centralized deterministic trend aggregator.

    WoW compares a period to its immediate predecessor only when neither is a
    baseline period (baseline boundary -> not available). The `weeks` window
    (default 4) uses the current period + up to `weeks-1` preceding NON-baseline
    periods (never zero-fills; shorter when data is insufficient).
    """
    ordered = sorted(snapshots, key=lambda s: _iso_week_key(s["period"]))
    latest = ordered[-1] if ordered else None
    wow: dict[str, dict] = {}
    four_week: dict[str, dict] = {}
    wow_by_period: dict[str, dict] = {}

    for name, spec in TREND_INDICATORS.items():
        cur_val = spec["extract"](latest["snapshot"]) if latest else None
        prev = ordered[-2] if len(ordered) >= 2 else None
        prev_val = spec["extract"](prev["snapshot"]) if prev else None
        wow[name] = compute_wow(
            name, spec,
            latest["period"] if latest else None, cur_val,
            prev["period"] if prev else None, prev_val,
            _snap_is_baseline(latest["snapshot"]) if latest else False,
            _snap_is_baseline(prev["snapshot"]) if prev else False,
        )

        points = []
        for s in reversed(ordered):
            if len(points) >= weeks:
                break
            if s["period"] == (latest["period"] if latest else None):
                points.append({"period": s["period"], "value": spec["extract"](s["snapshot"]),
                               "baseline": _snap_is_baseline(s["snapshot"])})
            elif not _snap_is_baseline(s["snapshot"]):
                points.append({"period": s["period"], "value": spec["extract"](s["snapshot"]),
                               "baseline": False})
        points.reverse()
        four_week[name] = {"available": len(points) >= 2,
                           "periods": [p["period"] for p in points], "points": points}

        wow_by_period[name] = {}
        for i, s in enumerate(ordered):
            prev_s = ordered[i - 1] if i > 0 else None
            wow_by_period[name][s["period"]] = compute_wow(
                name, spec, s["period"], spec["extract"](s["snapshot"]),
                prev_s["period"] if prev_s else None, spec["extract"](prev_s["snapshot"]) if prev_s else None,
                _snap_is_baseline(s["snapshot"]),
                _snap_is_baseline(prev_s["snapshot"]) if prev_s else False,
            )

    return {
        "wow": wow,
        "four_week": four_week,
        "wow_by_period": wow_by_period,
        "availability": {
            "has_history": len(ordered) >= 2,
            "baseline": _snap_is_baseline(latest["snapshot"]) if latest else False,
            "period_count": len(ordered),
            "comparable_periods": sum(1 for s in ordered if not _snap_is_baseline(s["snapshot"])),
        },
    }

# ---------------------------------------------------------------- top level

def collect_rag_evaluation(vault_root: Path | None = None) -> dict | None:
    """Read the latest RAG Evaluation summary (deterministic, read-only).

    Returns None when no evaluation has run yet, so the weekly review stays
    intact. Never modifies anything; numbers come from the real benchmark run.
    """
    vault_root = vault_root or VAULT_ROOT
    latest = vault_root / "40_Outputs" / "RAG Evaluation" / "latest.json"
    if not latest.exists():
        return None
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    m = data.get("metrics") or {}
    # RAG Evaluation 派生的知识缺口（gaps.yaml 注册表）
    gaps = {"open": None, "resolved": None}
    gap_registry = vault_root / "90_System" / "rag" / "evaluation" / "gaps.yaml"
    if gap_registry.exists():
        try:
            import yaml
            _gaps = yaml.safe_load(gap_registry.read_text(encoding="utf-8")) or []
            if isinstance(_gaps, list):
                gaps = {
                    "open": sum(1 for g in _gaps if g.get("status") == "open"),
                    "resolved": sum(1 for g in _gaps if g.get("status") == "resolved"),
                    "open_p0": sum(1 for g in _gaps if g.get("status") == "open" and g.get("priority") == "P0"),
                    "open_p1": sum(1 for g in _gaps if g.get("status") == "open" and g.get("priority") == "P1"),
                }
        except Exception:
            pass
    # 最近一次 before/after Diff（latest_diff.json）
    diff = None
    latest_diff = vault_root / "40_Outputs" / "RAG Evaluation" / "latest_diff.json"
    if latest_diff.exists():
        try:
            _d = json.loads(latest_diff.read_text(encoding="utf-8"))
            if isinstance(_d, dict):
                diff = {
                    "before_run": _d.get("before_run"),
                    "after_run": _d.get("after_run"),
                    "recovered": (_d.get("counts") or {}).get("recovered"),
                    "regressed": (_d.get("counts") or {}).get("regressed"),
                    "query_recovery_rate": _d.get("query_recovery_rate"),
                    "regression_classes": _d.get("regression_classes"),
                }
        except Exception:
            diff = None
    # Golden Set 人工标注统计
    golden = None
    golden_path = vault_root / "90_System" / "rag" / "evaluation" / "golden.yaml"
    if golden_path.exists():
        try:
            sys.path.insert(0, str(vault_root / "90_System" / "rag"))
            from rag_engine.golden_set import golden_stats, load_golden
            _g = load_golden(golden_path)
            golden = {"entries": len(_g.get("entries") or []), **golden_stats(_g.get("entries") or [])}
        except Exception:
            golden = None
    # Judge Variance（latest_judge_variance.json）
    judge_var = None
    jv_path = vault_root / "40_Outputs" / "RAG Evaluation" / "latest_judge_variance.json"
    if jv_path.exists():
        try:
            _j = json.loads(jv_path.read_text(encoding="utf-8"))
            if isinstance(_j, dict) and _j.get("stats"):
                judge_var = {
                    "tested_queries": (_j["stats"] or {}).get("tested_queries"),
                    "stable_rate": (_j["stats"] or {}).get("stable_rate"),
                    "flip_rate": (_j["stats"] or {}).get("flip_rate"),
                    "sample_too_small": (_j["stats"] or {}).get("sample_too_small"),
                }
        except Exception:
            judge_var = None
    # Source Acquisition：已验证来源数 + P0/P1 缺来源 gap 数
    sources = {"verified": None, "p0_p1_missing": None}
    src_path = vault_root / "90_System" / "rag" / "evaluation" / "source_acquisition.yaml"
    if src_path.exists():
        try:
            import yaml as _y
            _src = _y.safe_load(src_path.read_text(encoding="utf-8")) or {}
            _all = _src.get("sources") or []
            sources["verified"] = sum(1 for s in _all if s.get("source_status") == "verified")
            _gaps2 = yaml.safe_load(gap_registry.read_text(encoding="utf-8")) or [] if gap_registry.exists() else []
            _by_prio = {g.get("id"): g.get("priority") for g in _gaps2 if isinstance(g, dict)}
            _status = {}
            for s in _all:
                _status[s.get("gap_id")] = s.get("source_status")
            sources["p0_p1_missing"] = [
                gid for gid, prio in _by_prio.items()
                if prio in ("P0", "P1") and _status.get(gid) in (None, "missing")
            ]
        except Exception:
            sources = {"verified": None, "p0_p1_missing": None}
    # Wiki Compilation 状态（wiki_compilation.yaml）
    wiki_compilation = None
    comp_path = vault_root / "90_System" / "rag" / "evaluation" / "wiki_compilation.yaml"
    if comp_path.exists():
        try:
            import yaml as _yc
            _c = _yc.safe_load(comp_path.read_text(encoding="utf-8")) or {}
            tasks = [t for g in (_c.get("gaps") or []) for t in (g.get("wiki_tasks") or [])]
            rows = [r for t in tasks for r in (t.get("coverage_matrix") or [])]
            wiki_compilation = {
                "tasks": len(tasks),
                "recovered_queries": sum(1 for r in rows if (r.get("after") or {}).get("change") == "RECOVERED"),
                "still_failed": sum(1 for r in rows if (r.get("after") or {}).get("final_status") == "knowledge_missing"),
            }
        except Exception:
            wiki_compilation = None
    # Evaluation Baseline（baseline.json）+ 当前 run 的回归检查
    baseline_info = None
    baseline_path = vault_root / "40_Outputs" / "RAG Evaluation" / "baseline.json"
    if baseline_path.exists():
        try:
            sys.path.insert(0, str(vault_root / "90_System" / "rag"))
            from rag_engine.evaluation_baseline import load_baseline, regression_check
            _b = load_baseline(baseline_path)
            if _b:
                _cur = {"run_id": data.get("run_id"), "coverage": (m.get("overall") or {}).get("answer_coverage")}
                _chk = regression_check(_cur, _b)
                baseline_info = {
                    "baseline_id": _b.get("baseline_id"),
                    "baseline_run": _b.get("run_id"),
                    "coverage": _b.get("coverage"),
                    "status": _b.get("status"),
                    "established_at": _b.get("established_at"),
                    "current_run": data.get("run_id"),
                    "current_coverage": _cur.get("coverage"),
                    "delta_pp": _chk.get("delta_pp"),
                    "check_status": _chk.get("status"),
                }
        except Exception:
            baseline_info = None
    # Evaluation Governance 状态（evaluation_state.json）
    governance = None
    gov_path = vault_root / "40_Outputs" / "RAG Evaluation" / "evaluation_state.json"
    if gov_path.exists():
        try:
            sys.path.insert(0, str(vault_root / "90_System" / "rag"))
            from rag_engine.evaluation_governance import load_state
            _g = load_state(gov_path)
            governance = {
                "status": _g.get("status"),
                "required": _g.get("status") in ("required", "failed"),
                "reasons": _g.get("reasons") or [],
                "run_id": _g.get("run_id"),
                "baseline_id": _g.get("baseline_id"),
                "last_check": (_g.get("check") or {}).get("status"),
                "error": _g.get("error"),
            }
        except Exception:
            governance = None
    ov = m.get("overall") or {}
    wk = m.get("wiki") or {}
    rw = m.get("raw") or {}
    ev = m.get("evidence") or {}
    lt = m.get("latency") or {}
    fc = m.get("fail_closed") or {}
    gs = m.get("gap_signals") or {}
    return {
        "run_id": data.get("run_id"),
        "generated_at": data.get("generated_at"),
        "query_count": data.get("query_count"),
        "mode": data.get("mode"),
        "report_path": data.get("report_path"),
        "gaps": gaps,
        "diff": diff,
        "golden": golden,
        "judge_variance": judge_var,
        "sources": sources,
        "wiki_compilation": wiki_compilation,
        "baseline": baseline_info,
        "governance": governance,
        "metrics": {
            "answer_coverage": ov.get("answer_coverage"),
            "knowledge_missing_rate": ov.get("knowledge_missing_rate"),
            "system_error": ov.get("system_error"),
            "wiki_hit_rate": wk.get("wiki_hit_rate"),
            "wiki_fallback_rate": wk.get("wiki_fallback_rate"),
            "wiki_fallback_recovery_rate": wk.get("wiki_fallback_recovery_rate"),
            "raw_answer_rate": rw.get("raw_answer_rate"),
            "raw_evidence_sufficient_rate": rw.get("raw_evidence_sufficient_rate"),
            "avg_window_count": ev.get("avg_window_count"),
            "p50_total_ms": (lt.get("total_ms") or {}).get("p50"),
            "p95_total_ms": (lt.get("total_ms") or {}).get("p95"),
            "top_failures": fc.get("top_failures") or [],
            "gap_signals": {
                "likely_knowledge_gap": gs.get("likely_knowledge_gap"),
                "evidence_gap": gs.get("evidence_gap"),
                "retrieval_gap": gs.get("retrieval_gap"),
            },
        },
    }


def collect_metrics(
    period: str | None = None,
    vault_root: Path | None = None,
    config_path: str | None = None,
    now: datetime | None = None,
) -> dict:
    vault_root = vault_root or VAULT_ROOT
    config_path = config_path or str(RAG_DIR / "config.yaml")
    cfg = load_config(config_path)
    now = now or datetime.now()
    period = period or current_iso_week(now)
    start, end = iso_week_range(period)

    wiki = collect_wiki_stats(vault_root)
    growth = collect_growth(wiki["wikis"], start, end)
    resolved_cfg = resolve_paths(cfg, vault_root)
    gap_path = Path(resolved_cfg["paths"]["knowledge_gaps"])
    gaps = collect_gaps(gap_path)
    projects = collect_project_status(vault_root)
    wr = cfg.get("weekly_review") or {}
    stale_threshold = int(wr.get("stale_threshold_days", 90) or 90)
    stale = collect_stale_risk(wiki["wikis"], stale_threshold, now)
    health = collect_health(vault_root)
    activity = collect_activity(vault_root, since=start, limit=200)

    return {
        "period": period,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wiki": wiki,
        "growth": growth,
        "gaps": gaps,
        "projects": projects,
        "stale_risk": stale,
        "health": health,
        "review": collect_review_metrics(vault_root, config_path=config_path),
        "baseline": collect_baseline(period),
        "activity": activity,
        "rag_evaluation": collect_rag_evaluation(vault_root),
        "meta": {
            "config": str(config_path),
            "stale_threshold_days": stale_threshold,
            "generator": "metrics.collect_metrics",
        },
    }
