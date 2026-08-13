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


# ---------------------------------------------------------------- top level

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
        "activity": activity,
        "meta": {
            "config": str(config_path),
            "stale_threshold_days": stale_threshold,
            "generator": "metrics.collect_metrics",
        },
    }
