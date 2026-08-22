"""Control Center UI language & terminology tests (Phase 治理).

Read-only: checks the static index.html for Chinese-primary labels, no leftover
Phase-development copy, and that internal field names / API paths are untouched.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CTRL_DIR = Path(__file__).resolve().parents[1].parent / "control_center"
HTML = CTRL_DIR / "static" / "index.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def test_no_phase_leftover_copy():
    text = _html()
    assert "未计算（Phase D）" not in text
    for token in ("Phase A", "Phase B", "Phase C", "Phase D", "Phase E"):
        assert token not in text


def test_no_unimplemented_copy():
    text = _html()
    assert "未实现" not in text


def test_core_chinese_titles_exist():
    text = _html()
    for token in ("每周复盘", "知识健康度", "知识质量", "审核健康度", "知识缺口",
                  "项目活跃度", "系统可靠性", "需要关注"):
        assert token in text, f"missing: {token}"


def test_review_status_chinese():
    text = _html()
    for token in ("AI 已验证", "待人工审核", "Judge 失败", "审核中"):
        assert token in text, f"missing: {token}"


def test_automation_chinese():
    text = _html()
    for token in ("复盘自动化", "最近运行", "最近成功", "下次运行"):
        assert token in text, f"missing: {token}"


def test_ai_insight_chinese():
    text = _html()
    for token in ("AI 周度洞察", "关键变化", "建议行动"):
        assert token in text, f"missing: {token}"


def test_kpi_and_nav_unified():
    text = _html()
    for token in ("知识总量", "待处理知识缺口", "知识过期风险", "健康评分",
                  "历史复盘", "打开完整周报", "生成 AI 洞察"):
        assert token in text, f"missing: {token}"
    assert ">来源</button>" in text
    assert ">活动</button>" in text


def test_internal_fields_and_api_unchanged():
    text = _html()
    # internal enum/field names must remain (only display mapping changes)
    for token in ("judge_passed", "needs_review", "judge_failed", "pending_human",
                  "health_status", "consistency", "evidence_sufficiency"):
        assert token in text, f"internal field lost: {token}"
    # API paths unchanged
    for token in ("/api/weekly_review/dashboard", "/api/dashboard", "/api/weekly_review",
                  "/api/actions/", "/api/review/preflight"):
        assert token in text, f"API path lost: {token}"


def test_health_kpi_binds_real_data():
    # Health KPI must read health.score/status (not a static placeholder)
    text = _html()
    assert "healthColor(hh)" in text
    assert "hh.score==null?'—':esc(hh.score)" in text
    assert "uiHealthStatus(hh.status)" in text


if __name__ == "__main__":
    for t in (
        test_no_phase_leftover_copy, test_no_unimplemented_copy,
        test_core_chinese_titles_exist, test_review_status_chinese,
        test_automation_chinese, test_ai_insight_chinese,
        test_kpi_and_nav_unified, test_internal_fields_and_api_unchanged,
        test_health_kpi_binds_real_data,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all control center UI label tests passed")
