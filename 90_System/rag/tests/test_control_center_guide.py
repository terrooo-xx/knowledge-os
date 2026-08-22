"""Control Center 使用指南（Guide）tests (structural/static).

Verifies: guide nav/view exists, content renders, Docs-style section routing,
sidebar/search, workflow diagrams, dynamic status + recommendation, graceful
API fallback, refresh persistence, and that existing pages are untouched.
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


def test_guide_page_exists():
    html = _html()
    assert '<button data-view="guide">📖 使用指南</button>' in html
    assert "guide" in re.search(r"const views = \[(.*?)\]", html).group(1)


def test_navigation_exists():
    js = _script()
    assert "renderGuide" in js
    assert "view === 'guide'" in js


def test_guide_content_renders():
    js = _script()
    for token in ("开始使用", "整体流程", "页面说明", "常用操作",
                  "Governance", "Baseline", "常见问题", "故障排查",
                  "你现在想做什么？"):
        assert token in js, f"missing guide content: {token}"
    # 指南必须有版本与更新日期（不写死系统数值）
    assert "GUIDE_META" in js
    assert "version: '1.1'" in js and "updated: '2026-08-18'" in js


def test_toc_jump():
    js = _script()
    # Docs-style：目录点击 -> 路由（#guide/<slug>），不是 scrollIntoView
    assert "gotoGuideSection" in js
    assert "guideSidebarHtml" in js
    assert "data-guide-slug" in js
    assert "resolveGuideRoute" in js
    assert "location.hash = '#guide/' + slug" in js
    assert "scrollIntoView" not in js.split("const GUIDE_SECTIONS")[0]  # 不再用长页滚动


def test_page_jump_to_real_views():
    js = _script()
    # 指南内按钮跳转到真实页面（gotoView，不刷新页面）
    for v in ("todo", "wikis", "gaps", "rag_evaluation", "query_trace"):
        assert f"gotoView('{v}')" in js, f"missing jump to {v}"


def test_workflow_diagram_renders():
    js = _script()
    assert "g-flow" in js and "g-box" in js and "g-arrow" in js
    # 两张图：Knowledge OS 整体流程 + RAG 查询路径
    assert "Knowledge OS 整体流程" in js
    assert "RAG 查询路径" in js
    assert "Wiki First" in js and "RAW Fallback" in js and "Fail-Closed" in js


def test_dynamic_status_recommendation():
    js = _script()
    assert "当前建议" in js
    assert "当前系统状态" in js
    assert "safeApi('/api/rag/evaluation/baseline')" in js
    assert "safeApi('/api/rag/evaluation/governance')" in js
    assert "safeApi('/api/wikis')" in js
    assert "safeApi('/api/source_acquisition')" in js
    assert "safeApi('/api/gaps/evaluation')" in js
    assert "无需人工处理" in js
    assert "Mark Verified" in js  # Git Source 指引


def test_graceful_fallback_on_api_failure():
    js = _script()
    assert "async function safeApi" in js
    assert "try { return await api(path, opts); } catch (e) { return null; }" in js
    assert "API 不可用" in js


def test_refresh_persistence_guide():
    js = _script()
    # hash 路由：guide 在 views + VIEW_LABELS + routeFromHash（guide/ 前缀深链）
    assert "guide:'使用指南'" in js
    assert "hashchange" in js
    assert "routeFromHash" in js
    assert "h.startsWith('guide/')" in js


def test_existing_pages_untouched():
    js = _script()
    html = _html()
    # 原有 11 个页面仍存在且都有渲染分支
    for v in ('dashboard', 'todo', 'wikis', 'gaps', 'sources', 'activity',
              'weekly_review', 'projects', 'health', 'query_trace', 'rag_evaluation'):
        assert f'data-view="{v}"' in html, f"nav lost: {v}"
        assert f"view === '{v}'" in js, f"render branch lost: {v}"
    # guide 不改变任何状态：renderGuide 只读 API（GET），无 POST 写操作
    rg = js.split("async function renderGuide")[1].split("async function runEvaluation")[0]
    assert "method:'POST'" not in rg and "method: 'POST'" not in rg
    assert "guideLoadStatus(" in rg


def test_extracted_script_passes_node_syntax_check():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not available")
    p = subprocess.run([node, "--check", "-"], input=_script().encode("utf-8"),
                       capture_output=True, timeout=30)
    assert p.returncode == 0, (p.stdout + p.stderr).decode("utf-8", "replace")
