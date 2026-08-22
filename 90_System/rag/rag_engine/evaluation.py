"""RAG Evaluation metrics: derive transparent quality metrics from real retrieval records.

Pure functions only (no network / LLM / UI). Input is a list of evaluation
records produced by `scripts/evaluate_benchmark.py`, which calls the PRODUCTION
`knowledge_service.knowledge_search` path. Nothing here re-implements retrieval /
rerank / judge, and nothing modifies RAG algorithms or thresholds.

Design principles (per task requirements):
  - transparent raw metrics + per-item breakdown, NO composite RAG score
  - never treat benchmark `expected_*` labels as ground truth
  - distinguish answered / knowledge_missing / system_error
  - sample-too-small (N < 20) must be explicit, no fake trends
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- constants

FINAL_ANSWERED = "answered"
FINAL_KNOWLEDGE_MISSING = "knowledge_missing"
FINAL_SYSTEM_ERROR = "system_error"

FAILURE_TAXONOMY = {
    "WIKI_MISS": "Wiki 无候选（知识库 Wiki 侧未命中）",
    "WIKI_BELOW_THRESHOLD": "Wiki 候选未达置信度阈值",
    "WIKI_EVIDENCE_INSUFFICIENT": "Wiki 证据不足",
    "WIKI_JUDGE_REJECTED": "Wiki 被 Relevance Judge 拒绝",
    "RAW_RETRIEVAL_WEAK": "RAW 检索无/弱候选",
    "RAW_EVIDENCE_INSUFFICIENT": "RAW 证据不足",
    "RAW_JUDGE_REJECTED": "RAW 被 Relevance Judge 拒绝",
    "KNOWLEDGE_MISSING": "知识库缺失（通用）",
    "SYSTEM_ERROR": "系统错误（非知识缺失）",
}

GAP_SIGNAL_ANSWERED = "answered"
GAP_SIGNAL_KNOWLEDGE = "likely_knowledge_gap"
GAP_SIGNAL_EVIDENCE = "evidence_gap"
GAP_SIGNAL_RETRIEVAL = "retrieval_gap"
GAP_SIGNAL_SYSTEM = "system_error"
GAP_SIGNAL_UNKNOWN = "unknown"

SAMPLE_TOO_SMALL_N = 20

QUERY_TYPES = ("fact", "configuration", "procedure", "troubleshooting",
               "comparison", "concept", "cross_document", "unknown")

# ---------------------------------------------------------------- helpers


def _rate(num: int, den: int) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def _mean(values: list[float]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.mean(vals), 1) if vals else None


def _quantiles(values: list[float], marks: tuple[int, ...] = (50, 90, 95)) -> dict:
    """Percentiles with linear interpolation (numpy-like). Empty input -> {}."""
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return {}
    out = {}
    n = len(vals)
    for p in marks:
        pos = (p / 100.0) * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        out[f"p{p}"] = round(vals[lo] + (vals[hi] - vals[lo]) * frac, 1)
    return out


def _norm_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in ("true", "yes", "1")


VALID_EXPECTED_SOURCES = {"wiki", "wiki_or_raw", "raw", "either", "unknown"}
VALID_QUERY_TYPES = set(QUERY_TYPES)
VALID_EXPECTED_LABELS = {"heuristic", "manual", "unknown"}
REQUIRED_QUERY_FIELDS = ("id", "query", "category", "query_type", "expected_source", "expected_answerable")


def _load_yaml(path) -> Any:
    import yaml
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"evaluation file not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if data is None:
        return {}
    return data


def load_benchmark(path: str | Path) -> dict:
    """Load + validate benchmark.yaml. Returns {"benchmark_version", "queries": [...]}."""
    data = _load_yaml(path)
    if not isinstance(data, dict) or not isinstance(data.get("queries"), list):
        raise ValueError(f"benchmark 格式错误（需要 top-level queries 列表）: {path}")
    queries = data["queries"]
    ids = set()
    for i, q in enumerate(queries):
        if not isinstance(q, dict):
            raise ValueError(f"benchmark 第 {i + 1} 条不是对象")
        for f in REQUIRED_QUERY_FIELDS:
            if f not in q or q[f] in (None, ""):
                raise ValueError(f"benchmark 第 {i + 1} 条缺少字段: {f}")
        qid = str(q["id"])
        if qid in ids:
            raise ValueError(f"benchmark id 重复: {qid}")
        ids.add(qid)
        if q["query_type"] not in VALID_QUERY_TYPES:
            raise ValueError(f"{qid} query_type 非法: {q['query_type']}")
        if q["expected_source"] not in VALID_EXPECTED_SOURCES:
            raise ValueError(f"{qid} expected_source 非法: {q['expected_source']}")
        if q.get("expected") is not None and q["expected"] not in VALID_EXPECTED_LABELS:
            raise ValueError(f"{qid} expected 非法: {q['expected']}")
        if not isinstance(q["expected_answerable"], (bool, type(None))) and                 str(q["expected_answerable"]).strip().lower() not in ("true", "false", "unknown"):
            raise ValueError(f"{qid} expected_answerable 非法: {q['expected_answerable']}")
    return {"benchmark_version": str(data.get("benchmark_version") or "1.0"),
            "created": data.get("created"), "queries": queries}


def load_golden(path: str | Path) -> dict:
    """Load + validate golden.yaml. Returns {"golden_version", "entries": [...]}."""
    data = _load_yaml(path)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"golden 格式错误（需要 top-level entries 列表）: {path}")
    entries = data["entries"]
    ids = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("id"):
            raise ValueError(f"golden 第 {i + 1} 条缺少 id")
        if e["id"] in ids:
            raise ValueError(f"golden id 重复: {e['id']}")
        ids.add(e["id"])
    return {"golden_version": str(data.get("golden_version") or "1.0"),
            "created": data.get("created"), "entries": entries}


# ---------------------------------------------------------------- record access


def final_status(record: dict) -> str:
    """'answered' | 'knowledge_missing' | 'system_error'."""
    return record.get("final", {}).get("status") or record.get("final_status") or FINAL_SYSTEM_ERROR


def _exec(record: dict) -> dict:
    return record.get("execution") or {}


def _evidence(record: dict) -> dict:
    return record.get("evidence") or {}


def _judge(record: dict) -> dict:
    return record.get("judge") or {}


# ---------------------------------------------------------------- failure taxonomy


def classify_failure(record: dict) -> str | None:
    """Derive one failure type from the trace for knowledge_missing records.

    Never invents data: only reads execution / evidence / judge fields that were
    produced by the real chain. answered/system_error records get None.
    """
    if final_status(record) == FINAL_ANSWERED:
        return None
    if final_status(record) == FINAL_SYSTEM_ERROR:
        return "SYSTEM_ERROR"

    ex = _exec(record)
    ev = _evidence(record)
    jd = _judge(record)
    source = ex.get("source") or "raw"
    raw_count = int(ex.get("raw_count") or 0)
    wiki_count = int(ex.get("wiki_count") or 0)
    judge_rejected = bool(jd.get("executed")) and jd.get("result") == "insufficient"

    if source == "raw":
        if raw_count == 0:
            return "RAW_RETRIEVAL_WEAK"
        if judge_rejected:
            return "RAW_JUDGE_REJECTED"
        return "RAW_EVIDENCE_INSUFFICIENT"

    # source == "wiki" (wiki passed the gate but still failed)
    if wiki_count == 0:
        return "WIKI_MISS"
    if judge_rejected:
        return "WIKI_JUDGE_REJECTED"
    if ex.get("fallback_reason") == "below_threshold":
        return "WIKI_BELOW_THRESHOLD"
    return "WIKI_EVIDENCE_INSUFFICIENT"


# ---------------------------------------------------------------- gap signals


def classify_gap_signal(record: dict) -> str:
    """Classify a failed query into knowledge/evidence/retrieval gap.

    Conservative rules (no fabricated ground truth):
      - answered / system_error are reported as-is
      - no retrieval candidates at all:
          expected_answerable=True -> retrieval_gap (needs human confirmation)
          otherwise               -> likely_knowledge_gap
      - candidates exist but evidence/judge failed -> evidence_gap
    """
    status = final_status(record)
    if status == FINAL_ANSWERED:
        return GAP_SIGNAL_ANSWERED
    if status == FINAL_SYSTEM_ERROR:
        return GAP_SIGNAL_SYSTEM

    ex = _exec(record)
    jd = _judge(record)
    gate_passed = bool(ex.get("gate_passed"))
    raw_count = int(ex.get("raw_count") or 0)
    wiki_count = int(ex.get("wiki_count") or 0)
    judge_rejected = bool(jd.get("executed")) and jd.get("result") == "insufficient"

    # Judge 拒绝 / 有候选通过门槛但证据不足 -> 有资料但证据不完整
    if judge_rejected:
        return GAP_SIGNAL_EVIDENCE
    if gate_passed and (wiki_count > 0 or raw_count > 0):
        return GAP_SIGNAL_EVIDENCE

    # 没有任何候选通过门槛：预期有资料 -> 检索未命中（需人工确认），否则 -> 知识缺失
    if _norm_bool(record.get("expected_answerable")) is True:
        return GAP_SIGNAL_RETRIEVAL
    return GAP_SIGNAL_KNOWLEDGE


# ---------------------------------------------------------------- aggregation


def aggregate_metrics(records: list[dict], meta: dict | None = None) -> dict:
    total = len(records)
    small = total < SAMPLE_TOO_SMALL_N

    answered = [r for r in records if final_status(r) == FINAL_ANSWERED]
    km = [r for r in records if final_status(r) == FINAL_KNOWLEDGE_MISSING]
    err = [r for r in records if final_status(r) == FINAL_SYSTEM_ERROR]
    n_answered, n_km, n_err = len(answered), len(km), len(err)

    # ---- wiki-first metrics ----
    wiki_first = [r for r in records if _exec(r).get("initial_path") == "wiki_first"]
    gate_pass = [r for r in records if _exec(r).get("gate_passed")]
    wiki_answered = [r for r in records if _exec(r).get("source") == "wiki" and final_status(r) == FINAL_ANSWERED]
    fallback = [r for r in records if _exec(r).get("fallback_used")]
    fallback_recovered = [r for r in fallback if final_status(r) == FINAL_ANSWERED]

    # ---- raw metrics ----
    raw_ran = [r for r in records if _exec(r).get("raw_ran")]
    rerank_used = [r for r in records if _exec(r).get("reranker_used")]
    raw_sufficient = [r for r in raw_ran if _evidence(r).get("sufficient")]
    raw_answered = [r for r in raw_ran if final_status(r) == FINAL_ANSWERED]
    raw_km = [r for r in raw_ran if final_status(r) == FINAL_KNOWLEDGE_MISSING]

    # ---- evidence ----
    window_counts = [int(_evidence(r).get("window_count") or 0) for r in records]
    with_windows = [c for c in window_counts if c > 0]
    single_window = sum(1 for c in with_windows if c == 1)
    multi_window = sum(1 for c in with_windows if c >= 2)
    chars_per_query = []
    chars_per_window = []
    for r in records:
        wins = r.get("evidence_windows") or []
        if not wins:
            continue
        qchars = sum(len(str(w.get("text") or "")) for w in wins)
        chars_per_query.append(qchars)
        chars_per_window.extend(len(str(w.get("text") or "")) for w in wins)

    # ---- failure taxonomy breakdown ----
    failures: dict[str, int] = {}
    for r in km:
        f = classify_failure(r) or "KNOWLEDGE_MISSING"
        failures[f] = failures.get(f, 0) + 1
    top_failures = sorted(
        ({"type": t, "count": c, "rate": _rate(c, total),
          "examples": [r["query_id"] for r in km if (classify_failure(r) or "KNOWLEDGE_MISSING") == t][:3]}
         for t, c in failures.items()),
        key=lambda x: x["count"], reverse=True,
    )

    # ---- gap signals ----
    gap_counts: dict[str, int] = {}
    for r in records:
        s = classify_gap_signal(r)
        gap_counts[s] = gap_counts.get(s, 0) + 1
    retrieval_gap_ids = [r["query_id"] for r in records if classify_gap_signal(r) == GAP_SIGNAL_RETRIEVAL]

    # ---- expected vs actual (对照，不作为 ground truth) ----
    exp_true = [r for r in records if _norm_bool(r.get("expected_answerable")) is True]
    exp_false = [r for r in records if _norm_bool(r.get("expected_answerable")) is False]

    def _by_group(group: list[dict]) -> dict:
        return {
            "count": len(group),
            "answered": sum(1 for r in group if final_status(r) == FINAL_ANSWERED),
            "knowledge_missing": sum(1 for r in group if final_status(r) == FINAL_KNOWLEDGE_MISSING),
            "system_error": sum(1 for r in group if final_status(r) == FINAL_SYSTEM_ERROR),
        }

    return {
        "query_count": total,
        "sample_too_small": small,
        "sample_note": "样本数 < 20，趋势与百分位仅作参考" if small else None,
        "overall": {
            "answered": n_answered,
            "answer_coverage": _rate(n_answered, total),
            "knowledge_missing": n_km,
            "knowledge_missing_rate": _rate(n_km, total),
            "system_error": n_err,
            "system_error_rate": _rate(n_err, total),
            "expected_answerable_true": _by_group(exp_true),
            "expected_answerable_false": _by_group(exp_false),
            "expected_not_labeled": sum(1 for r in records if _norm_bool(r.get("expected_answerable")) is None),
        },
        "wiki": {
            "wiki_first_count": len(wiki_first),
            "wiki_first_rate": _rate(len(wiki_first), total),
            "wiki_hit_count": len(gate_pass),
            "wiki_hit_rate": _rate(len(gate_pass), total),
            "wiki_gate_pass_rate": _rate(len(gate_pass), len(wiki_first)),
            "wiki_answer_count": len(wiki_answered),
            "wiki_answer_rate": _rate(len(wiki_answered), total),
            "wiki_fallback_count": len(fallback),
            "wiki_fallback_rate": _rate(len(fallback), total),
            "wiki_fallback_recovered": len(fallback_recovered),
            "wiki_fallback_recovery_rate": _rate(len(fallback_recovered), len(fallback)),
            "wiki_fallback_not_recovered": len(fallback) - len(fallback_recovered),
        },
        "raw": {
            "raw_query_count": len(raw_ran),
            "raw_query_rate": _rate(len(raw_ran), total),
            "reranker_used_count": len(rerank_used),
            "reranker_used_rate": _rate(len(rerank_used), total),
            "raw_evidence_sufficient_count": len(raw_sufficient),
            "raw_evidence_sufficient_rate": _rate(len(raw_sufficient), len(raw_ran)),
            "raw_answer_count": len(raw_answered),
            "raw_answer_rate": _rate(len(raw_answered), len(raw_ran)),
            "raw_knowledge_missing_count": len(raw_km),
            "raw_knowledge_missing_rate": _rate(len(raw_km), len(raw_ran)),
        },
        "fail_closed": {
            "knowledge_missing_total": n_km,
            "breakdown": failures,
            "top_failures": top_failures,
            "judge_rejected_count": sum(
                1 for r in km if (_judge(r).get("executed") and _judge(r).get("result") == "insufficient")
            ),
            "evidence_insufficient_count": sum(
                1 for r in km
                if not (_judge(r).get("executed") and _judge(r).get("result") == "insufficient")
            ),
        },
        "evidence": {
            "avg_window_count": _mean([float(c) for c in with_windows]),
            "single_window_count": single_window,
            "single_window_rate": _rate(single_window, len(with_windows)),
            "multi_window_count": multi_window,
            "multi_window_rate": _rate(multi_window, len(with_windows)),
            "avg_evidence_chars_per_query": _mean([float(c) for c in chars_per_query]),
            "avg_evidence_chars_per_window": _mean([float(c) for c in chars_per_window]),
        },
        "latency": {
            "total_ms": _quantiles([r.get("metrics", {}).get("total_ms") for r in records]),
            "retrieval_ms": _quantiles([r.get("metrics", {}).get("retrieval_ms") for r in records]),
            "rerank_ms": _quantiles([r.get("metrics", {}).get("rerank_ms") for r in records]),
            "judge_ms": _quantiles([r.get("metrics", {}).get("judge_ms") for r in records]),
            "answer_ms": _quantiles([r.get("metrics", {}).get("answer_ms") for r in records]),
            "mean_total_ms": _mean([float(r.get("metrics", {}).get("total_ms")) for r in records if r.get("metrics", {}).get("total_ms") is not None]),
            "cold_warm": {
                "warmup_count": int((meta or {}).get("warmup_count") or 0),
                "warmup_total_ms": (meta or {}).get("warmup_total_ms"),
                "first_recorded_query_total_ms": records[0].get("metrics", {}).get("total_ms") if records else None,
            },
        },
        "by_domain": _group_breakdown(records, "category"),
        "by_query_type": _group_breakdown(records, "query_type"),
        "gap_signals": {
            "answered": gap_counts.get(GAP_SIGNAL_ANSWERED, 0),
            "likely_knowledge_gap": gap_counts.get(GAP_SIGNAL_KNOWLEDGE, 0),
            "evidence_gap": gap_counts.get(GAP_SIGNAL_EVIDENCE, 0),
            "retrieval_gap": gap_counts.get(GAP_SIGNAL_RETRIEVAL, 0),
            "system_error": gap_counts.get(GAP_SIGNAL_SYSTEM, 0),
            "retrieval_gap_needs_manual_confirmation": retrieval_gap_ids,
        },
        "golden": _golden_metrics(records),
        "records_summary": [
            {
                "query_id": r.get("query_id"),
                "query": r.get("query"),
                "category": r.get("category"),
                "query_type": r.get("query_type"),
                "expected_answerable": r.get("expected_answerable"),
                "final": final_status(r),
                "failure": classify_failure(r),
                "gap_signal": classify_gap_signal(r),
                "latency_ms": r.get("metrics", {}).get("total_ms"),
            }
            for r in records
        ],
    }


def _group_breakdown(records: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r.get(key) or "unknown", []).append(r)
    out = {}
    for name, group in sorted(groups.items()):
        n = len(group)
        out[name] = {
            "count": n,
            "answered": sum(1 for r in group if final_status(r) == FINAL_ANSWERED),
            "answer_coverage": _rate(sum(1 for r in group if final_status(r) == FINAL_ANSWERED), n),
            "knowledge_missing": sum(1 for r in group if final_status(r) == FINAL_KNOWLEDGE_MISSING),
            "knowledge_missing_rate": _rate(sum(1 for r in group if final_status(r) == FINAL_KNOWLEDGE_MISSING), n),
            "system_error": sum(1 for r in group if final_status(r) == FINAL_SYSTEM_ERROR),
        }
    return out


def _golden_metrics(records: list[dict]) -> dict:
    """Golden-set stats from records that carry manual_review (never fabricated)."""
    golden = [r for r in records if r.get("manual_review") is not None]
    n = len(golden)
    reviewed = [r for r in golden if (r.get("manual_review") or {}).get("answer_correct") is not None]
    correct = [r for r in reviewed if (r.get("manual_review") or {}).get("answer_correct") is True]
    return {
        "matched_count": n,
        "manual_reviewed_count": len(reviewed),
        "answer_correct_count": len(correct),
        "answer_correct_rate": _rate(len(correct), len(reviewed)),
        "note": "人工标注为 null/unknown 时不计入正确率；无人工标注时全部为 unknown",
    }


# ---------------------------------------------------------------- report


def build_report(records: list[dict], meta: dict | None = None) -> dict:
    """Full structured report: meta + aggregated metrics + per-record summary."""
    return {
        "meta": meta or {},
        "metrics": aggregate_metrics(records, meta),
        "run_id": (meta or {}).get("run_id"),
        "generated_at": (meta or {}).get("generated_at"),
    }


def _pct_line(value, suffix="%"):
    return f"{value}{suffix}" if value is not None else "N/A"


def _quant_line(q: dict, unit="ms") -> str:
    if not q:
        return "N/A"
    return " / ".join(f"P{k.replace('p', '')}={v}{unit}" for k, v in sorted(q.items()))


def render_markdown(report: dict) -> str:
    m = report.get("metrics") or {}
    meta = report.get("meta") or {}
    L: list[str] = []
    L.append("# RAG Evaluation Report")
    L.append("")
    L.append(f"- run_id：`{meta.get('run_id', '')}`")
    L.append(f"- generated_at：`{meta.get('generated_at', '')}`")
    L.append(f"- benchmark_version：`{meta.get('benchmark_version', '')}`")
    if meta.get("mode"):
        L.append(f"- mode：`{meta['mode']}`")
    if meta.get("model_config"):
        import json as _json
        L.append(f"- model_config：`{_json.dumps(meta['model_config'], ensure_ascii=False)}`")
    L.append("")

    # Dataset
    L.append("## Dataset")
    L.append("")
    L.append(f"- Total Queries：{m.get('query_count', 0)}")
    if m.get("sample_too_small"):
        L.append(f"- ⚠ {m.get('sample_note')}")
    L.append("")

    # Overall
    ov = m.get("overall") or {}
    L.append("## Overall")
    L.append("")
    L.append(f"- Answer Coverage：{_pct_line(ov.get('answer_coverage'))}（{ov.get('answered')} / {m.get('query_count', 0)}）")
    L.append(f"- Knowledge Missing Rate：{_pct_line(ov.get('knowledge_missing_rate'))}（{ov.get('knowledge_missing')}）")
    L.append(f"- System Error Rate：{_pct_line(ov.get('system_error_rate'))}（{ov.get('system_error')}）")
    et = ov.get("expected_answerable_true") or {}
    L.append(f"- 预期可回答（expected=true）命中：{et.get('answered', 0)} / {et.get('count', 0)}"
             f"（对照，非 ground truth）")
    L.append("")

    # Wiki
    wk = m.get("wiki") or {}
    L.append("## Wiki-First")
    L.append("")
    L.append(f"- Wiki Hit Rate：{_pct_line(wk.get('wiki_hit_rate'))}")
    L.append(f"- Wiki Gate Pass Rate：{_pct_line(wk.get('wiki_gate_pass_rate'))}")
    L.append(f"- Wiki Answer Rate：{_pct_line(wk.get('wiki_answer_rate'))}（{wk.get('wiki_answer_count', 0)}）")
    L.append(f"- Wiki Fallback Rate：{_pct_line(wk.get('wiki_fallback_rate'))}（{wk.get('wiki_fallback_count', 0)}）")
    L.append(f"- Fallback Recovery Rate：{_pct_line(wk.get('wiki_fallback_recovery_rate'))}"
             f"（{wk.get('wiki_fallback_recovered', 0)} / {wk.get('wiki_fallback_count', 0)}）")
    L.append(f"- Fallback 未救回：{wk.get('wiki_fallback_not_recovered', 0)}")
    L.append("")

    # RAW
    rw = m.get("raw") or {}
    L.append("## RAW Retrieval")
    L.append("")
    L.append(f"- RAW Query Rate：{_pct_line(rw.get('raw_query_rate'))}（{rw.get('raw_query_count', 0)}）")
    L.append(f"- Reranker Used Rate：{_pct_line(rw.get('reranker_used_rate'))}")
    L.append(f"- RAW Evidence Sufficient Rate：{_pct_line(rw.get('raw_evidence_sufficient_rate'))}")
    L.append(f"- RAW Answer Rate：{_pct_line(rw.get('raw_answer_rate'))}（{rw.get('raw_answer_count', 0)}）")
    L.append(f"- RAW Knowledge Missing Rate：{_pct_line(rw.get('raw_knowledge_missing_rate'))}")
    L.append("")

    # Fail-closed
    fc = m.get("fail_closed") or {}
    L.append("## Fail-Closed")
    L.append("")
    L.append(f"- Knowledge Missing Total：{fc.get('knowledge_missing_total', 0)}")
    L.append("- Knowledge Missing Breakdown：")
    if fc.get("breakdown"):
        for t, c in sorted(fc["breakdown"].items(), key=lambda x: -x[1]):
            L.append(f"  - {t}：{c}（{_pct_line(_rate(c, m.get('query_count', 0)))}）")
    else:
        L.append("  - 无")
    L.append(f"- Judge Rejected：{fc.get('judge_rejected_count', 0)}")
    L.append(f"- Evidence Insufficient（非 Judge 拒绝）：{fc.get('evidence_insufficient_count', 0)}")
    L.append("")

    # Evidence
    ev = m.get("evidence") or {}
    L.append("## Evidence")
    L.append("")
    L.append(f"- Avg Window Count：{ev.get('avg_window_count', 'N/A')}")
    L.append(f"- Single Window Rate：{_pct_line(ev.get('single_window_rate'))}")
    L.append(f"- Multi Window Rate：{_pct_line(ev.get('multi_window_rate'))}")
    L.append(f"- Avg Evidence Chars / Query：{ev.get('avg_evidence_chars_per_query', 'N/A')}")
    L.append(f"- Avg Evidence Chars / Window：{ev.get('avg_evidence_chars_per_window', 'N/A')}")
    L.append("")

    # Latency
    lt = m.get("latency") or {}
    L.append("## Latency")
    L.append("")
    L.append(f"- Total：{_quant_line(lt.get('total_ms') or {})}")
    L.append(f"- Retrieval：{_quant_line(lt.get('retrieval_ms') or {})}")
    L.append(f"- Rerank：{_quant_line(lt.get('rerank_ms') or {})}")
    L.append(f"- Judge：{_quant_line(lt.get('judge_ms') or {})}")
    if lt.get("answer_ms"):
        L.append(f"- Answer Generation：{_quant_line(lt['answer_ms'])}")
    cw = lt.get("cold_warm") or {}
    if cw.get("warmup_count"):
        L.append(f"- Warmup Queries：{cw.get('warmup_count')}（不计入指标）")
    if cw.get("warmup_total_ms") is not None:
        L.append(f"- Warmup 总耗时（含模型加载）：{cw.get('warmup_total_ms')}ms")
    if cw.get("first_recorded_query_total_ms") is not None:
        L.append(f"- 首个记录查询 total_ms（warm 后）：{cw.get('first_recorded_query_total_ms')}ms")
    L.append("")

    # By domain / query type
    L.append("## By Domain")
    L.append("")
    L.append("| Domain | Count | Answered | Coverage | KM | KM Rate |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for name, d in (m.get("by_domain") or {}).items():
        L.append(f"| {name} | {d['count']} | {d['answered']} | {_pct_line(d['answer_coverage'])} | "
                 f"{d['knowledge_missing']} | {_pct_line(d['knowledge_missing_rate'])} |")
    L.append("")
    L.append("## By Query Type")
    L.append("")
    L.append("| Type | Count | Answered | Coverage | KM | KM Rate |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for name, d in (m.get("by_query_type") or {}).items():
        L.append(f"| {name} | {d['count']} | {d['answered']} | {_pct_line(d['answer_coverage'])} | "
                 f"{d['knowledge_missing']} | {_pct_line(d['knowledge_missing_rate'])} |")
    L.append("")

    # Golden
    gd = m.get("golden") or {}
    L.append("## Golden Set")
    L.append("")
    L.append(f"- Golden 匹配记录：{gd.get('matched_count', 0)}")
    L.append(f"- 已人工核对：{gd.get('manual_reviewed_count', 0)}")
    if gd.get("manual_reviewed_count"):
        L.append(f"- Answer Correct：{_pct_line(gd.get('answer_correct_rate'))}（{gd.get('answer_correct_count', 0)}）")
    else:
        L.append("- 尚无人工标注（answer_correct / evidence_supported 均为 null/unknown，不编造质量标签）。")
    L.append("")

    # Failure analysis
    L.append("## Failure Analysis")
    L.append("")
    L.append("### Top Failure Reasons")
    L.append("")
    tf = fc.get("top_failures") or []
    if not tf:
        L.append("- 无失败（所有查询已回答或非知识缺失）。")
    for f in tf:
        L.append(f"- {f['type']}：{f['count']}（{_pct_line(f['rate'])}）示例：{', '.join(f['examples'])}")
    L.append("")

    # Knowledge gaps
    gs = m.get("gap_signals") or {}
    L.append("## Knowledge Gap Signals")
    L.append("")
    L.append(f"- Likely Knowledge Gap：{gs.get('likely_knowledge_gap', 0)}")
    L.append(f"- Evidence Gap（有候选但证据不足）：{gs.get('evidence_gap', 0)}")
    L.append(f"- Retrieval Gap（预期有资料但检索未命中，需人工确认）：{gs.get('retrieval_gap', 0)}")
    rg_ids = gs.get("retrieval_gap_needs_manual_confirmation") or []
    if rg_ids:
        L.append(f"  - 待人工确认：{', '.join(rg_ids)}")
    L.append("")

    # Recommendations (measurement-only; no parameter changes)
    L.append("## Recommendations")
    L.append("")
    L.append("- 本阶段只建立测量基线，不修改任何 RAG 参数/算法。")
    L.append("- 若后续要治理：优先处理 Top Failure 与 Retrieval Gap 对应的知识面。")
    L.append("")
    return "\n".join(L)
