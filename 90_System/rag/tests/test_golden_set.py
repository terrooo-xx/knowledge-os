"""Golden Set tests (offline): schema, manual review fields, stats,
q_drone_power entry, CC API, weekly metrics."""
from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
REVIEW_DIR = RAG_DIR / "scripts" / "review"
for d in (str(RAG_DIR), str(CTRL_DIR), str(REVIEW_DIR)):
    sys.path.insert(0, d)

from rag_engine.golden_set import (  # noqa: E402
    get_entry, golden_stats, load_golden, validate_golden,
)
import service  # noqa: E402
import metrics as review_metrics  # noqa: E402

GOLDEN = RAG_DIR / "evaluation" / "golden.yaml"


def _entry(id_, review=None, gt=None):
    return {
        "id": id_, "query": "Q",
        "ground_truth": {"answerable": True, "acceptable_paths": ["wiki", "either"], **(gt or {})},
        "review": {"answerable": None, "answer_correct": None, "evidence_supported": None,
                   "citation_correct": None, **(review or {})},
        "reviewer": "r", "date": "2026-08-15",
    }


def test_real_golden_schema_and_manual_fields():
    golden = load_golden(GOLDEN)
    entries = golden["entries"]
    assert len(entries) == 6
    assert validate_golden(entries) == []
    # 全部已人工标注（reviewer 非空 / review 字段非全 null）
    for e in entries:
        assert e.get("reviewer"), f"{e['id']} 缺 reviewer"
        rv = e.get("review") or {}
        assert any(rv.get(f) is not None for f in
                   ("answerable", "answer_correct", "evidence_supported", "citation_correct")), e["id"]
    # 路径覆盖：wiki-first / fallback / knowledge_missing / judge variance
    assert get_entry(entries, "q_freertos_scheduler")
    assert get_entry(entries, "q_stm32_usart")
    assert get_entry(entries, "q_freertos_stack_overflow")
    assert get_entry(entries, "q_px4_ekf")


def test_q_drone_power_in_golden():
    golden = load_golden(GOLDEN)
    e = get_entry(golden["entries"], "q_drone_power")
    assert e is not None
    rv = e["review"]
    assert rv["evidence_supported"] is True
    assert rv["answer_correct"] is None  # Judge variance 案例：跨 run 不稳定，不标正确/错误
    assert "Judge" in (e.get("notes") or "") or "variance" in (e.get("notes") or "").lower()


def test_golden_stats_assessed_vs_total():
    entries = [
        _entry("a", review={"answer_correct": True, "evidence_supported": True}),
        _entry("b", review={"answer_correct": True, "evidence_supported": True}),
        _entry("c", review={"answer_correct": None, "evidence_supported": False}),
        _entry("d", review={"answer_correct": False, "evidence_supported": True}),
    ]
    s = golden_stats(entries)
    assert s["reviewed"] == 4
    assert s["answer_correct_count"] == 2          # 相对总数
    assert s["answer_correct_assessed"] == 3       # 只有 3 条可评估
    assert s["answer_correct_rate"] == round(100.0 * 2 / 3, 1)
    assert s["evidence_supported_count"] == 3
    assert s["sample_too_small"] is True
    # 未回答(null) 不算答错
    assert s["answer_correct_rate"] != 50.0


def test_golden_schema_rejects_bad_paths():
    bad = [_entry("x", gt={"acceptable_paths": ["raw", "forbidden"]})]
    problems = validate_golden(bad)
    assert any("forbidden" in p for p in problems)


def test_service_golden_set_api(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "GOLDEN_PATH", GOLDEN)
    r = service.golden_set()
    assert r["ok"] is True
    assert r["stats"]["total"] == 6
    assert r["stats"]["reviewed"] == 6
    assert r["entries"][0]["review"]["answer_correct"] is not None or \
           any(k is not None for k in r["entries"][0]["review"].values())


def test_weekly_metrics_include_golden(tmp_path):
    vault = tmp_path
    (vault / "40_Outputs" / "RAG Evaluation").mkdir(parents=True)
    (vault / "40_Outputs" / "RAG Evaluation" / "latest.json").write_text(
        '{"metrics": {"overall": {}}}', encoding="utf-8")
    (vault / "90_System" / "rag" / "evaluation").mkdir(parents=True)
    # copy real golden to temp vault
    (vault / "90_System" / "rag" / "evaluation" / "golden.yaml").write_text(
        Path(GOLDEN).read_text(encoding="utf-8"), encoding="utf-8")
    re_ = review_metrics.collect_rag_evaluation(vault)
    assert re_ is not None and re_["golden"] is not None
    assert re_["golden"]["total"] == 6
    assert re_["golden"]["reviewed"] == 6
