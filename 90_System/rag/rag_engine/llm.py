"""Legacy entry point: delegate to the llm adapter layer."""
from __future__ import annotations

from llm import create_llm
from llm.context import build_context


def _source_references(chunks: list[dict]) -> str:
    lines = []
    for index, chunk in enumerate(chunks, start=1):
        source = (chunk.get("metadata") or {}).get("source", "未知来源")
        lines.append(f"[{index}] {source}")
    return "\n".join(lines)


def answer(question: str, chunks: list[dict], cfg: dict) -> str:
    adapter = create_llm(cfg)
    text = adapter.generate(question, build_context(chunks))
    references = _source_references(chunks)
    if references:
        text += "\n\n引用来源：\n" + references
    return text