"""CLI: rerank candidate chunks from a JSON file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.rerank import rerank


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerank candidate chunks")
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--chunks", required=True, help='JSON file containing {"chunks": [...]}'
    )
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    data = json.loads(Path(args.chunks).read_text(encoding="utf-8"))
    out = rerank(args.query, data["chunks"], cfg)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
