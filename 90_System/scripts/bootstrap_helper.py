"""Knowledge OS Bootstrap helper (Gate 3).

Pure Python helpers used by bootstrap.ps1. Every subcommand prints one JSON
object (machine-parseable). Read-only checks never modify the system; only
explicit subcommands (create-venv / install-deps / write-config-local /
rebuild-index / write-state) perform changes.

Design goals:
  - discover Python (venv -> py launcher -> python on PATH)
  - create/verify an isolated venv at <vault>/90_System/.venv
  - detect BGE embedding / reranker models (HF hub cache + ModelScope cache)
  - write machine-local config.local.yaml (reranker path override)
  - check / rebuild the RAG index
  - check DEEPSEEK_API_KEY presence (never prints its value)
  - verify RAG baseline (coverage vs official baseline)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]          # <vault>/90_System/scripts -> <vault>
RAG_DIR = VAULT_ROOT / "90_System" / "rag"
STATE_PATH = Path(__file__).resolve().parent / ".bootstrap_state.json"

OFFICIAL_BASELINE = {
    "baseline_id": "bl-eval-20260817T162956",
    "coverage": 89.3,
    "status": "STABLE",
}

MODELS = {
    "embedding": {
        "name": "BAAI/bge-small-zh-v1.5",
        "hf_dir": Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub" / "models--BAAI--bge-small-zh-v1.5",
        "weight_files": ("model.safetensors",),
    },
    "reranker": {
        "name": "BAAI/bge-reranker-v2-m3",
        "hf_dir": Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub" / "models--BAAI--bge-reranker-v2-m3",
        "modelscope_dir": Path(os.environ.get("MODELSCOPE_CACHE", str(Path.home() / ".cache" / "modelscope"))) / "models" / "BAAI--bge-reranker-v2-m3",
        "weight_files": ("model.safetensors",),
    },
}


def _out(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _run(cmd, cwd=None, timeout=600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _python_candidates() -> list[str]:
    out = []
    venv = VAULT_ROOT / "90_System" / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        out.append(str(venv))
    return out


def detect_python() -> dict:
    """Find a usable Python interpreter (venv first, then py -3.14, then PATH)."""
    candidates = _python_candidates()
    # py launcher for 3.14
    for tag in ("-3.14", "-3", ""):
        candidates.append("py")
        _ = tag  # py -3.14 handled below via arg list
    candidates += ["python", "python3"]
    tried = []
    for base in _python_candidates():
        code, out = _run([base, "-c", "import sys; print(sys.version.split()[0])"])
        tried.append(base)
        if code == 0:
            return {"ok": True, "python": base, "version": out.strip(), "source": "venv", "executable": base}
    # py launcher: try with explicit -3.14 then bare
    for args in (["py", "-3.14"], ["py", "-3"], ["py"]):
        code, out = _run(args + ["-c", "import sys; print(sys.version.split()[0])"])
        tried.append(" ".join(args))
        if code == 0:
            code2, exe = _run(args + ["-c", "import sys; print(sys.executable)"])
            return {"ok": True, "python": args[0], "version": out.strip(),
                    "source": "py-launcher", "args": args[1:],
                    "executable": exe.strip() if code2 == 0 else args[0]}
    for name in ("python", "python3"):
        code, out = _run([name, "-c", "import sys; print(sys.version.split()[0])"])
        tried.append(name)
        if code == 0:
            code2, exe = _run([name, "-c", "import sys; print(sys.executable)"])
            return {"ok": True, "python": name, "version": out.strip(),
                    "source": "path", "executable": exe.strip() if code2 == 0 else name}
    return {"ok": False, "tried": tried}


def _pycmd(python: str, args: list[str]) -> list[str]:
    if python == "py":
        return ["py", "-3.14"] + args
    return [python] + args


def check_deps(python: str) -> dict:
    imports = ["yaml", "pypdf", "trafilatura", "openai", "torch", "sentence_transformers"]
    missing = []
    code, out = _run(_pycmd(python, ["-c",
        "; ".join(f"import {m}" for m in imports) + "; print('OK')"]))
    if code == 0 and "OK" in out:
        return {"ok": True, "missing": [], "detail": out.strip()[-200:]}
    # per-module check to report which are missing
    for m in imports:
        c, o = _run(_pycmd(python, ["-c", f"import {m}"]))
        if c != 0:
            missing.append(m)
    return {"ok": len(missing) == 0, "missing": missing}


def create_venv(python: str) -> dict:
    venv = VAULT_ROOT / "90_System" / ".venv"
    if (venv / "Scripts" / "python.exe").is_file():
        return {"ok": True, "venv": str(venv / "Scripts" / "python.exe"), "created": False}
    code, out = _run(_pycmd(python, ["-m", "venv", str(venv)]), timeout=300)
    if code != 0:
        return {"ok": False, "error": out[-500:]}
    return {"ok": True, "venv": str(venv / "Scripts" / "python.exe"), "created": True}


def install_deps(python: str) -> dict:
    lock = RAG_DIR / "requirements-lock.txt"
    req = RAG_DIR / "requirements.txt"
    target = lock if lock.is_file() else req
    code, out = _run(_pycmd(python, ["-m", "pip", "install", "-r", str(target), "--disable-pip-version-check"]),
                     timeout=1800)
    return {"ok": code == 0, "used": str(target.relative_to(VAULT_ROOT)), "error": out[-500:] if code else None}


def _hf_snapshot_dir(model_dir: Path) -> Path | None:
    snap = model_dir / "snapshots"
    if not snap.is_dir():
        return None
    subs = [d for d in snap.iterdir() if d.is_dir()]
    return subs[0] if subs else None


def _model_complete(model_dir: Path, weight_files) -> bool:
    d = _hf_snapshot_dir(model_dir)
    if d is None:
        return False
    return all((d / wf).is_file() for wf in weight_files)


def detect_models() -> dict:
    res = {}
    emb = MODELS["embedding"]
    emb_dir = _hf_snapshot_dir(emb["hf_dir"])
    res["embedding"] = {
        "name": emb["name"],
        "found": emb_dir is not None,
        "complete": _model_complete(emb["hf_dir"], emb["weight_files"]),
        "path": str(emb_dir) if emb_dir else None,
    }
    rr = MODELS["reranker"]
    ms_dir = None
    snap = rr["modelscope_dir"] / "snapshots"
    if snap.is_dir():
        for rev in [d for d in snap.iterdir() if d.is_dir()]:
            if (rev / "model.safetensors").is_file():
                ms_dir = rev
                break
    if ms_dir is None and rr["modelscope_dir"].is_dir():
        # fallback: any direct subdir containing weights
        for s in [d for d in rr["modelscope_dir"].iterdir() if d.is_dir()]:
            if (s / "model.safetensors").is_file():
                ms_dir = s
                break
    hf_rr = _hf_snapshot_dir(rr["hf_dir"])
    hf_rr_complete = _model_complete(rr["hf_dir"], rr["weight_files"])
    res["reranker"] = {
        "name": rr["name"],
        "hf_found": hf_rr is not None,
        "hf_complete": hf_rr_complete,
        "modelscope_found": ms_dir is not None,
        "modelscope_path": str(ms_dir) if ms_dir else None,
    }
    ok = bool(res["embedding"]["complete"] and (res["reranker"]["modelscope_found"] or res["reranker"]["hf_complete"]))
    res["ok"] = ok
    if not ok:
        res["error"] = "embedding or reranker model incomplete; run bootstrap with models available (online download) "
    return res


def write_config_local(reranker_path: str | None) -> dict:
    local = RAG_DIR / "config.local.yaml"
    if not reranker_path:
        return {"ok": False, "error": "no reranker path provided"}
    # forward slashes keep the YAML readable and avoid \U / \s escape issues
    portable = str(reranker_path).replace("\\", "/")
    body = ("# 本机覆盖配置（由 bootstrap.ps1 生成，勿提交、勿复制到其他机器）\n"
            "# 优先级高于 config.yaml；如需还原为可移植默认，删除本文件即可。\n"
            "reranker:\n"
            f'  model: "{portable}"\n')
    local.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(local.relative_to(VAULT_ROOT)), "reranker": reranker_path}


def _index_ok() -> dict:
    rec = RAG_DIR / "database" / "main_vector_db" / "records.jsonl"
    if not rec.is_file():
        return {"ok": False, "records": 0}
    n = sum(1 for _ in rec.open(encoding="utf-8") if _.strip())
    return {"ok": n > 0, "records": n}


def check_index() -> dict:
    st = _index_ok()
    code, out = _run([sys.executable, str(RAG_DIR / "scripts" / "rag_health_check.py")], timeout=300)
    m = re.search(r"RAG_HEALTH_SUMMARY (ERROR=\d+ WARNING=\d+ PASS=\d+ INFO=\d+)", out)
    return {"ok": st["ok"] and code == 0 and m and "ERROR=0" in m.group(1),
            "records": st["records"], "summary": m.group(1) if m else (out or "no output")[-200:]}


def rebuild_index(python: str) -> dict:
    code, out = _run(_pycmd(python, [str(RAG_DIR / "scripts" / "update_index.py")]), timeout=1800)
    return {"ok": code == 0, "error": out[-500:] if code else None}


def check_secret() -> dict:
    present = bool(os.environ.get("DEEPSEEK_API_KEY"))
    return {"ok": present, "present": present}


def verify_baseline(python: str, limit: int | None = None) -> dict:
    cmd = _pycmd(python, [str(RAG_DIR / "scripts" / "evaluate_benchmark.py"), "--mode", "fast"])
    if limit:
        cmd += ["--limit", str(limit)]
    code, out = _run(cmd, timeout=3600)
    if code != 0:
        return {"ok": False, "error": out[-500:]}
    m = re.search(r'"answer_coverage": ([\d.]+)', out)
    if not m:
        return {"ok": False, "error": "coverage not found in output"}
    cov = float(m.group(1))
    delta = round(cov - OFFICIAL_BASELINE["coverage"], 1)
    ok = delta >= -0.1  # allow tiny negative rounding; regressions below baseline flagged
    return {"ok": ok, "coverage": cov, "baseline": OFFICIAL_BASELINE["coverage"],
            "delta_pp": delta, "baseline_id": OFFICIAL_BASELINE["baseline_id"]}


def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> dict:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(STATE_PATH.relative_to(VAULT_ROOT))}


def health_summary() -> dict:
    """Run the three existing health checks and summarize."""
    checks = {
        "architecture": (["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(VAULT_ROOT / "90_System" / "scripts" / "knowledge_os_check.ps1")]),
        "rag": ([sys.executable, str(RAG_DIR / "scripts" / "rag_health_check.py")]),
        "wiki": ([sys.executable, str(RAG_DIR / "scripts" / "wiki_health_check.py")]),
    }
    res = {}
    for name, cmd in checks.items():
        code, out = _run(cmd, timeout=300)
        res[name] = {"ok": code == 0, "exit": code,
                     "summary": (out or "").strip().splitlines()[-1] if out.strip() else "no output"}
    return {"ok": all(v["ok"] for v in res.values()), "checks": res}


def main() -> int:
    # Force UTF-8 stdout/stderr so PowerShell 5.1 (with Console.OutputEncoding=UTF8)
    # decodes JSON correctly even with non-ASCII paths.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Knowledge OS Bootstrap helper")
    ap.add_argument("cmd", choices=[
        "detect-python", "check-deps", "create-venv", "install-deps", "detect-models",
        "write-config-local", "check-index", "rebuild-index", "check-secret",
        "verify-baseline", "load-state", "save-state", "health-summary"])
    ap.add_argument("--python", default=None)
    ap.add_argument("--reranker", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--state", default=None)
    args = ap.parse_args()

    if args.cmd == "detect-python":
        _out(detect_python())
    elif args.cmd == "check-deps":
        _out(check_deps(args.python or "python"))
    elif args.cmd == "create-venv":
        _out(create_venv(args.python or "python"))
    elif args.cmd == "install-deps":
        _out(install_deps(args.python or "python"))
    elif args.cmd == "detect-models":
        _out(detect_models())
    elif args.cmd == "write-config-local":
        _out(write_config_local(args.reranker))
    elif args.cmd == "check-index":
        _out(check_index())
    elif args.cmd == "rebuild-index":
        _out(rebuild_index(args.python or "python"))
    elif args.cmd == "check-secret":
        _out(check_secret())
    elif args.cmd == "verify-baseline":
        _out(verify_baseline(args.python or "python", limit=args.limit))
    elif args.cmd == "load-state":
        _out({"state": load_state()})
    elif args.cmd == "save-state":
        _out(save_state(json.loads(args.state or "{}")))
    elif args.cmd == "health-summary":
        _out(health_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
