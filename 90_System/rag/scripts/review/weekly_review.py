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
import health  # noqa: E402
import insight  # noqa: E402

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
    r = m.get("review") or {}
    lines.append(
        f"Review 分流：AI 已验证 {r.get('judge_passed', '—')} / 待人工 {r.get('pending_human', '—')} / "
        f"Judge 失败 {r.get('judge_failed', '—')}。"
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


def _pct_line(value) -> str:
    return f"{value}%" if value is not None else "N/A"


def _review_queue(m: dict) -> list[dict]:
    """Human review queue from the unified Review metrics (judge split).

    judge_passed (AI 已验证) is excluded; needs_review / judge_failed /
    blocked / not_judged / judging are shown. Stale risk stays separate.
    """
    queue = []
    for it in m["review"].get("items", []):
        if it.get("classification") == "judge_passed":
            continue  # AI 已验证，不进人工队列
        queue.append({
            "priority": "high" if it.get("judge_status") == "failed" else "medium",
            "type": it.get("type", "review"),
            "title": it.get("title", ""),
            "object": it.get("action_id", ""),
            "reason": it.get("reason") or "需要人工审核",
            "evidence": f"classification={it.get('classification') or 'not_judged'}",
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


def _health_section(h: dict) -> list[str]:
    lines = []
    score = h.get("score")
    lines.append(f"- Health Score：{score if score is not None else '—'}（{h.get('status', 'not_calculated')}）")
    for d in (h.get("dimensions") or {}).values():
        ds = d.get("score")
        lines.append(f"  - {d.get('label')}：{ds if ds is not None else 'N/A'}（{d.get('status')}）")
    factors = h.get("factors") or []
    lines.append("  - 影响因素：")
    if not factors:
        lines.append("    - 无")
    for f in factors[:8]:
        mark = "−" if f.get("type") == "negative" else "+"
        lines.append(f"    - {mark} {f.get('metric')} = {f.get('value')}（impact={f.get('impact')}）")
    return lines


def _weekly_status(m: dict) -> list[str]:
    """5-second status block (transition; real charts come in Phase B)."""
    r = m["review"]
    h = m["health"]
    g = m["growth"]
    gaps = m["gaps"]
    projects = m["projects"]
    baseline = m.get("baseline") or {}
    lines = []
    if h["status"] == "ok":
        lines.append(f"- 🟢 Knowledge OS：运行正常（health=ok，errors={h['errors']}）")
    else:
        lines.append(f"- 🔴 Knowledge OS：异常（health={h['status']}，errors={h['errors']}）")
    growth_txt = f"本周新增 {g['new_this_week']} 篇"
    if baseline.get("is_baseline_period"):
        growth_txt += f"（⚠ {baseline.get('note', '初始化基线')}）"
    lines.append(f"- 📈 Knowledge：{growth_txt}　变化：—")
    lines.append(
        f"- 🟡 Review：{r['pending_human']} 项待人工处理（AI 已验证 {r['judge_passed']} / "
        f"Judge 失败 {r['judge_failed']} / 判断中 {r['judging']}）"
    )
    lines.append(f"- 🟠 Gaps：{gaps['knowledge_gaps_pending']} 个知识缺口待处理")
    if projects:
        ps = "；".join(f"{p['name']}={p['status'] or 'N/A'}" for p in projects[:3])
        lines.append(f"- 🔵 Projects：{len(projects)} 个项目（{ps}）")
    else:
        lines.append("- 🔵 Projects：暂无项目状态数据")
    stale = len(m["stale_risk"])
    lines.append(f"- {'🟢' if stale == 0 else '🟡'} Risk：{stale} 项 stale 复查风险")
    lines.append("")
    lines.append("| 指标 | 当前值 | 状态 |")
    lines.append("|---|---:|---|")
    lines.append("| Knowledge Health | 未计算 | — |")
    lines.append(f"| Wiki 总量 | {m['wiki']['wiki_total']} | — |")
    lines.append(f"| 本周新增 | {g['new_this_week']} | {'⚠ 初始化基线' if baseline.get('is_baseline_period') else '—'} |")
    lines.append(f"| AI 已验证 | {r['judge_passed']} | ✅ |")
    lines.append(f"| 待人工审核 | {r['pending_human']} | {'⚠' if r['pending_human'] else '✅'} |")
    lines.append(f"| Judge 失败 | {r['judge_failed']} | {'⚠' if r['judge_failed'] else '✅'} |")
    lines.append(f"| 知识缺口 | {gaps['knowledge_gaps_pending']} | {'⚠' if gaps['knowledge_gaps_pending'] else '✅'} |")
    active = sum(1 for p in projects if p.get("status") in ("active", "planning"))
    lines.append(f"| 活跃项目 | {active} | — |")
    return lines


def render_report(m: dict, summary: str, model_label: str = "unknown") -> str:
    w, g, gaps = m["wiki"], m["growth"], m["gaps"]
    h = m["health"]
    queue = _review_queue(m)
    lines: list[str] = []
    lines.append("# Knowledge OS Weekly Review")
    lines.append("")
    lines.append(f"- period：`{m['period']}`")
    lines.append(f"- generated_at：`{m['generated_at']}`")
    lines.append("")
    lines.append("## Weekly Status")
    lines.append("")
    lines.extend(_weekly_status(m))
    he = health.calculate_health(m)
    lines.append("")
    lines.append("## Health")
    lines.append("")
    lines.extend(_health_section(he))
    lines.append("")
    lines.append("## 1. 本周摘要")
    lines.append("")
    lines.append(summary)
    lines.append("")
    lines.append("## 2. Knowledge Growth")
    lines.append("")
    baseline = m.get("baseline") or {}
    if baseline.get("is_baseline_period"):
        lines.append(f"- 本周新增 Wiki：{g['new_this_week']}（⚠ {baseline.get('note', '初始化基线')}）")
    else:
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
    lines.append(f"- draft Wiki：{w['review_pending']}（仅 Wiki 状态，非人工审核队列；人工队列见第 6 节 Review Queue）")
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
    r = m["review"]
    lines.append(f"- AI 已验证：{r['judge_passed']}")
    lines.append(f"- 待人工审核：{r['pending_human']}（needs_review {r['needs_review']} + judge_failed {r['judge_failed']}）")
    if r.get("judging"):
        lines.append(f"- 判断中：{r['judging']}")
    if r.get("not_judged"):
        lines.append(f"- 未判断：{r['not_judged']}")
    human_items = [q for q in queue if q["type"] != "stale_risk"]
    if not human_items:
        lines.append("- 暂无待人工处理事项。")
    for q in human_items:
        lines.append(f"- [{q['priority']}] {q['type']}：{q['title']}（{q['reason']}）")
    stale_items = [q for q in queue if q["type"] == "stale_risk"]
    if stale_items:
        lines.append("- Stale 复查风险：")
        for q in stale_items:
            lines.append(f"  - [{q['priority']}] {q['title']}（{q['reason']}）")
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
    lines.append("## 8.5 AI Weekly Insight")
    lines.append("")
    ins = insight.load_cached_insight(m["period"], REVIEW_ROOT, model_label)
    if ins and ins.get("status") == "available" and ins.get("insight"):
        it = ins["insight"]
        lines.append(f"- summary：{it.get('summary', '')}")
        for a in (it.get("actions") or [])[:3]:
            lines.append(f"- [{a.get('priority', 'medium')}] {a.get('action', '')}（{a.get('reason', '')}）")
    else:
        lines.append("- AI Insight 未生成或不可用（确定性周报不受影响）。")
    lines.append("")
    lines.append("## 8.6 RAG Quality")
    lines.append("")
    re_ = m.get("rag_evaluation")
    if not re_ or not re_.get("run_id"):
        lines.append("- 暂无 RAG Evaluation 数据（先运行 Benchmark 后再测量 RAG 质量）。")
    else:
        rq = re_.get("metrics") or {}
        lines.append(f"- Answer Coverage：{_pct_line(rq.get('answer_coverage'))}"
                     f"（run_id=`{re_.get('run_id')}`，{re_.get('query_count')} 条，mode={re_.get('mode')}）")
        lines.append(f"- Knowledge Missing：{_pct_line(rq.get('knowledge_missing_rate'))}"
                     f"（system_error={rq.get('system_error', 0)}）")
        lines.append(f"- Wiki Hit Rate：{_pct_line(rq.get('wiki_hit_rate'))}　"
                     f"Wiki Fallback Rate：{_pct_line(rq.get('wiki_fallback_rate'))}　"
                     f"Fallback Recovery：{_pct_line(rq.get('wiki_fallback_recovery_rate'))}")
        lines.append(f"- RAW Answer Rate：{_pct_line(rq.get('raw_answer_rate'))}　"
                     f"RAW Evidence Sufficient：{_pct_line(rq.get('raw_evidence_sufficient_rate'))}")
        lines.append(f"- Evidence Avg Window：{rq.get('avg_window_count', 'N/A')}　"
                     f"P50 Latency：{rq.get('p50_total_ms', 'N/A')}ms　P95 Latency：{rq.get('p95_total_ms', 'N/A')}ms")
        tf = rq.get("top_failures") or []
        lines.append("### Main Failure Reasons")
        if tf:
            for f in tf[:5]:
                lines.append(f"- {f.get('type')}：{f.get('count')}（{_pct_line(f.get('rate'))}）")
        else:
            lines.append("- 无失败。")
        gs = rq.get("gap_signals") or {}
        lines.append("### Knowledge Gap Signals")
        lines.append(
            f"- Likely Knowledge Gap：{gs.get('likely_knowledge_gap', 0)}　"
            f"Evidence Gap：{gs.get('evidence_gap', 0)}　"
            f"Retrieval Gap：{gs.get('retrieval_gap', 0)}（Retrieval Gap 需人工确认）"
        )
        gaps = re_.get("gaps") or {}
        if gaps.get("open") is not None or gaps.get("resolved") is not None:
            lines.append(
                f"- Open Knowledge Gaps：{gaps.get('open', 0)}　"
                f"Resolved Gaps：{gaps.get('resolved', 0)}"
            )
        diff = re_.get("diff")
        if diff:
            lines.append(
                f"- Query Recovery：{diff.get('recovered', 0)}　"
                f"Regression：{diff.get('regressed', 0)}"
                f"（{diff.get('before_run')} → {diff.get('after_run')}）"
            )
            rc = diff.get("regression_classes") or {}
            if rc:
                lines.append(
                    f"- 回归分类：REAL_REGRESSION={rc.get('REAL_REGRESSION', 0)}　"
                    f"JUDGE_VARIANCE={rc.get('JUDGE_VARIANCE', 0)}　UNKNOWN={rc.get('UNKNOWN', 0)}"
                )
        gd = re_.get("golden")
        if gd:
            lines.append(
                f"- Golden Set：{gd.get('reviewed', 0)}/{gd.get('total', 0)} reviewed　"
                f"Answer Correct：{gd.get('answer_correct_count', 0)}/{gd.get('total', 0)}"
                f"（assessed {gd.get('answer_correct_assessed', 0)}）　"
                f"Evidence Support：{gd.get('evidence_supported_count', 0)}/{gd.get('total', 0)}"
            )
            if gd.get("sample_too_small"):
                lines.append(f"- ⚠ Golden 样本过小（{gd.get('reviewed', 0)} < 10），正确率仅作参考")
        jv = re_.get("judge_variance")
        if jv:
            lines.append(
                f"- Judge Flip Rate：{jv.get('flip_rate', 'N/A')}%　"
                f"Judge Stable Rate：{jv.get('stable_rate', 'N/A')}%"
                f"（tested {jv.get('tested_queries', 0)}）"
            )
            if jv.get("sample_too_small"):
                lines.append("- ⚠ Judge 重复样本 < 3，稳定率/翻转率仅作参考")
        src = re_.get("sources") or {}
        if src.get("verified") is not None or src.get("p0_p1_missing") is not None:
            lines.append(
                f"- Verified Sources：{src.get('verified', 0)}　"
                f"P0/P1 Source Gaps：{len(src.get('p0_p1_missing') or [])}"
            )
        wc = re_.get("wiki_compilation")
        if wc:
            lines.append(
                f"- Source-backed Wiki Drafts：{wc.get('tasks', 0)}　"
                f"Queries Recovered This Week：{wc.get('recovered_queries', 0)}　"
                f"Still Failed：{wc.get('still_failed', 0)}"
            )
        if gaps.get("open_p0") is not None or gaps.get("open_p1") is not None:
            lines.append(
                f"- Open P0 Gaps：{gaps.get('open_p0', 0)}　"
                f"Open P1 Gaps：{gaps.get('open_p1', 0)}"
            )
        bl = re_.get("baseline")
        if bl:
            lines.append(
                f"- Baseline：{_pct_line(bl.get('coverage'))}（{bl.get('baseline_id')}，{bl.get('status')}）　"
                f"Current Verification：{_pct_line(bl.get('current_coverage'))}　"
                f"Delta：{bl.get('delta_pp')}pp　Status：{bl.get('check_status')}"
            )
            if bl.get("delta_pp") == 0 and bl.get("status") == "UNVERIFIED":
                lines.append("- ⚠ Baseline 未正式确立：存在未批准 Wiki（WSL 仍为 draft），批准后重跑确认可转 STABLE")
        gov = re_.get("governance")
        if gov:
            lines.append(
                f"- Governance：{gov.get('status')}　Auto Verify：{'ON' if not gov.get('required') else 'PENDING'}"
                f"　Evaluation Required：{'YES' if gov.get('required') else 'NO'}"
                f"（{', '.join(gov.get('reasons') or []) or '无'}）"
                f"　Last Check：{gov.get('last_check') or '—'}"
            )
            if gov.get("required"):
                lines.append("- ⚠ 存在待验证知识变更：Scheduler/Preflight 将自动运行 Benchmark + Baseline Check")
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

def build_snapshot(m: dict, model_label: str = "unknown") -> dict:
    w, g, gaps, h = m["wiki"], m["growth"], m["gaps"], m["health"]
    he = health.calculate_health(m)
    return {
        "snapshot_schema_version": "1.0",
        "metrics_schema_version": "1.0",
        "period": m["period"],
        "generated_at": m["generated_at"],
        "wiki_total": w["wiki_total"],
        "wiki_draft": w["wiki_draft"],
        "wiki_reviewed": w["wiki_reviewed"],
        "wiki_stable": w["wiki_stable"],
        "review_pending": m["review"]["pending_human"],
        "review": m["review"],
        "baseline": m.get("baseline") or {"is_baseline_period": False, "note": None},
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
        "health_score": he.get("score"),
        "health": {"status": h["status"], "errors": h["errors"], "warnings": h["warnings"]},
        "health_algorithm_version": he.get("algorithm_version", health.HEALTH_ALGORITHM_VERSION),
        "health_status": he.get("status"),
        "health_dimensions": he.get("dimensions"),
        "health_factors": he.get("factors"),
        "insight_status": insight.load_cached_insight(m["period"], REVIEW_ROOT, model_label).get("status") if insight.load_cached_insight(m["period"], REVIEW_ROOT, model_label) else None,
        "insight_prompt_version": insight.load_cached_insight(m["period"], REVIEW_ROOT, model_label).get("prompt_version") if insight.load_cached_insight(m["period"], REVIEW_ROOT, model_label) else None,
        "growth_delta": {"new_wiki": g["new_this_week"], "updated_wiki": g["updated_this_week"]},
        "activity_count": len(m["activity"]),
        "rag_evaluation": m.get("rag_evaluation"),
    }


# ---------------------------------------------------------------- main

def _log_run(record: dict) -> None:
    """Append a structured weekly_review_run event to activity_log.jsonl (reuse)."""
    log = VAULT_ROOT / "90_System" / "control_center" / "activity_log.jsonl"
    try:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _insight_model_label(cfg) -> str:
    llm = cfg.get("llm") or {}
    model = llm.get("model")
    if isinstance(model, dict):
        model = model.get("name")
    return f"{llm.get('provider', 'unknown')}:{model or 'unknown'}"


def run_weekly_review(args) -> int:
    """Unified Weekly Review Pipeline (Phase E).

    Stages: preflight -> metrics -> trend -> health -> snapshot -> persist -> insight.
    Exit codes: 0=success, 1=success_with_warnings, 3=critical failure.
    AI (insight) failure never blocks the deterministic report.
    Same-period rerun is idempotent; --insight-only repairs a missing insight.
    """
    import time as _time
    run_id = datetime.now().strftime("wr-%Y%m%dT%H%M%S%f")
    started = _time.perf_counter()
    stages: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []
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

    def finish(status: str, action: str) -> dict:
        record = {
            "run_id": run_id, "type": "weekly_review_run", "period": period,
            "started_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_ms": int((_time.perf_counter() - started) * 1000),
            "status": status, "action": action,
            "stages": stages, "warnings": warnings, "errors": errors,
        }
        _log_run(record)
        print(json.dumps(record, ensure_ascii=False))
        return record

    stages["preflight"] = "success"
    cfg = metrics.load_config_public(args.config)
    model_label = _insight_model_label(cfg)
    complete = md_path.exists() and snap_path.exists()
    cached_insight = insight.load_cached_insight(period, out_root, model_label)
    insight_ok = bool(cached_insight and cached_insight.get("status") == "available")

    # ---- idempotency / insight-only repair ----
    if complete and not args.force:
        if args.insight_only or (args.insight and not insight_ok):
            stages["snapshot"] = "reuse"
            stages["persist"] = "reuse"
        elif insight_ok or not args.insight:
            stages["snapshot"] = "reuse"
            stages["persist"] = "reuse"
            stages["insight"] = "cached" if insight_ok else "skipped"
            finish("success", "already_complete")
            return 0
        else:
            warnings.append("insight.json 缺失（已请求 --insight 但不可用）")
            stages["snapshot"] = "reuse"
            stages["persist"] = "reuse"
            stages["insight"] = "skipped"
            finish("success_with_warnings", "already_complete_no_insight")
            return 1

    # ---- metrics (critical) ----
    try:
        m = metrics.collect_metrics(period=period, config_path=args.config, now=now)
        stages["metrics"] = "success"
    except Exception as exc:
        stages["metrics"] = "failed"
        errors.append(f"metrics: {exc}")
        finish("failed", "metrics_failed")
        return 3

    # ---- trend (recoverable) ----
    try:
        trends = metrics.build_weekly_trends(metrics.collect_weekly_snapshots())
        stages["trend"] = "success"
    except Exception as exc:
        trends = {}
        stages["trend"] = "warning"
        warnings.append(f"trend: {exc}")

    # ---- health (deterministic) ----
    try:
        he = health.calculate_health(m)
        stages["health"] = "success"
    except Exception as exc:
        he = {"score": None, "status": "not_calculated", "dimensions": {}, "factors": [],
              "algorithm_version": health.HEALTH_ALGORITHM_VERSION}
        stages["health"] = "warning"
        warnings.append(f"health: {exc}")

    # ---- snapshot + persist (critical for full run) ----
    insight_only = bool(args.insight_only and complete)
    if not insight_only:
        try:
            summary = ""
            if args.llm:
                summary = _llm_summary(m, cfg) or ""
            if not summary:
                summary = _deterministic_summary(m)
            md = render_report(m, summary, model_label)
            snap = build_snapshot(m, model_label)
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path.write_text(md, encoding="utf-8")
            snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stages["snapshot"] = "success"
            stages["persist"] = "success"
            print(f"written: {md_path}")
            print(f"written: {snap_path}")
        except Exception as exc:
            stages["snapshot"] = "failed"
            errors.append(f"snapshot/persist: {exc}")
            finish("failed", "persist_failed")
            return 3
    else:
        stages["snapshot"] = "reuse"
        stages["persist"] = "reuse"

    # ---- insight (optional / recoverable) ----
    if args.insight or args.insight_only:
        try:
            attention = health.build_attention(m)
            result = insight.generate_insight(m, he, trends, attention, cfg, model_label=model_label)
            insight.save_insight(period, result, out_root)
            if result.get("status") == "available":
                stages["insight"] = "success"
                print(f"written: {insight.insight_path(period, out_root)} (AI Insight available)")
            else:
                stages["insight"] = "warning"
                warnings.append(f"insight: {result.get('reason')}")
                print(f"AI Insight unavailable: {result.get('reason')}")
        except Exception as exc:
            stages["insight"] = "warning"
            warnings.append(f"insight: {exc}")
    else:
        stages["insight"] = "skipped"

    status = "success" if not warnings and not errors else "success_with_warnings"
    finish(status, "completed")
    return 0 if status == "success" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Knowledge OS weekly review")
    parser.add_argument("--week", default=None, help="ISO week, e.g. 2026-W33 (default: current week)")
    parser.add_argument("--force", action="store_true", help="regenerate even if the week already exists")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--llm", action="store_true", help="allow LLM natural-language summary (default: deterministic)")
    parser.add_argument("--out", default=None, help="override output root directory")
    parser.add_argument("--insight", action="store_true",
                        help="generate AI Weekly Insight (insight.json) for this period")
    parser.add_argument("--insight-only", action="store_true",
                        help="repair only the missing insight.json for an existing period")
    args = parser.parse_args()
    return run_weekly_review(args)


if __name__ == "__main__":
    raise SystemExit(main())
