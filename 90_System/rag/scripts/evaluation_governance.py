"""Evaluation Governance CLI (Phase 19).

Makes the Baseline Regression Check an automatic quality gate:

    python evaluation_governance.py --status
    python evaluation_governance.py --verify        # required/failed -> run -> check -> complete
    python evaluation_governance.py --reset

--verify: runs the production 28-query benchmark (if required/failed), auto-runs
the Baseline Regression Check, and only re-establishes the baseline when the
batch contained a knowledge change AND the check is STABLE/IMPROVED.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.evaluation_baseline import load_baseline, regression_check  # noqa: E402
from rag_engine.evaluation_governance import (  # noqa: E402
    STATUS_IMPROVED, STATUS_PASSED, STATUS_REGRESSED, STATUS_RUNNING,
    complete, fail, has_knowledge_change, load_state, mark_required,
    render_governance_markdown, save_state, should_verify, start,
)
from rag_engine.index_fingerprint import detect_index_change  # noqa: E402

EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
STATE_PATH = EVAL_ROOT / "evaluation_state.json"
BASELINE_PATH = EVAL_ROOT / "baseline.json"
ACTIVITY_LOG = VAULT_ROOT / "90_System" / "control_center" / "activity_log.jsonl"


def _log(entry: dict) -> None:
    entry["time"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(ACTIVITY_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_config():
    from rag_engine.config import load_config, resolve_paths
    cfg = resolve_paths(load_config(str(RAG_DIR / "config.yaml")), VAULT_ROOT)
    return cfg


def _index_roots(cfg):
    return [Path(cfg["paths"]["wiki"]), Path(cfg["paths"]["projects"])]


def _manifest_path(cfg):
    return Path(cfg["paths"]["main_vector_db"]).parent / "index_manifest.json"


def _detect_and_mark_index_change() -> dict:
    """Content-hash fingerprint vs manifest -> mark evaluation_required if real change."""
    try:
        cfg = _load_config()
        change = detect_index_change(_manifest_path(cfg), _index_roots(cfg), VAULT_ROOT)
    except Exception as exc:
        return {"ok": False, "message": f"fingerprint 检测失败: {exc}"}
    if not change.get("changed"):
        return {"ok": True, "changed": False, "reasons": []}
    state = load_state(STATE_PATH)
    state = mark_required(state, "index_updated",
                          {"added": len(change["added"]), "modified": len(change["modified"]),
                           "deleted": len(change["deleted"])})
    save_state(STATE_PATH, state)
    _log({"action_id": "governance_index_fingerprint", "type": "governance",
          "result": "required", "message": f"Index 内容变化：{','.join(change['reasons'])} -> evaluation_required"})
    return {"ok": True, "changed": True, "reasons": change["reasons"], "state": state}


# 跨进程并发保护（Windows）：O_EXCL 锁文件 + 过期接管
LOCK_PATH = EVAL_ROOT / ".governance.lock"
_LOCK_STALE_MINUTES = 30


def _acquire_lock() -> bool:
    import time
    if LOCK_PATH.exists():
        age = time.time() - LOCK_PATH.stat().st_mtime
        if age < _LOCK_STALE_MINUTES * 60:
            return False  # 已有进程在运行
        try:
            LOCK_PATH.unlink()  # 过期锁接管
        except Exception:
            return False
    try:
        fd = LOCK_PATH.open("x")
        fd.close()
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except Exception:
        pass


def _latest() -> dict:
    p = EVAL_ROOT / "latest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def verify() -> dict:
    # 并发保护：同一时间只允许一个 Benchmark（Scenario F）
    if not _acquire_lock():
        state = load_state(STATE_PATH)
        return {"ok": True, "message": "已有 Evaluation 正在运行（锁占用），跳过", "state": state,
                "already_running": True, "skipped": True}

    try:
        return _verify_locked()
    finally:
        _release_lock()


def _verify_locked() -> dict:
    state = load_state(STATE_PATH)
    if state["status"] == STATUS_RUNNING:
        return {"ok": True, "message": "已有 Evaluation 正在运行（state=running），跳过",
                "state": state, "already_running": True, "skipped": True}

    # Index 内容指纹检测：真实知识变化 -> evaluation_required（mtime 触碰不触发）
    fp = _detect_and_mark_index_change()
    state = load_state(STATE_PATH)

    if not should_verify(state):
        _log({"action_id": "governance_skip", "type": "governance", "target": "evaluation",
              "result": "skipped",
              "message": "无待验证知识变化，跳过 Benchmark（index_change="
                         f"{'true' if (fp or {}).get('changed') else 'false'}）"})
        return {"ok": True, "message": "无待验证的知识变化（idle/passed），跳过",
                "state": state, "skipped": True, "index_change": fp}

    state = start(state)
    save_state(STATE_PATH, state)
    _log({"action_id": "governance_verify", "type": "governance", "target": "evaluation",
          "result": "running", "message": f"Evaluation Governance 开始（reasons={state['reasons']}）"})
    try:
        cmd = [sys.executable, str(RAG_DIR / "scripts" / "evaluate_benchmark.py"), "--warmup", "1"]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=1200)
        out = (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:
        state = fail(state, str(exc))
        save_state(STATE_PATH, state)
        _log({"action_id": "governance_verify", "type": "governance", "target": "evaluation",
              "result": "failed", "message": f"Evaluation 执行失败: {exc}"})
        return {"ok": False, "message": f"Evaluation 执行失败: {exc}", "state": state}

    latest = _latest()
    run_id = latest.get("run_id")
    if proc.returncode != 0 or not run_id:
        state = fail(state, out[-500:] or "evaluate_benchmark 失败")
        save_state(STATE_PATH, state)
        _log({"action_id": "governance_verify", "type": "governance", "target": "evaluation",
              "result": "failed", "message": "Evaluation 运行失败（非回归）"})
        return {"ok": False, "message": f"Evaluation 运行失败: {out[-500:]}", "state": state}

    baseline = load_baseline(BASELINE_PATH)
    ov = ((latest.get("metrics") or {}).get("overall") or {})
    current = {"run_id": run_id, "coverage": ov.get("answer_coverage")}
    check = regression_check(current, baseline) if baseline else {
        "status": "STABLE", "current_run": run_id, "current_coverage": current["coverage"],
        "baseline_coverage": None, "delta_pp": None, "warning": None}

    reestablish = bool(baseline) and has_knowledge_change(state) and check["status"] != "REGRESSED"
    baseline_id = baseline.get("baseline_id") if baseline else None
    if reestablish:
        try:
            prev = baseline["run_id"]
            cmd2 = [sys.executable, str(RAG_DIR / "scripts" / "evaluation_baseline.py"),
                    "--establish", "--run", run_id, "--prev", prev, "--json"]
            p2 = subprocess.run(cmd2, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=120)
            out2 = (p2.stdout or "") + (p2.stderr or "")
            if p2.returncode == 0:
                new_b = load_baseline(BASELINE_PATH)
                baseline_id = new_b.get("baseline_id") if new_b else baseline_id
        except Exception:
            pass

    state = complete(state, run_id=run_id, check=check, baseline_id=baseline_id,
                     reestablish_baseline=reestablish)
    save_state(STATE_PATH, state)
    _log({"action_id": "governance_verify", "type": "governance", "target": "evaluation",
          "result": state["status"],
          "message": f"Baseline Check 完成：{check.get('status')}（delta={check.get('delta_pp')}pp）"
                     f" run={run_id}"})
    return {"ok": True, "state": state, "check": check, "run_id": run_id}


def exit_code_for(result: dict) -> int:
    """0 = 正常/无需执行/Stable/Improved；1 = Regression；2 = Evaluation Failed。
    JUDGE_VARIANCE 不会产生 Regression exit code（state 不会因此为 regressed）。"""
    if not result.get("ok"):
        return 2
    if result.get("skipped"):
        return 0
    if (result.get("state") or {}).get("status") == STATUS_REGRESSED:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation Governance CLI")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.verify:
        r = verify()
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(r.get("message"))
        return exit_code_for(r)

    if args.reset:
        from rag_engine.evaluation_governance import default_state
        save_state(STATE_PATH, default_state())
        print("governance state reset to idle")
        return 0

    state = load_state(STATE_PATH)
    baseline = load_baseline(BASELINE_PATH)
    if args.json:
        print(json.dumps({"ok": True, "state": state, "baseline": baseline}, ensure_ascii=False, indent=2))
    else:
        print(render_governance_markdown(state, baseline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
