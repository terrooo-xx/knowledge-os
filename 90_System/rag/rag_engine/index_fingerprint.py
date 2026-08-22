"""Index Fingerprint: content-hash based knowledge-change detection.

Detects REAL knowledge changes (file content hash change) for the governance
gate — an mtime-only touch or a non-indexed file does NOT count as a change.

Hash = sha256(file bytes), identical to rag_engine.indexing.file_hash so the
manifest comparison is exact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_docs(roots: list[Path], base_root: Path) -> dict[str, Path]:
    docs: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix.lower() != ".md":
                continue
            rel = p.relative_to(base_root).as_posix()
            docs[rel] = p
    return docs


def current_fingerprint(roots: list[Path], base_root: Path) -> dict[str, str]:
    """rel_path -> sha256 for every indexed .md file."""
    return {rel: file_hash(p) for rel, p in _scan_docs(roots, base_root).items()}


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def detect_index_change(manifest_path: Path, roots: list[Path], base_root: Path) -> dict:
    """Compare current content fingerprint against the index manifest.

    Returns {"changed": bool, "added": [...], "modified": [...], "deleted": [...],
             "reasons": [...]}. mtime-only / non-indexed changes are ignored.
    """
    manifest = load_manifest(manifest_path)
    current = current_fingerprint(roots, base_root)
    added = sorted(set(current) - set(manifest))
    deleted = sorted(set(manifest) - set(current))
    modified = []
    for rel in set(current) & set(manifest):
        prev = manifest.get(rel)
        prev_hash = prev.get("hash") if isinstance(prev, dict) else prev
        if prev_hash != current[rel]:
            modified.append(rel)
    modified.sort()
    changed = bool(added or modified or deleted)
    reasons = []
    if added:
        reasons.append(f"index_added:{len(added)}")
    if modified:
        reasons.append(f"index_modified:{len(modified)}")
    if deleted:
        reasons.append(f"index_deleted:{len(deleted)}")
    return {
        "changed": changed,
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "reasons": reasons,
        "fingerprint_size": len(current),
    }


def fingerprint_digest(manifest_path: Path, roots: list[Path], base_root: Path) -> str:
    """Stable digest of the CURRENT content fingerprint (for logging/state)."""
    fp = current_fingerprint(roots, base_root)
    return hashlib.sha256(
        json.dumps(fp, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
