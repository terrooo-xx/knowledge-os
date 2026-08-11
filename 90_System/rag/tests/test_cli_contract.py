"""CLI contract regression tests for the Phase 3 Scheme A architecture.

Guards: ingest_rag default target = main; raw/wiki targets remain valid;
hybrid_query default store = main and --compile-wiki is gone; wiki_compile.py
is the single formal Wiki compilation entry.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))


def _load(name: str):
    path = RAG_DIR / "scripts" / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _option_strings(parser) -> set:
    opts = set()
    for action in parser._actions:
        opts.update(action.option_strings)
    return opts


def test_ingest_rag_default_target_is_main():
    mod = _load("ingest_rag.py")
    assert mod.build_parser().parse_args([]).target == "main"


def test_ingest_rag_raw_and_wiki_targets_still_valid():
    mod = _load("ingest_rag.py")
    assert mod.build_parser().parse_args(["--target", "raw"]).target == "raw"
    assert mod.build_parser().parse_args(["--target", "wiki"]).target == "wiki"


def test_hybrid_query_default_store_is_main():
    mod = _load("hybrid_query.py")
    assert mod.build_parser().parse_args(["问题"]).store == "main"


def test_hybrid_query_compile_wiki_removed():
    mod = _load("hybrid_query.py")
    opts = _option_strings(mod.build_parser())
    assert "--compile-wiki" not in opts
    assert "--domain" not in opts
    assert "--store" in opts


def test_wiki_compile_is_formal_entry():
    mod = _load("wiki_compile.py")
    opts = _option_strings(mod.build_parser())
    assert "--action" in opts
    assert "--file" in opts
    assert "--compile-wiki" not in opts


if __name__ == "__main__":
    for t in (
        test_ingest_rag_default_target_is_main,
        test_ingest_rag_raw_and_wiki_targets_still_valid,
        test_hybrid_query_default_store_is_main,
        test_hybrid_query_compile_wiki_removed,
        test_wiki_compile_is_formal_entry,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all CLI contract tests passed")
