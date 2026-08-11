"""Inbox classifier tests: project/wiki/duplicate/update/keep_raw."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.inbox_classifier import classify_text

CFG = {
    "inbox": {"similarity_threshold": 0.82, "update_threshold": 0.65},
    "retrieval": {"confidence_threshold": 0.78},
}


class FakeStore:
    def __init__(self, hits, count=1):
        self._hits = hits
        self._count = count

    def search(self, vector, top_k):
        return self._hits[:top_k]

    def count(self):
        return self._count


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)


def test_create_wiki():
    result = classify_text(
        "DMA 直接存储器访问 用于数据搬运 不占用 CPU", CFG, source="in.md"
    )
    assert result["action"] == "create_wiki"
    assert result["domain"] == "03_STM32"


def test_project_update():
    result = classify_text(
        "移动底盘控制器 舵轮 AGV 使用工控机和伺服驱动器", CFG, source="in.md"
    )
    assert result["action"] == "project_update"
    assert result["project"] == "移动底盘控制器"


def test_no_new_wiki():
    store = FakeStore(
        [{"score": 0.95, "text": "相同内容", "metadata": {"source": "20_Wiki/a.md"}}]
    )
    result = classify_text(
        "相同内容", CFG, embedder=FakeEmbedder(), store=store, source="in.md"
    )
    assert result["action"] == "no_new_wiki"
    assert result["matched_wiki"] == "20_Wiki/a.md"


def test_update_wiki():
    store = FakeStore(
        [{"score": 0.7, "text": "相关但更短", "metadata": {"source": "20_Wiki/b.md"}}]
    )
    result = classify_text(
        "FreeRTOS 任务调度新增细节", CFG, embedder=FakeEmbedder(), store=store, source="in.md"
    )
    assert result["action"] == "update_wiki"
    assert result["matched_wiki"] == "20_Wiki/b.md"


def test_keep_raw_image_pdf():
    result = classify_text("", CFG, source="in.pdf", document_type="pdf")
    assert result["action"] == "keep_raw"


if __name__ == "__main__":
    for test in (
        test_create_wiki,
        test_project_update,
        test_no_new_wiki,
        test_update_wiki,
        test_keep_raw_image_pdf,
    ):
        test()
        print(f"PASS {test.__name__}")
    print("all inbox tests passed")