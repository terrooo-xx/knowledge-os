"""Configuration loading and path resolution for the RAG engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "paths": {
        "inbox": "00_Inbox",
        "wiki": "20_Wiki",
        "projects": "30_Projects",
        "raw_vector_db": "90_System/rag/database/raw_vector_db",
        "wiki_vector_db": "90_System/rag/database/wiki_vector_db",
        "main_vector_db": "90_System/rag/database/main_vector_db",
        "knowledge_gaps": "90_System/rag/tests/knowledge_gaps.yaml",
        "cache": "90_System/rag/cache",
    },
    "chunking": {"size": 800, "overlap": 100},
    "embedding": {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "api_key_env": "OPENAI_API_KEY",
    },
    "store": {"provider": "local"},
    "retrieval": {
        "wiki_first": True,
        "confidence_threshold": 0.78,
        "top_k": 5,
        "dense_weight": 0.6,
        "bm25_weight": 0.4,
    },
    "reranker": {
        "enabled": False,
        "provider": "bge",
        "model": "BAAI/bge-reranker-v2-m3",
        "top_k": 5,
    },
    "llm": {
        "provider": "none",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
    },
    "evidence_judge": {"enabled": False, "top_k": 5},
    "inbox": {"similarity_threshold": 0.82, "update_threshold": 0.65},
    "wiki": {
        "default_domain": "01_计算机基础",
        "status": "draft",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | None = None) -> dict:
    cfg = _deep_merge(DEFAULTS, {})
    if path and Path(path).is_file():
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to load config.yaml") from exc
        with open(path, "r", encoding="utf-8") as fh:
            cfg = _deep_merge(cfg, yaml.safe_load(fh) or {})
    return cfg


def resolve_paths(cfg: dict, base: Path) -> dict:
    resolved = dict(cfg)
    resolved["paths"] = {
        key: str(Path(base) / value) for key, value in cfg["paths"].items()
    }
    return resolved
