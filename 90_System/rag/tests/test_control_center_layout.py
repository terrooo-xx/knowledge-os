"""Control Center 固定布局（App Shell）tests (structural/static).

Verifies: body/app-shell heights, header/sidebar fixed (flex shell), main
independent scroll, body overflow hidden (no double scroll), and that Guide /
RAG Evaluation / Sidebar navigation / responsive behavior remain intact.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parents[1].parent / "control_center"
HTML = CTRL_DIR / "static" / "index.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _css() -> str:
    m = re.search(r"<style>(.*?)</style>", _html(), re.S)
    assert m, "style block missing"
    return m.group(1)


def _script() -> str:
    m = re.search(r"<script>(.*?)</script>", _html(), re.S)
    assert m, "script block missing"
    return m.group(1)


def _rule(css: str, selector: str) -> str:
    # 独立规则：selector 必须位于规则开头（行首），避免匹配 html, body / header .row 等组合选择器
    m = re.search(r"(?<=\n)\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"css rule not found: {selector}"
    return m.group(1)


def test_body_app_shell_height():
    css = _css()
    root = _rule(css, "html, body")
    assert "height: 100%" in root           # html/body 占满 viewport
    body = _rule(css, "body")
    assert "flex-direction: column" in body  # body = App Shell 列布局
    assert "overflow: hidden" in body


def test_header_fixed_via_flex_shell():
    css = _css()
    header = _rule(css, "header")
    assert "flex: 0 0 auto" in header     # App Shell 首行，不随内容滚动
    body = _rule(css, "body")
    assert "flex-direction: column" in body


def test_sidebar_fixed_with_own_scroll():
    css = _css()
    nav = _rule(css, "nav")
    assert "flex: 0 0 170px" in nav       # 固定宽度，不随主内容移动
    assert "overflow-y: auto" in nav      # 导航过长时可独立滚动


def test_main_independent_scroll():
    css = _css()
    main = _rule(css, "main")
    assert "overflow-y: auto" in main
    assert "min-height: 0" in main
    assert "min-width: 0" in main
    layout = _rule(css, ".layout")
    assert "flex: 1 1 auto" in layout and "min-height: 0" in layout


def test_body_overflow_hidden_no_double_scroll():
    css = _css()
    body = _rule(css, "body")
    assert "overflow: hidden" in body      # body 不滚动 -> 无浏览器级滚动条
    main = _rule(css, "main")
    assert "overflow-y: auto" in main      # 只有 main 滚动


def test_no_fixed_main_height_no_margin_hack():
    css = _css()
    main = _rule(css, "main")
    assert re.search(r"(?<!min-)(?<!max-)height:", main) is None  # 不硬编码 height（flex 撑满）
    assert "margin-top: 80px" not in main  # 不依赖 margin hack
    assert "position: fixed" not in main


def test_guide_routing_still_works():
    js = _script()
    for token in ("gotoGuideSection", "resolveGuideRoute", "routeFromHash",
                  "#guide/' + slug", "renderGuideSection"):
        assert token in js, f"guide routing lost: {token}"


def test_rag_evaluation_still_works():
    js = _script()
    html = _html()
    assert "view === 'rag_evaluation'" in js
    assert "/api/rag/evaluation" in js
    assert 'data-view="rag_evaluation"' in html


def test_sidebar_nav_still_works():
    js = _script()
    html = _html()
    assert "gotoView" in js
    for v in ("dashboard", "guide", "wikis", "gaps", "rag_evaluation"):
        assert f'data-view="{v}"' in html, f"nav lost: {v}"
        assert f"view === '{v}'" in js


def test_resize_behavior_flex_based():
    css = _css()
    # flex 撑满高度 -> 任意窗口高度下 header/sidebar/main 自适应，无双滚动
    assert "flex: 1 1 auto" in css
    assert "min-height: 0" in css
    # 已有响应式（窄屏目录抽屉）
    assert "@media (max-width: 900px)" in css


def test_extracted_script_passes_node_syntax_check():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not available")
    p = subprocess.run([node, "--check", "-"], input=_script().encode("utf-8"),
                       capture_output=True, timeout=30)
    assert p.returncode == 0, (p.stdout + p.stderr).decode("utf-8", "replace")
