"""Incremental RAG indexing with document hash manifest."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .atomic_io import atomic_write_json
from .ingest import ingest_file


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict) -> None:
    atomic_write_json(path, manifest)


def _scan_docs(roots: list[Path], base_root: Path) -> dict[str, Path]:
    docs = {}
    for root in roots:
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(base_root)).replace("\\", "/")
            docs[rel] = path
    return docs


def sync_index(
    cfg: dict,
    embedder,
    store,
    roots: list[Path],
    manifest_path: Path,
    base_root: Path,
    only_changed: bool = False,
    only_file: str | None = None,
) -> dict:
    docs = _scan_docs(roots, base_root)
    manifest = load_manifest(manifest_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = []
    deleted = []

    if not only_changed or not manifest:
        store.clear()
        manifest = {}
        for rel, path in docs.items():
            text_hash = file_hash(path)
            added = ingest_file(
                path,
                cfg,
                store,
                embedder,
                relative_root=base_root,
                extra_metadata={
                    "document_path": rel,
                    "document_hash": text_hash,
                    "updated_at": now,
                },
            )
            manifest[rel] = {
                "hash": text_hash,
                "chunks": added,
                "indexed_at": now,
            }
            changed.append(rel)
        save_manifest(manifest_path, manifest)
        return {
            "changed": changed,
            "deleted": [],
            "rebuilt": True,
            "total": len(docs),
        }

    for rel in list(manifest):
        if rel not in docs and (only_file is None or rel == only_file):
            removed = store.delete_by_metadata("source", rel)
            del manifest[rel]
            deleted.append({"path": rel, "removed_chunks": removed})

    for rel, path in docs.items():
        if only_file is not None and rel != only_file:
            continue
        text_hash = file_hash(path)
        previous = manifest.get(rel)
        if previous and previous["hash"] == text_hash:
            continue
        store.delete_by_metadata("source", rel)
        added = ingest_file(
            path,
            cfg,
            store,
            embedder,
            relative_root=base_root,
            extra_metadata={
                "document_path": rel,
                "document_hash": text_hash,
                "updated_at": now,
            },
        )
        manifest[rel] = {
            "hash": text_hash,
            "chunks": added,
            "indexed_at": now,
        }
        changed.append(rel)

    save_manifest(manifest_path, manifest)
    return {
        "changed": changed,
        "deleted": deleted,
        "rebuilt": False,
        "total": len(docs),
    }