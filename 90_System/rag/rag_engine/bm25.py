"""BM25 keyword index in pure Python (no external dependency)."""
from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


class BM25Index:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [tokenize(doc) for doc in docs]
        self.doc_lens = [len(tokens) for tokens in self.docs]
        self.avgdl = sum(self.doc_lens) / len(self.docs) if self.docs else 0.0
        self.df: dict[str, int] = {}
        for tokens in self.docs:
            for token in set(tokens):
                self.df[token] = self.df.get(token, 0) + 1
        self.num_docs = len(self.docs)
        self.k1 = k1
        self.b = b

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.num_docs - n + 0.5) / (n + 0.5))

    def _score(self, query_tokens: list[str], doc_idx: int) -> float:
        if self.avgdl == 0:
            return 0.0
        doc_tokens = self.docs[doc_idx]
        doc_len = self.doc_lens[doc_idx]
        total = 0.0
        for term in set(query_tokens):
            tf = doc_tokens.count(term)
            if tf == 0:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            total += self._idf(term) * (tf * (self.k1 + 1)) / denom
        return total

    def search(self, query: str, top_k: int) -> list[dict]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.docs:
            return []
        scored = [
            {"score": self._score(query_tokens, idx), "index": idx}
            for idx in range(self.num_docs)
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return [item for item in scored if item["score"] > 0][:top_k]
