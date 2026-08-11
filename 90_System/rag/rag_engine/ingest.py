"""Ingest raw sources and wiki notes into vector stores."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[end + 4 :].lstrip("\n")
    return text


def _read_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_pdf(path: Path, source: str) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to ingest PDF files") from exc
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(
                {"text": text, "page": index, "document_type": "pdf", "source": source}
            )
    return pages


def _parse_html(path: Path, source: str) -> list[dict]:
    raw = _read_text(path)
    try:
        import trafilatura
    except ImportError:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise RuntimeError(
                "trafilatura or beautifulsoup4 is required to ingest HTML files"
            ) from exc
        text = BeautifulSoup(raw, "html.parser").get_text("\n", strip=True)
    else:
        text = trafilatura.extract(raw) or ""
    return [{"text": text, "page": None, "document_type": "html", "source": source}]


def parse_file(path: Path, relative_root: Path | None = None) -> list[dict]:
    ext = path.suffix.lower()
    if relative_root is not None:
        try:
            source = path.relative_to(relative_root).as_posix()
        except ValueError:
            source = path.name
    else:
        source = str(path)
    if ext in (".md", ".txt"):
        raw = _read_text(path)
        frontmatter = _read_frontmatter(raw)
        text = strip_frontmatter(raw)
        return [
            {
                "text": text,
                "page": None,
                "document_type": ext[1:],
                "source": source,
                "frontmatter": frontmatter,
            }
        ]
    if ext == ".pdf":
        return _parse_pdf(path, source)
    if ext in (".html", ".htm"):
        return _parse_html(path, source)
    raise ValueError(f"unsupported file type: {ext}")


def _metadata_value(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def ingest_file(
    path: Path,
    cfg: dict,
    store,
    embedder,
    relative_root: Path | None = None,
    extra_metadata: dict | None = None,
) -> int:
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0
    for page in parse_file(path, relative_root):
        for text in chunk_text(
            page["text"], cfg["chunking"]["size"], cfg["chunking"]["overlap"]
        ):
            metadata = {
                "source": page["source"],
                "page": page["page"],
                "created_time": created,
                "document_type": page["document_type"],
            }
            for key in ("type", "domain", "status", "project", "aliases"):
                value = page.get("frontmatter", {}).get(key)
                if value is not None:
                    metadata[key] = _metadata_value(value)
            fm_source = page.get("frontmatter", {}).get("source")
            if fm_source is not None:
                metadata["source_frontmatter"] = _metadata_value(fm_source)
            if extra_metadata:
                metadata.update(extra_metadata)
            vector = embedder.embed([text])[0]
            store.add(text, metadata, vector)
            added += 1
    return added