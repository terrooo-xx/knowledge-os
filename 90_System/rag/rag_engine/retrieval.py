"""Hybrid retrieval: wiki-first, dense + BM25 fusion, optional rerank."""
from __future__ import annotations

import json

from .bm25 import BM25Index
from .evidence import assess_evidence
from .rerank import rerank
from .judge import judge_enabled, judge_relevance
from .evidence_window import build_document_index, build_evidence_windows


def minmax_scores(items: list[dict]) -> list[dict]:
    if not items:
        return items
    values = [float(item["score"]) for item in items]
    low, high = min(values), max(values)
    for item, value in zip(items, values):
        item["score"] = 1.0 if high == low else (value - low) / (high - low)
    return items


def _chunk_key(chunk: dict) -> str:
    metadata = json.dumps(chunk.get("metadata") or {}, sort_keys=True, ensure_ascii=False)
    return chunk["text"] + "\x00" + metadata


def fuse_results(dense: list[dict], keyword: list[dict], cfg: dict) -> list[dict]:
    dense_weight = cfg["retrieval"]["dense_weight"]
    keyword_weight = cfg["retrieval"]["bm25_weight"]
    merged: dict[str, dict] = {}
    for chunk in dense:
        merged[_chunk_key(chunk)] = {
            "text": chunk["text"],
            "metadata": chunk.get("metadata") or {},
            "score": float(chunk["score"]) * dense_weight,
        }
    for chunk in keyword:
        key = _chunk_key(chunk)
        if key in merged:
            merged[key]["score"] += float(chunk["score"]) * keyword_weight
        else:
            merged[key] = {
                "text": chunk["text"],
                "metadata": chunk.get("metadata") or {},
                "score": float(chunk["score"]) * keyword_weight,
            }
    return sorted(merged.values(), key=lambda item: item["score"], reverse=True)


def search_corpus(query: str, embedder, store, bm25, cfg: dict) -> list[dict]:
    top_k = int(cfg["retrieval"]["top_k"])
    dense = store.search(embedder.embed([query])[0], top_k * 2)
    minmax_scores(dense)
    docs = store.all()
    keyword = []
    for hit in bm25.search(query, top_k * 2):
        doc = docs[hit["index"]]
        keyword.append(
            {"score": hit["score"], "text": doc["text"], "metadata": doc["metadata"]}
        )
    minmax_scores(keyword)
    return fuse_results(dense, keyword, cfg)[:top_k]


