"""LLM-Wiki Compiler tests (mock LLM output)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rag_engine.wiki_compiler as wc
from rag_engine.wiki import read_frontmatter

BODY = "# DMA 数据搬运\n\n## 一、概念/定义\nDMA 用于数据搬运。\n\n## 九、来源\n个人笔记/a.pdf"


def _mock(body):
    original = wc._llm_text
    wc._llm_text = lambda *a, **k: body
    return original


def _cfg(tmp: str) -> dict:
    root = Path(tmp)
    return {
        "paths": {"wiki": str(root / "20_Wiki"), "projects": str(root / "30_Projects")},
        "wiki": {"status": "draft", "default_domain": "01_计算机基础"},
        "llm": {"provider": "mock", "model": "mock"},
    }


def test_create_draft_full_content():
    with tempfile.TemporaryDirectory() as tmp:
        original = _mock(BODY)
        try:
            cfg = _cfg(tmp)
            path = wc.create_draft("DMA 用于数据搬运", "个人笔记/a.pdf", cfg, domain="03_STM32")
        finally:
            wc._llm_text = original
        text = path.read_text(encoding="utf-8")
        frontmatter = read_frontmatter(path)
        assert frontmatter["status"] == "draft"
        assert "个人笔记/a.pdf" in text
        assert frontmatter.get("review_required") in ("True", True)
        assert "DMA 用于数据搬运" in text
        assert "待补充" not in text


def test_create_draft_no_overwrite_reviewed():
    with tempfile.TemporaryDirectory() as tmp:
        original = _mock("# 已审核\n内容")
        try:
            cfg = _cfg(tmp)
            path = wc.create_draft("内容", "来源", cfg, domain="03_STM32", title="已审核")
            path.write_text("---\nstatus: reviewed\n---\n人工内容", encoding="utf-8")
            try:
                wc.create_draft("新内容", "来源2", cfg, domain="03_STM32", title="已审核")
            except FileExistsError:
                pass
            else:
                raise AssertionError("reviewed wiki must not be overwritten")
        finally:
            wc._llm_text = original


def test_update_proposal():
    with tempfile.TemporaryDirectory() as tmp:
        original_llm = _mock("变更原因：新增调度细节")
        original_dir = wc.TASK_LOG_DIR
        wc.TASK_LOG_DIR = Path(tmp) / "任务记录"
        try:
            cfg = _cfg(tmp)
            target = Path(tmp) / "20_Wiki" / "04_FreeRTOS" / "FreeRTOS任务调度与状态.md"
            target.parent.mkdir(parents=True)
            target.write_text("---\nstatus: draft\n---\n已有内容", encoding="utf-8")
            proposal = wc.create_update_proposal(target, "新调度细节", "新来源.pdf", cfg)
        finally:
            wc._llm_text = original_llm
            wc.TASK_LOG_DIR = original_dir
        text = proposal.read_text(encoding="utf-8")
        assert "目标 Wiki" in text
        assert "新来源.pdf" in text
        assert "变更原因" in text


def test_project_draft():
    with tempfile.TemporaryDirectory() as tmp:
        original = _mock("# 硬件选型\n项目内容")
        try:
            cfg = _cfg(tmp)
            path = wc.create_project_draft("项目内容", "项目来源.pdf", "移动底盘控制器", cfg)
        finally:
            wc._llm_text = original
        assert path.exists()
        assert read_frontmatter(path)["type"] == "project"
        assert read_frontmatter(path)["status"] == "draft"


if __name__ == "__main__":
    for test in (
        test_create_draft_full_content,
        test_create_draft_no_overwrite_reviewed,
        test_update_proposal,
        test_project_draft,
    ):
        test()
        print(f"PASS {test.__name__}")
    print("all wiki compiler tests passed")