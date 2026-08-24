"""System Profile generator / freshness check (Knowledge OS).

Lightweight: stable sections are hand-maintained; only the frontmatter metadata
(source_commit / source_tag / generated_at) and the DYNAMIC block are machine
refreshed. Never rewrites the whole document.

Usage:
  python system_profile_generator.py --check   -> STALE / CURRENT (source_commit vs git HEAD)
  python system_profile_generator.py --update  -> refresh metadata + dynamic block
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
PROFILE = VAULT / "90_System" / "system_profile.md"
DYNAMIC_START = "<!-- DYNAMIC-START -->"
DYNAMIC_END = "<!-- DYNAMIC-END -->"


def _run(cmd, cwd=None, timeout=120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _head() -> str:
    code, out = _run(["git", "-C", str(VAULT), "rev-parse", "HEAD"])
    return out.strip() if code == 0 else "UNKNOWN"


def _tag() -> str:
    code, out = _run(["git", "-C", str(VAULT), "tag", "--list"])
    tags = [t for t in out.splitlines() if t.startswith("baseline/")]
    return tags[0] if tags else ""


def _parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm


def _dynamic_block() -> str:
    head = _head()
    tag = _tag()
    lines = [DYNAMIC_START, "## 附：自动刷新动态字段（由 system_profile_generator.py --update 覆盖此区块）", ""]
    lines.append(f"- source_commit: `{head}`")
    lines.append(f"- source_tag: `{tag}`")
    lines.append(f"- generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # baseline
    bl = VAULT / "40_Outputs" / "RAG Evaluation" / "baseline.json"
    if bl.is_file():
        try:
            d = json.loads(bl.read_text(encoding="utf-8"))
            lines.append(f"- rag_baseline: `{d.get('baseline_id')}` coverage={d.get('coverage')}% status={d.get('status')}")
        except Exception:
            lines.append("- rag_baseline: UNKNOWN (parse failed)")
    # bootstrap state
    bs = VAULT / "90_System" / "scripts" / ".bootstrap_state.json"
    if bs.is_file():
        try:
            st = json.loads(bs.read_text(encoding="utf-8-sig"))
            r = st.get("results", {})
            ok = all(bool(v) if not isinstance(v, list) else all(v) for v in r.values()) if r else None
            lines.append(f"- bootstrap_state: {'BOOTSTRAP READY' if ok else 'INCOMPLETE'} (mode={st.get('bootstrap', {}).get('mode')})")
        except Exception:
            lines.append("- bootstrap_state: UNKNOWN")
    # rag health summary
    code, out = _run([sys.executable, str(VAULT / "90_System" / "rag" / "scripts" / "rag_health_check.py")], timeout=300)
    m = re.search(r"RAG_HEALTH_SUMMARY (ERROR=\d+ WARNING=\d+ PASS=\d+ INFO=\d+)", out)
    lines.append(f"- rag_health: {m.group(1) if m else 'ERROR'}")
    # wiki counts
    wc = {"draft": 0, "reviewed": 0, "stable": 0, "unknown": 0}
    for p in (VAULT / "20_Wiki").rglob("*.md"):
        try:
            t = p.read_text(encoding="utf-8")
            m = re.search(r"^status:\s*(\w+)", t, re.M)
            k = m.group(1) if m else "unknown"
            wc[k] = wc.get(k, 0) + 1
        except Exception:
            pass
    lines.append("- wiki: " + ", ".join(f"{k}={v}" for k, v in wc.items()))
    lines.append(DYNAMIC_END)
    return "\n".join(lines)


def check() -> str:
    text = PROFILE.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    src = fm.get("source_commit", "").strip("`")
    head = _head()
    if not src or src == "UNKNOWN":
        return "PROFILE-UNREADABLE"
    return "CURRENT" if src == head else "STALE"


def update() -> str:
    text = PROFILE.read_text(encoding="utf-8")
    head = _head()
    tag = _tag()
    now = datetime.now().strftime("%Y-%m-%d")
    # refresh frontmatter fields
    def _set(key, value):
        nonlocal text
        text = re.sub(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
    _set("generated_at", now)
    _set("source_commit", head)
    _set("source_tag", tag or "none")
    # refresh dynamic block
    if DYNAMIC_START in text and DYNAMIC_END in text:
        text = re.sub(re.escape(DYNAMIC_START) + r".*?" + re.escape(DYNAMIC_END),
                      lambda _: _dynamic_block(), text, flags=re.S)
    PROFILE.write_text(text, encoding="utf-8", newline="\n")
    return f"UPDATED (source_commit={head})"


def main() -> int:
    ap = argparse.ArgumentParser(description="System Profile generator / freshness check")
    ap.add_argument("--check", action="store_true", help="print STALE/CURRENT")
    ap.add_argument("--update", action="store_true", help="refresh metadata + dynamic block")
    args = ap.parse_args()
    if args.update:
        print(update())
    else:
        print(check())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
