"""Reranker adapters: BGE, Jina, and score fallback."""
from __future__ import annotations


def rerank(query: str, chunks: list[dict], cfg: dict) -> list[dict]:
    reranker_cfg = cfg["reranker"]
    if not chunks:
        return chunks
    provider = reranker_cfg["provider"] if reranker_cfg.get("enabled") else "none"
    if provider == "bge":
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for BGE reranker"
            ) from exc
        model = CrossEncoder(reranker_cfg["model"])
        scores = model.predict([[query, c["text"]] for c in chunks])
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    elif provider == "jina":
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for Jina reranker"
            ) from exc
        model = CrossEncoder(reranker_cfg["model"])
        scores = model.predict([[query, c["text"]] for c in chunks])
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    return chunks[: int(reranker_cfg.get("top_k", len(chunks)))]
