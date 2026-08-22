"""Knowledge OS Control Center service layer.

Builds the human-in-the-loop Action list from real Knowledge OS state (no
second data store), executes decisions through the existing Knowledge OS
functions, and appends decisions to an audit log.

Actions are derived views of:
  - 20_Wiki frontmatter status (draft wikis -> wiki_review actions)
  - knowledge_gaps.yaml pending entries -> gap actions
  - health warnings

Execution reuses existing logic: rag_engine.wiki_review.set_status and
rag_engine.gaps.resolve_gap. The Control Center never edits Markdown or
Vector DB directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parent
SYSTEM_DIR = CTRL_DIR.parent
VAULT_ROOT = SYSTEM_DIR.parent
RAG_DIR = SYSTEM_DIR / "rag"
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.gaps import load_gaps, resolve_gap as _resolve_gap
from rag_engine.ingest import chunk_text, parse_file
from rag_engine.evidence_window import merge_chunk_sequence
from rag_engine import judge as rag_judge
from rag_engine.wiki import _slug  # noqa: F401 (re-exported for UI use)
from rag_engine.wiki_review import set_status
from rag_engine.wiki import read_frontmatter

REVIEW_DIR = RAG_DIR / "scripts" / "review"
if str(REVIEW_DIR) not in sys.path:
    sys.path.insert(0, str(REVIEW_DIR))
import metrics as review_metrics  # noqa: E402
import health as health_engine  # noqa: E402
import insight as weekly_insight  # noqa: E402

REVIEW_ROOT = VAULT_ROOT / "40_Outputs" / "reviews" / "每周复盘"
SYNC_STATE = RAG_DIR / "database" / "sync_state.json"
EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
GAP_REGISTRY = RAG_DIR / "evaluation" / "gaps.yaml"
GOVERNANCE_STATE = EVAL_ROOT / "evaluation_state.json"  # 兼容常量（推荐用 _governance_state_path() 以跟随 EVAL_ROOT 补丁）
SOURCE_REGISTRY = RAG_DIR / "evaluation" / "source_acquisition.yaml"
SOURCE_REGISTRY_HEADER = """# Knowledge OS Source Acquisition Registry
#
# 每个 P0/P1（及部分 P2）Knowledge Gap 关联的 Source Acquisition Task。
# 原则：不假装 URL 已验证。source_status: missing | candidate | acquired | verified
#   - candidate：官方/高可信来源 URL 已检索登记，但内容未人工核验、未本地获取
#   - acquired：本地已获取（10_Sources / 00_Inbox）
#   - verified：人工核验内容且可用于 Stable Wiki（本阶段不自动 verified）
# source_type 优先级：official_docs > datasheet > reference_manual > project_docs >
#                     trusted_tutorial > unknown
# sufficiency 只记录 high/medium/low/unknown，不做综合分数。

"""
GOLDEN_PATH = RAG_DIR / "evaluation" / "golden.yaml"

ACTIVITY_LOG = CTRL_DIR / "activity_log.jsonl"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_fm(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
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


def _body_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[end + 4:].lstrip("\n")
    return text


def list_wikis() -> list[dict]:
    out = []
    for p in sorted((VAULT_ROOT / "20_Wiki").rglob("*.md")):
        rel = p.relative_to(VAULT_ROOT).as_posix()
        fm = _parse_fm(p)
        src = fm.get("source") or []
        if not isinstance(src, list):
            src = [src]
        out.append({
            "path": rel,
            "title": fm.get("title") or p.stem,
            "domain": fm.get("domain", ""),
            "status": fm.get("status", "unknown"),
            "sources": [str(s) for s in src if str(s).strip()],
            "created": str(fm.get("created") or ""),
            "updated": str(fm.get("updated") or ""),
            "len": len(_body_of(p).strip()),
        })
    return out


def _gap_path() -> Path:
    cfg = resolve_paths(load_config(str(RAG_DIR / "config.yaml")), VAULT_ROOT)
    return Path(cfg["paths"].get("knowledge_gaps", "")) or RAG_DIR / "tests" / "knowledge_gaps.yaml"


def list_gaps() -> list[dict]:
    return load_gaps(str(_gap_path()))


def list_sources() -> list[dict]:
    wikis = list_wikis()
    files = []
    for p in sorted((VAULT_ROOT / "00_Inbox" / "待处理文件" / "个人笔记").rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".pdf", ".md", ".txt"):
            continue
        rel = p.relative_to(VAULT_ROOT).as_posix()
        linked = [w["path"] for w in wikis if rel in w["sources"]]
        files.append({
            "name": p.name,
            "type": p.suffix.lower().lstrip("."),
            "path": rel,
            "size_kb": round(p.stat().st_size / 1024, 1),
            "linked_wikis": linked,
            "processed": "wiki" if linked else "raw",
        })
    return files


def build_actions() -> list[dict]:
    actions = []
    for w in list_wikis():
        if w["status"] == "draft":
            actions.append({
                "id": "wiki_review:" + w["path"],
                "type": "wiki_review",
                "status": "pending",
                "created_at": w["created"],
                "source": w["sources"],
                "target": {"wiki": w["path"], "title": w["title"], "domain": w["domain"]},
                "reason": "新 Wiki 等待人工审核",
                "evidence": {"source": w["sources"], "content_length": w["len"]},
                "ai_recommendation": "approve" if w["len"] >= 300 else "review",
                "available_actions": ["approve", "reject", "ignore"],
                "execution_result": None,
            })
    for g in list_gaps():
        if g.get("status") == "pending":
            actions.append({
                "id": "gap:" + str(g.get("question", "")),
                "type": "knowledge_gap",
                "status": "pending",
                "created_at": g.get("detected_at", ""),
                "source": g.get("related_sources", []),
                "target": {"question": g.get("question", ""), "type": g.get("type", ""), "topic": g.get("topic", "")},
                "reason": "知识库证据不足记录的知识缺口",
                "evidence": {"related_sources": g.get("related_sources", []), "related_wiki": g.get("related_wiki", [])},
                "ai_recommendation": g.get("suggested_action") or "create_wiki",
                "available_actions": ["resolve", "ignore", "reprocess"],
                "execution_result": None,
            })
    records = _load_review_records()
    for a in actions:
        rec = records.get(a["id"]) or {}
        res = rec.get("result") or {}
        a["judge_status"] = rec.get("judge_status")
        a["classification"] = rec.get("classification")
        a["judge_recommendation"] = res.get("recommendation")
        a["judge_confidence"] = res.get("confidence")
        a["judge_consistency"] = res.get("consistency")
        a["judge_evidence_sufficiency"] = res.get("evidence_sufficiency")
        a["review_reason"] = _short_review_reason(rec)
    return actions


def batch_approve(action_ids: list, actor: str = "user", confirm: bool = False) -> dict:
    """Approve multiple wiki_review actions with explicit user confirmation.

    Each action executes independently, logs separately, and is idempotent;
    one failure does not mark others as success. No-op without confirm=True.
    """
    if not confirm:
        return {"ok": False, "message": "需要二次确认（confirm=true 才执行）", "results": []}
    if not isinstance(action_ids, list) or not action_ids or len(action_ids) > 50:
        return {"ok": False, "message": "ids 必须是非空列表（最多 50 项）", "results": []}
    results = []
    for aid in action_ids:
        r = execute_action(aid, "approve", actor=actor)
        results.append({
            "action_id": aid,
            "ok": r["ok"],
            "result": r["result"],
            "message": r["message"],
        })
    ok_count = sum(1 for r in results if r["ok"])
    return {
        "ok": True,
        "message": f"批量完成 {len(results)} 项：成功 {ok_count}，失败 {len(results) - ok_count}",
        "results": results,
    }


def _append_log(entry: dict) -> None:
    entry["time"] = _now()
    with open(ACTIVITY_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _activity_records() -> list[dict]:
    if not ACTIVITY_LOG.exists():
        return []
    recs = []
    with open(ACTIVITY_LOG, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    return recs


def execute_action(action_id: str, decision: str, actor: str = "user") -> dict:
    decision = decision.lower()
    if action_id.startswith("wiki_review:"):
        rel = action_id[len("wiki_review:"):]
        path = VAULT_ROOT / rel
        if not path.exists():
            return {"ok": False, "result": "error", "message": f"Wiki 不存在: {rel}"}
        current = read_frontmatter(path).get("status", "unknown")
        target = rel
        if decision == "approve":
            if current in ("reviewed", "stable"):
                return {"ok": True, "result": "already_done", "message": f"已是 {current}，无需重复操作"}
            new_status = set_status(path, "reviewed")
            _append_log({"action_id": action_id, "type": "wiki_review", "target": target, "actor": actor,
                         "ai_recommendation": "approve", "user_decision": "approve", "result": "success",
                         "message": f"{target} -> {new_status}"})
            # 治理门禁：Wiki 批准 -> evaluation_required（批量批准合并为一次）
            _mark_governance_required("wiki_approved", {"wiki_approved": 1})
            return {"ok": True, "result": "success", "message": f"{target} -> {new_status}"}
        if decision in ("reject", "ignore"):
            _append_log({"action_id": action_id, "type": "wiki_review", "target": target, "actor": actor,
                         "ai_recommendation": "approve", "user_decision": decision, "result": "success",
                         "message": f"已记录 {decision}，状态保持 {current}"})
            return {"ok": True, "result": "success", "message": f"已记录 {decision}（状态保持 {current}）"}
        return {"ok": False, "result": "error", "message": f"未知决定: {decision}"}

    if action_id.startswith("gap:"):
        question = action_id[len("gap:"):]
        gap_path = _gap_path()
        gaps = load_gaps(str(gap_path))
        cur = next((g for g in gaps if g.get("question") == question), None)
        if cur is None:
            return {"ok": False, "result": "error", "message": f"Gap 不存在: {question}"}
        if decision == "resolve":
            if cur.get("status") == "resolved":
                return {"ok": True, "result": "already_done", "message": "该 Gap 已 resolved，无需重复操作"}
            _resolve_gap(question, str(gap_path), resolved_by=actor, resolved_sources=cur.get("related_sources", []))
            _append_log({"action_id": action_id, "type": "knowledge_gap", "target": question, "actor": actor,
                         "ai_recommendation": cur.get("suggested_action") or "create_wiki", "user_decision": "resolve",
                         "result": "success", "message": "Gap 已 resolve"})
            return {"ok": True, "result": "success", "message": "Gap 已 resolve"}
        if decision in ("ignore", "reprocess"):
            _append_log({"action_id": action_id, "type": "knowledge_gap", "target": question, "actor": actor,
                         "ai_recommendation": cur.get("suggested_action") or "create_wiki", "user_decision": decision,
                         "result": "success", "message": f"已记录 {decision}"})
            return {"ok": True, "result": "success", "message": f"已记录 {decision}"}
        return {"ok": False, "result": "error", "message": f"未知决定: {decision}"}

    return {"ok": False, "result": "error", "message": f"未知 action: {action_id}"}


def _run_py(script_rel: str, extra: list[str] | None = None) -> tuple[int, str]:
    cmd = [sys.executable, str(RAG_DIR / script_rel)] + (extra or [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:
        return -1, str(exc)


def health() -> dict:
    result = {"rag": None, "wiki": None, "architecture": None}

    code, out = _run_py("scripts/rag_health_check.py")
    m = re.search(r"RAG_HEALTH_SUMMARY (ERROR=\d+ WARNING=\d+ PASS=\d+ INFO=\d+)", out)
    result["rag"] = {"ok": code == 0, "summary": m.group(1) if m else out.strip()[:200]}

    code, out = _run_py("scripts/wiki_health_check.py")
    err = re.search(r"ERROR\s*=\s*(\d+)", out)
    warn = re.search(r"WARNING\s*=\s*(\d+)", out)
    result["wiki"] = {
        "ok": code == 0,
        "error": int(err.group(1)) if err else None,
        "warning": int(warn.group(1)) if warn else None,
    }

    ps1 = SYSTEM_DIR / "scripts" / "knowledge_os_check.ps1"
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        summary = ""
        for line in (proc.stdout or "").splitlines():
            if "汇总" in line or "ERROR" in line and "=" in line:
                summary = line.strip()
        result["architecture"] = {"ok": proc.returncode == 0, "summary": summary or proc.stdout.strip()[:300]}
    except Exception as exc:
        result["architecture"] = {"ok": False, "summary": str(exc)}

    return result


def dashboard() -> dict:
    wikis = list_wikis()
    gaps = list_gaps()
    actions = build_actions()
    status_count = {}
    for w in wikis:
        status_count[w["status"]] = status_count.get(w["status"], 0) + 1
    inbox = [p for p in (VAULT_ROOT / "00_Inbox" / "待处理文件").rglob("*")
             if p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt")]
    return {
        "wiki_total": len(wikis),
        "wiki_status": status_count,
        "gaps_pending": sum(1 for g in gaps if g.get("status") == "pending"),
        "actions_pending": sum(1 for a in actions if a["status"] == "pending"),
        "actions_by_type": {
            t: sum(1 for a in actions if a["type"] == t) for t in ("wiki_review", "knowledge_gap")
        },
        "review_counts": review_counts(actions),
        "last_preflight": last_preflight_run(),
        "preflight_stale": _preflight_stale(),
        "preflight_staleness_hours": int(_preflight_cfg().get("staleness_hours", 24)),
        "inbox_files": len(inbox),
        "recent_activity": activity_timeline(limit=10),
    }


# ---------------------------------------------------------------- weekly review

def _safe_rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _extract_review_summary(md_path: Path) -> str | None:
    """Extract the '## 1. 本周摘要' text from a weekly-review.md for the API."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = re.search(r"## 1\. 本周摘要\n+(.*?)(?=\n## |\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else None


