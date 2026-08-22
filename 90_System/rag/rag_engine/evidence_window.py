"""Evidence Context Expansion (minimal): turn isolated hit chunks into complete
semantic Evidence Windows.

Reranker stays the ranking source; this module only EXPANDS around hits using
neighbor chunks of the same document (resolved by store insertion order).
It never re-embeds / re-reranks / re-searches, and never mutates the ranked
chunk list (reranker order is preserved).

Handles: neighbor expansion, overlap dedup, whole-chunk length capping,
multiple disjoint windows, and evidence metadata.
"""
from __future__ import annotations

DEFAULT_CFG = {
    "enabled": True,
    "prev_chunks": 1,
    "next_chunks": 1,
    "max_evidence_chars": 3000,
    "use_for_answer": False,
}


def evidence_cfg(cfg: dict) -> dict:
    e = cfg.get("evidence_window") or {}
    out = dict(DEFAULT_CFG)
    out.update(e)
    return out


def build_document_index(store) -> dict[str, list[dict]]:
    """Index all chunks by document in store insertion order (stable order)."""
    docs: dict[str, list[dict]] = {}
    for rec in store.all():
        md = rec.get("metadata") or {}
        key = md.get("document_path") or md.get("source") or ""
        docs.setdefault(key, []).append({
            "index": len(docs.get(key, [])),
            "text": rec["text"],
            "metadata": md,
        })
    return docs


def _find_chunk_index(doc: list[dict], chunk: dict) -> int | None:
    text = chunk.get("text") or ""
    for i, entry in enumerate(doc):
        if entry["text"] == text:
            return i
    return None


def merge_chunk_sequence(texts: list[str], overlap: int) -> str:
    return _merge_sequence(texts, overlap)


def _merge_sequence(texts: list[str], overlap: int) -> str:
    """Concatenate chunks, removing the actual shared overlap between neighbors."""
    if not texts:
        return ""
    out = texts[0]
    for t in texts[1:]:
        n = min(overlap, len(out), len(t))
        m = 0
        for k in range(n, 0, -1):
            if out[-k:] == t[:k]:
                m = k
                break
        out += t[m:]
    return out


def _cluster_hits(hits: list[int], prev: int, next_chunks: int) -> list[list[int]]:
    """Group hit indices into windows whose expansion spans overlap/are contiguous."""
    hits = sorted(set(hits))
    clusters: list[list[int]] = []
    for h in hits:
        lo, hi = h - prev, h + next_chunks
        if clusters and lo <= clusters[-1][1] + 1:
            clusters[-1][1] = max(clusters[-1][1], hi)
        else:
            clusters.append([lo, hi])
    return clusters


def _assemble_window(doc, start, end, hits, overlap, max_chars) -> tuple[list[int], str]:
    """Pick whole chunks (hit chunks first, then neighbors) within the budget."""
    idxs = list(range(start, end + 1))
    hit_set = set(hits)
    # Drop non-hit edge chunks until merged text fits; never drop a hit chunk.
    while len(idxs) > len(hit_set):
        text = _merge_sequence([doc[i]["text"] for i in idxs], overlap)
        if len(text) <= max_chars:
            break
        if idxs[0] in hit_set:
            drop_right = True
        elif idxs[-1] in hit_set:
            drop_right = False
        else:
            left_dist = min(abs(idxs[0] - h) for h in hits)
            right_dist = min(abs(idxs[-1] - h) for h in hits)
            drop_right = right_dist >= left_dist
        idxs.pop(-1 if drop_right else 0)
    text = _merge_sequence([doc[i]["text"] for i in idxs], overlap)
    return idxs, text


def build_evidence_windows(ranked_chunks: list[dict], doc_index: dict, cfg: dict) -> list[dict]:
    """Build complete Evidence Windows around the ranked hits.

    `ranked_chunks` is NOT mutated (reranker order preserved).
    """
    c = evidence_cfg(cfg)
    if not c["enabled"] or not ranked_chunks:
        return []
    prev = max(0, int(c["prev_chunks"]))
    next_chunks = max(0, int(c["next_chunks"]))
    max_chars = int(c["max_evidence_chars"])
    overlap = int((cfg.get("chunking") or {}).get("overlap", 100))

    hits_by_doc: dict[str, set[int]] = {}
    for chunk in ranked_chunks:
        md = chunk.get("metadata") or {}
        key = md.get("document_path") or md.get("source") or ""
        doc = doc_index.get(key, [])
        idx = _find_chunk_index(doc, chunk)
        if idx is not None:
            hits_by_doc.setdefault(key, set()).add(idx)

    windows = []
    for key, hits in hits_by_doc.items():
        doc = doc_index.get(key, [])
        for lo, hi in _cluster_hits(sorted(hits), prev, next_chunks):
            start = max(0, lo)
            end = min(len(doc) - 1, hi)
            idxs, text = _assemble_window(doc, start, end, hits, overlap, max_chars)
            hit_in = sorted(set(hits) & set(idxs))
            scores = []
            for chunk in ranked_chunks:
                if _find_chunk_index(doc, chunk) in hit_in:
                    scores.append(chunk)
            windows.append({
                "source": key,
                "document": key,
                "section": None,  # 当前 chunk 无 section metadata
                "hit_chunk_ids": hit_in,
                "context_start_chunk": min(idxs) if idxs else None,
                "context_end_chunk": max(idxs) if idxs else None,
                "text": text,
                "retrieval_score": round(max(float(ch.get("score") or 0.0) for ch in scores), 4) if scores else None,
                "rerank_score": round(max(float(ch.get("rerank_score") or 0.0) for ch in scores), 4) if scores else None,
            })
    windows.sort(key=lambda w: w["rerank_score"] if w["rerank_score"] is not None else -1.0, reverse=True)
    return windows
