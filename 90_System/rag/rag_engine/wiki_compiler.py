"""LLM-Wiki Compiler: create draft Wiki, update proposals and project drafts."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .inbox_classifier import detect_domain, detect_project
from .wiki import read_frontmatter, _slug

WIKI_PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "wiki_compile.md"
TASK_LOG_DIR = Path(__file__).resolve().parents[3] / "90_System" / "任务记录"


def _llm_text(cfg: dict, instruction: str, material: str) -> str:
    llm_cfg = dict(cfg["llm"])
    llm_cfg["template"] = str(WIKI_PROMPT)
    adapter_cfg = dict(cfg)
    adapter_cfg["llm"] = llm_cfg
    from llm import create_llm

    adapter = create_llm(adapter_cfg)
    return adapter.generate(instruction, material)


def _clean_body(body: str) -> str:
    body = body.strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\n?", "", body)
        body = re.sub(r"\n?```$", "", body)
    return body.strip()


def _extract_title(body: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+)$", body)
    title = match.group(1).strip() if match else fallback
    return title.strip().strip('"') or fallback


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _related_wikis(text: str, cfg: dict, embedder=None, store=None) -> list[str]:
    if embedder is None or store is None or store.count() == 0:
        return []
    vector = embedder.embed([text[:1000]])[0]
    hits = store.search(vector, 5)
    wiki_root = Path(cfg["paths"]["wiki"])
    related = []
    for hit in hits:
        source = (hit.get("metadata") or {}).get("source", "")
        if not str(source).startswith("20_Wiki"):
            continue
        candidate = wiki_root / source[len("20_Wiki/"):]
        if candidate.exists():
            related.append(candidate.stem)
    return related


def create_draft(
    text: str,
    source: str,
    cfg: dict,
    domain: str | None = None,
    title: str | None = None,
    embedder=None,
    store=None,
    force: bool = False,
) -> Path:
    domain = domain or detect_domain(text)
    related = _related_wikis(text, cfg, embedder=embedder, store=store)
    material = text
    if related:
        material += "\n\n知识库中已存在的相关 Wiki：" + "\n".join(
            f"- {name}" for name in related
        )
    body = _llm_text(
        cfg,
        "请根据资料生成工程知识 Wiki 草稿，并只使用资料中的事实。",
        material,
    )
    body = _clean_body(body)
    title = _extract_title(body, title or Path(source).stem)
    wiki_root = Path(cfg["paths"]["wiki"]) / domain
    wiki_root.mkdir(parents=True, exist_ok=True)
    path = wiki_root / f"{_slug(title)}.md"
    if path.exists():
        status = read_frontmatter(path).get("status")
        if status in ("reviewed", "stable"):
            raise FileExistsError(f"禁止覆盖人工审核笔记: {path}")
        if not force:
            raise FileExistsError(f"draft 已存在，使用 --force 才可更新: {path}")
    today = date.today().isoformat()
    content = _frontmatter(
        {
            "type": "wiki",
            "domain": domain,
            "status": "draft",
            "source": [source],
            "created": today,
            "updated": today,
            "confidence": "medium",
            "review_required": True,
        }
    ) + body + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def create_update_proposal(
    target_wiki: Path,
    new_text: str,
    new_source: str,
    cfg: dict,
) -> Path:
    target_text = target_wiki.read_text(encoding="utf-8")
    material = (
        f"目标 Wiki：\n{target_text}\n\n新资料：\n{new_text}\n\n新来源：{new_source}"
    )
    body = _llm_text(
        cfg,
        "请生成 Wiki 更新建议，包含目标Wiki、变更原因、新增知识、建议删除、建议修改、新增来源、风险，并用“原文/修改后”对比展示关键变更。",
        material,
    )
    TASK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    index = 1
    while (TASK_LOG_DIR / f"Wiki更新建议_{stamp}_{index:03d}.md").exists():
        index += 1
    path = TASK_LOG_DIR / f"Wiki更新建议_{stamp}_{index:03d}.md"
    vault_root = Path(__file__).resolve().parents[3]
    try:
        target_rel = target_wiki.relative_to(vault_root)
    except ValueError:
        target_rel = target_wiki
    content = (
        f"# Wiki 更新建议\n\n"
        f"- 目标 Wiki：`{target_rel}`\n"
        f"- 新增来源：`{new_source}`\n"
        f"- 状态：待人工确认\n\n---\n\n{_clean_body(body)}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def create_project_draft(
    text: str,
    source: str,
    project: str,
    cfg: dict,
    title: str | None = None,
    force: bool = False,
) -> Path:
    body = _llm_text(
        cfg,
        "请根据资料生成项目文档草稿，保留项目背景、方案、参数和来源，只使用资料中的事实。",
        text,
    )
    body = _clean_body(body)
    title = _extract_title(body, title or Path(source).stem)
    project_root = Path(cfg["paths"]["projects"]) / project
    project_root.mkdir(parents=True, exist_ok=True)
    path = project_root / f"{_slug(title)}.md"
    if path.exists():
        status = read_frontmatter(path).get("status")
        if status in ("reviewed", "stable"):
            raise FileExistsError(f"禁止覆盖人工审核笔记: {path}")
        if not force:
            raise FileExistsError(f"draft 已存在，使用 --force 才可更新: {path}")
    today = date.today().isoformat()
    content = _frontmatter(
        {
            "type": "project",
            "domain": project,
            "status": "draft",
            "source": [source],
            "created": today,
            "updated": today,
            "confidence": "medium",
            "review_required": True,
        }
    ) + body + "\n"
    path.write_text(content, encoding="utf-8")
    return path