def _iter_reviews():
    if not REVIEW_ROOT.exists():
        return
    for year_dir in sorted(REVIEW_ROOT.iterdir()):
        if not year_dir.is_dir() or not re.match(r"^\d{4}$", year_dir.name):
            continue
        for week_dir in sorted(year_dir.iterdir()):
            if not week_dir.is_dir() or not re.match(r"^W\d{1,2}$", week_dir.name):
                continue
            snap = {}
            snap_path = week_dir / "snapshot.json"
            if snap_path.exists():
                try:
                    snap = json.loads(snap_path.read_text(encoding="utf-8"))
                except Exception:
                    snap = {}
            md = week_dir / "weekly-review.md"
            yield {
                "period": snap.get("period") or f"{year_dir.name}-{week_dir.name}",
                "year": year_dir.name,
                "week": week_dir.name,
                "report_path": _safe_rel(md, VAULT_ROOT) if md.exists() else None,
                "snapshot_path": _safe_rel(snap_path, VAULT_ROOT) if snap_path.exists() else None,
                "generated_at": snap.get("generated_at"),
                "wiki_total": snap.get("wiki_total"),
                "wiki_draft": snap.get("wiki_draft"),
                "wiki_reviewed": snap.get("wiki_reviewed"),
                "wiki_stable": snap.get("wiki_stable"),
                "knowledge_gaps_pending": snap.get("knowledge_gaps_pending"),
                "stale_count": len(snap.get("stale_items", [])),
                "health_status": (snap.get("health") or {}).get("status"),
                "review": snap.get("review"),
                "review_pending": snap.get("review_pending"),
                "baseline": snap.get("baseline"),
                "snapshot_health": snap.get("health") or {},
                "summary": _extract_review_summary(md) if md.exists() else None,
            }


def _insight_model_label(cfg: dict) -> str:
    llm = cfg.get("llm") or {}
    model = llm.get("model")
    if isinstance(model, dict):
        model = model.get("name")
    return f"{llm.get('provider', 'unknown')}:{model or 'unknown'}"


def generate_weekly_insight(period: str | None = None) -> dict:
    """Generate + cache AI Weekly Insight for the latest period (fail-closed).

    Cached: same period + prompt_version + model -> reuse, no LLM call.
    """
    wr = weekly_review_list()
    latest = wr.get("latest") or {}
    period = period or latest.get("period") or review_metrics.current_iso_week()
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    model = _insight_model_label(cfg)
    cached = weekly_insight.load_cached_insight(period, REVIEW_ROOT, model)
    if cached:
        return {"ok": True, "cached": True, "period": period, **cached}
    resolved = resolve_paths(cfg, VAULT_ROOT)
    gap_path = Path(resolved["paths"]["knowledge_gaps"])
    wiki = review_metrics.collect_wiki_stats(VAULT_ROOT)
    start, _end = review_metrics.iso_week_range(period)
    growth = review_metrics.collect_growth(wiki["wikis"], start, _end)
    gaps = review_metrics.collect_gaps(gap_path)
    projects = review_metrics.collect_project_status(VAULT_ROOT)
    wr_cfg = cfg.get("weekly_review") or {}
    stale = review_metrics.collect_stale_risk(wiki["wikis"], int(wr_cfg.get("stale_threshold_days", 90) or 90))
    review = review_metrics.collect_review_metrics(VAULT_ROOT, gap_path=gap_path, config_path=str(RAG_DIR / "config.yaml"))
    health_snap = (latest.get("snapshot_health") or {})
    metrics_like = {"period": period, "wiki": wiki, "growth": growth, "gaps": gaps,
                    "projects": projects, "stale_risk": stale, "review": review, "health": health_snap}
    health_result = health_engine.calculate_health(metrics_like)
    attention = health_engine.build_attention(metrics_like)
    trends = review_metrics.build_weekly_trends(review_metrics.collect_weekly_snapshots())
    result = weekly_insight.generate_insight(metrics_like, health_result, trends, attention, cfg, model_label=model)
    path = weekly_insight.save_insight(period, result, REVIEW_ROOT)
    return {"ok": True, "cached": False, "period": period, "path": str(path), **result}


def weekly_review_automation() -> dict:
    """Real Windows Task Scheduler state for the Weekly Review task.

    Reads the actual scheduled task (never fabricates health). On any failure
    the status is 'unknown' so we never pretend automation is healthy.
    """
    ps = (
        "$t = Get-ScheduledTask -TaskName 'Knowledge OS Weekly Review' -ErrorAction SilentlyContinue; "
        "$i = Get-ScheduledTaskInfo -TaskName 'Knowledge OS Weekly Review' -ErrorAction SilentlyContinue; "
        "if ($t -and $i) { [pscustomobject]@{ state=[string]$t.State; next=[string]$i.NextRunTime; "
        "last=[string]$i.LastRunTime; result=[int]$i.LastTaskResult } | ConvertTo-Json -Compress } else { 'null' }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        out = (proc.stdout or "").strip()
        if not out or out == "null":
            return {"status": "unknown", "state": "unknown", "last_run": None,
                    "last_success": None, "next_run": None, "last_result": None}
        data = json.loads(out.splitlines()[-1])
        state = str(data.get("state") or "").lower()
        last = str(data.get("last") or "")
        next_run = str(data.get("next") or "")
        try:
            result = int(data.get("result") or 0)
        except (TypeError, ValueError):
            result = None
        never_run = (not last) or last.startswith("1999")
        if never_run:
            status = "not_run"
        elif result is None:
            status = "unknown"
        elif result != 0:
            status = "failed"
        else:
            status = "success"
        return {
            "status": status, "state": state,
            "last_run": None if never_run else last,
            "last_success": None if (never_run or result != 0) else last,
            "next_run": next_run or None,
            "last_result": result,
        }
    except Exception as exc:
        return {"status": "unknown", "state": "unknown", "last_run": None,
                "last_success": None, "next_run": None, "last_result": None, "error": str(exc)}


def weekly_review_runs(limit: int = 5) -> list:
    """Most recent structured weekly_review_run records from activity_log.jsonl."""
    out = []
    for rec in reversed(_activity_records()):
        if rec.get("type") == "weekly_review_run":
            out.append({k: rec.get(k) for k in
                        ("run_id", "period", "started_at", "finished_at", "duration_ms",
                         "status", "action", "warnings", "errors", "stages")})
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- rag evaluation

def _eval_runs_dir() -> Path:
    return EVAL_ROOT / "runs"


def evaluation_latest() -> dict:
    """Latest RAG Evaluation run summary (or None if never run). Read-only."""
    latest_path = EVAL_ROOT / "latest.json"
    if not latest_path.exists():
        return {"ok": True, "latest": None, "runs": evaluation_runs()}
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        latest = None
    return {"ok": True, "latest": latest, "runs": evaluation_runs()}


def evaluation_runs(limit: int = 20) -> list:
    """Most recent evaluation run summaries (meta.json), newest first."""
    runs_dir = _eval_runs_dir()
    out = []
    if not runs_dir.exists():
        return out
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        meta = run_dir / "meta.json"
        if not meta.exists():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        data["run_id"] = run_dir.name
        data["report_path"] = _safe_rel(run_dir / "evaluation_report.md", VAULT_ROOT)
        out.append(data)
    out.sort(key=lambda r: r.get("generated_at") or "", reverse=True)
    return out[: int(limit)]


def evaluation_report(run_id: str) -> dict:
    """Full structured report for one run (JSON)."""
    run_dir = _eval_runs_dir() / run_id
    report_path = run_dir / "evaluation_report.json"
    if not report_path.exists():
        return {"ok": False, "message": f"evaluation run 不存在: {run_id}"}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "message": f"读取报告失败: {exc}"}
    return {"ok": True, "run_id": run_id, "report": report}


