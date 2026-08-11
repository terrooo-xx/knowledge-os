"""Hybrid retrieval: wiki-first, dense + BM25 fusion, optional rerank."""
from __future__ import annotations

import json

from .bm25 import BM25Index
from .evidence import assess_evidence
from .rerank import rerank
from .judge import judge_enabled, judge_relevance


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


def answer_query(
    query: str,
    cfg: dict,
    embedder,
    raw_store,
    wiki_store,
    llm_answer=None,
) -> dict:
    retrieval = cfg["retrieval"]
    chunks = None
    source = "raw"
    confidence = 0.0

    if retrieval["wiki_first"] and wiki_store.count() > 0:
        wiki_docs = wiki_store.all()
        bm25 = BM25Index([doc["text"] for doc in wiki_docs])
        wiki_chunks = search_corpus(query, embedder, wiki_store, bm25, cfg)
        wiki_confidence = max(
            (chunk["score"] for chunk in wiki_chunks), default=0.0
        )
        if wiki_confidence >= retrieval["confidence_threshold"]:
            chunks = wiki_chunks
            source = "wiki"
            confidence = wiki_confidence

    if chunks is None:
        raw_docs = raw_store.all()
        bm25 = BM25Index([doc["text"] for doc in raw_docs])
        chunks = search_corpus(query, embedder, raw_store, bm25, cfg)
        chunks = rerank(query, chunks, cfg)
        confidence = max(
            (chunk.get("rerank_score", chunk["score"]) for chunk in chunks),
            default=0.0,
        )

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

    answer = None
    if llm_answer:
        if evidence["sufficient"]:
            answer = llm_answer(query, chunks, cfg)
            evidence = assess_evidence(query, chunks, cfg, answer=answer)
        else:
            answer = "当前知识库没有足够资料支持这个问题。"

    return {
        "source": source,
        "confidence": confidence,
        "chunks": chunks,
        "answer": answer,
        "evidence": evidence,
        "gap_type": evidence["gap_type"],
        "judge": judge,
    }