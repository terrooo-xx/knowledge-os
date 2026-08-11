"""Vector stores: local JSONL (default) and optional Chroma."""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

from .atomic_io import atomic_write_jsonl


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector dimension mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    """Local JSONL store; each line holds text, metadata and vector."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._records_path = self.path / "records.jsonl"

    def _records(self):
        if not self._records_path.exists():
            return
        with open(self._records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def _last_line(self) -> str | None:
        """Return the last non-empty line, or None for empty/missing files.

        Reads the whole file: chunk lines can exceed 8KB, so a tail-only read
        could cut a line in half and produce a false corruption report.
        """
        if not self._records_path.exists() or self._records_path.stat().st_size == 0:
            return None
        with open(self._records_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        return lines[-1] if lines else None

    def add(self, text: str, metadata: dict, vector: list[float]) -> None:
        record = {
            "id": str(uuid.uuid4()),
            "text": text,
            "metadata": metadata,
            "vector": vector,
        }
        last = self._last_line()
        if last is not None:
            try:
                json.loads(last)
            except Exception as exc:
                raise RuntimeError(
                    "records.jsonl 尾部存在损坏记录（上次写入可能被中断）。"
                    "禁止继续追加；请先按 RAG 数据恢复流程 rebuild 或恢复备份。"
                ) from exc
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        scored = []
        for record in self._records():
            score = cosine_similarity(vector, record["vector"])
            scored.append((score, record["text"], record["metadata"]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"score": score, "text": text, "metadata": metadata}
            for score, text, metadata in scored[:top_k]
        ]

    def all(self) -> list[dict]:
        return [
            {"text": record["text"], "metadata": record["metadata"]}
            for record in self._records()
        ]

    def delete_by_metadata(self, key: str, value) -> int:
        if not self._records_path.exists():
            return 0
        kept = []
        removed = 0
        with open(self._records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["metadata"].get(key) == value:
                    removed += 1
                else:
                    kept.append(record)
        atomic_write_jsonl(self._records_path, kept)
        return removed

    def count(self) -> int:
        return sum(1 for _ in self._records())

    def clear(self) -> None:
        atomic_write_jsonl(self._records_path, [])


class ChromaStore:
    """Optional Chroma adapter with the same interface as VectorStore."""

    def __init__(self, path: str):
        import chromadb

        self._client = chromadb.PersistentClient(path=str(Path(path)))
        self._collection = self._client.get_or_create_collection("documents")

    def add(self, text: str, metadata: dict, vector: list[float]) -> None:
        self._collection.add(
            ids=[str(uuid.uuid4())],
            documents=[text],
            metadatas=[metadata],
            embeddings=[vector],
        )

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        result = self._collection.query(query_embeddings=[vector], n_results=top_k)
        chunks = []
        for distance, text, metadata in zip(
            result["distances"][0], result["documents"][0], result["metadatas"][0]
        ):
            chunks.append(
                {"score": -float(distance), "text": text, "metadata": metadata or {}}
            )
        return chunks

    def all(self) -> list[dict]:
        result = self._collection.get(include=["documents", "metadatas"])
        return [
            {"text": text, "metadata": metadata or {}}
            for text, metadata in zip(result["documents"], result["metadatas"])
        ]

    def delete_by_metadata(self, key: str, value) -> int:
        result = self._collection.get(where={key: value})
        ids = result.get("ids") or []
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        try:
            self._client.delete_collection("documents")
        except Exception:
            pass
        self._collection = self._client.create_collection("documents")


def create_store(cfg: dict, path: str):
    if cfg.get("store", {}).get("provider") == "chroma":
        return ChromaStore(path)
    return VectorStore(path)
