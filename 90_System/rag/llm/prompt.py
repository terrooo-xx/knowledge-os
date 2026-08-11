"""Load the RAG answer prompt template and build chat messages."""
from __future__ import annotations

from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[2] / "prompts" / "rag_answer.md"
VAULT_ROOT = Path(__file__).resolve().parents[3]
SYSTEM_USER_MARKER = "---USER---"


def _template_path(cfg: dict) -> Path:
    template = cfg["llm"].get("template")
    if not template:
        return DEFAULT_TEMPLATE
    path = Path(template)
    return path if path.is_absolute() else VAULT_ROOT / path


def build_messages(question: str, context: str, cfg: dict) -> list[dict]:
    template = _template_path(cfg).read_text(encoding="utf-8")
    if SYSTEM_USER_MARKER in template:
        system_part, user_part = template.split(SYSTEM_USER_MARKER, 1)
    else:
        system_part, user_part = template, template
    user_part = (
        user_part.replace("{{context}}", context)
        .replace("{{question}}", question)
        .strip()
    )
    return [
        {"role": "system", "content": system_part.strip()},
        {"role": "user", "content": user_part},
    ]