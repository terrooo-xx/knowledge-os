"""Reranker adapters: BGE, Jina, and score fallback.

Process-wide lazy singleton for the CrossEncoder model so a long-lived process
(e.g. the MCP server) does not reload the reranker on every call.
Thread-safe: model creation is guarded by a lock (double-checked).
"""
from __future__ import annotations

import os
import threading

# 与 embeddings.py 相同：默认离线加载本地模型，避免 HF hub 联网重试卡住。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_reranker_lock = threading.Lock()
_reranker_model = None
_reranker_provider = None
_reranker_model_name = None


def _get_reranker(provider: str, model_name: str):
    """Return the cached CrossEncoder for (provider, model); create once."""
    global _reranker_model, _reranker_provider, _reranker_model_name
    if (
        _reranker_model is not None
        and _reranker_provider == provider
        and _reranker_model_name == model_name
    ):
        return _reranker_model
    with _reranker_lock:
        if (
            _reranker_model is not None
            and _reranker_provider == provider
            and _reranker_model_name == model_name
        ):
            return _reranker_model
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name)
        _reranker_model = model
        _reranker_provider = provider
        _reranker_model_name = model_name
        return model


def rerank(query: str, chunks: list[dict], cfg: dict) -> list[dict]:
    reranker_cfg = cfg["reranker"]
    if not chunks:
        return chunks
    provider = reranker_cfg["provider"] if reranker_cfg.get("enabled") else "none"
    if provider in ("bge", "jina"):
        model = _get_reranker(provider, reranker_cfg["model"])
        scores = model.predict([[query, c["text"]] for c in chunks])
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    return chunks[: int(reranker_cfg.get("top_k", len(chunks)))]
