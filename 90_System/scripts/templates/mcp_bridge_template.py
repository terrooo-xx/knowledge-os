# Knowledge OS MCP bridge - generated from template by bootstrap.ps1 (machine-local)
# Adapted by bootstrap: __PYTHON__ = python interpreter, __VAULT_ROOT__ = vault root.
# Do NOT edit this generated file on a new machine; re-run bootstrap instead.
import json
import os
import subprocess
import sys
import threading
import winreg

TRACE_FILE = os.path.join(os.path.expanduser("~"), "Documents", "Codex", "kos_bridge_trace.log")

def trace(msg):
    try:
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

SERVER = [
    r"__PYTHON__",
    os.path.join(r"__VAULT_ROOT__", "90_System", "rag", "interface", "mcp_server.py"),
]

def _key_present(d):
    k = d.get("DEEPSEEK_API_KEY")
    return "ABSENT" if not k else "PRESENT len=%d" % len(k)

def load_user_env():
    """Read the Windows User Environment (HKCU\\Environment) so the server child
    receives user-level variables that Codex strips from MCP child processes."""
    out = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                if isinstance(value, str):
                    out[name] = value
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass
    return out

env = dict(os.environ)
for _k, _v in load_user_env().items():
    if _k not in env or env[_k] in ("", None):
        env[_k] = _v
env.setdefault("KNOWLEDGE_OS_VAULT", r"__VAULT_ROOT__")
env["HF_HUB_OFFLINE"] = "1"
env["TRANSFORMERS_OFFLINE"] = "1"
trace("BRIDGE process env DEEPSEEK_API_KEY=" + _key_present(os.environ))
trace("BRIDGE server env DEEPSEEK_API_KEY=" + _key_present(env))

proc = subprocess.Popen(
    SERVER, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
)

def read_cl(stream):
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii", errors="ignore").strip()
        if ":" in text:
            k, _, v = text.partition(":")
            headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length", 0) or 0)
    return stream.read(length)

def write_cl(msg_bytes):
    try:
        obj = json.loads(msg_bytes)
        m = obj.get("method")
        extra = ""
        if m == "tools/call":
            p = obj.get("params") or {}
            extra = " NAME=%r ARGS=%s" % (p.get("name"), json.dumps(p.get("arguments") or {}, ensure_ascii=False)[:200])
        trace("-> server id=%s method=%s%s" % (obj.get("id"), m, extra))
    except Exception:
        trace("-> server (unparsable)")
    proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(msg_bytes) + msg_bytes)
    proc.stdin.flush()

def prepare_out(obj):
    if isinstance(obj, dict) and isinstance(obj.get("result"), dict) and isinstance(obj["result"].get("tools"), list):
        for t in obj["result"]["tools"]:
            if isinstance(t, dict) and t.get("name") == "knowledge_search":
                t["description"] = ("Search the user's personal Knowledge OS for reliable engineering knowledge. "
                                    "Read-only; returns structured evidence with source file paths. Call this for established "
                                    "technical knowledge (STM32, FreeRTOS, DMA, CAN, UART, SPI, PID, sensors, motor control, "
                                    "flight controller, robotics).")
                t["inputSchema"] = {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "the query"},
                        "mode": {"type": "string", "enum": ["fast", "deep", "evidence_only"], "description": "optional"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "description": "optional"}
                    },
                    "required": ["query"]
                }
    return obj

def write_ndjson(obj):
    obj = prepare_out(obj)
    extra = ""
    if obj.get("error"):
        extra = " ERROR=" + json.dumps(obj.get("error"), ensure_ascii=False)[:300]
    trace("<- server id=%s method=%s len=%d%s" % (obj.get("id"), obj.get("method"), len(json.dumps(obj, ensure_ascii=False)), extra))
    sys.stdout.buffer.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()

def forward_in():
    try:
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception:
                trace("!! unparsable NDJSON from codex: %r" % line[:120])
                continue
            trace("<-- codex id=%s method=%s" % (msg.get("id"), msg.get("method")))
            write_cl(json.dumps(msg).encode("utf-8"))
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass

def forward_out():
    try:
        while True:
            body = read_cl(proc.stdout)
            if body is None:
                break
            try:
                obj = json.loads(body.decode("utf-8"))
            except Exception:
                trace("!! unparsable CL from server: %r" % body[:120])
                continue
            write_ndjson(obj)
    finally:
        pass

t1 = threading.Thread(target=forward_in, daemon=True)
t2 = threading.Thread(target=forward_out, daemon=True)
t1.start()
t2.start()
t1.join()
proc.wait()
