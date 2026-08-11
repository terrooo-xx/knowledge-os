"""OpenAI-compatible API adapter (OpenAI, Azure-style or any compatible host)."""
from __future__ import annotations

import os

from .base_adapter import BaseAdapter
from .prompt import build_messages


class OpenAIAdapter(BaseAdapter):
    def generate(self, question: str, context: str) -> str:
        llm_cfg = self.cfg["llm"]
        api_key_env = llm_cfg.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} 未设置")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required") from exc
        client = OpenAI(api_key=api_key, base_url=llm_cfg.get("base_url") or None)
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            messages=build_messages(question, context, self.cfg),
            temperature=llm_cfg.get("temperature", 0.2),
        )
        return response.choices[0].message.content or ""