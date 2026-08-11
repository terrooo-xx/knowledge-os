"""Incremental RAG tests: add/modify/delete/unchanged via hash manifest."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.indexing import sync_index
from rag_engine.vector_store import VectorStore

CFG = {"chunking": {"size": 800, "overlap": 100}}


class FakeEmbedder:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return [[1.0, 0.0]] * len(texts)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntype: wiki\nstatus: draft\n---\n{text}", encoding="utf-8")


def test_incremental_add_modify_delete():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wiki = root / "20_Wiki" / "03_STM32"
        projects = root / "30_Projects"
        store = VectorStore(str(root / "db"))
        manifest = root / "db" / "index_manifest.json"
        embedder = FakeEmbedder()

        a = wiki / "DMA.md"
        _write(a, "DMA 数据搬运")

        result = sync_index(
            CFG, embedder, store, [wiki, projects], manifest, root, only_changed=True
        )
        assert result["rebuilt"] is True
        assert store.count() == 1

        calls_before = embedder.calls
        result = sync_index(
            CFG, embedder, store, [wiki, projects], manifest, root, only_changed=True
        )
        assert result["changed"] == []
        assert embedder.calls == calls_before
        assert store.count() == 1

        _write(a, "DMA 数据搬运 增加新内容")
        result = sync_index(
            CFG, embedder, store, [wiki, projects], manifest, root, only_changed=True
        )
        assert a.relative_to(root).as_posix() in result["changed"]
        assert store.count() == 1

        a.unlink()
        result = sync_index(
            CFG, embedder, store, [wiki, projects], manifest, root, only_changed=True
        )
        assert result["deleted"] and result["deleted"][0]["removed_chunks"] == 1
        assert store.count() == 0


if __name__ == "__main__":
    test_incremental_add_modify_delete()
    print("PASS test_incremental_add_modify_delete")