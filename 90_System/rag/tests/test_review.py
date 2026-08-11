"""Wiki review status transition tests."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.wiki import read_frontmatter
from rag_engine.wiki_review import set_status


def _wiki(tmp: str, status: str) -> Path:
    path = Path(tmp) / "test.md"
    path.write_text(f"---\ntype: wiki\nstatus: {status}\nupdated: 2026-08-10\n---\n内容", encoding="utf-8")
    return path


def test_draft_to_reviewed():
    with tempfile.TemporaryDirectory() as tmp:
        path = _wiki(tmp, "draft")
        set_status(path, "reviewed")
        assert read_frontmatter(path)["status"] == "reviewed"


def test_reviewed_to_stable():
    with tempfile.TemporaryDirectory() as tmp:
        path = _wiki(tmp, "reviewed")
        set_status(path, "stable")
        assert read_frontmatter(path)["status"] == "stable"


def test_draft_to_stable_forbidden():
    with tempfile.TemporaryDirectory() as tmp:
        path = _wiki(tmp, "draft")
        try:
            set_status(path, "stable")
        except ValueError:
            pass
        else:
            raise AssertionError("draft -> stable must be forbidden")
        assert read_frontmatter(path)["status"] == "draft"


def test_draft_to_stable_force_allowed():
    with tempfile.TemporaryDirectory() as tmp:
        path = _wiki(tmp, "draft")
        set_status(path, "stable", force=True)
        assert read_frontmatter(path)["status"] == "stable"


if __name__ == "__main__":
    for test in (
        test_draft_to_reviewed,
        test_reviewed_to_stable,
        test_draft_to_stable_forbidden,
        test_draft_to_stable_force_allowed,
    ):
        test()
        print(f"PASS {test.__name__}")
    print("all review tests passed")