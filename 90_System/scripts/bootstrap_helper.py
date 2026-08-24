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
    """Run the benchmark and classify the diff vs the official baseline run with
    the official gap_diagnosis semantics (REAL_REGRESSION=0 is PASS; judge
    variance on known queries does not block)."""
    cmd = _pycmd(python, [str(RAG_DIR / "scripts" / "evaluate_benchmark.py"), "--mode", "fast"])
    if limit:
        cmd += ["--limit", str(limit)]
    code, out = _run(cmd, timeout=3600)
    if code != 0:
        return {"ok": False, "error": out[-500:]}
    m = re.search(r'"run_id":\s*"([^"]+)"', out)
    run_id = m.group(1) if m else None
    m = re.search(r'"answer_coverage": ([\d.]+)', out)
    cov = float(m.group(1)) if m else None
    delta = round(cov - OFFICIAL_BASELINE["coverage"], 1) if cov is not None else None
    real_reg = None
    judge_var = 0
    if run_id:
        try:
            if str(RAG_DIR) not in sys.path:
                sys.path.insert(0, str(RAG_DIR))
            from rag_engine.gap_diagnosis import compare_runs
            ev = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"
            base_run = ev / "runs" / "eval-20260817T162956" / "evaluation_records.jsonl"
            cur_run = ev / "runs" / run_id / "evaluation_records.jsonl"
            if base_run.is_file() and cur_run.is_file():
                def _recs(p):
                    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]
                diff = compare_runs(_recs(base_run), _recs(cur_run))
                rc = diff.get("regression_classes") or {}
                real_reg = int(rc.get("REAL_REGRESSION", 0))
                judge_var = int(rc.get("JUDGE_VARIANCE", 0))
        except Exception:
            pass
    ok = (real_reg is not None and real_reg == 0) if real_reg is not None else (delta is not None and delta >= -0.1)
    return {"ok": ok, "coverage": cov, "baseline": OFFICIAL_BASELINE["coverage"],
            "delta_pp": delta, "baseline_id": OFFICIAL_BASELINE["baseline_id"],
            "real_regressions": real_reg, "judge_variance": judge_var, "run_id": run_id}


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



# =====================================================================
# AI Runtime (Gate 3 Upgrade): Codex / CC Switch / DeepSeek / MCP
# =====================================================================

def detect_codex() -> dict:
    """Find Codex CLI (PATH, npm global, WindowsApps) and report version."""
    candidates = []
    # PATH
    for name in ("codex", "codex.cmd"):
        try:
            import shutil
            p = shutil.which(name)
            if p:
                candidates.append(p)
        except Exception:
            pass
    # npm global shim
    npm_codex = Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd"
    if npm_codex.is_file() and str(npm_codex) not in candidates:
        candidates.append(str(npm_codex))
    # WindowsApps (OpenAI.Codex)
    winapps = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps"
    if winapps.is_dir():
        for cand in winapps.glob("OpenAI.Codex*/*/codex*"):
            if cand.is_file():
                candidates.append(str(cand))
    for cand in candidates:
        code, out = _run([cand, "--version"], timeout=60)
        if code == 0:
            return {"ok": True, "version": out.strip().splitlines()[0] if out.strip() else "unknown",
                    "path": cand, "source": "detected"}
    return {"ok": False, "found_paths": candidates}


def detect_ccswitch() -> dict:
    """Find CC Switch (exe + config db) on this machine."""
    home = Path.home()
    db = home / ".cc-switch" / "cc-switch.db"
    exe_candidates = []
    # known install locations (portable)
    for p in (home / ".cc-switch" / "cc-switch.exe",
              Path("D:/sorfware/ccSwitch/cc-switch.exe"),
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cc-switch" / "cc-switch.exe",
              Path(os.environ.get("APPDATA", "")) / "cc-switch" / "cc-switch.exe"):
        if p.is_file():
            exe_candidates.append(str(p))
    # running process path via tasklist
    try:
        code, out = _run(["tasklist", "/v", "/fo", "csv", "/nh", "/fi", "IMAGENAME eq cc-switch.exe"], timeout=30)
        for line in out.splitlines():
            if "cc-switch.exe" in line.lower() and "\\" in line:
                # CSV: "cc-switch.exe","pid",...,"path"
                import csv, io
                try:
                    row = next(csv.reader(io.StringIO(line)))
                    if len(row) >= 9 and row[8] and row[8].lower().endswith("cc-switch.exe"):
                        exe_candidates.append(row[8])
                except Exception:
                    pass
    except Exception:
        pass
    exe = None
    if exe_candidates:
        exe = exe_candidates[0]
        for c in exe_candidates:
            if os.path.normcase(c) == os.path.normcase(str(Path("D:/sorfware/ccSwitch/cc-switch.exe"))):
                exe = c
                break
    db_ok = db.is_file()
    if not exe and not db_ok:
        return {"ok": False}
    return {"ok": True, "exe": exe, "config_dir": str(home / ".cc-switch"),
            "db": str(db), "db_ok": db_ok}


