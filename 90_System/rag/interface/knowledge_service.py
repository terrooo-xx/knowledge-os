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
# 否则按本文件位置反推（<vault>/90_System/rag/interface/）。绝不依赖当前工作目录。
RAG_DIR = AGENT_DIR.parent
VAULT_ROOT = Path(
    os.environ.get("KNOWLEDGE_OS_VAULT", str(RAG_DIR.parent.parent))
).resolve()
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths  # noqa: E402
from rag_engine.embeddings import create_embedder  # noqa: E402
from rag_engine.vector_store import create_store  # noqa: E402
from rag_engine.retrieval import answer_query  # noqa: E402
from rag_engine.evidence import assess_evidence  # noqa: E402


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


def _is_timeout_error(exc: Exception) -> bool:
    import openai
    return isinstance(exc, (TimeoutError, openai.APITimeoutError, openai.APIConnectionError))


def knowledge_search(
    query: str,
    *,
    mode: str = "deep",
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

    mode:
      - "deep" (default): Retrieval + Evidence + Judge + Answer Generation.
      - "fast" / "evidence_only": Retrieval + Evidence + Judge, NO long answer
        (returns structured evidence so Codex can continue without a second LLM pass).

    Evidence / Judge / fail-closed are always preserved. In deep mode an Answer
    timeout returns `answer_generation_timeout` with evidence/judge/source_trace
    preserved (never a guessed answer).
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

    generate_answer = mode == "deep"
    provider = (cfg.get("llm") or {}).get("provider", "none")
    if llm_answer is None and use_llm and generate_answer and provider not in ("none", "mock"):
        from rag_engine.llm import answer as _answer
        llm_answer = _answer

    # Phase 1: Retrieval + Evidence + Judge (no answer yet), so a later Answer
    # timeout can still preserve the already-confirmed evidence.
    try:
        result = answer_query(query, cfg, embedder, raw_store, wiki_store, llm_answer=None)
    except Exception as exc:
        return {
            "query": query,
            "mode": mode,
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
    if sufficient and judge is not None and judge.get("relevance") != "relevant":
        sufficient = False
        gap_type = "knowledge_missing"

    status = "answerable" if sufficient else gap_type
    answer = None
    if sufficient and generate_answer and llm_answer is not None:
        # Phase 2: Answer generation (deep mode only), timeout preserves evidence.
        try:
            answer = llm_answer(query, chunks, cfg)
            evidence = assess_evidence(query, chunks, cfg, answer=answer)
            if not evidence["sufficient"]:
                status = evidence.get("gap_type") or "answer_quality_problem"
                answer = None
                sufficient = False
        except Exception as exc:
            if _is_timeout_error(exc):
                status = "answer_generation_timeout"
                answer = None
            else:
                return {
                    "query": query,
                    "mode": mode,
                    "status": "error",
                    "answer": None,
                    "evidence": ev_list,
                    "sufficient": False,
                    "judge": judge,
                    "gap": None,
                    "source_trace": sorted({e["source"] for e in ev_list if e["source"]}),
                    "reason": f"Answer generation failed (fail closed): {exc}",
                }

    return {
        "query": query,
        "mode": mode,
        "status": status,
        "answer": answer,
        "evidence": ev_list,
        "sufficient": sufficient,
        "judge": judge,
        "gap": {"status": "pending"} if status not in ("answerable", "answer_generation_timeout") else None,
        "source_trace": sorted({e["source"] for e in ev_list if e["source"]}),
        "reason": evidence.get("reason"),
    }
