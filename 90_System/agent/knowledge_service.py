"""Agent Knowledge Interface: stable, READ-ONLY wrapper over the Knowledge OS query chain.

Codex / other agents call knowledge_search() instead of touching Wiki / Vector DB.
It reuses the existing retrieval -> heuristic evidence -> LLM relevance judge chain
(rag_engine.retrieval.answer_query) and never writes knowledge.

Fail-closed: any exception / LLM unavailability maps to a non-answerable status,
never a guessed answer.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
# Vault 根目录：优先环境变量 KNOWLEDGE_OS_VAULT（供 MCP/外部调用覆盖），
# 否则按本文件位置反推（<vault>/90_System/agent/）。绝不依赖当前工作目录。
VAULT_ROOT = Path(
    os.environ.get("KNOWLEDGE_OS_VAULT", str(AGENT_DIR.parent.parent))
).resolve()
RAG_DIR = VAULT_ROOT / "90_System" / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths  # noqa: E402
from rag_engine.embeddings import create_embedder  # noqa: E402
from rag_engine.vector_store import create_store  # noqa: E402
from rag_engine.retrieval import answer_query  # noqa: E402


def _evidence_list(chunks) -> list[dict]:
    out = []
    for chunk in chunks or []:
        md = chunk.get("metadata") or {}
        src = str(md.get("source", ""))
        out.append({
            "title": Path(src).stem if src else "",
            "source": src,
            "score": round(float(chunk.get("rerank_score", chunk.get("score", 0.0))), 4),
            "status": md.get("status", "unknown"),
        })
    return out


def knowledge_search(
    query: str,
    *,
    use_llm: bool = True,
    record_gap: bool = False,
    top_k: int | None = None,
    cfg: dict | None = None,
    config_path: str | None = None,
    embedder=None,
    raw_store=None,
    wiki_store=None,
    llm_answer=None,
) -> dict:
    """Query Knowledge OS and return a stable structured result (READ-ONLY).

    Args mirror the existing query chain; components may be injected for offline
    testing. Defaults build the production main index from config.
    """
    if cfg is None:
        cfg = resolve_paths(
            load_config(config_path or str(RAG_DIR / "config.yaml")), VAULT_ROOT
        )
    if top_k is not None:
        cfg["retrieval"]["top_k"] = int(top_k)
    if embedder is None:
        embedder = create_embedder(cfg)
    if raw_store is None:
        raw_store = create_store(cfg, cfg["paths"]["main_vector_db"])
    if wiki_store is None:
        wiki_store = raw_store

    provider = (cfg.get("llm") or {}).get("provider", "none")
    if llm_answer is None and use_llm and provider not in ("none", "mock"):
        from rag_engine.llm import answer as _answer
        llm_answer = _answer

    try:
        result = answer_query(query, cfg, embedder, raw_store, wiki_store, llm_answer=llm_answer)
    except Exception as exc:
        return {
            "query": query,
            "status": "error",
            "answer": None,
            "evidence": [],
            "sufficient": False,
            "judge": None,
            "gap": None,
            "source_trace": [],
            "reason": f"Agent Interface 查询失败（fail closed）: {exc}",
        }

    evidence = result.get("evidence") or {}
    chunks = result.get("chunks") or []
    ev_list = _evidence_list(chunks)
    sufficient = bool(evidence.get("sufficient"))
    gap_type = evidence.get("gap_type") or "knowledge_missing"
    judge = result.get("judge")
    # Defensive: judge "irrelevant" must never be answerable (normally handled inside answer_query).
    if sufficient and judge is not None and judge.get("relevance") != "relevant":
        sufficient = False
        gap_type = "knowledge_missing"

    status = "answerable" if sufficient else gap_type
    answer = result.get("answer") if sufficient else None
    # Reuse existing Gap semantics in the response (read-only; no auto-write).
    # record_gap=True is reserved for future opt-in; not implemented this phase.
    return {
        "query": query,
        "status": status,
        "answer": answer,
        "evidence": ev_list,
        "sufficient": sufficient,
        "judge": judge,
        "gap": {"status": "pending"} if not sufficient else None,
        "source_trace": sorted({e["source"] for e in ev_list if e["source"]}),
        "reason": evidence.get("reason"),
    }