def _ccswitch_db():
    db = Path.home() / ".cc-switch" / "cc-switch.db"
    if not db.is_file():
        return None
    import sqlite3
    try:
        return sqlite3.connect(str(db))
    except Exception:
        return None


def ccswitch_deepseek() -> dict:
    """Read CC Switch: active Codex provider + proxy config + routing need.

    NEVER returns the API key value; only a boolean presence flag.
    """
    con = _ccswitch_db()
    if con is None:
        return {"ok": False, "error": "cc-switch db not found"}
    try:
        cur = con.cursor()
        rows = cur.execute(
            "SELECT id, name, is_current, settings_config FROM providers WHERE app_type='codex'").fetchall()
        provider = None
        for rid, name, is_cur, sc in rows:
            if is_cur == 1:
                provider = {"id": rid, "name": name}
                break
        if provider is None:
            for rid, name, is_cur, sc in rows:
                if name and "deepseek" in name.lower():
                    provider = {"id": rid, "name": name}
                    break
        res = {"ok": True, "provider": None, "proxy": None, "needs_routing": None,
               "active_codex_base_url": None, "api_key_present": False}
        if provider is not None:
            try:
                cfg = json.loads(sc)
            except Exception:
                cfg = {}
            config_text = cfg.get("config", "") or ""
            auth = cfg.get("auth", {}) or {}
            api_key_present = any(k and v for k, v in auth.items() if "key" in k.lower() or "token" in k.lower())
            base_url = None
            wire_api = None
            model = None
            m = re.search(r'base_url\s*=\s*"([^"]+)"', config_text)
            if m:
                base_url = m.group(1)
            m = re.search(r'wire_api\s*=\s*"([^"]+)"', config_text)
            if m:
                wire_api = m.group(1)
            m = re.search(r'^model\s*=\s*"([^"]+)"', config_text, re.M)
            if m:
                model = m.group(1)
            provider.update({"base_url": base_url, "wire_api": wire_api, "model": model,
                             "api_key_present": api_key_present})
            res["provider"] = provider
            res["api_key_present"] = api_key_present
        # proxy config for codex
        try:
            pr = cur.execute("SELECT proxy_enabled, listen_address, listen_port, enabled FROM proxy_config WHERE app_type='codex'").fetchone()
            if pr:
                res["proxy"] = {"enabled": bool(pr[0]), "listen": "%s:%s" % (pr[1], pr[2]), "port": pr[2]}
        except Exception:
            pass
        # needs routing: native Responses API needs no protocol conversion
        if provider and provider.get("wire_api"):
            res["needs_routing"] = str(provider["wire_api"]).lower() != "responses"
        # active codex config base_url
        cfg_toml = Path.home() / ".codex" / "config.toml"
        if cfg_toml.is_file():
            m = re.search(r'base_url\s*=\s*"([^"]+)"', cfg_toml.read_text(encoding="utf-8", errors="replace"))
            if m:
                res["active_codex_base_url"] = m.group(1)
        return res
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            con.close()
        except Exception:
            pass


def validate_deepseek_key() -> dict:
    """Validate DEEPSEEK_API_KEY against the DeepSeek API (GET /models).

    Returns ok/status only; NEVER prints or returns the key value.
    """
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return {"ok": False, "error": "DEEPSEEK_API_KEY not set in env"}
    try:
        import urllib.request
        req = urllib.request.Request("https://api.deepseek.com/models",
                                     headers={"Authorization": "Bearer %s" % key})
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": r.status == 200, "status": r.status, "http": r.status}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def ccswitch_mcp() -> dict:
    """Check whether the knowledge-os MCP server is registered+enabled for Codex in CC Switch."""
    con = _ccswitch_db()
    if con is None:
        return {"ok": False, "error": "db not found"}
    try:
        cur = con.cursor()
        row = cur.execute(
            "SELECT name, enabled_codex, server_config FROM mcp_servers WHERE name='knowledge-os'").fetchone()
        if not row:
            return {"ok": False, "error": "knowledge-os mcp not registered in CC Switch"}
        return {"ok": True, "name": row[0], "enabled_codex": bool(row[1]),
                "command": (json.loads(row[2]) or {}).get("command") if row[2] else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            con.close()
        except Exception:
            pass

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
        "verify-baseline", "load-state", "save-state", "health-summary",
        "detect-codex", "detect-ccswitch", "ccswitch-deepseek", "ccswitch-mcp", "validate-deepseek-key"])
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
    elif args.cmd == "detect-codex":
        _out(detect_codex())
    elif args.cmd == "detect-ccswitch":
        _out(detect_ccswitch())
    elif args.cmd == "ccswitch-deepseek":
        _out(ccswitch_deepseek())
    elif args.cmd == "validate-deepseek-key":
        _out(validate_deepseek_key())
    elif args.cmd == "ccswitch-mcp":
        _out(ccswitch_mcp())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