def build_retrieval_trace(query, retrieval, gate, initial_path, fallback_reason, raw_ran,
                         wiki_count, raw_count, evidence, judge, window_count, cfg) -> dict:
    """Structured, human-readable decision-chain trace (built during the query run).

    Additive only: nothing here re-runs retrieval / rerank / judge. Never exposes
    chain-of-thought or prompts.
    """
    path = "wiki_fallback" if (initial_path == "wiki_first" and gate.get("fallback_used")) else (
        "wiki_first" if gate.get("gate_passed") else "raw")
    reranker_cfg = cfg.get("reranker") or {}
    reranker_used = bool(raw_ran and reranker_cfg.get("enabled"))
    reranker_reason = "wiki_first" if not reranker_used else "raw_path"
    judge_executed = judge is not None
    if not judge_executed:
        judge_result = "not_executed"
    elif judge.get("relevance") == "relevant":
        judge_result = "passed"
    else:
        judge_result = "insufficient"
    answer_status = "answered" if evidence.get("sufficient") else "knowledge_missing"

    # 决策链摘要（人类可读一行）
    chain = []
    if initial_path != "wiki_first":
        chain = ["Wiki 未命中", "RAW 检索"]
        if reranker_used:
            chain.append("Reranker")
    else:
        chain = ["Wiki 命中"]
        if fallback_reason == "below_threshold":
            chain = ["Wiki 未达阈值", "RAW 检索"]
            if reranker_used:
                chain.append("Reranker")
        elif fallback_reason == "evidence_insufficient":
            chain += ["Evidence 不足", "RAW fallback", "Reranker" if reranker_used else "RAW"]
        elif fallback_reason == "judge_rejected":
            chain += ["Judge 拒绝", "RAW fallback", "Reranker" if reranker_used else "RAW"]
    if evidence.get("sufficient"):
        if judge_executed and judge_result == "insufficient":
            chain.append("Judge 不足")
        chain.append("已回答")
    else:
        chain.append("Evidence 不足")
        chain.append("Fail-Closed")
        chain.append("未回答")
    summary = " → ".join(chain)

    return {
        "query": query,
        "retrieval": {
            "path": path,
            "initial_path": initial_path,
            "wiki_first": bool(retrieval.get("wiki_first", True)),
            "wiki_confidence": gate.get("wiki_confidence"),
            "wiki_threshold": retrieval.get("confidence_threshold"),
            "gate_passed": bool(gate.get("gate_passed")),
            "fallback_enabled": bool(gate.get("fallback_enabled", True)),
            "fallback_used": bool(gate.get("fallback_used")),
            "fallback_reason": fallback_reason,
        },
        "candidates": {
            "wiki_count": wiki_count,
            "raw_count": raw_count,
            "reranked": reranker_used,
        },
        "ranking": {
            "reranker_used": reranker_used,
            "reranker_reason": reranker_reason,
            "reranker": str(reranker_cfg.get("model")) if reranker_used else None,
            "top_k": int(retrieval.get("top_k", 5)),
        },
        "evidence": {
            "window_count": window_count,
            "sufficient": bool(evidence.get("sufficient")),
            "gap_type": evidence.get("gap_type"),
        },
        "judge": {"executed": judge_executed, "result": judge_result},
        "answer": {"status": answer_status},
        "summary": summary,
    }


def _raw_retrieval(query, cfg, embedder, raw_store):
    """RAW path: dense + BM25 + fusion + BGE reranker (unchanged)."""
    raw_docs = raw_store.all()
    bm25 = BM25Index([doc["text"] for doc in raw_docs])
    chunks = search_corpus(query, embedder, raw_store, bm25, cfg)
    chunks = rerank(query, chunks, cfg)
    confidence = max(
        (chunk.get("rerank_score", chunk["score"]) for chunk in chunks),
        default=0.0,
    )
    return chunks, confidence


