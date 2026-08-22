"""Index Fingerprint tests (offline): content-hash change detection, mtime-only
no-change, non-indexed files ignored, added/modified/deleted."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.index_fingerprint import (  # noqa: E402
    current_fingerprint, detect_index_change, file_hash, fingerprint_digest,
    load_manifest,
)


def _mk_vault(tmp):
    root = Path(tmp)
    wiki = root / "20_Wiki" / "04_FreeRTOS"
    proj = root / "30_Projects" / "P"
    wiki.mkdir(parents=True)
    proj.mkdir(parents=True)
    (wiki / "Task.md").write_text("# FreeRTOS 任务\n内容", encoding="utf-8")
    (proj / "Index.md").write_text("# 项目\n内容", encoding="utf-8")
    (wiki / ".gitkeep").write_text("", encoding="utf-8")   # 非 .md，忽略
    return root, wiki, proj


def _manifest(root, entries):
    mp = root / "manifest.json"
    mp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return mp


def test_file_hash_content_based_not_mtime():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "a.md"
        p.write_text("hello", encoding="utf-8")
        h1 = file_hash(p)
        os.utime(p, (p.stat().st_atime + 10, p.stat().st_mtime + 10))  # 仅改 mtime
        assert file_hash(p) == h1
        p.write_text("hello2", encoding="utf-8")
        assert file_hash(p) != h1


def test_no_change_when_mtime_only_or_non_indexed():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, proj = _mk_vault(tmp)
        cur = current_fingerprint([wiki, proj], root)
        mp = _manifest(root, cur)
        # 无变化
        d = detect_index_change(mp, [wiki, proj], root)
        assert d["changed"] is False
        assert d["reasons"] == []
        # mtime 触碰（内容不变）-> 不触发
        for f in (wiki / "Task.md", proj / "Index.md"):
            os.utime(f, (f.stat().st_atime + 1, f.stat().st_mtime + 1))
        d2 = detect_index_change(mp, [wiki, proj], root)
        assert d2["changed"] is False
        # 修改 .gitkeep（非索引文件）-> 不触发
        (wiki / ".gitkeep").write_text("x", encoding="utf-8")
        d3 = detect_index_change(mp, [wiki, proj], root)
        assert d3["changed"] is False


def test_detect_added_modified_deleted():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, proj = _mk_vault(tmp)
        cur = current_fingerprint([wiki, proj], root)
        mp = _manifest(root, cur)
        # modified
        (wiki / "Task.md").write_text("# FreeRTOS 任务\n改过的内容", encoding="utf-8")
        # added
        (wiki / "New.md").write_text("# 新增\n内容", encoding="utf-8")
        # deleted
        (proj / "Index.md").unlink()
        d = detect_index_change(mp, [wiki, proj], root)
        assert d["changed"] is True
        assert "20_Wiki/04_FreeRTOS/Task.md" in d["modified"]
        assert "20_Wiki/04_FreeRTOS/New.md" in d["added"]
        assert "30_Projects/P/Index.md" in d["deleted"]
        assert any("index_" in r for r in d["reasons"])


def test_fingerprint_digest_stable():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, proj = _mk_vault(tmp)
        mp = _manifest(root, current_fingerprint([wiki, proj], root))
        d1 = fingerprint_digest(mp, [wiki, proj], root)
        d2 = fingerprint_digest(mp, [wiki, proj], root)
        assert d1 == d2
        (wiki / "Task.md").write_text("不同内容", encoding="utf-8")
        assert fingerprint_digest(mp, [wiki, proj], root) != d1


def test_load_manifest_tolerates_missing():
    assert load_manifest(Path("nonexistent.json")) == {}
