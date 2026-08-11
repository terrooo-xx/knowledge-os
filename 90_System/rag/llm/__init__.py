"""LLM adapter layer: RAG core only sees create_llm().generate()."""
from __future__ import annotations

from .base_adapter import BaseAdapter, ContextOnlyAdapter
from .mock_adapter import MockAdapter
from .deepseek_adapter import DeepSeekAdapter
from .openai_adapter import OpenAIAdapter
from .ollama_adapter import OllamaAdapter


def _normalize_llm_cfg(cfg: dict) -> None:
    llm_cfg = cfg["llm"]
    if isinstance(llm_cfg.get("model"), dict):
        llm_cfg["model"] = llm_cfg["model"].get("name")
    api = llm_cfg.get("api")
    if isinstance(api, dict) and api.get("base_url"):
        llm_cfg.setdefault("base_url", api["base_url"])


def create_llm(cfg: dict):
    _normalize_llm_cfg(cfg)
    provider = cfg["llm"]["provider"]
    if provider == "none":
        return ContextOnlyAdapter(cfg)
    if provider == "mock":
        return MockAdapter(cfg)
    if provider == "deepseek":
        return DeepSeekAdapter(cfg)
    if provider in ("openai", "openai_compatible"):
        return OpenAIAdapter(cfg)
    if provider == "ollama":
        return OllamaAdapter(cfg)
    raise RuntimeError(f"unsupported llm provider: {provider}")


__all__ = [
    "BaseAdapter",
    "ContextOnlyAdapter",
    "MockAdapter",
    "DeepSeekAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
    "create_llm",
]