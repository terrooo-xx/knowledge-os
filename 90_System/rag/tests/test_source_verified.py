"""Source Verified（人工核验）tests: lifecycle acquired->verified, audit log,
no auto evaluation trigger, API verified state."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
CTRL_DIR = RAG_DIR.parent / "control_center"
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(CTRL_DIR))

import service

from rag_engine.evaluation_governance import default_state, load_state, save_state  # noqa: E402

REG = {"created": "2026-08-17", "sources": [
    {"id": "src_git_config", "gap_id": "gap_git_config", "title": "Obsidian-Git Getting Started",
     "priority": "P1", "source_status": "acquired", "source_type": "trusted_tutorial",
     "source": {"title": "Obsidian-Git Getting Started",
                "local_path": "10_Sources/工具链/Obsidian-Git_GettingStarted.md"},
     "verification": {"verified": False, "reviewer": "", "notes": ""},
     "sufficiency": {f: "unknown" for f in (
         "source_relevance", "source_authority", "source_completeness",
         "source_recency", "source_extractability")},
     "reason": "r"},
    {"id": "src_px4", "gap_id": "gap_px4_ekf", "title": "PX4 EKF", "priority": "P2",
     "source_status": "candidate", "source_type": "official_docs", "source": {},
     "verification": {"verified": False}, "sufficiency": {}, "reason": "r"},
]}


def _patch(tmp: Path):
    old = (service.SOURCE_REGISTRY, service.ACTIVITY_LOG, service.EVAL_ROOT)
    reg = tmp / "source_acquisition.yaml"
    reg.write_text(json.dumps(REG, ensure_ascii=False), encoding="utf-8")
    service.SOURCE_REGISTRY = reg
    service.ACTIVITY_LOG = tmp / "activity_log.jsonl"
    service.EVAL_ROOT = tmp / "RAG Evaluation"
    (service.EVAL_ROOT).mkdir(parents=True, exist_ok=True)
    save_state(service.EVAL_ROOT / "evaluation_state.json", default_state())
    return old


def _restore(old):
    service.SOURCE_REGISTRY, service.ACTIVITY_LOG, service.EVAL_ROOT = old


def _find(registry, sid):
    return next(s for s in registry["sources"] if s["id"] == sid)


def test_unverified_source_returned():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            reg = service.source_acquisition()["registry"]
            s = _find(reg, "src_git_config")
            assert s["source_status"] == "acquired"
            assert s["verification"]["verified"] is False
        finally:
            _restore(old)


def test_mark_verified_succeeds_and_sets_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            r = service.mark_source_verified("src_git_config", actor="user")
            assert r["ok"] is True and r["result"] == "success"
            s = r["source"]
            assert s["source_status"] == "verified"
            assert s["verification"]["verified"] is True
            assert s["verification"]["verified_by"] == "user"
            assert s["verification"]["verified_at"]
            assert len(s["verification"]["verified_at"]) == 19  # YYYY-MM-DD HH:mm:ss
        finally:
            _restore(old)


def test_activity_log_records_source_verified():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            service.mark_source_verified("src_git_config")
            recs = service._activity_records()
            hits = [x for x in recs if x.get("action_id") == "SOURCE_VERIFIED"]
            assert len(hits) == 1
            e = hits[0]
            assert e["target"] == "src_git_config"
            assert e["previous_verified"] is False
            assert e["new_verified"] is True
            assert e["verified_by"] == "user"
            assert e["time"]
        finally:
            _restore(old)


def test_verified_does_not_trigger_evaluation():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            service.mark_source_verified("src_git_config")
            st = load_state(service.EVAL_ROOT / "evaluation_state.json")
            assert st["status"] == "idle"          # 不进入 required
            assert st["reasons"] == []
            assert service.governance_state()["required"] is False
        finally:
            _restore(old)


def test_api_returns_verified_state():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            service.mark_source_verified("src_git_config")
            reg = service.source_acquisition()["registry"]
            s = _find(reg, "src_git_config")
            assert s["verification"]["verified"] is True
            assert s["source_status"] == "verified"
            d = service.source_acquisition_detail("src_git_config")
            assert d["ok"] is True
            assert d["source"]["verification"]["verified"] is True
            assert d["source"]["verification"]["verified_at"]
        finally:
            _restore(old)


def test_mark_verified_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            r1 = service.mark_source_verified("src_git_config")
            r2 = service.mark_source_verified("src_git_config")
            assert r1["ok"] and r1["result"] == "success"
            assert r2["ok"] and r2["result"] == "already_done"
            hits = [x for x in service._activity_records()
                    if x.get("action_id") == "SOURCE_VERIFIED"]
            assert len(hits) == 1  # 只记一次
        finally:
            _restore(old)


def test_mark_verified_requires_acquired_and_known_id():
    with tempfile.TemporaryDirectory() as tmp:
        old = _patch(Path(tmp))
        try:
            r = service.mark_source_verified("src_px4")   # candidate 不能跳过 acquired
            assert r["ok"] is False
            r2 = service.mark_source_verified("nope")
            assert r2["ok"] is False
            assert "不存在" in r2["message"]
        finally:
            _restore(old)
