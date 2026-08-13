"""Knowledge OS Weekly Review generator (deterministic stats + optional LLM summary).

Usage:
    python weekly_review.py                 # current ISO week
    python weekly_review.py --week 2026-W33 # a specific week
    python weekly_review.py --force         # regenerate (overwrites in place)
    python weekly_review.py --llm           # allow LLM natural-language summary

Rules:
  - Same week = same artifact: files are written to
    40_Outputs/reviews/每周复盘/YYYY/WNN/weekly-review.md + snapshot.json
    and never duplicated (without --force an existing week is skipped).
  - All statistics come from metrics.py (deterministic). LLM is only allowed
    to summarize / suggest; if it fails or is disabled, the summary is built
    from deterministic facts. Project progress is never guessed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[2]
VAULT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics  # noqa: E402

REVIEW_ROOT = VAULT_ROOT / "40_Outputs" / "reviews" / "每周复盘"

PERIOD_RE = re.compile(r"^(\d{4})-W(\d{1,2})$")


# ---------------------------------------------------------------- summary

def _deterministic_summary(m: dict) -> str:
    w, g, gaps = m["wiki"], m["growth"], m["gaps"]
    h = m["health"]
    lines = [
        f"本周（{m['period']}）知识库共有 Wiki {w['wiki_total']} 篇"
        f"（draft {w['wiki_draft']} / reviewed {w['wiki_reviewed']} / stable {w['wiki_stable']}）。"
    ]
    if g["new_this_week"] or g["updated_this_week"]:
        lines.append(
            f"本周新增 Wiki {g['new_this_week']} 篇，更新 {g['updated_this_week']} 篇。"
        )
    else:
        lines.append("本周无 Wiki 新增或更新。")
    lines.append(
        f"待处理知识缺口 {gaps['knowledge_gaps_pending']} 条（累计 {gaps['knowledge_gaps_total']} 条）。"
    )
    if m["projects"]:
        ps = "；".join(
            f"{p['name']}（status={p['status'] or 'N/A'}，phase={p['phase'] or 'N/A'}，"
            f"progress={p['progress'] if p['progress'] is not None else 'N/A'}）"
            for p in m["projects"]
        )
        lines.append(f"项目：{ps}。")
    else:
        lines.append("项目：暂无项目状态数据。")
    lines.append(
        f"Stale 风险项 {len(m['stale_risk'])} 条；系统健康：{h['status']}"
        f"（errors={h['errors']}，warnings={h['warnings']}）。"
    )
    return "\n".join(lines)


def _llm_summary(m: dict, cfg: dict) -> str | None:
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("provider") or llm_cfg.get("provider") == "none":
        return None
    key_env = llm_cfg.get("api_key_env")
    if key_env and not os.environ.get(key_env):
        return None
    try:
        from rag_engine.llm import create_llm

        payload = {
            k: m[k] for k in ("wiki", "growth", "gaps", "projects", "stale_risk", "health")
        }
        context = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        question = "请根据以下确定性统计事实，用中文写一段 100~200 字的本周知识库摘要，只能陈述数据中出现的事实。"
        adapter = create_llm(cfg)
        text = adapter.generate(question, context)
        return text.strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------- render

def _fmt_date(dt) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "N/A"


def _review_queue(m: dict) -> list[dict]:
    queue = []
    for w in m["wiki"]["wikis"]:
        if w["status"] == "draft":
            queue.append({
                "priority": "medium",
                "type": "wiki_review",
                "title": w["title"],
                "object": w["path"],
                "reason": "draft Wiki 等待人工审核",
                "evidence": f"status={w['status']}",
            })
    for g in m["gaps"].get("pending_gaps", []):
        queue.append({
            "priority": g.get("priority", "medium"),
            "type": "knowledge_gap",
            "title": g.get("question", ""),
            "object": g.get("question", ""),
            "reason": "知识库证据不足记录的知识缺口",
            "evidence": "; ".join(g.get("related_sources", [])[:3]) or "无关联来源",
        })
    for s in m["stale_risk"]:
        queue.append({
            "priority": "high" if "review_required" in s["risk_factors"] else "medium",
            "type": "stale_risk",
            "title": s["title"],
            "object": s["path"],
            "reason": "存在复查风险",
            "evidence": ", ".join(s["risk_factors"]),
        })
    order = {"high": 0, "medium": 1, "low": 2}
    queue.sort(key=lambda q: order.get(q["priority"], 3))
    return queue


def _suggestions(m: dict, queue: list[dict]) -> list[str]:
    out = []
    high = [q for q in queue if q["priority"] == "high"]
    med = [q for q in queue if q["priority"] == "medium"]
    for q in high[:5]:
        out.append(f"🔴 {q['title']}（{q['reason']}，证据：{q['evidence']}）")
    for q in med[:8]:
        out.append(f"🟡 {q['title']}（{q['reason']}）")
    if m["gaps"]["knowledge_gaps_pending"] == 0 and not high and not med:
        out.append("🟢 本周无高/中优先级待处理事项。")
    if not any(p["progress"] is not None for p in m["projects"]):
        out.append("📋 项目进度字段缺失：请在 00_项目索引.md frontmatter 补充 progress 后再展示完成率。")
    return out


def _unverified(m: dict) -> list[str]:
    out = []
    for p in m["projects"]:
        if p["progress"] is None:
            out.append(f"{p['name']}：progress 无结构化来源（Project status source insufficient），不得猜测完成率。")
        if not p.get("phase"):
            out.append(f"{p['name']}：phase 未在 frontmatter 中声明。")
    for g in m["gaps"].get("pending_gaps", []):
        if not g.get("related_sources"):
            out.append(f"知识缺口“{g.get('question', '')}”缺少关联来源，结论待验证。")
    return out


def render_report(m: dict, summary: str) -> str:
    w, g, gaps = m["wiki"], m["growth"], m["gaps"]
    h = m["health"]
    queue = _review_queue(m)
    lines: list[str] = []
    lines.append("# Knowledge OS Weekly Review")
    lines.append("")
    lines.append(f"- period：`{m['period']}`")
    lines.append(f"- generated_at：`{m['generated_at']}`")
    lines.append("")
    lines.append("## 1. 本周摘要")
    lines.append("")
    lines.append(summary)
    lines.append("")
    lines.append("## 2. Knowledge Growth")
    lines.append("")
    lines.append(f"- 本周新增 Wiki：{g['new_this_week']}")
    lines.append(f"- 本周更新 Wiki：{g['updated_this_week']}")
    if g["new_items"]:
        lines.append("  - 新增：" + "；".join(g["new_items"]))
    if g["updated_items"]:
        lines.append("  - 更新：" + "；".join(g["updated_items"]))
    lines.append("")
    lines.append("## 3. Wiki 状态")
    lines.append("")
    lines.append(f"- 总数：{w['wiki_total']}（draft {w['wiki_draft']} / reviewed {w['wiki_reviewed']} / stable {w['wiki_stable']} / unknown {w['wiki_unknown']}）")
    lines.append(f"- 待审核（draft）：{w['review_pending']}")
    lines.append("")
    lines.append("## 4. Knowledge Gaps")
    lines.append("")
    lines.append(f"- 待处理：{gaps['knowledge_gaps_pending']} / 累计：{gaps['knowledge_gaps_total']}")
    for g_ in gaps.get("pending_gaps", []):
        lines.append(
            f"- [{g_.get('priority', 'medium')}] {g_.get('question', '')}"
            f"（suggested: {g_.get('suggested_action', '')}）"
        )
    lines.append("")
    lines.append("## 5. Project Status")
    lines.append("")
    if not m["projects"]:
        lines.append("- 暂无项目状态数据。")
    for p in m["projects"]:
        lines.append(f"- {p['name']}")
        lines.append(f"  - status：{p['status'] or 'N/A'} | phase：{p['phase'] or 'N/A'} | updated：{p['updated'] or 'N/A'}")
        lines.append(f"  - progress：{p['progress'] if p['progress'] is not None else 'N/A（未提供结构化数据，禁止猜测）'}")
        lines.append(f"  - next_step：{p['next_step'] or 'N/A'}")
        lines.append(f"  - blockers：{', '.join(p['blockers']) if p['blockers'] else '无'}")
    lines.append("")
    lines.append("## 6. Review Queue")
    lines.append("")
    if not queue:
        lines.append("- 暂无待处理事项。")
    for q in queue:
        lines.append(f"- [{q['priority']}] {q['type']}：{q['title']}（{q['reason']}）")
    lines.append("")
    lines.append("## 7. Stale Risk")
    lines.append("")
    if not m["stale_risk"]:
        lines.append("- 无（本报告将以下信号定义为“复查风险”，不判定为“知识已过期”）。")
    for s in m["stale_risk"]:
        lines.append(
            f"- {s['path']}（status={s['status']}，updated={s['updated']}，"
            f"review_required={str(s['review_required']).lower()}，confidence={s['confidence']}）"
            f"：{', '.join(s['risk_factors'])}"
        )
    lines.append("")
    lines.append("## 8. Activity")
    lines.append("")
    if not m["activity"]:
        lines.append("- 本周无活动记录。")
    for a in m["activity"][:30]:
        lines.append(f"- `{a['timestamp']}` [{a['type']}/{a['source']}] {a['object'] or ''}：{a['summary']}")
    lines.append("")
    lines.append("## 9. System Health")
    lines.append("")
    lines.append(f"- 综合状态：{h['status']}（errors={h['errors']}，warnings={h['warnings']}）")
    lines.append(f"- RAG：{h['rag']['ok']}（{h['rag']['summary']}）")
    lines.append(f"- Wiki：{h['wiki']['ok']}（errors={h['wiki']['error']}，warnings={h['wiki']['warning']}）")
    lines.append(f"- Architecture：{h['architecture']['ok']}（{h['architecture']['summary']}）")
    lines.append("")
    lines.append("## 10. 本周建议")
    lines.append("")
    for s in _suggestions(m, queue):
        lines.append(f"- {s}")
    lines.append("")
    lines.append("## 11. 待验证事项")
    lines.append("")
    unverified = _unverified(m)
    if not unverified:
        lines.append("- 无。")
    for u in unverified:
        lines.append(f"- {u}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- snapshot

def build_snapshot(m: dict) -> dict:
    w, g, gaps, h = m["wiki"], m["growth"], m["gaps"], m["health"]
    return {
        "period": m["period"],
        "generated_at": m["generated_at"],
        "wiki_total": w["wiki_total"],
        "wiki_draft": w["wiki_draft"],
        "wiki_reviewed": w["wiki_reviewed"],
        "wiki_stable": w["wiki_stable"],
        "review_pending": w["review_pending"],
        "knowledge_gaps_pending": gaps["knowledge_gaps_pending"],
        "knowledge_gaps_total": gaps["knowledge_gaps_total"],
        "stale_items": [
            {"path": s["path"], "status": s["status"], "risk_factors": s["risk_factors"]}
            for s in m["stale_risk"]
        ],
        "projects": [
            {
                "name": p["name"],
                "status": p["status"],
                "phase": p["phase"],
                "progress": p["progress"],
                "next_step": p["next_step"],
                "blockers": p["blockers"],
                "updated": p["updated"],
            }
            for p in m["projects"]
        ],
        "health_score": None,
        "health": {"status": h["status"], "errors": h["errors"], "warnings": h["warnings"]},
        "growth_delta": {"new_wiki": g["new_this_week"], "updated_wiki": g["updated_this_week"]},
        "activity_count": len(m["activity"]),
    }


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Knowledge OS weekly review")
    parser.add_argument("--week", default=None, help="ISO week, e.g. 2026-W33 (default: current week)")
    parser.add_argument("--force", action="store_true", help="regenerate even if the week already exists")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--llm", action="store_true", help="allow LLM natural-language summary (default: deterministic)")
    parser.add_argument("--out", default=None, help="override output root directory")
    args = parser.parse_args()

    now = datetime.now()
    period = args.week or metrics.current_iso_week(now)
    mch = PERIOD_RE.match(period)
    if not mch:
        print(f"invalid --week: {period!r} (expected YYYY-WNN)", file=sys.stderr)
        return 2
    year, week_num = mch.group(1), int(mch.group(2))

    out_root = Path(args.out) if args.out else REVIEW_ROOT
    out_dir = out_root / year / f"W{week_num:02d}"
    md_path = out_dir / "weekly-review.md"
    snap_path = out_dir / "snapshot.json"

    if (md_path.exists() or snap_path.exists()) and not args.force:
        print(f"weekly review already exists for {period}: {out_dir}")
        print("use --force to regenerate (same week = same artifact, files overwritten in place)")
        return 0

    cfg = metrics.load_config_public(args.config)
    m = metrics.collect_metrics(period=period, config_path=args.config, now=now)

    summary: str | None = None
    if args.llm:
        summary = _llm_summary(m, cfg)
    if not summary:
        summary = _deterministic_summary(m)

    md = render_report(m, summary)
    snap = build_snapshot(m)

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {md_path}")
    print(f"written: {snap_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
