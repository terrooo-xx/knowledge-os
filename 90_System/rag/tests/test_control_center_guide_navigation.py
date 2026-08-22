"""Control Center 使用指南 Docs-style 导航测试（Phase 22-C, structural/static）。

验证：Guide Home / 章节路由 / 只渲染当前章节 / Sidebar active / 上一章下一章 /
浏览器后退前进（hash 驱动）/ 刷新深链 / 搜索进章节 / 页面跳转 / Workflow 独立章节 /
移动端目录抽屉。
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


def _script() -> str:
    m = re.search(r"<script>(.*?)</script>", _html(), re.S)
    assert m, "script block missing"
    return m.group(1)


def test_guide_home():
    js = _script()
    assert "renderGuideHome" in js
    assert "resolveGuideRoute" in js
    assert "route.isHome" in js
    assert "你现在想做什么？" in js          # 首页入口卡片
    assert "全部章节" in js                  # 首页章节列表


def test_section_route():
    js = _script()
    assert "location.hash = '#guide/' + slug" in js
    assert "h.startsWith('guide/')" in js
    assert "guideFind" in js
    for slug in ("getting-started", "workflow", "wiki-review", "source-verification",
                 "rag-evaluation", "governance", "baseline"):
        assert "'" + slug + "'" in js, f"missing section slug: {slug}"


def test_section_render_only_current():
    js = _script()
    assert "renderGuideSection" in js
    # 不再一次性渲染所有章节：没有 GUIDE_SECTIONS.map 全量插入
    assert "GUIDE_SECTIONS.map" not in js
    assert "GUIDE_FLAT.map(x => '<li>" in js or "GUIDE_FLAT.map" in js  # 首页列表可用
    assert "guideFlatten" in js


def test_sidebar_active_state():
    js = _script()
    assert "guideSidebarHtml" in js
    assert "data-guide-slug" in js
    assert "class=\"g-parent" in js
    assert "class=\"g-child" in js
    assert "currentSlug" in js and "active" in js


def test_prev_next():
    js = _script()
    assert "guidePrevNext" in js
    assert "← 上一章" in js
    assert "下一章：" in js
    assert "GUIDE_FLAT.findIndex" in js


def test_browser_back_forward_hash_driven():
    js = _script()
    # 章节切换通过 location.hash（push history）而不是 replaceState/滚动
    assert "location.hash = '#guide/' + slug" in js
    assert "window.addEventListener('hashchange', routeFromHash)" in js


def test_refresh_deep_link():
    js = _script()
    assert "routeFromHash" in js
    assert "h === 'guide' || h.startsWith('guide/')" in js
    assert "loadStatus();" in js and "routeFromHash();" in js


def test_search_result_to_section():
    js = _script()
    assert "guideSearchResults" in js
    assert "guideText(x.html)" in js            # 搜索标题 + 内容
    assert "gotoGuideSection(\\''+esc(x.slug)+'\\')" in js or "gotoGuideSection" in js


def test_guide_to_wiki_review():
    js = _script()
    assert "gotoView('wikis')" in js
    assert "'wiki-review'" in js


def test_guide_to_source_acquisition():
    js = _script()
    assert "gotoView('rag_evaluation')" in js   # Source 治理入口在 RAG Evaluation
    assert "'source-verification'" in js
    assert "Mark Verified" in js


def test_guide_to_rag_evaluation():
    js = _script()
    assert "gotoView('rag_evaluation')" in js
    assert "'rag-evaluation'" in js


def test_workflow_page_standalone():
    js = _script()
    # Workflow 是独立章节（slug workflow），包含双图
    assert "'workflow'" in js
    assert "Knowledge OS 整体流程" in js
    assert "RAG 查询路径" in js


def test_only_current_section_rendered():
    # renderGuide 分支：isHome -> home；否则 -> 单章节；无全量 sections 拼接
    js = _script()
    rg = js.split("async function renderGuide")[1].split("function renderGuideHome")[0]
    assert "renderGuideHome(st)" in rg
    assert "renderGuideSection(route.section, st)" in rg


def test_mobile_fallback():
    js = _script()
    assert "g-toc-toggle" in js
    assert "classList.toggle" in js
    html = _html()
    assert "@media (max-width: 900px)" in html
    assert ".g-toc.open { display: block; }" in html


def test_extracted_script_passes_node_syntax_check():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not available")
    p = subprocess.run([node, "--check", "-"], input=_script().encode("utf-8"),
                       capture_output=True, timeout=30)
    assert p.returncode == 0, (p.stdout + p.stderr).decode("utf-8", "replace")