# ---------------------------------------------------------------- gap diagnosis / diff

def _load_gap_registry() -> list:
    if not GAP_REGISTRY.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(GAP_REGISTRY.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    return data if isinstance(data, list) else []


def evaluation_gaps() -> dict:
    """Evaluation-derived Knowledge Gap registry (evidence-backed),
    enriched with per-gap source acquisition status."""
    gaps = _load_gap_registry()
    try:
        from rag_engine.source_acquisition import gaps_source_summary, load_registry
        summary = gaps_source_summary(gaps, load_registry(SOURCE_REGISTRY)["sources"])
    except Exception:
        summary = {}
    for g in gaps:
        g["source_status"] = (summary.get(g.get("id")) or {}).get("source_status", "missing")
    return {"ok": True, "gaps": gaps,
            "open": sum(1 for g in gaps if g.get("status") == "open"),
            "resolved": sum(1 for g in gaps if g.get("status") == "resolved"),
            "source": "RAG Evaluation"}


def evaluation_gap_detail(gap_id: str) -> dict:
    for g in _load_gap_registry():
        if g.get("id") == gap_id:
            return {"ok": True, "gap": g}
    return {"ok": False, "message": f"gap 不存在: {gap_id}"}


def run_gap_diagnosis() -> dict:
    """Run scripts/diagnose_gaps.py (audit -> gaps.yaml + audit report)."""
    cmd = [sys.executable, str(RAG_DIR / "scripts" / "diagnose_gaps.py"), "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
    except Exception as exc:
        return {"ok": False, "message": f"运行 Gap 诊断失败: {exc}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        _append_log({"action_id": "gap_diagnosis", "type": "gap_diagnosis",
                     "target": "rag evaluation", "actor": "user",
                     "ai_recommendation": "run", "user_decision": "run",
                     "result": "success", "message": "Gap 诊断完成"})
        return {"ok": True, "output": out[-500:], "gaps": evaluation_gaps()}
    return {"ok": False, "message": f"诊断失败（exit={proc.returncode}）: {out[-500:]}"}


def evaluation_diff() -> dict:
    """Latest before/after diff (latest_diff.json) or None."""
    diff_path = EVAL_ROOT / "latest_diff.json"
    if not diff_path.exists():
        return {"ok": True, "diff": None}
    try:
        diff = json.loads(diff_path.read_text(encoding="utf-8"))
    except Exception:
        diff = None
    return {"ok": True, "diff": diff}


# ---------------------------------------------------------------- evaluation governance

def _governance_state_path() -> Path:
    return EVAL_ROOT / "evaluation_state.json"


def governance_state() -> dict:
    """Evaluation Governance state machine (idle/required/running/passed/...)."""
    from rag_engine.evaluation_governance import load_state
    state = load_state(_governance_state_path())
    baseline = None
    try:
        from rag_engine.evaluation_baseline import load_baseline
        baseline = load_baseline(EVAL_ROOT / "baseline.json")
    except Exception:
        pass
    return {"ok": True, "state": state, "baseline": baseline,
            "required": state.get("status") in ("required", "failed"),
            "running": state.get("status") == "running"}


def _mark_governance_required(reason: str, batch_meta: dict | None = None) -> dict:
    """Mark evaluation_required (batched: N changes -> one required state)."""
    from rag_engine.evaluation_governance import load_state, mark_required, save_state
    try:
        state = load_state(_governance_state_path())
        state = mark_required(state, reason, batch_meta)
        save_state(_governance_state_path(), state)
        return {"ok": True, "state": state}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def _finalize_governance_run() -> dict:
    """After a benchmark run: auto Baseline Regression Check + state update.

    Failed/REGRESSED runs never overwrite the existing baseline. Re-establish
    the baseline only when the batch contained a knowledge change AND the
    check is STABLE/IMPROVED.
    """
    from rag_engine.evaluation_baseline import load_baseline, regression_check
    from rag_engine.evaluation_governance import (
        STATUS_RUNNING, STATUS_REQUIRED, STATUS_FAILED,
        complete, has_knowledge_change, load_state, save_state,
    )
    state = load_state(_governance_state_path())
    if state.get("status") not in (STATUS_RUNNING, STATUS_REQUIRED, STATUS_FAILED):
        return {"ok": True, "skipped": True}
    latest = evaluation_latest().get("latest") or {}
    run_id = latest.get("run_id")
    if not run_id:
        return {"ok": False, "message": "no run"}
    baseline = load_baseline(EVAL_ROOT / "baseline.json")
    ov = (latest.get("metrics") or {}).get("overall") or {}
    current = {"run_id": run_id, "coverage": ov.get("answer_coverage")}
    check = regression_check(current, baseline) if baseline else {
        "status": "STABLE", "current_run": run_id, "current_coverage": current["coverage"],
        "baseline_coverage": None, "delta_pp": None, "warning": None}
    reestablish = bool(baseline) and has_knowledge_change(state) and check["status"] != "REGRESSED"
    baseline_id = baseline.get("baseline_id") if baseline else None
    if reestablish:
        try:
            cmd = [sys.executable, str(RAG_DIR / "scripts" / "evaluation_baseline.py"),
                   "--establish", "--run", run_id, "--prev", baseline.get("run_id", ""), "--json"]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=120)
            if proc.returncode == 0:
                nb = load_baseline(EVAL_ROOT / "baseline.json")
                baseline_id = nb.get("baseline_id") if nb else baseline_id
        except Exception:
            pass
    state = complete(state, run_id=run_id, check=check, baseline_id=baseline_id,
                     reestablish_baseline=reestablish)
    save_state(_governance_state_path(), state)
    _append_log({"action_id": "governance_finalize", "type": "governance",
                 "target": "evaluation", "actor": "system",
                 "ai_recommendation": "auto", "user_decision": "auto",
                 "result": state["status"],
                 "message": f"Baseline Check 自动完成：{check.get('status')}（delta={check.get('delta_pp')}pp） run={run_id}"})
    return {"ok": True, "state": state, "check": check}


