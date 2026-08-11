"""CLI: LLM-Wiki Compiler for create_wiki / update_wiki / project_update."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.ingest import parse_file
from rag_engine.vector_store import create_store
from rag_engine.wiki_compiler import (
    create_draft,
    create_project_draft,
    create_update_proposal,
)


def _extract(path: Path) -> str:
    pages = parse_file(path, relative_root=None)
    return "\n\n".join(page.get("text", "") for page in pages if page.get("text"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile wiki drafts with LLM")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--action",
        choices=["create", "update", "project"],
        default="create",
    )
    parser.add_argument("--file", help="inbox source file (vault-relative path)")
    parser.add_argument("--domain", default=None, help="wiki domain for create")
    parser.add_argument("--title", default=None, help="wiki title override")
    parser.add_argument(
        "--target-wiki", default=None, help="target wiki for update action"
    )
    parser.add_argument("--project", default=None, help="project name for project action")
    parser.add_argument(
        "--no-related", action="store_true", help="skip related wiki lookup"
    )
    parser.add_argument("--force", action="store_true", help="allow overwriting a draft")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.file:
        parser.error("--file is required")
    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    source_path = Path(args.file)
    source = str(source_path.relative_to(VAULT_ROOT)) if source_path.is_absolute() else args.file
    text = _extract(Path(VAULT_ROOT) / source)
    if not text.strip():
        print("error: file has no extractable text", file=sys.stderr)
        return 1

    embedder = None
    store = None
    if not args.no_related:
        embedder = create_embedder(cfg)
        store = create_store(cfg, cfg["paths"]["main_vector_db"])

    if args.action == "create":
        path = create_draft(
            text,
            source,
            cfg,
            domain=args.domain,
            title=args.title,
            embedder=embedder,
            store=store,
            force=args.force,
        )
        print(path)
        return 0

    if args.action == "update":
        if not args.target_wiki:
            parser.error("--target-wiki is required for update action")
        target = Path(VAULT_ROOT) / args.target_wiki
        if not target.exists():
            parser.error(f"target wiki not found: {args.target_wiki}")
        proposal = create_update_proposal(target, text, source, cfg)
        print(proposal)
        return 0

    if args.action == "project":
        if not args.project:
            parser.error("--project is required for project action")
        path = create_project_draft(
            text,
            source,
            args.project,
            cfg,
            title=args.title,
            force=args.force,
        )
        print(path)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())