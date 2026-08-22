"""Control Center RAG Evaluation view tests (structural).

Covers the Phase 22-A fixes: TDZ bug (diff used before declaration), render
error resilience (blank-page guard), hash routing (refresh persistence), and
the nav -> view chain integrity for the RAG Evaluation page.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parents[1].parent / "control_center"
HTML = CTRL_DIR / "static" / "index.html"
SCRIPT = CTRL_DIR / "static" / "index.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _script() -> str:
    m = re.search(r"<script>(.*?)</script>", _html(), re.S)
    assert m, "script block missing"
    return m.group(1)


def test_route_exists():
    html = _html()
    assert 'data-view="rag_evaluation"' in html
    assert ">RAG Evaluation</button>" in html
    assert "rag_evaluation" in re.search(r"const views = \[(.*?)\]", html).group(1)


def test_navigation_switches_and_persists_hash():
    js = _script()
    # click handler: remove active -> add active -> render(view) + hash 持久化
    assert "classList.remove('active')" in js
    assert "b.classList.add('active')" in js
    assert "history.replaceState(null, '', '#'+b.dataset.view)" in js
    # 刷新恢复：hashchange -> routeFromHash；初始加载读 hash（guide 深链走 guide/）
    assert "hashchange" in js
    assert "routeFromHash" in js
    assert "gotoView(h)" in js


def test_view_render_branch_exists():
    js = _script()
    assert "view === 'rag_evaluation'" in js
    assert "'/api/rag/evaluation'" in js


def test_baseline_and_governance_render():
    js = _script()
    assert "'/api/rag/evaluation/baseline'" in js
    assert "Evaluation Baseline" in js
    assert "'/api/rag/evaluation/governance'" in js
    assert "Evaluation Governance" in js


def test_api_failure_handled_gracefully():
    js = _script()
    # render 顶层 try/catch -> 错误卡 + 重试，不允许空白页
    assert "try {" in js and "_renderBody(view)" in js
    assert "数据加载失败" in js
    assert "重试" in js
    assert "onclick=\"render(" in js


def test_no_broken_navigation():
    js = _script()
    html = _html()
    nav_views = re.findall(r'<button data-view="([^"]+)"', html)
    for v in nav_views:
        assert f"view === '{v}'" in js or f"view === '{v}'" in js.replace("\n", " "), f"missing render branch for {v}"


def test_tdz_regression_diff_declared_before_use():
    # 修复：diff 必须在 df2 = diff && diff.diff 之前 fetch（TDZ ReferenceError 回归保护）
    js = _script()
    decl = js.index("const diff = await api('/api/rag/evaluation/diff');")
    use = js.index("const df2 = diff && diff.diff;")
    assert decl < use, "diff 仍在声明前被使用（TDZ 回归）"


def test_source_verified_ui_present():
    js = _script()
    assert "markSourceVerified" in js
    assert "Mark Verified" in js
    assert "已核验" in js and "待人工核验" in js
    assert "'/api/source_acquisition/'" in js and "/verify" in js


def test_extracted_script_passes_node_syntax_check():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not available")
    p = subprocess.run([node, "--check", "-"], input=_script().encode("utf-8"),
                       capture_output=True, timeout=30)
    assert p.returncode == 0, (p.stdout + p.stderr).decode("utf-8", "replace")