def run_baseline_verification() -> dict:
    """Governance verify: required/failed -> run benchmark -> baseline check."""
    st = governance_state()
    if st.get("running"):
        return {"ok": False, "message": "已有 Evaluation 正在运行"}
    if not st.get("required"):
        return {"ok": True, "message": "无待验证的知识变化（idle/passed），跳过", "skipped": True,
                "state": st.get("state")}
    _mark_governance_required("manual_request", {})
    cmd = [sys.executable, str(RAG_DIR / "scripts" / "evaluation_governance.py"), "--verify", "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=1500)
    except Exception as exc:
        return {"ok": False, "message": f"运行验证失败: {exc}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    try:
        result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        result = {"ok": False, "message": out[-500:]}
    return result


# ---------------------------------------------------------------- source acquisition / golden / judge variance

def source_acquisition() -> dict:
    """Source Acquisition registry + per-gap source status summary."""
    from rag_engine.source_acquisition import gaps_source_summary, load_registry
    registry = load_registry(SOURCE_REGISTRY)
    gaps = _load_gap_registry()
    summary = gaps_source_summary(gaps, registry["sources"])
    return {"ok": True, "registry": registry,
            "per_gap": summary,
            "source_count": len(registry["sources"])}


def source_acquisition_detail(source_id: str) -> dict:
    registry = source_acquisition().get("registry") or {}
    for s in registry.get("sources") or []:
        if s.get("id") == source_id:
            return {"ok": True, "source": s}
    return {"ok": False, "message": f"source task 不存在: {source_id}"}


def mark_source_verified(source_id: str, actor: str = "user") -> dict:
    """人工核验 Source：仅 acquired 可升级为 verified（生命周期严格相邻）。

    - 设置 verification.verified=true / verified_at / verified_by
    - 通过既有生命周期 apply_transition 把 source_status 前进到 verified
    - 只记录 Activity Log（SOURCE_VERIFIED），不触发 Evaluation / Benchmark
      （verified 是治理 metadata，不是知识内容变化）
    """
    from rag_engine.source_acquisition import apply_transition, load_registry, save_registry
    registry = load_registry(SOURCE_REGISTRY)
    sources = registry.get("sources") or []
    for i, s in enumerate(sources):
        if s.get("id") != source_id:
            continue
        vf = s.get("verification") or {}
        if vf.get("verified") or s.get("source_status") == "verified":
            return {"ok": True, "result": "already_done",
                    "message": f"{source_id} 已是 verified 状态", "source": s}
        if s.get("source_status") != "acquired":
            return {"ok": False,
                    "message": f"{source_id} 当前状态 {s.get('source_status')}，仅 acquired 可人工核验"}
        previous = bool(vf.get("verified"))
        try:
            updated = apply_transition(s, "verified", reviewer=actor)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        updated.setdefault("verification", {})
        updated["verification"]["verified_at"] = _now()
        updated["verification"]["verified_by"] = actor
        sources[i] = updated
        registry["sources"] = sources
        save_registry(SOURCE_REGISTRY, registry)
        # safe_dump 会丢掉文件头注释；写回后补回头部说明（避免重复补头）
        text = SOURCE_REGISTRY.read_text(encoding="utf-8")
        if not text.startswith("# Knowledge OS Source Acquisition Registry"):
            SOURCE_REGISTRY.write_text(SOURCE_REGISTRY_HEADER + text, encoding="utf-8")
        _append_log({
            "action_id": "SOURCE_VERIFIED", "type": "source", "target": source_id,
            "actor": actor, "result": "success",
            "previous_verified": previous, "new_verified": True,
            "verified_by": actor,
            "message": f"{source_id}（{updated.get('title', '')}）已人工核验 -> verified",
        })
        return {"ok": True, "result": "success", "source": updated,
                "message": f"{source_id} 已标记 verified"}
    return {"ok": False, "message": f"source task 不存在: {source_id}"}


def golden_set() -> dict:
    """Golden Set entries + manual-review statistics (read-only)."""
    from rag_engine.golden_set import golden_stats, load_golden
    golden = load_golden(GOLDEN_PATH)
    entries = golden.get("entries") or []
    return {"ok": True, "golden_version": golden.get("golden_version"),
            "entries": entries, "stats": golden_stats(entries)}


def evaluation_baseline() -> dict:
    """Official Evaluation Baseline + current run + regression check (read-only)."""
    from rag_engine.evaluation_baseline import load_baseline, regression_check
    baseline = load_baseline(EVAL_ROOT / "baseline.json")
    latest = evaluation_latest().get("latest") or {}
    ov = (latest.get("metrics") or {}).get("overall") or {}
    current = {"run_id": latest.get("run_id"),
               "coverage": ov.get("answer_coverage"),
               "knowledge_missing_rate": ov.get("knowledge_missing_rate")}
    check = None
    if baseline:
        check = regression_check(current, baseline)
    return {"ok": True, "baseline": baseline, "current": current, "check": check}


def judge_variance() -> dict:
    """Latest Judge Variance experiment (latest_judge_variance.json) or None."""
    p = EVAL_ROOT / "latest_judge_variance.json"
    if not p.exists():
        return {"ok": True, "judge_variance": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = None
    return {"ok": True, "judge_variance": data}


def run_evaluation_diff(before: str, after: str) -> dict:
    """Run scripts/evaluation_diff.py comparing two runs."""
    cmd = [sys.executable, str(RAG_DIR / "scripts" / "evaluation_diff.py"),
           "--before", before, "--after", after, "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    except Exception as exc:
        return {"ok": False, "message": f"运行 Diff 失败: {exc}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        _append_log({"action_id": "evaluation_diff", "type": "evaluation_diff",
                     "target": "rag evaluation", "actor": "user",
                     "ai_recommendation": "run", "user_decision": "run",
                     "result": "success", "message": f"Evaluation Diff {before} -> {after} 完成"})
        return {"ok": True, "output": out[-500:], "diff": evaluation_diff().get("diff")}
    return {"ok": False, "message": f"Diff 失败（exit={proc.returncode}）: {out[-500:]}"}


def run_evaluation(limit: int | None = None, mode: str = "fast") -> dict:
    """Run the RAG Evaluation benchmark through scripts/evaluate_benchmark.py.

    Real production retrieval path; may take minutes with real models. Returns
    the resulting summary (latest.json content).
    """
    extra = ["--out", str(EVAL_ROOT), "--mode", mode]
    if limit:
        extra += ["--limit", str(int(limit))]
    cmd = [sys.executable, str(RAG_DIR / "scripts" / "evaluate_benchmark.py")] + extra
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900,
        )
    except Exception as exc:
        return {"ok": False, "message": f"运行 Evaluation 失败: {exc}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    latest_path = EVAL_ROOT / "latest.json"
    if proc.returncode == 0 and latest_path.exists():
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            latest = None
        _append_log({"action_id": "rag_evaluation", "type": "rag_evaluation",
                     "target": "rag evaluation", "actor": "user",
                     "ai_recommendation": "run", "user_decision": "run",
                     "result": "success",
                     "message": f"RAG Evaluation 完成（run_id={latest.get('run_id') if latest else '?'}）"})
        # 治理门禁：任何成功 Evaluation 后自动执行 Baseline Regression Check
        try:
            _finalize_governance_run()
        except Exception:
            pass
        return {"ok": True, "latest": latest, "output": out[-500:]}
    _append_log({"action_id": "rag_evaluation", "type": "rag_evaluation",
                 "target": "rag evaluation", "actor": "user",
                 "ai_recommendation": "run", "user_decision": "run",
                 "result": "error", "message": "RAG Evaluation 运行失败"})
    return {"ok": False, "message": f"运行失败（exit={proc.returncode}）: {out[-500:]}"}


def query_trace(query: str) -> dict:
    """Run one real query and return the structured Retrieval Trace for the CC UI.

    Uses knowledge_service.knowledge_search (fast mode, no long answer) so the
    trace reflects the real Wiki-first / RAW / fallback / rerank / judge chain.
    The trace is produced during this single execution; nothing is re-run.
    """
    from interface import knowledge_service as ks

    q = (query or "").strip()
    if not q:
        return {"ok": False, "message": "query 为空"}
    try:
        result = ks.knowledge_search(q, mode="fast", use_llm=True, record_gap=False)
    except Exception as exc:
        return {"ok": False, "message": f"查询失败（fail-closed）: {exc}"}
    return {"ok": True, "query": q, "result": result}


def weekly_review_dashboard() -> dict:
    """Weekly Review Dashboard aggregate (single structured endpoint).

    Built from the same cheap deterministic collectors metrics.py uses for the
    weekly report, so dashboard numbers always equal the unified metrics.
    No Health Score is computed (Phase D); no fake trends (Phase C).
    """
    wr = weekly_review_list()
    latest = wr.get("latest") or {}
    period = latest.get("period") or review_metrics.current_iso_week()
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    resolved = resolve_paths(cfg, VAULT_ROOT)
    gap_path = Path(resolved["paths"]["knowledge_gaps"])
    wiki = review_metrics.collect_wiki_stats(VAULT_ROOT)
    start, _end = review_metrics.iso_week_range(period)
    growth = review_metrics.collect_growth(wiki["wikis"], start, _end)
    gaps = review_metrics.collect_gaps(gap_path)
    projects = review_metrics.collect_project_status(VAULT_ROOT)
    wr_cfg = cfg.get("weekly_review") or {}
    stale = review_metrics.collect_stale_risk(wiki["wikis"], int(wr_cfg.get("stale_threshold_days", 90) or 90))
    review = review_metrics.collect_review_metrics(
        VAULT_ROOT, gap_path=gap_path, config_path=str(RAG_DIR / "config.yaml")
    )
    baseline = review_metrics.collect_baseline(period)

    snapshots = review_metrics.collect_weekly_snapshots()
    trends = review_metrics.build_weekly_trends(snapshots)
    # health：system_reliability 用最新 snapshot 的健康结果（不重复执行健康检查子进程）
    health_snap = (latest.get("snapshot_health") or {})
    metrics_like = {
        "period": period,
        "wiki": wiki,
        "growth": growth,
        "gaps": gaps,
        "projects": projects,
        "stale_risk": stale,
        "review": review,
        "health": health_snap,
    }
    attention = health_engine.build_attention(metrics_like)
    health_result = health_engine.calculate_health(metrics_like)
    insight_cached = weekly_insight.load_cached_insight(period, REVIEW_ROOT, _insight_model_label(cfg))
    insight_result = insight_cached or {"status": "unavailable", "reason": "not_generated",
                                        "prompt_version": weekly_insight.PROMPT_VERSION,
                                        "model": _insight_model_label(cfg), "insight": None}
    return {
        "ok": True,
        "period": period,
        "generated_at": latest.get("generated_at"),
        "report_path": latest.get("report_path"),
        "status": {
            "health": health_result.get("score"),
            "health_status": health_result.get("status"),
            "baseline": bool(baseline.get("is_baseline_period")),
            "health_detail": health_snap,
        },
        "health": health_result,
        "insight": insight_result,
        "knowledge": {
            "total": wiki["wiki_total"],
            "new": growth["new_this_week"],
            "updated": growth["updated_this_week"],
            "stale": len(stale),
            "status_distribution": {
                "draft": wiki.get("wiki_draft", 0),
                "reviewed": wiki.get("wiki_reviewed", 0),
                "stable": wiki.get("wiki_stable", 0),
                "unknown": wiki.get("wiki_unknown", 0),
            },
        },
        "review": {k: review[k] for k in
                   ("judge_passed", "needs_review", "judge_failed", "judging", "not_judged", "pending_human")},
        "gaps": {
            "pending": gaps["knowledge_gaps_pending"],
            "total": gaps["knowledge_gaps_total"],
            "resolved": gaps["knowledge_gaps_resolved"],
        },
        "projects": {
            "counts": {
                "active": sum(1 for pr in projects if pr.get("status") == "active"),
                "planning": sum(1 for pr in projects if pr.get("status") == "planning"),
                "blocked": sum(1 for pr in projects if pr.get("status") == "blocked"),
            },
            "items": [
                {"name": pr["name"], "status": pr.get("status"), "phase": pr.get("phase"),
                 "updated": pr.get("updated"), "blockers": pr.get("blockers") or []}
                for pr in projects
            ],
        },
        "risk": {"stale": len(stale)},
        "baseline": baseline,
        "attention": attention,
        "historical": wr.get("history") or [],
        "automation": weekly_review_automation(),
        "runs": weekly_review_runs(5),
        "has_trend": bool(trends["availability"]["has_history"]),
        "trend": {
            "wow": trends["wow"],
            "four_week": trends["four_week"],
            "wow_by_period": trends["wow_by_period"],
            "availability": trends["availability"],
        },
        "rag_evaluation": review_metrics.collect_rag_evaluation(VAULT_ROOT),
    }


def weekly_review_list() -> dict:
    reviews = list(_iter_reviews())
    reviews.sort(key=lambda r: (r["year"], int(re.findall(r"\d+", r["week"] or "")[0]) if re.findall(r"\d+", r["week"] or "") else 0), reverse=True)
    return {"latest": reviews[0] if reviews else None, "history": reviews}


def project_status() -> list:
    return review_metrics.collect_project_status(VAULT_ROOT)


def activity_timeline(limit: int = 50) -> list:
    return review_metrics.collect_activity(VAULT_ROOT, limit=limit)


def _next_review_time() -> str | None:
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    wr = cfg.get("weekly_review") or {}
    if not wr.get("enabled", True):
        return None
    weekday_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    wd = weekday_map.get(str(wr.get("weekday", "friday")).lower())
    if wd is None:
        return None
    t = str(wr.get("time", "18:00"))
    try:
        hh, mm = t.split(":")
        target = datetime.now().replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except Exception:
        return None
    days_ahead = (wd - target.weekday()) % 7
    if days_ahead == 0 and target <= datetime.now():
        days_ahead = 7
    target += timedelta(days=days_ahead)
    return target.strftime("%Y-%m-%d %H:%M")


def cc_status() -> dict:
    state = _load_sync_state()
    latest = weekly_review_list().get("latest")
    last_review = None
    if latest:
        last_review = latest.get("generated_at") or latest.get("period")
    gov = {}
    try:
        from rag_engine.evaluation_governance import load_state
        g = load_state(_governance_state_path())
        gov = {"status": g.get("status"), "required": g.get("status") in ("required", "failed"),
               "run_id": g.get("run_id"), "last_check": (g.get("check") or {}).get("status")}
    except Exception:
        gov = {}
    return {
        "last_sync": state.get("last_sync"),
        "last_sync_result": state.get("last_result"),
        "last_review": last_review,
        "next_review": _next_review_time(),
        "governance": gov,
    }


def _load_sync_state() -> dict:
    if not SYNC_STATE.exists():
        return {}
    try:
        return json.loads(SYNC_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_sync_state(state: dict) -> None:
    SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_kb() -> dict:
    """Scan vault -> incrementally update index -> recompute metrics -> activity."""
    started = _now()
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    resolved = resolve_paths(cfg, VAULT_ROOT)
    manifest_path = Path(resolved["paths"]["main_vector_db"]).parent / "index_manifest.json"
    before_keys = set()
    if manifest_path.exists():
        try:
            before_keys = set(json.loads(manifest_path.read_text(encoding="utf-8")).keys())
        except Exception:
            before_keys = set()

    try:
        code, out = _run_py("scripts/update_index.py", ["--changed", "--target", "main"])
    except Exception as exc:
        code, out = -1, str(exc)

    result = {
        "success": code == 0,
        "last_sync": _now(),
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "indexed": None,
    }
    if code != 0:
        result["error"] = (out or "").strip()[-500:]
        _save_sync_state({"last_sync": result["last_sync"], "last_result": result})
        _append_log({"action_id": "sync", "type": "sync", "target": "knowledge base", "actor": "user",
                     "ai_recommendation": "sync", "user_decision": "sync", "result": "error",
                     "message": "同步失败"})
        return result

    after_keys = set()
    if manifest_path.exists():
        try:
            after_keys = set(json.loads(manifest_path.read_text(encoding="utf-8")).keys())
        except Exception:
            after_keys = set()
    added = len(after_keys - before_keys)
    changed = 0
    deleted = 0
    mchg = re.search(r"changed=(\d+)", out)
    if mchg:
        changed = int(mchg.group(1))
    mdel = re.search(r"deleted=(\d+)", out)
    if mdel:
        deleted = int(mdel.group(1))
    modified = max(0, changed - added)
    result.update({"added": added, "modified": modified, "deleted": deleted,
                   "indexed": max(0, changed)})
    _save_sync_state({"last_sync": result["last_sync"], "last_result": result})
    _append_log({"action_id": "sync", "type": "sync", "target": "knowledge base", "actor": "user",
                 "ai_recommendation": "sync", "user_decision": "sync", "result": "success",
                 "message": f"同步完成（新增 {added} / 修改 {modified} / 删除 {deleted}）"})
    # 治理门禁：Index 实际发生知识变化才标记 evaluation_required（纯查看/无变化不触发）
    if added + modified + deleted > 0:
        _mark_governance_required("index_updated", {"added": added, "modified": modified, "deleted": deleted})
    return result


def generate_weekly_review() -> dict:
    code, out = _run_py("scripts/review/weekly_review.py", ["--force"])
    ok = code == 0
    result = {"success": ok, "message": (out or "").strip()[-500:] or ("ok" if ok else "failed")}
    if not ok:
        result["error"] = (out or "").strip()[-500:]
    _append_log({"action_id": "weekly_review", "type": "weekly_review", "target": "weekly review",
                 "actor": "user", "ai_recommendation": "generate", "user_decision": "generate",
                 "result": "success" if ok else "error",
                 "message": "生成本周复盘" if ok else "生成失败"})
    return result
# ---------------------------------------------------------------- review context

"""Review Context: assemble an audit workbench for a pending action.

Read-only: never mutates Wiki / Markdown / Vector DB / gap state. Reuses the
existing source of truth (frontmatter, gaps.yaml) and the exact chunking logic
(rag_engine.ingest.parse_file / chunk_text) used by RAG indexing. AI judgement
is derived from persisted fields and clearly labelled as derived; there is no
stored LLM Judge result to reuse, so we do not fabricate one.
"""

GAP_TYPE_TEXT = {
    "knowledge_missing": "知识库缺少该主题的资料，检索命中不足",
    "knowledge_insufficient": "存在相关知识但内容或可信度不足",
    "knowledge_conflict": "已有资料之间存在冲突，无法确定结论",
    "retrieval_problem": "知识存在但检索未正确命中",
    "answer_quality_problem": "检索正确但回答为空或过短",
}
MAX_CHUNKS_PER_SOURCE = 20


def _norm_rel(value) -> str:
    return str(value).replace("\\", "/").strip()


def _chunk_cfg() -> tuple[int, int]:
    try:
        cfg = load_config(str(RAG_DIR / "config.yaml"))
        return int(cfg.get("chunking", {}).get("size", 800)), int(cfg.get("chunking", {}).get("overlap", 100))
    except Exception:
        return 800, 100


def _extract_evidence(source_paths, role: str) -> dict:
    """Read existing source files into sources[] + chunks[].

    Uses parse_file + chunk_text (the same pipeline RAG indexing uses), so the
    displayed evidence matches what would be indexed; no new retrieval logic.
    A broken/missing source never breaks the whole context.
    """
    size, overlap = _chunk_cfg()
    sources, chunks, seen = [], [], set()
    for raw in source_paths:
        rel = _norm_rel(raw)
        if not rel:
            continue
        key = rel.lower()
        if key in seen:
            continue
        seen.add(key)
        path = VAULT_ROOT / rel
        entry = {
            "path": rel,
            "name": path.name,
            "type": path.suffix.lower().lstrip(".") or "unknown",
            "role": role,
            "readable": False,
            "chunk_count": 0,
            "error": None,
        }
        if not path.exists():
            entry["error"] = "文件不存在（相对路径无法解析）"
            sources.append(entry)
            continue
        try:
            pages = parse_file(path, relative_root=VAULT_ROOT)
            text = "\n\n".join(p.get("text", "") for p in pages if p.get("text"))
        except Exception as exc:
            entry["error"] = f"读取失败: {exc}"
            sources.append(entry)
            continue
        if not text.strip():
            entry["error"] = "无可提取文本"
            sources.append(entry)
            continue
        parts = chunk_text(text, size, overlap)
        entry["readable"] = True
        entry["chunk_count"] = len(parts)
        entry["window_start"] = 1 if parts else None
        entry["window_end"] = len(parts) if parts else None
        entry["window_text"] = merge_chunk_sequence(parts, overlap) if parts else ""
        entry["truncated"] = len(parts) > MAX_CHUNKS_PER_SOURCE
        sources.append(entry)
        for index, part in enumerate(parts[:MAX_CHUNKS_PER_SOURCE]):
            chunks.append({
                "source": rel,
                "source_name": path.name,
                "content": part,
                "score": None,
                "chunk_id": f"{rel}#{index}",
                "position": index,
                "context_start_chunk": 1,
                "context_end_chunk": len(parts),
            })
    return {"sources": sources, "chunks": chunks}


def _wiki_review_context(action: dict) -> dict:
    rel = action["target"].get("wiki", "")
    path = VAULT_ROOT / rel
    fm = _parse_fm(path) if path.exists() else {}
    body = _body_of(path) if path.exists() else ""
    sources_raw = action.get("source") or []
    ev = _extract_evidence(sources_raw, role="source")
    readable = [s for s in ev["sources"] if s["readable"]]
    missing = [s for s in ev["sources"] if not s["readable"]]

    warnings = [f"来源文件不可读: {s['path']}（{s['error']}）" for s in missing]
    if not sources_raw:
        warnings.append("Wiki 未记录任何来源，无法核对依据")
    if len(body.strip()) < 300:
        warnings.append("正文较短（<300 字符），建议重点核对内容是否完整")

    if not readable:
        sufficiency = "insufficient"
    elif missing:
        sufficiency = "partial"
    else:
        sufficiency = "sufficient"

    content_len = len(body.strip())
    recommendation = action.get("ai_recommendation") or "review"
    reasoning = (
        f"推荐操作来自现有规则：正文 {content_len} 字符，"
        f"{'达到 300 字符阈值 → approve' if content_len >= 300 else '未达到 300 字符阈值 → review'}；"
        f"来源 {len(sources_raw)} 个，其中可读取 {len(readable)} 个；"
        f"frontmatter confidence={fm.get('confidence') or '未记录'}，review_required={fm.get('review_required', '未记录')}。"
        "（由 Control Center 基于现有字段派生，非 LLM Judge 输出）"
    )
    if recommendation == "approve":
        summary = "建议批准：将 Wiki 状态由 draft 升级为 reviewed（需人工点击「批准」后才执行）。"
        changes = [{"target": rel, "before": fm.get("status") or "draft", "after": "reviewed"}]
    elif recommendation == "reject":
        summary = "建议拒绝：状态保持 draft，不修改内容。"
        changes = []
    else:
        summary = "建议人工复核：内容或来源不足以直接批准，核对后再决定 approve / reject。"
        changes = []

    return {
        "ok": True,
        "action_id": action["id"],
        "task": {
            "id": action["id"],
            "type": action["type"],
            "title": action["target"].get("title", ""),
            "target": {"wiki": rel, "domain": action["target"].get("domain", "")},
            "status": action["status"],
            "created_at": action.get("created_at") or "",
        },
        "ai_judgement": _merge_judge_record({
            "recommendation": recommendation,
            "confidence": fm.get("confidence") or "unknown",
            "evidence_sufficiency": sufficiency,
            "reasoning": reasoning,
            "warnings": warnings,
            "review_reason_hint": "Wiki 处于 draft 状态，按规则进入人工审核",
        }, action["id"]),
        "evidence": ev,
        "target_content": {
            "path": rel,
            "title": action["target"].get("title", ""),
            "status": fm.get("status") or "unknown",
            "domain": fm.get("domain", ""),
            "content": body,
            "length": content_len,
        },
        "ai_suggestion": {
            "action": recommendation,
            "summary": summary,
            "changes": changes,
            "conflict": [],
        },
        "actions": action.get("available_actions") or [],
    }


def _gap_context(action: dict) -> dict:
    question = action["target"].get("question", "")
    gap = next((g for g in load_gaps(str(_gap_path())) if g.get("question") == question), None)
    gap = gap or action.get("target") or {}
    rel_sources = gap.get("related_sources") or []
    rel_wiki = gap.get("related_wiki") or []
    ev_src = _extract_evidence(rel_sources, role="related_source")
    ev_wiki = _extract_evidence(rel_wiki, role="related_wiki")
    sources = ev_src["sources"] + ev_wiki["sources"]
    chunks = ev_src["chunks"] + ev_wiki["chunks"]

    gap_type = str(gap.get("type") or "knowledge_missing")
    warnings = []
    for s in sources:
        if not s["readable"]:
            warnings.append(f"相关文件不可读: {s['path']}（{s['error']}）")
    if gap_type == "knowledge_conflict":
        sufficiency = "conflict"
    else:
        sufficiency = "insufficient"
    recommendation = str(gap.get("suggested_action") or action.get("ai_recommendation") or "create_wiki")
    reasoning = (
        f"Gap 类型: {gap_type}（{GAP_TYPE_TEXT.get(gap_type, '未知类型')}）；"
        f"相关来源 {len(rel_sources)} 个、相关 Wiki {len(rel_wiki)} 篇，可读取 {sum(1 for s in sources if s['readable'])} 个。"
        "Gap 记录本身即表示当前证据不足以直接回答问题。"
        "（由 Control Center 基于 knowledge_gaps.yaml 派生，非 LLM Judge 输出）"
    )
    summary = f"建议{recommendation}：基于相关来源补齐知识后再处理；「解决」操作仅标记已解决，不会自动写入 Wiki。"
    return {
        "ok": True,
        "action_id": action["id"],
        "task": {
            "id": action["id"],
            "type": action["type"],
            "title": question,
            "target": {"question": question, "type": gap_type, "topic": gap.get("topic") or ""},
            "status": action["status"],
            "created_at": action.get("created_at") or gap.get("detected_at") or "",
        },
        "ai_judgement": _merge_judge_record({
            "recommendation": recommendation,
            "confidence": None,
            "priority": str(gap.get("priority") or "medium"),
            "evidence_sufficiency": sufficiency,
            "reasoning": reasoning,
            "warnings": warnings,
            "review_reason_hint": "知识库证据不足时自动记录的知识缺口，按规则进入人工审核",
        }, action["id"]),
        "evidence": {"sources": sources, "chunks": chunks},
        "target_content": None,
        "ai_suggestion": {
            "action": recommendation,
            "summary": summary,
            "changes": [],
            "conflict": [],
        },
        "actions": action.get("available_actions") or [],
    }


def _generic_context(action: dict) -> dict:
    return {
        "ok": True,
        "action_id": action["id"],
        "task": {
            "id": action["id"],
            "type": action["type"],
            "title": "",
            "target": action.get("target") or {},
            "status": action["status"],
            "created_at": action.get("created_at") or "",
        },
        "ai_judgement": _merge_judge_record({
            "recommendation": action.get("ai_recommendation"),
            "confidence": None,
            "evidence_sufficiency": None,
            "reasoning": action.get("reason") or "",
            "warnings": [],
            "review_reason_hint": "该任务按规则进入待审核列表",
        }, action["id"]),
        "evidence": {"sources": [], "chunks": []},
        "target_content": None,
        "ai_suggestion": {
            "action": action.get("ai_recommendation"),
            "summary": action.get("reason") or "",
            "changes": [],
            "conflict": [],
        },
        "actions": action.get("available_actions") or [],
    }


# ---------------------------------------------------------------- review judge

"""Review Judge integration: run the real LLM Review Judge (rag_engine.judge)
for a pending action and persist the structured result in a review records
store keyed by action_id. Rule-based signals stay separate and are never
labelled as an LLM judgement.
"""

REVIEW_RECORDS = CTRL_DIR / "review_records.json"
JUDGE_VERSION = "review_judge/v1"
REVIEW_JUDGE_PROMPT_FILE = "90_System/rag/prompts/review_judge.md"


def _review_records_path() -> Path:
    return REVIEW_RECORDS


def _load_review_records() -> dict:
    if not REVIEW_RECORDS.exists():
        return {}
    try:
        data = json.loads(REVIEW_RECORDS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_review_records(records: dict) -> None:
    from rag_engine.atomic_io import atomic_write_json

    atomic_write_json(REVIEW_RECORDS, records)


def _judge_model_label(cfg: dict) -> str:
    llm = cfg.get("llm") or {}
    provider = llm.get("provider", "unknown")
    model = llm.get("model")
    if isinstance(model, dict):
        model = model.get("name")
    return f"{provider}:{model or 'unknown'}"


def _build_judge_input(action: dict) -> dict | None:
    """Collect Evidence + Target + Task background for the Review Judge."""
    if action["type"] == "wiki_review":
        rel = action["target"].get("wiki", "")
        path = VAULT_ROOT / rel
        if not path.exists():
            return None
        fm = _parse_fm(path)
        body = _body_of(path)
        ev = _extract_evidence(action.get("source") or [], role="source")
        task_text = (
            f"审核任务：Wiki Review\n"
            f"目标：{action['target'].get('title', '')}（{rel}）\n"
            f"当前状态：{fm.get('status', 'unknown')}\n"
            f"为什么进入审核：{action.get('reason', '新 Wiki 等待人工审核')}\n"
            "请比较下方『来源证据』与『当前 Wiki』，判断是否需要人工审核，并输出结构化审核结论。"
        )
        return {"task_text": task_text, "chunks": ev["chunks"], "target_content": body,
                "target_path": rel, "evidence": ev}
    if action["type"] == "knowledge_gap":
        question = action["target"].get("question", "")
        gap = next((g for g in load_gaps(str(_gap_path())) if g.get("question") == question), None) or {}
        rel_sources = gap.get("related_sources") or []
        rel_wiki = gap.get("related_wiki") or []
        ev_src = _extract_evidence(rel_sources, role="related_source")
        ev_wiki = _extract_evidence(rel_wiki, role="related_wiki")
        chunks = ev_src["chunks"] + ev_wiki["chunks"]
        sources = ev_src["sources"] + ev_wiki["sources"]
        task_text = (
            f"审核任务：Knowledge Gap\n"
            f"问题：{question}\n"
            f"Gap 类型：{gap.get('type', 'knowledge_missing')}\n"
            f"为什么进入审核：知识库证据不足时自动记录的知识缺口\n"
            "请根据『来源证据』（相关来源与相关 Wiki）判断该知识缺口是否真实存在、证据是否足以回答问题，并输出结构化审核结论。"
        )
        return {"task_text": task_text, "chunks": chunks, "target_content": None,
                "target_path": question, "evidence": {"sources": sources}}
    return None


def run_review_judge(action_id: str) -> dict:
    """Run the real LLM Review Judge for an action and persist the result.

    Manual entry (POST /api/actions/{id}/judge). Never auto-approves: on any
    failure a fail-closed record is persisted so the UI can show 'AI Judge
    未完成' stably. Reading the context never runs the judge again.
    """
    action = next((a for a in build_actions() if a["id"] == action_id), None)
    if action is None:
        return {"ok": False, "message": f"action not found: {action_id}"}
    records = _load_review_records()
    with _PREFLIGHT_LOCK:
        r = _judge_one(action, load_config(str(RAG_DIR / "config.yaml")), records, _preflight_cfg(), force=True)
    if r["status"] == "judging":
        return {"ok": False, "message": "该任务正在被自动审核中，请稍后刷新", "judge_status": "judging"}
    record = records.get(action_id) or {}
    return {"ok": True, "action_id": action_id, "judge_status": record.get("judge_status"),
            "classification": record.get("classification"), "judgement": record}


def _rule_review_reason(rule_j: dict) -> str:
    hint = rule_j.get("review_reason_hint") or "当前任务按规则进入待审核列表"
    parts = [hint]
    suff = rule_j.get("evidence_sufficiency")
    if suff in ("insufficient", "partial"):
        parts.append(f"来源证据{suff}，无法仅凭规则确认。")
    warnings = rule_j.get("warnings") or []
    if warnings:
        parts.append("；".join(warnings[:2]))
    parts.append("尚未运行 LLM Judge 语义比较。")
    return " ".join(parts)


def _judge_review_reason(res: dict) -> str:
    lines = []
    consistency = res.get("consistency")
    if consistency == "conflict":
        lines.append("AI 发现当前 Wiki 与来源资料存在冲突，无法安全自动确认。")
    elif consistency == "partial":
        lines.append("AI 发现当前 Wiki 与来源资料仅部分一致，需要人工核对差异。")
    sufficiency = res.get("evidence_sufficiency")
    if sufficiency == "insufficient":
        lines.append("现有来源证据不足以验证 Wiki 中的关键结论。")
    elif sufficiency == "partial":
        lines.append("现有来源证据只能部分支持 Wiki 内容。")
    if res.get("missing_information"):
        lines.append("来源包含 Wiki 未覆盖的重要信息：" + "；".join(res["missing_information"][:5]) + "。")
    if res.get("unsupported_claims"):
        lines.append("Wiki 存在来源无法支持的内容：" + "；".join(res["unsupported_claims"][:5]) + "。")
    if res.get("conflicts"):
        lines.append("冲突：" + "；".join(res["conflicts"][:5]) + "。")
    if not lines:
        if consistency == "consistent" and sufficiency == "sufficient":
            lines.append("AI 比较后未发现冲突或缺失，建议按推荐操作处理；最终决定由人工确认。")
        else:
            lines.append("AI 判断需要人工复核（详见判断理由）。")
    return " ".join(lines)


def _merge_judge_record(rule_j: dict, action_id: str) -> dict:
    """Attach the stored LLM Judge record to the rule-based judgement.

    Without a record the judgement stays clearly labelled source=rule /
    derived=true. With a record, the LLM Judge becomes the primary judgement
    and the rule signals are kept as auxiliary fields.
    """
    rule_j = dict(rule_j)
    record = _load_review_records().get(action_id)
    if not record:
        rule_j["source"] = "rule"
        rule_j["derived"] = True
        rule_j["judge_available"] = False
        rule_j["rule_recommendation"] = rule_j.get("recommendation")
        rule_j["rule_reasoning"] = rule_j.get("reasoning")
        rule_j["review_reason"] = _rule_review_reason(rule_j)
        return rule_j
    res = record.get("result") or {}
    judged = {
        "source": "llm_judge",
        "judge_available": True,
        "derived": False,
        "judge_status": record.get("judge_status", "failed"),
        "judged_at": record.get("judged_at"),
        "judge_model": record.get("judge_model"),
        "judge_version": record.get("judge_version"),
        "rule_recommendation": rule_j.get("recommendation"),
        "rule_reasoning": rule_j.get("reasoning"),
        "rule_warnings": rule_j.get("warnings", []),
        "rule_evidence_sufficiency": rule_j.get("evidence_sufficiency"),
    }
    judged["classification"] = record.get("classification")
    if record.get("judge_status") == "completed":
        judged.update({
            "status": "completed",
            "recommendation": res.get("recommendation") or "review",
            "confidence": res.get("confidence") or "unknown",
            "evidence_sufficiency": res.get("evidence_sufficiency") or "unknown",
            "consistency": res.get("consistency") or "unknown",
            "conflicts": res.get("conflicts") or [],
            "missing_information": res.get("missing_information") or [],
            "unsupported_claims": res.get("unsupported_claims") or [],
            "reasoning": res.get("reasoning") or "",
            "warnings": res.get("warnings") or [],
            "review_reason": _judge_review_reason(res),
        })
    elif record.get("judge_status") == "blocked":
        judged.update({
            "status": "blocked",
            "recommendation": "review",
            "confidence": "unknown",
            "evidence_sufficiency": "unknown",
            "consistency": "unknown",
            "conflicts": [],
            "missing_information": [],
            "unsupported_claims": [],
            "reasoning": str(record.get("reason") or "缺少可读取来源或目标，无法进行 LLM Judge"),
            "warnings": [],
            "review_reason": "无法进行 LLM Judge（" + str(record.get("reason") or "缺少可读取来源或目标") + "），因此需要人工审核。",
        })
    elif record.get("judge_status") == "judging":
        judged.update({
            "status": "judging",
            "recommendation": "review",
            "confidence": "unknown",
            "evidence_sufficiency": "unknown",
            "consistency": "unknown",
            "conflicts": [],
            "missing_information": [],
            "unsupported_claims": [],
            "reasoning": "AI Judge 正在运行中",
            "warnings": [],
            "review_reason": "AI Judge 运行中，请稍后刷新查看结果。",
        })
    else:
        judged.update({
            "status": "failed",
            "recommendation": "review",
            "confidence": "unknown",
            "evidence_sufficiency": res.get("evidence_sufficiency") or "unknown",
            "consistency": "unknown",
            "conflicts": [],
            "missing_information": [],
            "unsupported_claims": [],
            "reasoning": res.get("reasoning") or "AI Judge 未完成",
            "warnings": [],
            "review_reason": "AI Judge 未能完成（" + str(res.get("reason") or "未知原因") + "），因此需要人工审核。",
        })
    return judged


# ---------------------------------------------------------------- review preflight

"""Review Preflight: automatically run the LLM Review Judge on new/stale
Review Candidates before they reach the human queue, then classify them.

Guarantees:
  - fingerprint cache: unchanged source+target+version reuse the stored result
  - judging lock: a candidate in 'judging' state is never judged twice
  - bounded pass: at most `max_per_run` candidates per call (from config)
  - fail-closed: any LLM failure -> judge_failed -> needs_review, never approve
  - read-only for Wiki: never modifies Wiki / gap / frontmatter
"""

_PREFLIGHT_LOCK = threading.Lock()


def _stable_fingerprint(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def _evidence_fingerprint(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        src = c.get("source") or ""
        content = c.get("content") or c.get("text") or ""
        parts.append(f"{src}\x00{content}")
    return _stable_fingerprint("\n".join(parts))


def _target_fingerprint(target_content, fallback: str) -> str:
    return _stable_fingerprint(target_content or fallback or "")


def _prompt_fingerprint() -> str:
    try:
        return _stable_fingerprint((RAG_DIR / "prompts" / "review_judge.md").read_text(encoding="utf-8"))
    except Exception:
        return "unknown"


def _preflight_cfg() -> dict:
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    p = cfg.get("review_preflight") or {}
    return {
        "enabled": bool(p.get("enabled", True)),
        "max_per_run": int(p.get("max_per_run", 8)),
        "judge_timeout_seconds": int(p.get("judge_timeout_seconds", 180)),
        "failed_retry_minutes": int(p.get("failed_retry_minutes", 15)),
        "staleness_hours": int(p.get("staleness_hours", 24)),
    }


def _classify_judge(result: dict) -> str:
    """judge_passed / needs_review / judge_failed.

    judge_passed only when ALL of: sufficient + consistent + high +
    approve + no conflicts/missing/unsupported/warnings + no error.
    Everything else goes to needs_review; errors go to judge_failed.
    """
    if result.get("error"):
        return "judge_failed"
    if (
        result.get("status") == "sufficient"
        and result.get("consistency") == "consistent"
        and result.get("confidence") == "high"
        and result.get("recommendation") == "approve"
        and not result.get("conflicts")
        and not result.get("missing_information")
        and not result.get("unsupported_claims")
        and not result.get("warnings")
    ):
        return "judge_passed"
    return "needs_review"


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _current_fingerprints(action: dict) -> tuple[str, str, str] | None:
    judge_input = _build_judge_input(action)
    if judge_input is None:
        return None
    source_fp = _evidence_fingerprint(judge_input["chunks"])
    target_fp = _target_fingerprint(judge_input["target_content"], judge_input["target_path"])
    prompt_fp = _prompt_fingerprint()
    input_fp = _stable_fingerprint(f"{source_fp}|{target_fp}|{JUDGE_VERSION}|{prompt_fp}")
    return source_fp, target_fp, input_fp


def _preflight_decision(action_id: str, records: dict, pc: dict) -> str:
    """'valid' (reuse cache) | 'judging' (locked, skip) | 'needs_judge'."""
    record = records.get(action_id)
    if record is None:
        return "needs_judge"
    status = record.get("judge_status")
    now = datetime.now()
    if status == "judging":
        judging_at = _parse_time(record.get("judging_at"))
        if judging_at and (now - judging_at).total_seconds() < pc["judge_timeout_seconds"]:
            return "judging"
        return "needs_judge"  # stale lock -> takeover
    if status in ("completed", "blocked", "failed"):
        action = next((a for a in build_actions() if a["id"] == action_id), None)
        fp = _current_fingerprints(action) if action else None
        if fp is not None and record.get("input_fingerprint") == fp[2]:
            if status == "failed":
                judged_at = _parse_time(record.get("judged_at"))
                if judged_at and (now - judged_at).total_seconds() < pc["failed_retry_minutes"] * 60:
                    return "valid"  # recent failure, avoid spam retry
                return "needs_judge"  # retry after cooldown
            return "valid"
        return "needs_judge"  # source/target/version changed
    return "needs_judge"


def _persist_blocked(action: dict, judge_input: dict, cfg: dict, records: dict,
                     source_fp: str, target_fp: str, prompt_fp: str, input_fp: str, reason: str) -> dict:
    aid = action["id"]
    final = {
        "action_id": aid,
        "type": action["type"],
        "target": judge_input["target_path"] or "",
        "source_refs": [s["path"] for s in judge_input["evidence"].get("sources", [])],
        "evidence_chunk_count": len(judge_input["chunks"]),
        "judge_status": "blocked",
        "classification": "needs_review",
        "judge_version": JUDGE_VERSION,
        "prompt_file": REVIEW_JUDGE_PROMPT_FILE,
        "prompt_fingerprint": prompt_fp,
        "judge_model": _judge_model_label(cfg),
        "judged_at": _now(),
        "judging_at": None,
        "source_fingerprint": source_fp,
        "target_fingerprint": target_fp,
        "input_fingerprint": input_fp,
        "result": None,
        "reason": reason,
    }
    records[aid] = final
    _save_review_records(records)
    _append_log({"action_id": aid, "type": "review_judge", "target": final["target"], "actor": "system",
                 "ai_recommendation": "review", "user_decision": "auto_judge", "result": "blocked",
                 "message": f"Review Judge 阻塞: {reason}"})
    return {"action_id": aid, "status": "blocked", "classification": "needs_review", "reason": reason, "record": final}


def _judge_one(action: dict, cfg: dict, records: dict, pc: dict, force: bool = False) -> dict:
    """Judge a single candidate and persist. Callers hold _PREFLIGHT_LOCK."""
    aid = action["id"]
    judge_input = _build_judge_input(action)
    if judge_input is None:
        return {"action_id": aid, "status": "blocked", "classification": "needs_review",
                "reason": f"任务类型不支持: {action['type']}"}
    source_fp = _evidence_fingerprint(judge_input["chunks"])
    target_fp = _target_fingerprint(judge_input["target_content"], judge_input["target_path"])
    prompt_fp = _prompt_fingerprint()
    input_fp = _stable_fingerprint(f"{source_fp}|{target_fp}|{JUDGE_VERSION}|{prompt_fp}")

    readable = [s for s in judge_input["evidence"].get("sources", []) if s.get("readable")]
    if not readable:
        return _persist_blocked(action, judge_input, cfg, records, source_fp, target_fp, prompt_fp, input_fp,
                                "无可读取来源证据，无法进行 LLM Judge")
    if action["type"] == "wiki_review" and not (judge_input["target_content"] and str(judge_input["target_content"]).strip()):
        return _persist_blocked(action, judge_input, cfg, records, source_fp, target_fp, prompt_fp, input_fp,
                                "目标 Wiki 内容为空，无法进行 LLM Judge")

    existing = records.get(aid) or {}
    if existing.get("judge_status") == "judging" and not force:
        judging_at = _parse_time(existing.get("judging_at"))
        if judging_at and (datetime.now() - judging_at).total_seconds() < pc["judge_timeout_seconds"]:
            return {"action_id": aid, "status": "judging", "classification": None, "reason": "另一任务正在审核中"}

    rec = dict(existing)
    rec.update({"judge_status": "judging", "judging_at": _now()})
    records[aid] = rec
    _save_review_records(records)

    try:
        result = rag_judge.judge_review(
            judge_input["task_text"], judge_input["chunks"], judge_input["target_content"], cfg
        )
    except Exception as exc:
        result = dict(rag_judge.REVIEW_FAIL_CLOSED)
        result["reason"] = f"Review Judge 执行异常（fail closed）: {exc}"

    status = "completed" if not result.get("error") else "failed"
    classification = _classify_judge(result)
    final = {
        "action_id": aid,
        "type": action["type"],
        "target": judge_input["target_path"] or "",
        "source_refs": [s["path"] for s in judge_input["evidence"].get("sources", [])],
        "evidence_chunk_count": len(judge_input["chunks"]),
        "judge_status": status,
        "classification": classification,
        "judge_version": JUDGE_VERSION,
        "prompt_file": REVIEW_JUDGE_PROMPT_FILE,
        "prompt_fingerprint": prompt_fp,
        "judge_model": _judge_model_label(cfg),
        "judged_at": _now(),
        "judging_at": None,
        "source_fingerprint": source_fp,
        "target_fingerprint": target_fp,
        "input_fingerprint": input_fp,
        "result": result,
    }
    records[aid] = final
    _save_review_records(records)
    if status == "completed":
        message = f"Review Judge 完成（{classification}, consistency={result.get('consistency')}, recommendation={result.get('recommendation')}）"
    else:
        message = f"Review Judge 失败: {str(result.get('reason') or '')[:200]}"
    _append_log({"action_id": aid, "type": "review_judge", "target": final["target"], "actor": "system",
                 "ai_recommendation": result.get("recommendation", "review"), "user_decision": "auto_judge",
                 "result": "success" if status == "completed" else "error", "message": message})
    return {"action_id": aid, "status": status, "classification": classification, "record": final}


def _preflight_runtime_dir() -> Path:
    d = CTRL_DIR / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _acquire_preflight_file_lock(pc: dict) -> bool:
    """Cross-process mutual exclusion via an O_EXCL lock file.

    Single-process deployment assumption: the Control Center server and the
    CLI share one machine. The lock file lives in 90_System/control_center/
    runtime/ (never in the Vault knowledge content). A stale lock older than
    judge_timeout_seconds is taken over (crash recovery).
    """
    lock_path = _preflight_runtime_dir() / "review_preflight.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        return True
    except FileExistsError:
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return True
        if age > pc["judge_timeout_seconds"]:
            try:
                lock_path.unlink()
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("ascii"))
                os.close(fd)
                return True
            except OSError:
                return False
        return False
    except OSError:
        return False


def _release_preflight_file_lock() -> None:
    lock_path = _preflight_runtime_dir() / "review_preflight.lock"
    try:
        lock_path.unlink()
    except OSError:
        pass


def _preflight_stale() -> bool:
    run = last_preflight_run()
    if not run:
        return True  # never ran -> treat as stale / no data
    t = _parse_time(str(run.get("time") or ""))
    if not t:
        return True
    hours = int(_preflight_cfg().get("staleness_hours", 24))
    return (datetime.now() - t).total_seconds() > hours * 3600


def last_preflight_run() -> dict | None:
    """Most recent review_preflight_finished activity record (if any)."""
    for rec in reversed(_activity_records()):
        if rec.get("type") == "review_preflight_finished":
            return rec
    return None


def preflight_review_candidates(limit: int | None = None, trigger: str = "manual") -> dict:
    """One bounded Review Preflight pass over pending candidates.

    Shared by the CLI and the HTTP manual API (POST /api/review/preflight).
    Cache (input_fingerprint), judging lock, max_per_run and a cross-process
    lock file prevent duplicate LLM calls. Never modifies Wiki and never
    auto-approves. `trigger` is recorded in the audit log (manual/cli/scheduled).
    """
    pc = _preflight_cfg()
    if not pc["enabled"]:
        return {"ok": True, "enabled": False, "trigger": trigger, "judged": 0, "reused": 0,
                "blocked": 0, "failed": 0, "skipped_judging": 0, "pending": 0,
                "more_pending": False, "pending_remaining": 0, "llm_called": False,
                "duration_ms": 0, "details": [], "message": "review_preflight disabled"}
    if not _acquire_preflight_file_lock(pc):
        return {"ok": True, "enabled": True, "trigger": trigger, "skipped": True,
                "message": "已有 Review Preflight 正在运行（跨进程锁）", "judged": 0, "reused": 0,
                "blocked": 0, "failed": 0, "skipped_judging": 0, "pending": 0,
                "more_pending": False, "pending_remaining": 0, "llm_called": False,
                "duration_ms": 0, "details": []}
    started = time.perf_counter()
    limit = int(limit) if limit else int(pc["max_per_run"])
    actions = [a for a in build_actions() if a.get("status") == "pending"]
    cfg = load_config(str(RAG_DIR / "config.yaml"))
    records = _load_review_records()
    judged = reused = blocked = failed = skipped = 0
    processed = 0
    details = []
    _append_log({"action_id": "", "type": "review_preflight_started", "target": "", "actor": trigger,
                 "ai_recommendation": "preflight", "user_decision": trigger, "result": "started",
                 "message": f"Review Preflight 开始（trigger={trigger}）"})
    try:
        with _PREFLIGHT_LOCK:
            for action in actions:
                decision = _preflight_decision(action["id"], records, pc)
                if decision == "valid":
                    reused += 1
                    details.append({"action_id": action["id"], "status": "reused",
                                    "classification": records.get(action["id"], {}).get("classification")})
                    continue
                if decision == "judging":
                    skipped += 1
                    continue
                if processed >= limit:
                    break
                r = _judge_one(action, cfg, records, pc, force=False)
                processed += 1
                if r["status"] == "blocked":
                    blocked += 1
                elif r["status"] == "judging":
                    skipped += 1
                elif r["status"] == "failed":
                    failed += 1
                else:
                    judged += 1
                details.append({"action_id": action["id"], "status": r["status"],
                                "classification": r.get("classification")})
            records = _load_review_records()
            more_pending = sum(1 for a in actions if _preflight_decision(a["id"], records, pc) == "needs_judge")
    finally:
        _release_preflight_file_lock()
    duration_ms = int((time.perf_counter() - started) * 1000)
    llm_called = (judged + failed) > 0
    _append_log({"action_id": "", "type": "review_preflight_finished", "target": "", "actor": trigger,
                 "ai_recommendation": "preflight", "user_decision": trigger, "result": "finished",
                 "trigger": trigger, "processed": processed, "judged": judged, "reused": reused,
                 "blocked": blocked, "failed": failed, "pending": more_pending,
                 "duration_ms": duration_ms, "llm_called": llm_called,
                 "message": f"Review Preflight 完成（trigger={trigger}，judged={judged}，reused={reused}，failed={failed}）"})
    return {"ok": True, "enabled": True, "trigger": trigger, "judged": judged, "reused": reused,
            "blocked": blocked, "failed": failed, "skipped_judging": skipped, "pending": more_pending,
            "more_pending": more_pending > 0, "pending_remaining": more_pending,
            "llm_called": llm_called, "duration_ms": duration_ms, "details": details,
            "message": f"judged={judged}, reused={reused}, failed={failed}, pending={more_pending}"}


def _short_review_reason(record: dict | None) -> str:
    if not record:
        return "尚未运行 LLM Judge"
    status = record.get("judge_status")
    if status == "completed":
        return _judge_review_reason(record.get("result") or {})
    if status == "failed":
        return "AI Judge 未完成（" + str((record.get("result") or {}).get("reason") or "未知原因") + "），需要人工审核"
    if status == "blocked":
        return "无法进行 LLM Judge（" + str(record.get("reason") or "缺少可读取来源或目标") + "），需要人工审核"
    if status == "judging":
        return "AI Judge 运行中…"
    return "尚未运行 LLM Judge"


def review_counts(actions: list | None = None) -> dict:
    """Unified Review counts — single source metrics.collect_review_metrics().

    Weekly Review and Control Center share the exact same counting logic.
    pending_human = needs_review + judge_failed; not_judged is a separate bucket.
    """
    return review_metrics.collect_review_metrics(
        vault_root=VAULT_ROOT,
        review_records_path=REVIEW_RECORDS,
        gap_path=_gap_path(),
        config_path=str(RAG_DIR / "config.yaml"),
    )


def review_context(action_id: str) -> dict:
    """Build the Review Context workbench for a pending action (read-only)."""
    action = next((a for a in build_actions() if a["id"] == action_id), None)
    if action is None:
        return {"ok": False, "message": f"action not found: {action_id}"}
    if action["type"] == "wiki_review":
        return _wiki_review_context(action)
    if action["type"] == "knowledge_gap":
        return _gap_context(action)
    return _generic_context(action)
