"""CLI: review wiki drafts and promote draft -> reviewed -> stable."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.wiki_review import find_wiki, list_wikis, set_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Review wiki drafts")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--list", action="store_true", help="list all wikis")
    parser.add_argument("--show", metavar="NAME", help="show a wiki")
    parser.add_argument("--approve", metavar="NAME", help="draft -> reviewed")
    parser.add_argument("--stabilize", metavar="NAME", help="reviewed -> stable")
    parser.add_argument("--force", action="store_true", help="allow draft -> stable")
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    wiki_root = Path(cfg["paths"]["wiki"])

    if args.list:
        for record in list_wikis(wiki_root):
            print(f"{record['status']:10s} {record['path']}")
        return 0
    if args.show:
        path = find_wiki(wiki_root, args.show)
        print(path.read_text(encoding="utf-8"))
        return 0
    if args.approve:
        path = find_wiki(wiki_root, args.approve)
        status = set_status(path, "reviewed")
        print(f"{path} -> {status}")
        return 0
    if args.stabilize:
        path = find_wiki(wiki_root, args.stabilize)
        status = set_status(path, "stable", force=args.force)
        print(f"{path} -> {status}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())