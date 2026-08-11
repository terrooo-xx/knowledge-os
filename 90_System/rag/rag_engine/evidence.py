"""Evidence assessment: decide whether retrieval evidence can support an answer."""
from __future__ import annotations

import re


def _missing_topic_tokens(query: str, texts: list[str]) -> list[str]:
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{2,}", query)
    }
    if not tokens:
        return []
    all_text = " ".join(texts).lower()
    return sorted(token for token in tokens if token not in all_text)


def assess_evidence(
    query: str,
    chunks: list[dict],
    cfg: dict,
    answer: str | None = None,
) -> dict:
    retrieval = cfg.get("retrieval", {})
    threshold = float(retrieval.get("confidence_threshold", 0.78))
    if not chunks:
        return {
            "sufficient": False,
            "gap_type": "knowledge_missing",
            "reason": "知识库没有检索到相关内容",
            "confidence": 0.0,
            "chunk_count": 0,
            "statuses": [],
            "sources": [],
            "conflict": False,
        }

    scores = [
        float(chunk.get("rerank_score", chunk.get("score", 0.0))) for chunk in chunks
    ]
    top_score = max(scores)
    statuses = sorted(
        {
            str((chunk.get("metadata") or {}).get("status", "unknown"))
            for chunk in chunks
        }
    )
    sources = sorted(
        {str((chunk.get("metadata") or {}).get("source", "")) for chunk in chunks}
    )
    conflict = False

    if top_score < threshold:
        missing = _missing_topic_tokens(
            query, [chunk["text"] for chunk in chunks]
        )
        if missing:
            gap_type = "knowledge_missing"
            reason = f"知识库缺少主题词: {', '.join(missing)}"
        elif set(statuses) <= {"draft", "unknown"}:
            gap_type = "knowledge_insufficient"
            reason = "存在相关知识但内容/可信度不足"
        else:
            gap_type = "retrieval_problem"
            reason = "知识存在但检索未正确命中"
        return {
            "sufficient": False,
            "gap_type": gap_type,
            "reason": reason,
            "confidence": top_score,
            "chunk_count": len(chunks),
            "statuses": statuses,
            "sources": sources,
            "conflict": conflict,
        }

    if top_score >= threshold:
        missing = _missing_topic_tokens(
            query, [chunk["text"] for chunk in chunks]
        )
        if missing:
            # Relevance gate: high similarity alone does not mean the question
            # is answered. If distinctive query terms are absent from every
            # retrieved chunk, prefer knowledge_missing over a false answer.
            return {
                "sufficient": False,
                "gap_type": "knowledge_missing",
                "reason": "检索到高相似内容但未覆盖问题主题词: " + ", ".join(missing),
                "confidence": top_score,
                "chunk_count": len(chunks),
                "statuses": statuses,
                "sources": sources,
                "conflict": conflict,
            }

    if answer is not None and len((answer or "").strip()) < 20:
        return {
            "sufficient": False,
            "gap_type": "answer_quality_problem",
            "reason": "检索正确但回答为空或过短",
            "confidence": top_score,
            "chunk_count": len(chunks),
            "statuses": statuses,
            "sources": sources,
            "conflict": conflict,
        }

    return {
        "sufficient": True,
        "gap_type": None,
        "reason": "证据充分",
        "confidence": top_score,
        "chunk_count": len(chunks),
        "statuses": statuses,
        "sources": sources,
        "conflict": conflict,
    }