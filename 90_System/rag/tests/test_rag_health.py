"""RAG Health Check tests: healthy / corrupt / NUL / dup / orphan / mismatch / empty."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.vector_store import VectorStore
from scripts.rag_health_check import run_checks


def _write_source(root: Path, rel: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# " + rel + "\ncontent", encoding="utf-8")
    return p


def _healthy_env(tmp: str):
    root = Path(tmp)
    db = root / "db"
    store = VectorStore(str(db))
    rels = ["20_Wiki/03_STM32/a.md", "30_Projects/p.md"]
    for i, rel in enumerate(rels):
        src = _write_source(root, rel)
        store.add(
            "DMA 数据搬运" if i == 0 else "底盘控制",
            {"source": rel, "document_path": rel, "document_hash": "h" + str(i), "status": "stable" if i == 0 else "draft"},
            [1.0, 0.0, 0.0],
        )
    manifest = {
        rel: {"hash": "h" + str(i), "chunks": 1, "indexed_at": "2026-08-11T00:00:00+00:00"}
        for i, rel in enumerate(rels)
    }
    manifest_path = db / "index_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root, db / "records.jsonl", manifest_path


def _levels(results):
    return [r.level for r in results]


def _counts(results):
    from collections import Counter
    return Counter(r.level for r in results)


def test_healthy_db_no_error():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] == 0
        assert any(r.level == "PASS" for r in res)


def test_corrupt_json_line():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        records.write_text("{not json\n", encoding="utf-8")
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] >= 1
        assert any("解析失败" in r.message for r in res if r.level == "ERROR")


def test_nul_bytes():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        records.write_bytes(b"\x00\x00\x00")
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] >= 1
        assert any("NUL" in r.message for r in res if r.level == "ERROR")


def test_duplicate_chunk_id():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        recs = []
        for line in records.read_text(encoding="utf-8").splitlines():
            recs.append(json.loads(line))
        recs.append(dict(recs[0], id=recs[0]["id"]))
        records.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] >= 1
        assert any("重复 chunk id" in r.message for r in res if r.level == "ERROR")


def test_orphan_document():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        store = VectorStore(str(root / "db"))
        store.add("孤儿 chunk", {"source": "20_Wiki/missing.md", "document_path": "20_Wiki/missing.md", "document_hash": "x"}, [1.0, 0.0, 0.0])
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] >= 1
        assert any("orphan" in r.message for r in res if r.level == "ERROR")


def test_manifest_records_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        root, records, manifest = _healthy_env(tmp)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["20_Wiki/ghost.md"] = {"hash": "g", "chunks": 1, "indexed_at": "2026-08-11T00:00:00+00:00"}
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        res = run_checks(records, manifest, root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] >= 1
        assert any("不一致" in r.message for r in res if r.level == "ERROR")


def test_empty_db_is_info_not_error():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        res = run_checks(root / "db" / "records.jsonl", root / "db" / "index_manifest.json", root, require_index_metadata=True, gaps_path=None)
        assert _counts(res)["ERROR"] == 0
        assert any(r.level == "INFO" for r in res)


if __name__ == "__main__":
    for t in (
        test_healthy_db_no_error,
        test_corrupt_json_line,
        test_nul_bytes,
        test_duplicate_chunk_id,
        test_orphan_document,
        test_manifest_records_mismatch,
        test_empty_db_is_info_not_error,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all RAG health tests passed")