def answer_query(
    query: str,
    cfg: dict,
    embedder,
    raw_store,
    wiki_store,
    llm_answer=None,
) -> dict:
    retrieval = cfg["retrieval"]
    threshold = retrieval["confidence_threshold"]
    fallback_enabled = bool(retrieval.get("wiki_fallback_on_insufficient", True))

    gate = {
        "wiki_first": bool(retrieval.get("wiki_first", True)),
        "threshold": threshold,
        "wiki_confidence": None,
        "gate_passed": False,
        "fallback_used": False,
        "fallback_enabled": fallback_enabled,
    }
    chunks = None
    source = "raw"
    confidence = 0.0
    initial_path = None
    fallback_reason = None
    raw_ran = False
    wiki_count = 0
    raw_count = 0

    # ---- Phase 1: Wiki-first with a quality gate ----
    if retrieval["wiki_first"] and wiki_store.count() > 0:
        wiki_docs = wiki_store.all()
        bm25 = BM25Index([doc["text"] for doc in wiki_docs])
        wiki_chunks = search_corpus(query, embedder, wiki_store, bm25, cfg)
        wiki_confidence = max(
            (chunk["score"] for chunk in wiki_chunks), default=0.0
        )
        initial_path = "wiki_first"
        wiki_count = len(wiki_chunks)
        gate["wiki_confidence"] = round(wiki_confidence, 4)
        if wiki_confidence >= threshold:
            gate["gate_passed"] = True
            chunks = wiki_chunks
            source = "wiki"
            confidence = wiki_confidence
            # Deterministic evidence gate (no LLM): if the Wiki hit cannot
            # support the query, fall back to RAW instead of "hit-and-terminate".
            if fallback_enabled and not assess_evidence(query, wiki_chunks, cfg)["sufficient"]:
                gate["fallback_used"] = True
                fallback_reason = "evidence_insufficient"
                raw_ran = True
                chunks, confidence = _raw_retrieval(query, cfg, embedder, raw_store)
                source = "raw"
        else:
            fallback_reason = "below_threshold"

    if chunks is None:
        if initial_path is None:
            initial_path = "raw"
        else:
            fallback_reason = fallback_reason or "below_threshold"
        raw_ran = True
        chunks, confidence = _raw_retrieval(query, cfg, embedder, raw_store)
        source = "raw"

    # ---- Phase 2: Evidence + Judge (fail-closed, unchanged) ----
    evidence = assess_evidence(query, chunks, cfg)
    judge = None
    if evidence["sufficient"] and judge_enabled(cfg):
        top_k = int(cfg.get("evidence_judge", {}).get("top_k", 5))
        try:
            judge = judge_relevance(query, chunks[:top_k], cfg)
        except Exception as exc:
            # Defense in depth: any judge failure fails closed.
            judge = {
                "relevance": "irrelevant",
                "reason": f"LLM Relevance Judge 异常（fail closed）: {exc}",
                "confidence": 0.0,
                "error": True,
            }
        if judge["relevance"] != "relevant":
            evidence = {
                "sufficient": False,
                "gap_type": "knowledge_missing",
                "reason": judge["reason"],
                "confidence": evidence["confidence"],
                "chunk_count": evidence["chunk_count"],
                "statuses": evidence["statuses"],
                "sources": evidence["sources"],
                "conflict": False,
            }

    # ---- Phase 3: judge-level RAW fallback (Wiki passed the gate but the
    # LLM Judge found the evidence insufficient) ----
    if (
        fallback_enabled
        and not gate["fallback_used"]
        and source == "wiki"
        and not evidence["sufficient"]
    ):
        gate["fallback_used"] = True
        fallback_reason = "judge_rejected"
        raw_ran = True
        chunks, confidence = _raw_retrieval(query, cfg, embedder, raw_store)
        source = "raw"
        evidence = assess_evidence(query, chunks, cfg)
        judge = None
        if evidence["sufficient"] and judge_enabled(cfg):
            top_k = int(cfg.get("evidence_judge", {}).get("top_k", 5))
            try:
                judge = judge_relevance(query, chunks[:top_k], cfg)
            except Exception as exc:
                judge = {
                    "relevance": "irrelevant",
                    "reason": f"LLM Relevance Judge 异常（fail closed）: {exc}",
                    "confidence": 0.0,
                    "error": True,
                }
            if judge["relevance"] != "relevant":
                evidence = {
                    "sufficient": False,
                    "gap_type": "knowledge_missing",
                    "reason": judge["reason"],
                    "confidence": evidence["confidence"],
                    "chunk_count": evidence["chunk_count"],
                    "statuses": evidence["statuses"],
                    "sources": evidence["sources"],
                    "conflict": False,
                }

    answer = None
    if llm_answer:
        if evidence["sufficient"]:
            answer = llm_answer(query, chunks, cfg)
            evidence = assess_evidence(query, chunks, cfg, answer=answer)
        else:
            answer = "当前知识库没有足够资料支持这个问题。"

    if source == "raw":
        raw_count = len(chunks) if chunks else 0

    windows = []
    try:
        if chunks:
            store_for_windows = wiki_store if source == "wiki" else raw_store
            windows = build_evidence_windows(chunks, build_document_index(store_for_windows), cfg)
    except Exception:
        windows = []  # Context Expansion 失败不影响主链路

    trace = build_retrieval_trace(
        query, retrieval, gate, initial_path, fallback_reason, raw_ran,
        wiki_count, raw_count, evidence, judge, len(windows), cfg,
    )
    return {
        "source": source,
        "confidence": confidence,
        "chunks": chunks,
        "answer": answer,
        "evidence": evidence,
        "gap_type": evidence["gap_type"],
        "judge": judge,
        "evidence_windows": windows,
        "retrieval_gate": gate,
        "retrieval_trace": trace,
    }