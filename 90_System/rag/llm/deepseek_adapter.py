"""DeepSeek API adapter. Reads DEEPSEEK_API_KEY from environment only."""
from __future__ import annotations

import os

from .base_adapter import BaseAdapter
from .prompt import build_messages


class DeepSeekAdapter(BaseAdapter):
    def generate(self, question: str, context: str) -> str:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未设置")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required") from exc
        llm_cfg = self.cfg["llm"]
        client = OpenAI(
            api_key=api_key,
            base_url=llm_cfg.get("base_url") or "https://api.deepseek.com",
        )
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            messages=build_messages(question, context, self.cfg),
            temperature=llm_cfg.get("temperature", 0.2),
        )
        return response.choices[0].message.content or ""