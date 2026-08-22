"""Knowledge OS Health Engine (Phase D1) — pure deterministic, no LLM.

Calculates a stable, explainable, repeatable Health Score (0-100) from the
unified metrics (collect_metrics), using weighted sub-scores per dimension.
Insufficient data never fabricates a 0 score: dimensions and the total become
not_available / not_calculated.
"""
from __future__ import annotations

# 维度定义：key / label / weight（权重之和 = 1.0）
HEALTH_DIMENSIONS = [
    {"key": "knowledge_quality", "label": "Knowledge Quality", "weight": 0.20},
    {"key": "review_health", "label": "Review Health", "weight": 0.20},
    {"key": "knowledge_gaps", "label": "Knowledge Gaps", "weight": 0.15},
    {"key": "freshness", "label": "Freshness", "weight": 0.15},
    {"key": "project_activity", "label": "Project Activity", "weight": 0.10},
    {"key": "system_reliability", "label": "System Reliability", "weight": 0.20},
]

HEALTH_ALGORITHM_VERSION = "health_v1"

# 状态阈值（集中常量，避免散落）
HEALTH_STATUS_LEVELS = [
    (90, "excellent"),
    (75, "good"),
    (60, "attention"),
    (40, "warning"),
    (0, "critical"),
]


def status_for(score: int | None) -> str:
    if score is None:
        return "not_available"
    for threshold, label in HEALTH_STATUS_LEVELS:
        if score >= threshold:
            return label
    return "critical"


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _knowledge_quality(wiki: dict):
    total = int(wiki.get("wiki_total") or 0)
    if total <= 0:
        return None, {"reason": "no_wiki"}
    reviewed_stable = int(wiki.get("wiki_reviewed") or 0) + int(wiki.get("wiki_stable") or 0)
    ratio = reviewed_stable / total
    # draft 不等于错误：未审核基线给 40 分，满审核 100 分
    score = _clamp(40 + 60 * ratio)
    return score, {"reviewed_stable_ratio": round(ratio, 3), "reviewed_stable": reviewed_stable, "total": total}


def _review_health(review: dict):
    candidates = int(review.get("candidates") or review.get("total") or 0)
    if candidates <= 0:
        return None, {"reason": "no_candidates"}
    pending = int(review.get("pending_human") or 0)
    failed = int(review.get("judge_failed") or 0)
    backlog = pending / candidates
    failure = failed / candidates
    score = _clamp(100 * (1 - 0.8 * backlog - 1.5 * failure))
    return score, {"backlog_ratio": round(backlog, 3), "failure_ratio": round(failure, 3),
                   "pending_human": pending, "judge_failed": failed, "candidates": candidates}


def _knowledge_gaps(gaps: dict):
    total = int(gaps.get("knowledge_gaps_total") or 0)
    if total <= 0:
        return None, {"reason": "no_gaps_data"}
    pending = int(gaps.get("knowledge_gaps_pending") or 0)
    resolved = int(gaps.get("knowledge_gaps_resolved") or 0)
    backlog = pending / total
    resolution = resolved / total
    # 新发现缺口本身可能是健康行为：backlog 扣分，resolution 加分
    score = _clamp(100 * (1 - 0.7 * backlog + 0.3 * resolution))
    return score, {"backlog_ratio": round(backlog, 3), "resolution_ratio": round(resolution, 3),
                   "pending": pending, "resolved": resolved, "total": total}


def _freshness(wiki: dict, stale_count: int):
    total = int(wiki.get("wiki_total") or 0)
    if total <= 0:
        return None, {"reason": "no_wiki"}
    ratio = (stale_count or 0) / total
    score = _clamp(100 * (1 - 1.5 * ratio))
    return score, {"stale_ratio": round(ratio, 3), "stale": stale_count, "total": total}


def _project_activity(projects: list[dict]):
    if not projects:
        return None, {"reason": "no_projects"}
    n = len(projects)
    phase_coverage = sum(1 for p in projects if p.get("phase")) / n
    recent = sum(1 for p in projects if p.get("updated")) / n
    blocked = sum(1 for p in projects if p.get("status") == "blocked")
    blocked_ratio = blocked / n
    score = _clamp(100 * (0.5 * phase_coverage + 0.3 * recent + 0.2 * (1 - blocked_ratio)))
    return score, {"phase_coverage": round(phase_coverage, 3),
                   "recently_updated_ratio": round(recent, 3), "blocked_ratio": round(blocked_ratio, 3)}


