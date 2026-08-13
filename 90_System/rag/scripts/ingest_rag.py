"""CLI: ingest source files into raw or wiki vector store (optional paths).

main_vector_db is maintained by update_index.py (the standard entry).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.ingest import ingest_file
from rag_engine.vector_store import create_store

SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".html", ".htm"}


def _target_paths(cfg: dict, target: str):
    paths = cfg["paths"]
    if target == "raw":
        return [Path(paths["inbox"])], Path(paths["inbox"]), paths["raw_vector_db"]
    if target == "wiki":
        return [Path(paths["wiki"])], Path(paths["wiki"]), paths["wiki_vector_db"]
    raise ValueError(f"unsupported target: {target} (main is owned by update_index.py)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest files into vector store")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--target",
        choices=["raw", "wiki"],
        default="raw",
        help=(
            "raw indexes 00_Inbox into raw_vector_db; wiki indexes 20_Wiki into "
            "wiki_vector_db. main_vector_db is maintained by update_index.py."
        ),
    )
    parser.add_argument("--file", action="append", help="specific file; repeatable")
    parser.add_argument("--clear", action="store_true", help="clear store before ingest")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    roots, relative_root, store_path = _target_paths(cfg, args.target)
    store = create_store(cfg, store_path)
    if args.clear:
        store.clear()
    embedder = create_embedder(cfg)

    files = [Path(p) for p in args.file] if args.file else []
    if not files:
        files = sorted(
            p
            for root in roots
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        )

    total = 0
    skipped = 0
    for path in files:
        try:
            added = ingest_file(path, cfg, store, embedder, relative_root=relative_root)
        except Exception as exc:
            print(f"SKIP {path}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        total += added
        print(f"ingested {path}: {added} chunks")
    print(f"total chunks: {total}; skipped: {skipped}; store size: {store.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())