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

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parent
SYSTEM_DIR = CTRL_DIR.parent
VAULT_ROOT = SYSTEM_DIR.parent
RAG_DIR = SYSTEM_DIR / "rag"
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.gaps import load_gaps, resolve_gap as _resolve_gap
from rag_engine.wiki import _slug  # noqa: F401 (re-exported for UI use)
from rag_engine.wiki_review import set_status
from rag_engine.wiki import read_frontmatter

REVIEW_DIR = RAG_DIR / "scripts" / "review"
if str(REVIEW_DIR) not in sys.path:
    sys.path.insert(0, str(REVIEW_DIR))
import metrics as review_metrics  # noqa: E402

REVIEW_ROOT = VAULT_ROOT / "40_Outputs" / "reviews" / "每周复盘"
SYNC_STATE = RAG_DIR / "database" / "sync_state.json"

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
        "inbox_files": len(inbox),
        "recent_activity": activity_timeline(limit=10),
    }


# ---------------------------------------------------------------- weekly review

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
                "report_path": md.relative_to(VAULT_ROOT).as_posix() if md.exists() else None,
                "snapshot_path": snap_path.relative_to(VAULT_ROOT).as_posix() if snap_path.exists() else None,
                "generated_at": snap.get("generated_at"),
                "wiki_total": snap.get("wiki_total"),
                "wiki_draft": snap.get("wiki_draft"),
                "wiki_reviewed": snap.get("wiki_reviewed"),
                "wiki_stable": snap.get("wiki_stable"),
                "knowledge_gaps_pending": snap.get("knowledge_gaps_pending"),
                "stale_count": len(snap.get("stale_items", [])),
                "health_status": (snap.get("health") or {}).get("status"),
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
    return {
        "last_sync": state.get("last_sync"),
        "last_sync_result": state.get("last_result"),
        "last_review": last_review,
        "next_review": _next_review_time(),
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