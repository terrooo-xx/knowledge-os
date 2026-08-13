"""Knowledge OS query performance benchmark (per-layer timing via monkey-patch).

No production code is modified: layers are timed by wrapping the module-level
functions the pipeline uses (retrieval.search_corpus / rerank / assess_evidence /
judge_relevance, embedder.embed, and rag_engine.llm.answer).

Usage:
    python benchmark_query.py "<query>" <out.json> [--no-llm] [--runs N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
RAG_DIR = AGENT_DIR.parent
for d in (str(AGENT_DIR), str(RAG_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

import rag_engine.retrieval as retrieval
from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.vector_store import create_store
from rag_engine.llm import answer as llm_answer  # noqa: F401 (patched below)

VAULT_ROOT = Path(
    __import__("os").environ.get("KNOWLEDGE_OS_VAULT", str(AGENT_DIR.parent.parent.parent))
).resolve()

# ---------- timing wrappers ----------
_timings: dict[str, list] = {}


def _t(key):
    def deco(fn):
        def wrap(*a, **k):
            t0 = time.perf_counter()
            r = fn(*a, **k)
            _timings.setdefault(key, []).append((time.perf_counter() - t0) * 1000)
            return r
        return wrap
    return deco


def _install_wrappers(embedder):
    embedder.embed = _t("embedding")(embedder.embed)
    retrieval.search_corpus = _t("retrieval")(retrieval.search_corpus)
    retrieval.rerank = _t("rerank")(retrieval.rerank)
    retrieval.assess_evidence = _t("evidence")(retrieval.assess_evidence)
    retrieval.judge_relevance = _t("judge")(retrieval.judge_relevance)
    global llm_answer
    _orig_answer = llm_answer

    def _timed_answer(q, chunks, cfg):
        t0 = time.perf_counter()
        r = _orig_answer(q, chunks, cfg)
        _timings.setdefault("answer", []).append({
            "ms": (time.perf_counter() - t0) * 1000,
            "chars": len(r),
        })
        return r
    # patch the module attribute so knowledge_service's `from ... import answer` picks it up
    import rag_engine.llm as llm_mod
    llm_mod.answer = _timed_answer
    return embedder


def run_one(query: str, use_llm: bool, mode: str = "deep") -> dict:
    _timings.clear()
    t_cfg = time.perf_counter()
    cfg = resolve_paths(load_config(str(RAG_DIR / "config.yaml")), VAULT_ROOT)
    cfg_ms = (time.perf_counter() - t_cfg) * 1000
    if not use_llm:
        # 纯本地基线：关闭 Judge 与 LLM（不修改生产配置，仅本 benchmark 进程内）
        cfg["llm"] = dict(cfg.get("llm") or {})
        cfg["llm"]["provider"] = "none"
        cfg["evidence_judge"] = dict(cfg.get("evidence_judge") or {})
        cfg["evidence_judge"]["enabled"] = False

    t_embedder = time.perf_counter()
    embedder = create_embedder(cfg)
    embedder_ms = (time.perf_counter() - t_embedder) * 1000

    raw_store = create_store(cfg, cfg["paths"]["main_vector_db"])
    wiki_store = raw_store
    _install_wrappers(embedder)

    from knowledge_service import knowledge_search
    t0 = time.perf_counter()
    result = knowledge_search(
        query, mode=mode, use_llm=use_llm, cfg=cfg,
        embedder=embedder, raw_store=raw_store, wiki_store=wiki_store,
    )
    total_ms = (time.perf_counter() - t0) * 1000

    layers = {}
    for k, v in _timings.items():
        if k == "answer":
            layers[k] = v
        else:
            layers[k] = [round(x, 1) for x in v]

    answer_chars = len(result.get("answer") or "")
    return {
        "query": query,
        "mode": mode,
        "use_llm": use_llm,
        "status": result.get("status"),
        "sufficient": result.get("sufficient"),
        "answer_chars": answer_chars,
        "total_ms": round(total_ms, 1),
        "config_ms": round(cfg_ms, 1),
        "embedder_create_ms": round(embedder_ms, 1),
        "layers_ms": layers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("out")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--mode", default="deep", choices=["deep", "fast", "evidence_only"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    results = []
    for i in range(args.runs):
        results.append(run_one(args.query, use_llm=not args.no_llm, mode=args.mode))
    Path(args.out).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {args.out}: {len(results)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
