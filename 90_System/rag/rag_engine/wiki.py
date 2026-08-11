"""Shared Markdown frontmatter and slug helpers for the Wiki toolchain.

Used by `wiki_compiler` and `wiki_review`. The legacy placeholder draft
compiler (`compile_draft`) was removed in Phase 3; `wiki_compile.py` is the
single formal Wiki compilation entry.
"""
from __future__ import annotations

import re
from pathlib import Path


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    frontmatter: dict = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip().strip("\"'")
    return frontmatter


def _slug(text: str) -> str:
    slug = re.sub(
        r"[^\w\u4e00-\u9fff-]+", "-", text.strip(), flags=re.UNICODE
    ).strip("-")
    return slug or "未命名"
