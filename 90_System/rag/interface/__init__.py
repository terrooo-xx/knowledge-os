"""Knowledge OS Agent Knowledge Interface (READ-ONLY).

外部 AI Agent / Codex 通过本包查询 Knowledge OS，不直接访问 Wiki / Vector DB。
未来可在此之上包装成 MCP Tool（阶段⑪-B）。
"""
from .knowledge_service import knowledge_search

__all__ = ["knowledge_search"]
