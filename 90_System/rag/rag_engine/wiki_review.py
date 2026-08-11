"""Wiki review: list/show and draft -> reviewed -> stable transitions."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .wiki import read_frontmatter

VALID_STATUSES = {"draft", "reviewed", "stable"}


def find_wiki(wiki_root: Path, name: str) -> Path:
    name = name.replace("\\", "/").rstrip(".md")
    for path in wiki_root.rglob("*.md"):
        if path.stem == name or str(path).replace("\\", "/").endswith(name + ".md"):
            return path
    raise FileNotFoundError(f"Wiki 不存在: {name}")


def list_wikis(wiki_root: Path) -> list[dict]:
    records = []
    for path in sorted(wiki_root.rglob("*.md")):
        frontmatter = read_frontmatter(path)
        records.append(
            {
                "path": str(path.relative_to(wiki_root.parent)),
                "status": frontmatter.get("status", "unknown"),
            }
        )
    return records


def set_status(path: Path, new_status: str, force: bool = False) -> str:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    current = read_frontmatter(path).get("status", "unknown")
    if current == new_status:
        return current
    allowed = {"draft": {"reviewed"}, "reviewed": {"stable"}}
    if new_status == "stable" and current == "draft":
        if not force:
            raise ValueError("禁止 draft 直接升级为 stable，需先 approved")
    elif new_status not in allowed.get(current, set()):
        raise ValueError(f"不允许从 {current} 转为 {new_status}")
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^status:\s*.*$", f"status: {new_status}", text, count=1)
    text = re.sub(r"(?m)^updated:\s*.*$", f"updated: {date.today().isoformat()}", text, count=1)
    path.write_text(text, encoding="utf-8")
    return new_status