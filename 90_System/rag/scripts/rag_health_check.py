"""RAG Health Check: read-only integrity checks for the RAG vector index.

Checks records.jsonl, index_manifest.json, chunk metadata, duplicates,
orphan documents, NUL bytes, manifest/records consistency and the
knowledge_gaps.yaml registry.

READ_ONLY: this script never writes, deletes or rebuilds anything.
Exit code: 0 = no ERROR, 1 = at least one ERROR. WARNING/INFO do not fail.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.config import load_config, resolve_paths

LEVELS = ("PASS", "WARNING", "ERROR", "INFO")


class HealthResult:
    def __init__(self, level: str, message: str):
        assert level in LEVELS, level
        self.level = level
        self.message = message


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _load_jsonl(path: Path) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def check_records_jsonl(records_path: Path, results: list, require_index_metadata: bool):
    if not records_path.exists():
        results.append(HealthResult("INFO", "records.jsonl 不存在（库为空或未建立）"))
        return None
    data = _read_bytes(records_path)
    if b"\x00" in data:
        results.append(HealthResult("ERROR", "records.jsonl 包含 NUL 字节（0x00，疑似半写入损坏）"))
        return None
    try:
        records = _load_jsonl(records_path)
    except Exception as exc:
        results.append(HealthResult("ERROR", f"records.jsonl JSON 解析失败: {exc}"))
        return None
    results.append(HealthResult("PASS", "records.jsonl 存在且每行 JSON 合法"))
    ids = [str(r.get("id", "")) for r in records]
    dup_ids = {i for i in ids if i and ids.count(i) > 1}
    if dup_ids:
        results.append(HealthResult("ERROR", f"存在重复 chunk id: {sorted(dup_ids)[:5]}"))
    else:
        results.append(HealthResult("PASS", "chunk id 唯一"))
    if require_index_metadata:
        missing = []
        for idx, r in enumerate(records):
            md = r.get("metadata") or {}
            for key in ("source", "document_path", "document_hash"):
                if md.get(key) in (None, ""):
                    missing.append((idx, key))
        if missing:
            results.append(HealthResult(
                "ERROR", f"{len(missing)} 条记录缺少关键 metadata（source/document_path/document_hash）"
            ))
        else:
            results.append(HealthResult("PASS", "关键 metadata（source/document_path/document_hash）完整"))
    return records


def check_manifest(manifest_path: Path, results: list):
    if manifest_path is None or not manifest_path.exists():
        results.append(HealthResult("INFO", "index_manifest.json 不存在（未索引或已清理）"))
        return None
    data = _read_bytes(manifest_path)
    if b"\x00" in data:
        results.append(HealthResult("ERROR", "index_manifest.json 包含 NUL 字节（0x00，疑似损坏）"))
        return None
    try:
        manifest = json.loads(data.decode("utf-8"))
    except Exception as exc:
        results.append(HealthResult("ERROR", f"index_manifest.json JSON 解析失败: {exc}"))
        return None
    if not isinstance(manifest, dict):
        results.append(HealthResult("ERROR", "index_manifest.json 顶层不是对象"))
        return None
    bad = [
        doc for doc, entry in manifest.items()
        if not isinstance(entry, dict) or entry.get("hash") in (None, "") or entry.get("indexed_at") in (None, "")
    ]
    if bad:
        results.append(HealthResult("ERROR", f"{len(bad)} 个 manifest entry 缺少 hash/indexed_at"))
    else:
        results.append(HealthResult("PASS", "manifest JSON 合法且 entry 含 hash/indexed_at"))
    return manifest


def check_consistency(records, manifest, source_root: Path, results: list):
    if records is None or manifest is None:
        return
    rec_docs = {str(r.get("metadata", {}).get("document_path", "")) for r in records}
    rec_docs.discard("")
    man_docs = set(manifest.keys())
    missing_in_records = sorted(man_docs - rec_docs)
    extra_in_records = sorted(rec_docs - man_docs)
    if missing_in_records or extra_in_records:
        results.append(HealthResult(
            "ERROR",
            f"manifest/records 不一致：{len(missing_in_records)} 个 manifest 文档无记录，"
            f"{len(extra_in_records)} 个记录文档不在 manifest",
        ))
    else:
        results.append(HealthResult("PASS", "manifest/records 文档集合一致"))
    orphans = [doc for doc in rec_docs if not (source_root / doc).exists()]
    if orphans:
        results.append(HealthResult("ERROR", f"{len(orphans)} 个 chunk 的源文档不存在（orphan）：{orphans[:5]}"))
    else:
        results.append(HealthResult("PASS", "无 orphan chunk（源文档均存在）"))


def check_duplicate_chunks(records, results: list):
    if records is None:
        return
    keys = Counter(
        (str(r.get("metadata", {}).get("document_path", "")), r.get("text", ""))
        for r in records
    )
    dups = {k: n for k, n in keys.items() if n > 1}
    if dups:
        results.append(HealthResult("WARNING", f"存在 {len(dups)} 组重复 chunk（同文档同文本）"))
    else:
        results.append(HealthResult("PASS", "无重复 chunk"))


def check_knowledge_gaps(gaps_path: Path, results: list):
    if gaps_path is None or not gaps_path.exists():
        results.append(HealthResult("INFO", "knowledge_gaps.yaml 不存在"))
        return
    try:
        import yaml
        gaps = yaml.safe_load(gaps_path.read_text(encoding="utf-8")) or []
    except Exception as exc:
        results.append(HealthResult("ERROR", f"knowledge_gaps.yaml 解析失败: {exc}"))
        return
    if not isinstance(gaps, list):
        results.append(HealthResult("ERROR", "knowledge_gaps.yaml 顶层不是列表"))
        return
    valid = {"pending", "resolved"}
    bad = [
        i for i, g in enumerate(gaps)
        if not isinstance(g, dict) or not all(k in g for k in ("question", "type", "status"))
        or g.get("status") not in valid
    ]
    if bad:
        results.append(HealthResult("ERROR", f"{len(bad)} 个 gap entry 字段不完整或 status 非法"))
    else:
        results.append(HealthResult("PASS", "knowledge_gaps.yaml 可解析且字段完整"))
    pending = sum(1 for g in gaps if g.get("status") == "pending")
    if pending:
        results.append(HealthResult("INFO", f"knowledge_gaps pending = {pending}（仅报告，不自动 resolve）"))


def run_checks(
    records_path: Path,
    manifest_path: Path | None,
    source_root: Path,
    require_index_metadata: bool = True,
    gaps_path: Path | None = None,
) -> list:
    results = []
    records = check_records_jsonl(records_path, results, require_index_metadata)
    manifest = check_manifest(manifest_path, results)
    check_consistency(records, manifest, source_root, results)
    check_duplicate_chunks(records, results)
    check_knowledge_gaps(gaps_path, results)
    return results


def _print_report(results: list) -> int:
    counts = Counter(r.level for r in results)
    print("RAG HEALTH CHECK")
    for r in results:
        print(f"[{r.level}] {r.message}")
    print("SUMMARY")
    print(f"ERROR   = {counts.get('ERROR', 0)}")
    print(f"WARNING = {counts.get('WARNING', 0)}")
    print(f"PASS    = {counts.get('PASS', 0)}")
    print(f"INFO    = {counts.get('INFO', 0)}")
    print(
        f"RAG_HEALTH_SUMMARY ERROR={counts.get('ERROR', 0)} "
        f"WARNING={counts.get('WARNING', 0)} PASS={counts.get('PASS', 0)} "
        f"INFO={counts.get('INFO', 0)}"
    )
    return 1 if counts.get("ERROR", 0) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG Health Check (read-only)")
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument(
        "--store",
        choices=["main", "raw", "wiki"],
        default="main",
        help="default main checks the production index; raw/wiki are optional stores",
    )
    args = parser.parse_args()
    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    db_path = Path(cfg["paths"][f"{args.store}_vector_db"])
    records_path = db_path / "records.jsonl"
    manifest_path = None
    gaps_path = None
    if args.store == "main":
        manifest_path = Path(cfg["paths"]["main_vector_db"]).parent / "index_manifest.json"
        gaps_path = Path(cfg["paths"].get("knowledge_gaps", "")) if cfg["paths"].get("knowledge_gaps") else None
    results = run_checks(
        records_path,
        manifest_path,
        VAULT_ROOT,
        require_index_metadata=(args.store == "main"),
        gaps_path=gaps_path,
    )
    return _print_report(results)


if __name__ == "__main__":
    raise SystemExit(main())
