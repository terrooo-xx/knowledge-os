"""Regression test: CLI scripts must resolve the vault root correctly."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = RAG_DIR.parents[1]

SCRIPT_NAMES = [
    "ingest_rag.py",
    "update_index.py",
    "hybrid_query.py",
    "reranker.py",
    "wiki_compile.py",
]


def _load_script(name: str):
    path = RAG_DIR / "scripts" / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_vault_root_is_vault():
    for name in SCRIPT_NAMES:
        module = _load_script(name)
        assert Path(module.VAULT_ROOT).resolve() == VAULT_ROOT.resolve()


if __name__ == "__main__":
    test_vault_root_is_vault()
    print("PASS test_vault_root_is_vault")
