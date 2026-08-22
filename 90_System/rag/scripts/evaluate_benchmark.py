"""RAG Evaluation / Query Benchmark runner.

Reads benchmark.yaml (+ optional golden.yaml), executes every query through the
PRODUCTION retrieval chain (knowledge_service.knowledge_search), records the real
retrieval_trace / evidence / judge / latency, then aggregates metrics and writes:

    40_Outputs/RAG Evaluation/runs/<run_id>/
        meta.json
        evaluation_records.jsonl
        evaluation_report.json
        evaluation_report.md
    40_Outputs/RAG Evaluation/latest.json      (pointer for CC / Weekly Review)

It NEVER re-implements retrieval / embedding / rerank / judge, and never writes
to the knowledge base. Default mode="fast" (no long answer LLM pass) keeps cost
bounded while still exercising the full Wiki-first -> gate -> RAW fallback ->
reranker -> evidence -> judge chain.

Usage:
    python evaluate_benchmark.py [--benchmark PATH] [--golden PATH]
        [--out DIR] [--limit N] [--mode fast|deep] [--warmup N]
        [--no-llm] [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "interface"
RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
for d in (str(AGENT_DIR), str(RAG_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

from rag_engine.config import load_config, resolve_paths  # noqa: E402
from rag_engine.evaluation import (  # noqa: E402
    classify_failure,
    classify_gap_signal,
    final_status,
    load_benchmark,
    load_golden,
    build_report,
    render_markdown,
)
import rag_engine.retrieval as retrieval  # noqa: E402

DEFAULT_BENCHMARK = RAG_DIR / "evaluation" / "benchmark.yaml"
DEFAULT_GOLDEN = RAG_DIR / "evaluation" / "golden.yaml"
DEFAULT_OUT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"

# ---------------------------------------------------------------- timing


def _install_timing() -> dict[str, list]:
    timings: dict[str, list] = {}

    def _t(key):
        def deco(fn):
            def wrap(*a, **k):
                t0 = time.perf_counter()
                r = fn(*a, **k)
                timings.setdefault(key, []).append((time.perf_counter() - t0) * 1000)
                return r
            return wrap
        return deco

    retrieval.search_corpus = _t("retrieval")(retrieval.search_corpus)
    retrieval.rerank = _t("rerank")(retrieval.rerank)
    retrieval.assess_evidence = _t("evidence")(retrieval.assess_evidence)
    retrieval.judge_relevance = _t("judge")(retrieval.judge_relevance)
    return timings


def _sum_ms(values: list) -> float | None:
    if not values:
        return None
    return round(sum(values), 1)


# ---------------------------------------------------------------- record builder


def _norm_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in ("true", "yes", "1")


def _build_record(query: dict, result: dict, timings: dict,
                  run_id: str, warmup_count: int, golden_lookup: dict) -> dict:
    trace = result.get("retrieval_trace") or {}
    tr = trace.get("retrieval") or {}
    cand = trace.get("candidates") or {}
    rank = trace.get("ranking") or {}
    tev = trace.get("evidence") or {}
    tjudge = trace.get("judge") or {}

    status = result.get("status") or "error"
    if status == "error":
        final = "system_error"
    elif status == "answerable":
        final = "answered"
    else:
        final = "knowledge_missing"

    path = tr.get("path") or "raw"
    source = "wiki" if path == "wiki_first" else "raw"
    evidence_list = result.get("evidence") or []
    scores = [float(e.get("score") or 0.0) for e in evidence_list]
    confidence = round(max(scores), 4) if scores else 0.0
    statuses = sorted({str(e.get("status") or "unknown") for e in evidence_list})

    record = {
        "run_id": run_id,
        "query_id": query["id"],
        "query": query["query"],
        "category": query.get("category"),
        "project": query.get("project"),
        "query_type": query.get("query_type"),
        "difficulty": query.get("difficulty"),
        "expected_source": query.get("expected_source"),
        "expected_answerable": query.get("expected_answerable"),
        "expected": query.get("expected"),
        "notes": query.get("notes"),
        "execution": {
            "source": source,
            "path": path,
            "initial_path": tr.get("initial_path"),
            "gate_passed": bool(tr.get("gate_passed")),
            "fallback_used": bool(tr.get("fallback_used")),
            "fallback_reason": tr.get("fallback_reason"),
            "reranker_used": bool(rank.get("reranker_used")),
            "raw_ran": bool(tr.get("fallback_used")) or path == "raw" or tr.get("initial_path") == "raw",
            "wiki_count": int(cand.get("wiki_count") or 0),
            "raw_count": int(cand.get("raw_count") or 0),
            "wiki_confidence": tr.get("wiki_confidence"),
            "confidence": confidence,
        },
        "evidence": {
            "sufficient": bool(result.get("sufficient")),
            "gap_type": None if status == "answerable" else status,
            "chunk_count": len(evidence_list),
            "confidence": confidence,
            "sources": result.get("source_trace") or [],
            "statuses": statuses,
            "reason": result.get("reason"),
            "window_count": int(tev.get("window_count") or 0),
        },
        "judge": {
            "executed": bool(tjudge.get("executed")),
            "result": tjudge.get("result"),
            "relevance": (result.get("judge") or {}).get("relevance"),
        },
        "final": {
            "status": final,
            "status_code": result.get("status"),
            "mode": result.get("mode"),
        },
        "metrics": {
            "total_ms": round(result.get("_total_ms") or 0.0, 1),
            "retrieval_ms": _sum_ms(timings.get("retrieval", [])),
            "rerank_ms": _sum_ms(timings.get("rerank", [])),
            "judge_ms": _sum_ms(timings.get("judge", [])),
            "answer_ms": _sum_ms(timings.get("answer", [])),
        },
        "manual_review": golden_lookup.get(query["id"]),
        "retrieval_trace": trace,
        "retrieval_gate": result.get("retrieval_gate"),
        "judge_detail": result.get("judge"),
        "evidence_windows": result.get("evidence_windows") or [],
    }
    # failure taxonomy / gap signal from the final record (self-contained)
    record["failure_type"] = classify_failure(record)
    record["gap_signal"] = classify_gap_signal(record)
    return record


# ---------------------------------------------------------------- main


def run_benchmark(args) -> dict:
    benchmark = load_benchmark(args.benchmark)
    golden = load_golden(args.golden) if args.golden and Path(args.golden).exists() else {"entries": []}
    golden_lookup = {e["id"]: e for e in golden.get("entries", [])}

    queries = benchmark["queries"]
    if args.limit:
        queries = queries[: int(args.limit)]

    cfg = resolve_paths(load_config(args.config), VAULT_ROOT)
    if args.no_llm:
        cfg["llm"] = dict(cfg.get("llm") or {})
        cfg["llm"]["provider"] = "none"
        cfg["evidence_judge"] = dict(cfg.get("evidence_judge") or {})
        cfg["evidence_judge"]["enabled"] = False

    from rag_engine.embeddings import create_embedder
    from rag_engine.vector_store import create_store
    from knowledge_service import knowledge_search

    # 进程内复用 embedder / store：首次（warmup）吸收模型加载，后续为真实热查询
    embedder = create_embedder(cfg)
    raw_store = create_store(cfg, cfg["paths"]["main_vector_db"])
    wiki_store = raw_store

    run_id = datetime.now().strftime("eval-%Y%m%dT%H%M%S")
    warmup = max(0, int(args.warmup))
    records: list[dict] = []
    warmup_total_ms = 0.0

    _originals = {name: getattr(retrieval, name) for name in
                  ("search_corpus", "rerank", "assess_evidence", "judge_relevance")}
    timings = _install_timing()
    try:
        # ---- warmup (discarded, models are cold-loaded here) ----
        if warmup:
            t0 = time.perf_counter()
            for q in queries[:warmup]:
                try:
                    knowledge_search(q["query"], mode=args.mode, use_llm=not args.no_llm,
                                     cfg=cfg, record_gap=False, embedder=embedder,
                                     raw_store=raw_store, wiki_store=wiki_store)
                except Exception:
                    pass  # warmup 失败不影响指标
            warmup_total_ms = (time.perf_counter() - t0) * 1000

        # ---- real run ----
        target = queries[warmup:] if warmup else queries
        for q in target:
            timings.clear()
            t0 = time.perf_counter()
            try:
                result = knowledge_search(q["query"], mode=args.mode, use_llm=not args.no_llm,
                                          cfg=cfg, record_gap=False, embedder=embedder,
                                          raw_store=raw_store, wiki_store=wiki_store)
                result["_total_ms"] = (time.perf_counter() - t0) * 1000
            except Exception as exc:
                result = {
                    "status": "error", "mode": args.mode, "sufficient": False,
                    "evidence": [], "judge": None, "source_trace": [], "reason": str(exc),
                    "retrieval_trace": None, "retrieval_gate": None, "evidence_windows": [],
                    "_total_ms": (time.perf_counter() - t0) * 1000,
                }
            record = _build_record(q, result, timings, run_id, warmup, golden_lookup)
            records.append(record)
            if args.json:
                sys.stdout.write(json.dumps({
                    "query_id": record["query_id"], "final": record["final"]["status"],
                    "failure": record["failure_type"], "gap_signal": record["gap_signal"],
                    "total_ms": record["metrics"]["total_ms"],
                }, ensure_ascii=False) + "\n")
                sys.stdout.flush()
    finally:
        for name, fn in _originals.items():
            setattr(retrieval, name, fn)

    llm = cfg.get("llm") or {}
    model = llm.get("model")
    if isinstance(model, dict):
        model = model.get("name")
    meta = {
        "run_id": run_id,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "benchmark_version": benchmark.get("benchmark_version"),
        "golden_version": golden.get("golden_version"),
        "query_count": len(records),
        "mode": args.mode,
        "use_llm": not args.no_llm,
        "warmup_count": warmup,
        "warmup_total_ms": round(warmup_total_ms, 1),
        "model_config": {
            "llm": f"{llm.get('provider')}:{model or 'unknown'}",
            "embedding": (cfg.get("embedding") or {}).get("model"),
            "reranker": (cfg.get("reranker") or {}).get("model"),
            "confidence_threshold": (cfg.get("retrieval") or {}).get("confidence_threshold"),
            "evidence_window": cfg.get("evidence_window") or {},
        },
    }

    report = build_report(records, meta)
    return {
        "run_id": run_id,
        "meta": meta,
        "report": report,
        "records": records,
    }


def persist(run: dict, out_root: Path) -> dict:
    run_dir = out_root / "runs" / run["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = run["meta"]
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(run_dir / "evaluation_records.jsonl", "w", encoding="utf-8") as fh:
        for r in run["records"]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (run_dir / "evaluation_report.json").write_text(
        json.dumps(run["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "evaluation_report.md").write_text(
        render_markdown(run["report"]), encoding="utf-8")

    def _vault_rel(path: Path) -> str:
        try:
            return path.relative_to(VAULT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    latest = {
        "run_id": run["run_id"],
        "generated_at": meta["generated_at"],
        "benchmark_version": meta.get("benchmark_version"),
        "query_count": meta["query_count"],
        "mode": meta["mode"],
        "metrics": run["report"]["metrics"],
        "report_path": _vault_rel(run_dir / "evaluation_report.md"),
        "records_path": _vault_rel(run_dir / "evaluation_records.jsonl"),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge OS RAG Evaluation / Query Benchmark runner")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--config", default=str(RAG_DIR / "config.yaml"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mode", default="fast", choices=["fast", "deep"])
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--no-llm", action="store_true", help="进程内关闭 Judge 与 LLM（纯本地基线）")
    parser.add_argument("--json", action="store_true", help="逐条输出 JSON 进度")
    parser.add_argument("--dry-run", action="store_true", help="只校验 benchmark/golden 并统计查询数")
    args = parser.parse_args()

    if args.dry_run:
        bench = load_benchmark(args.benchmark)
        gold = load_golden(args.golden) if Path(args.golden).exists() else {"entries": []}
        print(json.dumps({
            "benchmark_version": bench.get("benchmark_version"),
            "queries": len(bench["queries"]),
            "golden_entries": len(gold.get("entries", [])),
            "ok": True,
        }, ensure_ascii=False, indent=2))
        return 0

    run = run_benchmark(args)
    latest = persist(run, Path(args.out))
    print(json.dumps({
        "ok": True,
        "run_id": run["run_id"],
        "output": str(Path(args.out) / "runs" / run["run_id"]),
        "summary": {
            "query_count": latest["query_count"],
            "answer_coverage": (latest["metrics"]["overall"] or {}).get("answer_coverage"),
            "knowledge_missing_rate": (latest["metrics"]["overall"] or {}).get("knowledge_missing_rate"),
            "top_failure": (latest["metrics"]["fail_closed"] or {}).get("top_failures", [{}])[0].get("type")
                           if (latest["metrics"]["fail_closed"] or {}).get("top_failures") else None,
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
