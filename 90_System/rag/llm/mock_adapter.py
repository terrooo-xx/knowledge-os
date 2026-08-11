"""Mock adapter for offline tests."""
from __future__ import annotations

from .base_adapter import BaseAdapter


class MockAdapter(BaseAdapter):
    def generate(self, question: str, context: str) -> str:
        return f"Mock answer for: {question}\n\n{context[:200]}"