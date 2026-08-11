"""CLI: hybrid RAG query against the production main index, with gap logging."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.gaps import record_gap, resolve_gap
from rag_engine.llm import answer as llm_answer
from rag_engine.retrieval import answer_query
from rag_engine.vector_store import create_store


def _record_result_gap(result: dict, question: str, cfg: dict) -> None:
    gap_type = result.get("gap_type")
    if not gap_type:
        return
    gap_path = cfg["paths"].get("knowledge_gaps")
    if not gap_path:
        return
    sources = [
        (chunk.get("metadata") or {}).get("source", "")
        for chunk in result.get("chunks", [])
    ]
    record_gap(
        {
            "question": question,
            "topic": question,
            "type": gap_type,
            "suggested_action": "create_wiki"
            if gap_type == "knowledge_missing"
            else "",
            "related_sources": sources,
            "related_wiki": [
                source for source in sources if str(source).startswith("20_Wiki")
            ],
        },
        gap_path,
    )
    print(f"knowledge gap recorded: {gap_type}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid RAG query")
    parser.add_argument("question")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument(
        "--store",
        choices=["main", "raw", "wiki"],
        default="main",
        help=(
            "default main uses 20_Wiki + 30_Projects combined index "
            "(production); raw/wiki are optional explicit stores"
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    if args.top_k:
        cfg["retrieval"]["top_k"] = args.top_k
    if args.no_llm:
        cfg["llm"]["provider"] = "none"

    if args.store == "raw":
        raw_store = create_store(cfg, cfg["paths"]["raw_vector_db"])
        wiki_store = create_store(cfg, cfg["paths"]["wiki_vector_db"])
    elif args.store == "wiki":
        raw_store = create_store(cfg, cfg["paths"]["wiki_vector_db"])
        wiki_store = raw_store
    else:
        raw_store = create_store(cfg, cfg["paths"]["main_vector_db"])
        wiki_store = raw_store

    embedder = create_embedder(cfg)
    result = answer_query(
        args.question, cfg, embedder, raw_store, wiki_store, llm_answer=llm_answer
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    _record_result_gap(result, args.question, cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())