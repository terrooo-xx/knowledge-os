"""CLI: rebuild or incrementally update the main/wiki vector index."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.indexing import sync_index
from rag_engine.ingest import ingest_file
from rag_engine.vector_store import create_store


def _rebuild_wiki(cfg, embedder, args) -> int:
    wiki_root = Path(cfg["paths"]["wiki"])
    store = create_store(cfg, cfg["paths"]["wiki_vector_db"])
    store.clear()
    roots = [wiki_root / domain for domain in args.domain] if args.domain else [wiki_root]
    total = 0
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            added = ingest_file(path, cfg, store, embedder, relative_root=wiki_root)
            total += added
            print(f"indexed {path}: {added} chunks")
    print(f"total chunks: {total}; wiki store size: {store.count()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild or update vector index")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--target", choices=["main", "wiki"], default="main",
        help="main indexes 20_Wiki + 30_Projects with manifest",
    )
    parser.add_argument(
        "--changed", action="store_true",
        help="only index changed/new/deleted documents (requires manifest)",
    )
    parser.add_argument(
        "--file", default=None, help="only process one document (vault-relative path)"
    )
    parser.add_argument(
        "--domain", action="append", help="restrict wiki rebuild to a domain subdir"
    )
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    embedder = create_embedder(cfg)

    if args.target == "wiki":
        return _rebuild_wiki(cfg, embedder, args)

    store = create_store(cfg, cfg["paths"]["main_vector_db"])
    manifest_path = Path(cfg["paths"]["main_vector_db"]).parent / "index_manifest.json"
    roots = [Path(cfg["paths"]["wiki"]), Path(cfg["paths"]["projects"])]
    result = sync_index(
        cfg,
        embedder,
        store,
        roots,
        manifest_path,
        base_root=VAULT_ROOT,
        only_changed=args.changed,
        only_file=args.file,
    )
    print(f"rebuilt={result['rebuilt']} changed={len(result['changed'])} deleted={len(result['deleted'])}")
    for rel in result["changed"]:
        print(f"changed: {rel}")
    for item in result["deleted"]:
        print(f"deleted: {item['path']} (removed {item['removed_chunks']} chunks)")
    print(f"store size: {store.count()}; manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())