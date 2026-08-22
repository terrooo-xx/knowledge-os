"""Knowledge Gap Diagnosis CLI (Phase 15, stage 1 audit).

Reads the latest (or specified) RAG Evaluation run records, classifies each
failure (knowledge_gap / evidence_gap / retrieval_gap / judge_gap / system_error),
clusters failures into knowledge-boundary gaps (explicit map, NOT string
similarity), checks wiki/source coverage, assigns P0/P1/P2, and writes:

    - 90_System/rag/evaluation/gaps.yaml            (gap registry, evidence-backed)
    - 40_Outputs/RAG Evaluation/audit/<run_id>/audit_report.md

Read-only wrt the knowledge base: never creates/edits Wiki or Sources.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

from rag_engine.gap_diagnosis import (  # noqa: E402
    ACTION_ACQUIRE, ACTION_CREATE, ACTION_EXPAND,
    build_gap_registry, render_audit_report,
)

EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
DEFAULT_REGISTRY = RAG_DIR / "evaluation" / "gaps.yaml"

# ---------------------------------------------------------------- audit data
# 聚类是人工知识边界判断（不是字符串相似度）：8 个失败 → 7 个知识域
CLUSTER_MAP = {
    "q_freertos_stack_overflow": "gap_freertos_config_debug",
    "q_freertos_task_notification": "gap_freertos_config_debug",
    "q_stm32_timer_pwm": "gap_stm32_cubemx_pwm",
    "q_stm32_low_power": "gap_stm32_low_power",
    "q_git_config": "gap_git_config",
    "q_px4_ekf": "gap_px4_ekf",
    "q_ros2_nav2": "gap_ros2_nav2",
    "q_wsl_ubuntu": "gap_wsl_ubuntu",
}

GAP_META = {
    "gap_freertos_config_debug": {
        "domain": "freertos",
        "title": "FreeRTOS 实战配置与调试",
        "wiki_target": {"existing": True, "path": "20_Wiki/04_FreeRTOS/CubeMX配置FreeRTOS.md"},
        "recommended_action": ACTION_EXPAND,
        "sources": ["00_Inbox/待处理文件/FreeRTOS任务通知补充资料.md"],
        "problem": [
            "已有 Wiki（CubeMX配置FreeRTOS）只列了 MINIMAL_STACK_SIZE / RECORD_STACK_HIGH_ADDRESS，缺少栈溢出检测与排查步骤",
            "任务通知有 Inbox Source 但未编译为 Wiki",
        ],
        "notes": "栈溢出检测无可靠来源，需先获取来源；任务通知可直接用 Inbox 资料编译 Draft Wiki",
    },
    "gap_stm32_cubemx_pwm": {
        "domain": "stm32",
        "title": "STM32CubeMX 定时器 PWM 输出",
        "wiki_target": {"existing": True, "path": "20_Wiki/03_STM32/STM32CubeMX定时器配置.md"},
        "recommended_action": ACTION_EXPAND,
        "sources": ["00_Inbox/待处理文件/个人笔记/STM32/STM32cubeMx使用笔记/STM32CubeMx定时器（Timers)配置选项.note.pdf"],
        "problem": ["Wiki 有 PWM 模式选项，但缺少「输出 PWM 的完整配置步骤」（分频/ARR/占空比/引脚映射）"],
    },
    "gap_stm32_low_power": {
        "domain": "stm32", "title": "STM32 低功耗模式配置",
        "wiki_target": {"existing": False},
        "recommended_action": ACTION_ACQUIRE,
        "sources": [],
        "problem": ["完全缺资料：低功耗待机模式无 Wiki 无 Source"],
    },
    "gap_git_config": {
        "domain": "tooling", "title": "Obsidian Git 配置",
        "wiki_target": {"existing": False},
        "recommended_action": ACTION_CREATE,
        "sources": ["00_Inbox/待处理文件/个人笔记/个人数据库Obsidian/Git 配置.note.pdf"],
        "problem": ["有 PDF Source（Git 身份配置）但未编译为 Wiki"],
    },
    "gap_px4_ekf": {
        "domain": "drone", "title": "PX4 EKF 卡尔曼滤波调参",
        "wiki_target": {"existing": False},
        "recommended_action": ACTION_ACQUIRE,
        "sources": [],
        "problem": ["完全缺资料（已在 knowledge_gaps.yaml 记录）"],
    },
    "gap_ros2_nav2": {
        "domain": "robot", "title": "ROS2 Nav2 代价地图配置",
        "wiki_target": {"existing": False},
        "recommended_action": ACTION_ACQUIRE,
        "sources": [],
        "problem": ["完全缺资料（已在 knowledge_gaps.yaml 记录）"],
    },
    "gap_wsl_ubuntu": {
        "domain": "tooling", "title": "WSL 安装 Ubuntu",
        "wiki_target": {"existing": False},
        "recommended_action": ACTION_ACQUIRE,
        "sources": [],
        "problem": ["完全缺资料（已在 knowledge_gaps.yaml 记录）"],
    },
}


def _load_records(run_dir: Path) -> list[dict]:
    if run_dir.is_file():
        path = run_dir
    else:
        path = run_dir / "evaluation_records.jsonl"
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _build_indexes() -> tuple[dict[str, Path], dict[str, Path]]:
    wiki_index = {}
    for p in (VAULT_ROOT / "20_Wiki").rglob("*.md"):
        wiki_index[p.relative_to(VAULT_ROOT).as_posix()] = p
    source_index = {}
    for root in ("00_Inbox", "10_Sources"):
        for p in (VAULT_ROOT / root).rglob("*"):
            if p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt"):
                source_index[p.relative_to(VAULT_ROOT).as_posix()] = p
    return wiki_index, source_index


def _merge_registry(existing_path: Path, new_entries: list[dict]) -> list[dict]:
    """Preserve resolved state from an existing registry (idempotent audit)."""
    if not existing_path.exists():
        return new_entries
    try:
        import yaml
        old = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or []
    except Exception:
        old = []
    old_by_id = {g.get("id"): g for g in old if isinstance(g, dict)}
    for entry in new_entries:
        prev = old_by_id.get(entry["id"])
        if prev and prev.get("status") == "resolved":
            entry["status"] = "resolved"
            entry["resolved_by"] = prev.get("resolved_by")
            entry["resolved_at"] = prev.get("resolved_at")
            entry["before"] = prev.get("before")
            entry["after"] = prev.get("after")
    return new_entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge Gap Diagnosis CLI")
    parser.add_argument("--records", default=str(EVAL_ROOT / "runs"),
                        help="run dir or records.jsonl path (default: latest run dir)")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out", default=str(EVAL_ROOT / "audit"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    records_path = Path(args.records)
    if records_path.is_dir():
        # latest run dir by generated_at in meta.json
        runs = [d for d in records_path.iterdir() if d.is_dir() and (d / "meta.json").exists()]
        runs.sort(key=lambda d: (d / "meta.json").read_text(encoding="utf-8"))
        if not runs:
            print("no evaluation runs found", file=sys.stderr)
            return 1
        run_dir = runs[-1]
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    else:
        run_dir = records_path.parent
        meta = {}
        if (run_dir / "meta.json").exists():
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

    records = _load_records(run_dir)
    wiki_index, source_index = _build_indexes()

    # 校验审计数据中声明的 source 是否真实存在（不编造）
    for gid, m in GAP_META.items():
        for s in m.get("sources") or []:
            if s not in source_index:
                print(f"WARN: {gid} 声明的 source 不存在于仓库: {s}", file=sys.stderr)
                m["sources"] = [x for x in m["sources"] if x in source_index]

    entries = build_gap_registry(
        records, CLUSTER_MAP, GAP_META,
        wiki_index=wiki_index, source_index=source_index,
        created=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    )
    entries = _merge_registry(Path(args.registry), entries)

    reg_path = Path(args.registry)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    reg_path.write_text(yaml.safe_dump(entries, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")

    audit_dir = Path(args.out) / (meta.get("run_id") or "audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_md = render_audit_report(records, entries, {"run_id": meta.get("run_id")})
    audit_path = audit_dir / "audit_report.md"
    audit_path.write_text(audit_md, encoding="utf-8")
    (audit_dir / "gaps.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({
            "ok": True, "run_id": meta.get("run_id"), "registry": str(reg_path),
            "audit_report": str(audit_path), "gaps": len(entries),
            "open": sum(1 for g in entries if g["status"] == "open"),
            "resolved": sum(1 for g in entries if g["status"] == "resolved"),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"registry: {reg_path}")
        print(f"audit: {audit_path}")
        print(f"gaps: {len(entries)} (open={sum(1 for g in entries if g['status']=='open')}, "
              f"resolved={sum(1 for g in entries if g['status']=='resolved')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
