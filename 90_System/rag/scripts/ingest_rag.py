"""CLI: ingest source files into raw, wiki or main vector store."""
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
    if target == "main":
        return (
            [Path(paths["wiki"]), Path(paths["projects"])],
            Path(VAULT_ROOT),
            paths["main_vector_db"],
        )
    raise ValueError(f"unsupported target: {target}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest files into vector store")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--target",
        choices=["raw", "wiki", "main"],
        default="main",
        help=(
            "default main indexes 20_Wiki + 30_Projects into main_vector_db "
            "(production index); raw/wiki are optional explicit targets"
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