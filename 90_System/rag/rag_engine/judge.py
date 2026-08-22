"""LLM Relevance Judge: does the retrieved evidence set actually answer the question?

The judge is a structured classifier (RELEVANT / IRRELEVANT), NOT an answer
generator. It decides whether top-K chunks can support an answer.

Fail-closed: any failure (timeout, invalid JSON, LLM unavailable) treats the
evidence as NOT sufficient, so the system never answers on uncertain evidence.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
JUDGE_PROMPT = RAG_DIR / "prompts" / "relevance_judge.md"

FAIL_CLOSED = {
    "relevance": "irrelevant",
    "reason": "LLM Relevance Judge 不可用或解析失败（fail closed）",
    "confidence": 0.0,
    "error": True,
}


def _judge_cfg(cfg: dict) -> dict:
    jcfg = copy.deepcopy(cfg)
    jcfg["llm"] = dict(cfg["llm"])
    jcfg["llm"]["template"] = str(JUDGE_PROMPT)
    return jcfg


def parse_judge_output(raw: str) -> dict:
    """Parse the judge JSON; any failure returns the fail-closed result."""
    if not raw:
        return dict(FAIL_CLOSED)
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return dict(FAIL_CLOSED)
    try:
        data = json.loads(m.group(0))
    except Exception:
        return dict(FAIL_CLOSED)
    relevance = str(data.get("relevance", "")).strip().lower()
    if relevance not in ("relevant", "irrelevant"):
        return dict(FAIL_CLOSED)
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "relevance": relevance,
        "reason": str(data.get("reason", "")).strip() or relevance,
        "confidence": max(0.0, min(1.0, conf)),
        "error": False,
    }


def judge_enabled(cfg: dict) -> bool:
    judge_cfg = cfg.get("evidence_judge", {})
    if not judge_cfg.get("enabled"):
        return False
    provider = (cfg.get("llm") or {}).get("provider", "none")
    if provider in ("none", "mock"):
        return False  # offline / mock mode: skip the judge
    return True


def judge_relevance(query: str, chunks: list[dict], cfg: dict) -> dict:
    """Judge whether the evidence set can answer `query`. Fail closed on any error."""
    try:
        from llm import create_llm
        from llm.context import build_context

        adapter = create_llm(_judge_cfg(cfg))
        context = build_context(chunks)
        raw = adapter.generate(query, context)
        return parse_judge_output(raw)
    except Exception as exc:
        result = dict(FAIL_CLOSED)
        result["reason"] = f"LLM Relevance Judge 失败（fail closed）: {exc}"
        return result


# ---------------------------------------------------------------- review judge

"""Review Judge: compare source evidence against the current Wiki / target
content for a Review Task. Reuses the same LLM adapter and prompt mechanism as
the relevance judge; fail-closed on any error. It is a reviewer, not an answer
generator: it only outputs a structured judgement for human review.
"""

REVIEW_JUDGE_PROMPT = RAG_DIR / "prompts" / "review_judge.md"

REVIEW_STATUSES = {"sufficient", "insufficient", "conflict", "uncertain"}
REVIEW_RECOMMENDATIONS = {"approve", "reject", "resolve", "review"}
REVIEW_CONFIDENCES = {"high", "medium", "low"}
REVIEW_SUFFICIENCIES = {"sufficient", "insufficient", "partial", "unknown"}
REVIEW_CONSISTENCIES = {"consistent", "partial", "conflict", "unknown"}

REVIEW_FAIL_CLOSED = {
    "status": "uncertain",
    "recommendation": "review",
    "confidence": "low",
    "evidence_sufficiency": "unknown",
    "consistency": "unknown",
    "conflicts": [],
    "missing_information": [],
    "unsupported_claims": [],
    "reasoning": "LLM Review Judge 不可用或解析失败（fail closed）",
    "warnings": [],
    "error": True,
}


def _review_judge_cfg(cfg: dict) -> dict:
    jcfg = copy.deepcopy(cfg)
    jcfg["llm"] = dict(cfg["llm"])
    jcfg["llm"]["template"] = str(REVIEW_JUDGE_PROMPT)
    return jcfg


def _clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def parse_review_judgement(raw: str) -> dict:
    """Parse the structured review JSON; any failure returns fail-closed."""
    if not raw:
        return dict(REVIEW_FAIL_CLOSED)
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return dict(REVIEW_FAIL_CLOSED)
    try:
        data = json.loads(m.group(0))
    except Exception:
        return dict(REVIEW_FAIL_CLOSED)
    if not isinstance(data, dict):
        return dict(REVIEW_FAIL_CLOSED)

    status = str(data.get("status", "")).strip().lower()
    recommendation = str(data.get("recommendation", "")).strip().lower()
    confidence = str(data.get("confidence", "")).strip().lower()
    sufficiency = str(data.get("evidence_sufficiency", "")).strip().lower()
    consistency = str(data.get("consistency", "")).strip().lower()
    if status not in REVIEW_STATUSES:
        return dict(REVIEW_FAIL_CLOSED)
    if recommendation not in REVIEW_RECOMMENDATIONS:
        return dict(REVIEW_FAIL_CLOSED)
    if confidence not in REVIEW_CONFIDENCES:
        confidence = "unknown"
    if sufficiency not in REVIEW_SUFFICIENCIES:
        sufficiency = "unknown"
    if consistency not in REVIEW_CONSISTENCIES:
        consistency = "unknown"
    return {
        "status": status,
        "recommendation": recommendation,
        "confidence": confidence,
        "evidence_sufficiency": sufficiency,
        "consistency": consistency,
        "conflicts": _clean_list(data.get("conflicts")),
        "missing_information": _clean_list(data.get("missing_information")),
        "unsupported_claims": _clean_list(data.get("unsupported_claims")),
        "reasoning": str(data.get("reasoning", "")).strip(),
        "warnings": _clean_list(data.get("warnings")),
        "error": False,
    }


def build_review_context(chunks: list[dict], target_content: str | None) -> str:
    """Assemble SOURCE EVIDENCE + CURRENT WIKI as the judge input block."""
    parts = []
    if not chunks:
        parts.append("SOURCE EVIDENCE\n────────────────\n（无可用来源证据）")
    else:
        ev_parts = []
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.get("source") or (chunk.get("metadata") or {}).get("source", "未知来源")
            content = chunk.get("content") or chunk.get("text") or ""
            ev_parts.append(f"[{index}] 来源：{source}\n{content}")
        parts.append("SOURCE EVIDENCE\n────────────────\n" + "\n\n".join(ev_parts))
    if target_content and str(target_content).strip():
        parts.append("CURRENT WIKI\n────────────────\n" + str(target_content).strip())
    else:
        parts.append("CURRENT WIKI\n────────────────\n（无当前 Wiki：本任务为知识缺口审核，只需判断证据是否足以回答问题）")
    return "\n\n".join(parts)


def judge_review(
    task_text: str,
    chunks: list[dict],
    target_content: str | None,
    cfg: dict,
    adapter=None,
) -> dict:
    """Run the LLM Review Judge on evidence vs target content.

    Fail-closed: any failure (timeout, invalid JSON, LLM unavailable) returns a
    REVIEW_FAIL_CLOSED result so the review task is never auto-approved.
    `adapter` is injectable for offline tests.
    """
    try:
        if adapter is None:
            from llm import create_llm

            adapter = create_llm(_review_judge_cfg(cfg))
        context = build_review_context(chunks, target_content)
        raw = adapter.generate(task_text, context)
        return parse_review_judgement(raw)
    except Exception as exc:
        result = dict(REVIEW_FAIL_CLOSED)
        result["reason"] = f"LLM Review Judge 失败（fail closed）: {exc}"
        return result
