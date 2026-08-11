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
