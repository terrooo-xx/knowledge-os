"""Ollama adapter via its OpenAI-compatible endpoint (default localhost:11434)."""
from __future__ import annotations

from .base_adapter import BaseAdapter
from .prompt import build_messages


class OllamaAdapter(BaseAdapter):
    def generate(self, question: str, context: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required") from exc
        llm_cfg = self.cfg["llm"]
        client = OpenAI(
            api_key="ollama",
            base_url=llm_cfg.get("base_url") or "http://localhost:11434/v1",
        )
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            messages=build_messages(question, context, self.cfg),
            temperature=llm_cfg.get("temperature", 0.2),
        )
        return response.choices[0].message.content or ""