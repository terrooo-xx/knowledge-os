"""AI Weekly Insight (Phase D2): structured LLM interpretation of deterministic facts.

Pipeline: metrics -> health -> trend -> evidence -> LLM -> validator -> insight.
The LLM is never a data source: it only interprets the structured input. Any
hallucinated metric value is rejected (fail-closed). Results are cached per
snapshot period (insight.json) keyed by prompt_version + model.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[2]
VAULT_ROOT = Path(__file__).resolve().parents[4]
INSIGHT_PROMPT = RAG_DIR / "prompts" / "weekly_insight.md"
PROMPT_VERSION = "weekly_insight_v1"
SCHEMA_VERSION = "1.0"

# 只允许 AI 引用这些已知指标（用于幻觉检测）
KNOWN_METRICS = {
    "wiki_total", "wiki_new", "wiki_updated", "review_pending", "judge_passed",
    "judge_failed", "gaps_pending", "gaps_resolved", "stale",
    "projects_active", "projects_blocked",
}
MAX_ACTIONS = 3


# ---------------------------------------------------------------- input

def build_insight_input(metrics: dict, health: dict, trends: dict, attention: list) -> dict:
    review = metrics.get("review") or {}
    gaps = metrics.get("gaps") or {}
    wiki = metrics.get("wiki") or {}
    projects = metrics.get("projects") or []
    return {
        "period": metrics.get("period"),
        "metrics": {
            "wiki_total": wiki.get("wiki_total"),
            "wiki_new": (metrics.get("growth") or {}).get("new_this_week"),
            "wiki_updated": (metrics.get("growth") or {}).get("updated_this_week"),
            "review_pending": review.get("pending_human"),
            "judge_passed": review.get("judge_passed"),
            "judge_failed": review.get("judge_failed"),
            "gaps_pending": gaps.get("knowledge_gaps_pending"),
            "gaps_resolved": gaps.get("knowledge_gaps_resolved"),
            "stale": len(metrics.get("stale_risk") or []),
            "projects_active": sum(1 for p in projects if p.get("status") == "active"),
            "projects_blocked": sum(1 for p in projects if p.get("status") == "blocked"),
        },
        "health": {
            "score": health.get("score"),
            "status": health.get("status"),
            "dimensions": {
                k: {"score": d.get("score"), "status": d.get("status")}
                for k, d in (health.get("dimensions") or {}).items()
            },
        },
        "wow": {
            k: {"available": v.get("available"), "current": v.get("current"),
                "previous": v.get("previous"), "delta": v.get("delta"),
                "delta_percent": v.get("delta_percent"), "direction": v.get("direction"),
                "health_effect": v.get("health_effect")}
            for k, v in (trends.get("wow") or {}).items()
        },
        "four_week": {
            k: {"periods": v.get("periods"), "points": v.get("points")}
            for k, v in (trends.get("four_week") or {}).items()
        },
        "attention": attention,
        "evidence": [
            {"type": "review", "metric": "review_pending", "current": review.get("pending_human")},
            {"type": "gaps", "metric": "gaps_pending", "current": gaps.get("knowledge_gaps_pending")},
            {"type": "stale", "metric": "stale", "current": len(metrics.get("stale_risk") or [])},
            {"type": "health", "metric": "health_score", "current": health.get("score")},
        ],
    }


# ---------------------------------------------------------------- parse / validate

def _extract_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _facts_map(insight_input: dict) -> dict:
    facts = {}
    for k, v in (insight_input.get("metrics") or {}).items():
        if k in KNOWN_METRICS and v is not None:
            facts[k] = v
    return facts


def validate_insight(data: dict, insight_input: dict) -> tuple[bool, str]:
    """Schema + hallucinated-metric validation (fail-closed)."""
    for field in ("summary", "changes", "attention", "actions"):
        if field not in data:
            return False, f"missing_field:{field}"
    if not isinstance(data.get("summary"), str) or not data["summary"].strip():
        return False, "summary_not_string"
    for field in ("changes", "attention", "actions"):
        if not isinstance(data.get(field), list):
            return False, f"{field}_not_list"
    if len(data.get("actions", [])) > MAX_ACTIONS:
        return False, f"actions_exceed_{MAX_ACTIONS}"
    facts = _facts_map(insight_input)
    periods = set()
    for k, v in (insight_input.get("four_week") or {}).items():
        periods.update(v.get("periods") or [])
    for item in data.get("changes", []) + data.get("attention", []):
        for ev in item.get("evidence") or []:
            metric = ev.get("metric")
            if metric == "health_score":
                continue
            if metric in facts and ev.get("current") is not None:
                if int(ev["current"]) != int(facts[metric]):
                    return False, f"hallucinated_metric:{metric}:got={ev['current']},real={facts[metric]}"
    for item in data.get("changes", []) + data.get("attention", []):
        for ev in item.get("evidence") or []:
            if ev.get("type") == "period" and ev.get("period") not in periods:
                return False, f"unknown_period:{ev.get('period')}"
    return True, "ok"


# ---------------------------------------------------------------- generation

def _insight_cfg(cfg: dict) -> dict:
    jcfg = dict(cfg)
    jcfg["llm"] = dict(cfg["llm"])
    jcfg["llm"]["template"] = str(INSIGHT_PROMPT)
    return jcfg


def generate_insight(metrics: dict, health: dict, trends: dict, attention: list,
                     cfg: dict, adapter=None, model_label: str = "unknown") -> dict:
    """Generate + validate a Weekly Insight. Fail-closed on any error."""
    insight_input = build_insight_input(metrics, health, trends, attention)
    context = json.dumps(insight_input, ensure_ascii=False, indent=2, default=str)
    question = f"请基于以下结构化事实生成 {insight_input.get('period')} 的周度知识洞察。"
    try:
        if adapter is None:
            from llm import create_llm
            adapter = create_llm(_insight_cfg(cfg))
        raw = adapter.generate(question, context)
    except Exception as exc:
        return {"status": "unavailable", "reason": f"LLM 调用失败（fail-closed）: {exc}",
                "insight": None, "prompt_version": PROMPT_VERSION, "model": model_label}
    data = _extract_json(raw)
    if data is None:
        return {"status": "unavailable", "reason": "insight JSON 解析失败（fail-closed）",
                "insight": None, "prompt_version": PROMPT_VERSION, "model": model_label}
    ok, reason = validate_insight(data, insight_input)
    if not ok:
        return {"status": "unavailable", "reason": f"insight 校验失败（fail-closed）: {reason}",
                "insight": None, "prompt_version": PROMPT_VERSION, "model": model_label}
    return {
        "status": "available",
        "reason": None,
        "insight": {
            "schema_version": SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "model": model_label,
            "summary": data.get("summary"),
            "changes": data.get("changes", []),
            "attention": data.get("attention", []),
            "actions": data.get("actions", []),
        },
        "prompt_version": PROMPT_VERSION,
        "model": model_label,
    }


# ---------------------------------------------------------------- cache

def insight_path(period: str, review_root: Path) -> Path:
    m = re.match(r"^(\d{4})-W(\d{1,2})$", period or "")
    if not m:
        raise ValueError(f"invalid period: {period}")
    return review_root / m.group(1) / f"W{int(m.group(2)):02d}" / "insight.json"


def load_cached_insight(period: str, review_root: Path, model: str) -> dict | None:
    path = insight_path(period, review_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("prompt_version") != PROMPT_VERSION or data.get("model") != model:
        return None  # 缓存键不匹配 -> 视为无缓存
    if data.get("status") != "available":
        return None  # 不可用的结果不是有效缓存 -> 允许重试
    return data


def save_insight(period: str, result: dict, review_root: Path) -> Path:
    path = insight_path(period, review_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "period": period,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": result.get("prompt_version", PROMPT_VERSION),
        "model": result.get("model"),
        "status": result.get("status"),
        "reason": result.get("reason"),
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "insight": result.get("insight"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
