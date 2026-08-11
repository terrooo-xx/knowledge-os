"""Wiki Health Check tests: frontmatter/status/source (read-only)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.wiki_health_check import run_checks


def _env(tmp: str):
    root = Path(tmp)
    src = root / "00_Inbox" / "a.pdf"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x", encoding="utf-8")
    wiki = root / "20_Wiki" / "03_STM32"
    wiki.mkdir(parents=True, exist_ok=True)
    return root, wiki, src


def test_valid_wiki_passes():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, src = _env(tmp)
        (wiki / "good.md").write_text(
            "---\nstatus: draft\nsource:\n  - 00_Inbox/a.pdf\n---\n内容", encoding="utf-8"
        )
        res = run_checks(wiki, root)
        assert not any(r.level == "ERROR" for r in res)
        assert any(r.level == "PASS" for r in res)


def test_invalid_status_error():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, src = _env(tmp)
        (wiki / "bad.md").write_text("---\nstatus: nope\nsource:\n  - 00_Inbox/a.pdf\n---\n内容", encoding="utf-8")
        res = run_checks(wiki, root)
        assert any(r.level == "ERROR" and "status 非法" in r.message for r in res)


def test_missing_source_warning():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, src = _env(tmp)
        (wiki / "nosrc.md").write_text("---\nstatus: draft\n---\n内容", encoding="utf-8")
        res = run_checks(wiki, root)
        assert any(r.level == "WARNING" and "source 字段缺失" in r.message for r in res)


def test_stale_source_warning():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, src = _env(tmp)
        (wiki / "stale.md").write_text(
            "---\nstatus: draft\nsource:\n  - 个人笔记/moved.pdf\n---\n内容", encoding="utf-8"
        )
        res = run_checks(wiki, root)
        assert any(r.level == "WARNING" and "不存在" in r.message for r in res)


def test_external_url_source_info():
    with tempfile.TemporaryDirectory() as tmp:
        root, wiki, src = _env(tmp)
        (wiki / "url.md").write_text(
            "---\nstatus: draft\nsource:\n  - https://example.com/doc\n---\n内容", encoding="utf-8"
        )
        res = run_checks(wiki, root)
        assert any(r.level == "INFO" and "外部 URL" in r.message for r in res)


if __name__ == "__main__":
    for t in (
        test_valid_wiki_passes,
        test_invalid_status_error,
        test_missing_source_warning,
        test_stale_source_warning,
        test_external_url_source_info,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all wiki health tests passed")
