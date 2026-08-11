"""Build the context block from reranked chunks."""


def build_context(chunks: list[dict]) -> str:
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        source = (chunk.get("metadata") or {}).get("source", "未知来源")
        parts.append(f"[{index}] 来源：{source}\n{chunk['text']}")
    return "\n\n".join(parts)