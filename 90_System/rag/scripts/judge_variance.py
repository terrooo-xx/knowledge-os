"""Judge Variance CLI: repeat the LLM Relevance Judge N times on FIXED evidence.

For each query, the full production chain (knowledge_search mode=fast) runs once;
the judge input chunks are captured via a patched judge_relevance wrapper. Then
the judge runs N more times on the exact same chunks (retrieval/reranker/evidence
unchanged). Outputs:

    - 40_Outputs/RAG Evaluation/judge_variance/<run>/judge_variance.json
    - 40_Outputs/RAG Evaluation/judge_variance/<run>/judge_variance.md
    - 40_Outputs/RAG Evaluation/latest_judge_variance.json

Usage:
    python judge_variance.py --query-ids q_drone_power,q_freertos_scheduler --runs 3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
AGENT_DIR = RAG_DIR / "interface"
VAULT_ROOT = Path(__file__).resolve().parents[3]
for d in (str(RAG_DIR), str(AGENT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

import rag_engine.retrieval as retrieval  # noqa: E402
from rag_engine.config import load_config, resolve_paths  # noqa: E402
from rag_engine.embeddings import create_embedder  # noqa: E402
from rag_engine.judge_variance import (  # noqa: E402
    classify_variance, judge_variance_stats, render_variance_markdown,
)
from rag_engine.vector_store import create_store  # noqa: E402

EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"


def run_one(query: str, cfg: dict, embedder, raw_store, wiki_store, repeats: int) -> dict:
    """Run the production chain once (capture judge input), then repeat judge N times."""
    from knowledge_service import knowledge_search

    captured: dict = {}
    original = retrieval.judge_relevance

    def _capture(q, chunks, cfg_):
        if not captured.get("chunks"):
            captured["chunks"] = chunks
        return original(q, chunks, cfg_)

    retrieval.judge_relevance = _capture
    try:
        result = knowledge_search(query, mode="fast", use_llm=True, cfg=cfg,
                                  embedder=embedder, raw_store=raw_store, wiki_store=wiki_store,
                                  record_gap=False)
    finally:
        retrieval.judge_relevance = original

    chunks = captured.get("chunks") or []
    results = []
    for _ in range(max(1, repeats)):
        try:
            j = original(query, chunks, cfg)
        except Exception as exc:
            j = {"relevance": "irrelevant", "error": str(exc)}
        results.append(j)
    return {
        "query": query,
        "status": result.get("status"),
        "sufficient": result.get("sufficient"),
        "judge_input_chunks": len(chunks),
        "results": [{"relevance": r.get("relevance"), "confidence": r.get("confidence"),
                     "error": r.get("error")} for r in results],
        "classification": classify_variance(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge Variance CLI")
    parser.add_argument("--query-ids", required=True, help="comma-separated benchmark query ids")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--out", default=str(EVAL_ROOT / "judge_variance"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    embedder = create_embedder(cfg)
    raw_store = create_store(cfg, cfg["paths"]["main_vector_db"])
    wiki_store = raw_store

    # load benchmark queries
    import yaml
    bench = yaml.safe_load((RAG_DIR / "evaluation" / "benchmark.yaml").read_text(encoding="utf-8")) or {}
    by_id = {q["id"]: q["query"] for q in bench.get("queries", [])}

    qids = [x.strip() for x in args.query_ids.split(",") if x.strip()]
    entries = []
    for qid in qids:
        if qid not in by_id:
            print(f"WARN: unknown query id {qid}", file=sys.stderr)
            continue
        print(f"running judge variance for {qid} ({args.runs}x) ...", file=sys.stderr)
        e = run_one(by_id[qid], cfg, embedder, raw_store, wiki_store, args.runs)
        e["query_id"] = qid
        entries.append(e)

    stats = judge_variance_stats(entries)
    run_id = datetime.now().strftime("jv-%Y%m%dT%H%M%S")
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "runs": args.runs,
        "entries": entries,
        "stats": stats,
    }
    (out_dir / "judge_variance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "judge_variance.md").write_text(
        render_variance_markdown(entries, stats, {"runs": args.runs, "generated_at": payload["generated_at"]}),
        encoding="utf-8")
    latest = {
        "run_id": run_id, "generated_at": payload["generated_at"], "runs": args.runs,
        "stats": stats, "entries": entries,
        "report_path": (out_dir / "judge_variance.md").relative_to(VAULT_ROOT).as_posix(),
    }
    (EVAL_ROOT / "latest_judge_variance.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"ok": True, "run_id": run_id, "stats": stats,
                          "entries": [{e["query_id"]: e["classification"]} for e in entries]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"stable_rate={stats['stable_rate']}% flip_rate={stats['flip_rate']}% "
              f"({stats['stable_sufficient_count']} stable_sufficient / "
              f"{stats['stable_insufficient_count']} stable_insufficient / "
              f"{stats['flip_count']} variance)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