def _system_reliability(health: dict):
    if not health or health.get("status") is None:
        return None, {"reason": "no_health_data"}
    errors = int(health.get("errors") or 0)
    warnings = int(health.get("warnings") or 0)
    score = _clamp(100 - 40 * errors - 10 * warnings)
    return score, {"errors": errors, "warnings": warnings, "status": health.get("status")}


def build_attention(metrics: dict) -> list[dict]:
    """What deserves attention (shared by dashboard + AI insight input)."""
    review = metrics.get("review") or {}
    gaps = metrics.get("gaps") or {}
    stale = metrics.get("stale_risk") or []
    projects = metrics.get("projects") or []
    attention = []
    if int(review.get("pending_human") or 0) > 0:
        attention.append({"level": "warning", "count": review["pending_human"],
                          "label": "项需要人工审核", "action": "todo"})
    if int(gaps.get("knowledge_gaps_pending") or 0) > 0:
        attention.append({"level": "warning", "count": gaps["knowledge_gaps_pending"],
                          "label": "个知识缺口待处理", "action": "gaps"})
    if len(stale) > 0:
        attention.append({"level": "warning", "count": len(stale),
                          "label": "项 stale 复查风险", "action": "health"})
    for p in projects:
        if p.get("status") == "blocked":
            attention.append({"level": "critical", "count": 1,
                              "label": f"项目 {p['name']} 被阻塞", "action": "projects"})
    return attention


def _build_factors(metrics: dict) -> list[dict]:
    review = metrics.get("review") or {}
    gaps = metrics.get("gaps") or {}
    projects = metrics.get("projects") or []
    health = metrics.get("health") or {}
    stale = metrics.get("stale_risk") or []
    factors = []

    def negative(metric, value, impact):
        if value is not None and value > 0:
            factors.append({"type": "negative", "metric": metric, "value": value, "impact": impact})

    negative("review_pending", review.get("pending_human"), "medium")
    negative("judge_failed", review.get("judge_failed"), "high")
    negative("gaps_pending", gaps.get("knowledge_gaps_pending"), "medium")
    negative("stale", len(stale), "medium")
    negative("projects_blocked", sum(1 for p in projects if p.get("status") == "blocked"), "high")
    if health:
        negative("system_errors", health.get("errors"), "high")
        negative("system_warnings", health.get("warnings"), "low")

    if int(review.get("judge_failed") or 0) == 0:
        factors.append({"type": "positive", "metric": "judge_failed", "value": 0, "impact": "medium"})
    if health and int(health.get("errors") or 0) == 0 and int(health.get("warnings") or 0) == 0:
        factors.append({"type": "positive", "metric": "system_health", "value": 0, "impact": "low"})
    if int(gaps.get("knowledge_gaps_resolved") or 0) > 0:
        factors.append({"type": "positive", "metric": "gaps_resolved",
                        "value": gaps.get("knowledge_gaps_resolved"), "impact": "low"})
    return factors


def calculate_health(metrics: dict) -> dict:
    """Deterministic Health Score from the unified metrics dict.

    Same input -> same output. Missing data -> not_available (never 0).
    """
    wiki = metrics.get("wiki") or {}
    review = metrics.get("review") or {}
    gaps = metrics.get("gaps") or {}
    projects = metrics.get("projects") or []
    stale = metrics.get("stale_risk") or []
    health = metrics.get("health") or {}

    calculators = {
        "knowledge_quality": _knowledge_quality(wiki),
        "review_health": _review_health(review),
        "knowledge_gaps": _knowledge_gaps(gaps),
        "freshness": _freshness(wiki, len(stale)),
        "project_activity": _project_activity(projects),
        "system_reliability": _system_reliability(health),
    }

    dimensions = {}
    available_weight = 0.0
    for dim in HEALTH_DIMENSIONS:
        key = dim["key"]
        score, detail = calculators[key]
        dimensions[key] = {
            "score": score,
            "status": status_for(score),
            "available": score is not None,
            "weight": dim["weight"],
            "label": dim["label"],
            "detail": detail,
        }
        if score is not None:
            available_weight += dim["weight"]

    if available_weight <= 0:
        return {
            "score": None, "status": "not_calculated", "available": False,
            "reason": "insufficient_data", "algorithm_version": HEALTH_ALGORITHM_VERSION,
            "dimensions": dimensions, "factors": _build_factors(metrics),
        }

    total = sum(
        dimensions[k]["score"] * dimensions[k]["weight"]
        for k in dimensions if dimensions[k]["available"]
    ) / available_weight
    score = _clamp(total)
    return {
        "score": score, "status": status_for(score), "available": True,
        "reason": None, "algorithm_version": HEALTH_ALGORITHM_VERSION,
        "dimensions": dimensions, "factors": _build_factors(metrics),
    }
