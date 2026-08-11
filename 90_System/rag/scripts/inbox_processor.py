"""Inbox Processor: analyze inbox files and produce draft suggestions.

First version is analysis-first: it never deletes, overwrites, moves or
renames original files. With --apply it may generate a new draft Wiki.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths
from rag_engine.embeddings import create_embedder
from rag_engine.inbox_classifier import classify_text
from rag_engine.ingest import parse_file
from rag_engine.vector_store import create_store
from rag_engine.wiki_compiler import create_draft

SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".html", ".htm"}
TASK_LOG = Path(VAULT_ROOT) / "90_System" / "任务记录" / "inbox_processor_log.md"


def _extract_text(path: Path) -> tuple[str, str]:
    pages = parse_file(path, relative_root=None)
    text = "\n\n".join(page.get("text", "") for page in pages if page.get("text"))
    document_type = pages[0]["document_type"] if pages else path.suffix.lower().lstrip(".")
    return text, document_type


def _log_run(records: list[dict]) -> None:
    TASK_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = TASK_LOG.read_text(encoding="utf-8") if TASK_LOG.exists() else ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = "\n".join(
        f"| {r.get('source')} | {r.get('document_type')} | {r.get('action')} | {r.get('target') or ''} | {r.get('reason')} |"
        for r in records
    )
    section = (
        f"\n## {stamp}\n\n"
        "| 原始文件 | 类型 | 动作 | 目标 | 原因 |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n"
    )
    TASK_LOG.write_text(existing.rstrip() + "\n" + section + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze and classify inbox files")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--file", action="append", help="specific file; repeatable")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="generate new draft Wiki for create_wiki suggestions",
    )
    args = parser.parse_args()

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    inbox_root = Path(cfg["paths"]["inbox"])
    embedder = create_embedder(cfg)
    main_store = create_store(cfg, cfg["paths"]["main_vector_db"])

    files = []
    for raw in args.file or []:
        p = Path(raw)
        files.append(p if p.is_absolute() else Path(VAULT_ROOT) / p)
    if not files:
        files = sorted(
            p
            for p in inbox_root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        )

    records = []
    for path in files:
        try:
            text, document_type = _extract_text(path)
        except Exception as exc:
            records.append(
                {
                    "source": str(path.relative_to(VAULT_ROOT)),
                    "document_type": "unknown",
                    "action": "needs_review",
                    "target": None,
                    "reason": f"解析失败: {exc}",
                }
            )
            continue
        source = path.relative_to(VAULT_ROOT).as_posix()
        suggestion = classify_text(
            text,
            cfg,
            embedder=embedder,
            store=main_store,
            source=source,
            document_type=document_type,
        )
        if args.apply and suggestion["action"] == "create_wiki" and suggestion.get("domain"):
            try:
                draft_path = create_draft(
                    text,
                    source,
                    cfg,
                    domain=suggestion["domain"],
                    title=path.stem,
                    embedder=embedder,
                    store=main_store,
                )
                suggestion["generated_draft"] = str(draft_path.relative_to(VAULT_ROOT))
            except Exception as exc:
                suggestion["generated_draft_error"] = str(exc)
        records.append(suggestion)
        print(json.dumps(suggestion, ensure_ascii=False))

    _log_run(records)
    print(f"processed: {len(records)} files; log: {TASK_LOG}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())