"""CLI entry for the Agent Knowledge Interface (READ-ONLY).

Usage:
    python 90_System/rag/interface/knowledge_cli.py "问题" [--no-llm] [--top-k N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from knowledge_service import knowledge_search  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge OS Agent Knowledge Interface CLI")
    parser.add_argument("query", help="要查询的问题")
    parser.add_argument("--no-llm", action="store_true", help="离线模式：不调用 LLM（无回答/无 Judge）")
    parser.add_argument("--top-k", type=int, default=None, help="检索 top_k（默认取配置）")
    args = parser.parse_args()
    result = knowledge_search(args.query, use_llm=not args.no_llm, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
