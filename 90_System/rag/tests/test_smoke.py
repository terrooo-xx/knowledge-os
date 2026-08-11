"""Offline smoke tests for pure RAG engine logic (no external deps)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.bm25 import BM25Index
from rag_engine.ingest import chunk_text, strip_frontmatter
from rag_engine.retrieval import fuse_results
from rag_engine.vector_store import VectorStore, cosine_similarity


def test_chunk_text():
    text = "甲" * 100 + "乙" * 100
    chunks = chunk_text(text, size=80, overlap=20)
    assert len(chunks) >= 2
    assert all(chunks)
    assert chunks[0][-20:] == chunks[1][:20]


def test_cosine_similarity():
    assert cosine_similarity([1, 0], [1, 0]) > 0.999
    assert abs(cosine_similarity([1, 0], [0, 1])) < 1e-9


def test_bm25_keyword_ranking():
    docs = [
        "STM32F405 使用 DMA 搬运 ADC 数据",
        "FreeRTOS 任务调度使用 PendSV 切换上下文",
    ]
    index = BM25Index(docs)
    hits = index.search("STM32F405 DMA", 1)
    assert hits and hits[0]["index"] == 0


def test_vector_store():
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(tmp)
        store.add("DMA 负责数据搬运", {"source": "00_Inbox/a.md"}, [1.0, 0.0])
        store.add("FreeRTOS 调度", {"source": "00_Inbox/b.md"}, [0.0, 1.0])
        assert store.count() == 2
        top = store.search([0.9, 0.1], 1)
        assert top[0]["text"] == "DMA 负责数据搬运"
        assert top[0]["metadata"]["source"] == "00_Inbox/a.md"


def test_hybrid_fusion():
    dense = [
        {"text": "A", "metadata": {}, "score": 1.0},
        {"text": "B", "metadata": {}, "score": 0.5},
    ]
    keyword = [{"text": "B", "metadata": {}, "score": 1.0}]
    cfg = {"retrieval": {"dense_weight": 0.5, "bm25_weight": 0.5}}
    merged = fuse_results(dense, keyword, cfg)
    assert merged[0]["text"] == "B"


def test_vector_store_add_long_line_no_false_positive():
    # A chunk line longer than 8KB must not trip the trailing-line guard.
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(tmp)
        long_text = "甲" * 20000
        store.add(long_text, {"source": "a.md"}, [1.0, 0.0])
        store.add("第二条", {"source": "b.md"}, [1.0, 0.0])
        assert store.count() == 2


def test_strip_frontmatter():
    md = "---\nstatus: draft\n---\n正文内容"
    assert strip_frontmatter(md) == "正文内容"



def test_ingest_frontmatter_metadata():
    from rag_engine.ingest import ingest_file

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "note.md"
        src.write_text(
            "---\ntype: wiki\nstatus: draft\nsource:\n  - 原始.pdf\n---\n正文内容",
            encoding="utf-8",
        )
        cfg = {"chunking": {"size": 800, "overlap": 100}}
        store = VectorStore(str(root / "db"))

        class FakeEmbedder:
            def embed(self, texts):
                return [[1.0, 0.0]] * len(texts)

        ingest_file(src, cfg, store, FakeEmbedder(), relative_root=root)
        metadata = store.all()[0]["metadata"]
        assert metadata["source"] == "note.md"
        assert metadata["status"] == "draft"
        assert metadata["source_frontmatter"] == "原始.pdf"

if __name__ == "__main__":
    tests = [
        test_chunk_text,
        test_cosine_similarity,
        test_bm25_keyword_ranking,
        test_vector_store,
        test_hybrid_fusion,
        test_vector_store_add_long_line_no_false_positive,
        test_strip_frontmatter,
        test_ingest_frontmatter_metadata,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("all smoke tests passed")
