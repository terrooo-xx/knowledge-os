"""LLM adapter base interface and context-only fallback."""
from __future__ import annotations


class BaseAdapter:
    """统一生成接口；RAG 流程只调用 generate(question, context)。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def generate(self, question: str, context: str) -> str:
        raise NotImplementedError


class ContextOnlyAdapter(BaseAdapter):
    def generate(self, question: str, context: str) -> str:
        return "（未配置 LLM，以下为检索上下文）\n\n" + context