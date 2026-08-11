"""Wiki Health Check: read-only frontmatter/status/source checks for 20_Wiki.

Checks frontmatter parseability, status legality (draft/reviewed/stable) and
source field existence + file existence. Does NOT change any Wiki status.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

VALID_STATUSES = {"draft", "reviewed", "stable"}
LEVELS = ("PASS", "WARNING", "ERROR", "INFO")


class HealthResult:
    def __init__(self, level: str, message: str):
        assert level in LEVELS, level
        self.level = level
        self.message = message


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        import yaml
        data = yaml.safe_load(text[3:end])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def run_checks(wiki_root: Path, source_root: Path) -> list:
    results = []
    files = sorted(wiki_root.rglob("*.md"))
    if not files:
        results.append(HealthResult("INFO", f"{wiki_root} 下无 md 文件"))
        return results
    for path in files:
        rel = path.relative_to(source_root).as_posix()
        fm = parse_frontmatter(path)
        if not fm:
            results.append(HealthResult("ERROR", f"{rel}: frontmatter 不可解析或为空"))
            continue
        status = fm.get("status")
        if status not in VALID_STATUSES:
            results.append(HealthResult("ERROR", f"{rel}: status 非法（{status!r}，允许 draft/reviewed/stable）"))
        src = fm.get("source")
        if not src:
            results.append(HealthResult("WARNING", f"{rel}: source 字段缺失"))
            continue
        sources = src if isinstance(src, list) else [src]
        missing = []
        for s in sources:
            s = str(s).strip()
            if not s or s == "待补充":
                missing.append("<空/待补充>")
                continue
            if s.startswith(("http://", "https://")):
                results.append(HealthResult("INFO", f"{rel}: source 为外部 URL（跳过存在性检查）：{s[:60]}"))
                continue
            if not (source_root / s).exists():
                missing.append(s)
        if missing:
            results.append(HealthResult(
                "WARNING", f"{rel}: {len(missing)} 个 source 文件不存在（可能已移动）：{missing[:3]}"
            ))
        else:
            results.append(HealthResult("PASS", f"{rel}: frontmatter/status/source 正常"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki Health Check (read-only)")
    parser.add_argument("--wiki", default=str(VAULT_ROOT / "20_Wiki"))
    parser.add_argument("--source-root", default=str(VAULT_ROOT))
    args = parser.parse_args()
    results = run_checks(Path(args.wiki), Path(args.source_root))
    from collections import Counter
    counts = Counter(r.level for r in results)
    print("WIKI HEALTH CHECK")
    for r in results:
        print(f"[{r.level}] {r.message}")
    print("SUMMARY")
    print(f"ERROR   = {counts.get('ERROR', 0)}")
    print(f"WARNING = {counts.get('WARNING', 0)}")
    print(f"PASS    = {counts.get('PASS', 0)}")
    print(f"INFO    = {counts.get('INFO', 0)}")
    return 1 if counts.get("ERROR", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
