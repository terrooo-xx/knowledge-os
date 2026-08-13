"""MCP Server tests: protocol handshake, tools list/call, fail-closed (offline).

knowledge_search is mocked; no real LLM / network needed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "interface"
sys.path.insert(0, str(AGENT_DIR))

import mcp_server


def _call(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return mcp_server._handle(msg)


def test_initialize_handshake():
    r = _call("initialize", {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}})
    assert r["id"] == 1
    res = r["result"]
    assert res["protocolVersion"] == "2024-11-05"
    assert res["serverInfo"]["name"] == "knowledge-os"
    assert "tools" in res["capabilities"]


def test_tools_list_single_tool():
    r = _call("tools/list")
    tools = r["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "knowledge_search"
    assert "query" in tools[0]["inputSchema"]["properties"]
    assert "top_k" in tools[0]["inputSchema"]["properties"]
    assert tools[0]["inputSchema"]["required"] == ["query"]


def test_tools_call_answerable():
    original = mcp_server.knowledge_search
    mcp_server.knowledge_search = lambda *a, **kw: {
        "query": kw.get("query"), "status": "answerable", "answer": "测试回答",
        "evidence": [{"source": "20_Wiki/a.md", "score": 0.9}], "sufficient": True,
        "judge": {"relevance": "relevant"}, "gap": None, "source_trace": ["20_Wiki/a.md"], "reason": None}
    try:
        r = _call("tools/call", {"name": "knowledge_search", "arguments": {"query": "Q"}})
    finally:
        mcp_server.knowledge_search = original
    assert r["result"]["isError"] is False
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "answerable"


def test_tools_call_knowledge_missing_preserved():
    original = mcp_server.knowledge_search
    mcp_server.knowledge_search = lambda *a, **kw: {
        "query": kw.get("query"), "status": "knowledge_missing", "answer": None,
        "evidence": [], "sufficient": False, "judge": None, "gap": {"status": "pending"},
        "source_trace": [], "reason": "no data"}
    try:
        r = _call("tools/call", {"name": "knowledge_search", "arguments": {"query": "Q"}})
    finally:
        mcp_server.knowledge_search = original
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "knowledge_missing"
    assert text["answer"] is None


def test_tools_call_unknown_tool():
    r = _call("tools/call", {"name": "approve", "arguments": {}})
    assert "error" in r and r["error"]["code"] == -32602


def test_tools_call_fail_closed_on_exception():
    original = mcp_server.knowledge_search
    def boom(*a, **kw):
        raise RuntimeError("boom")
    mcp_server.knowledge_search = boom
    try:
        r = _call("tools/call", {"name": "knowledge_search", "arguments": {"query": "Q"}})
    finally:
        mcp_server.knowledge_search = original
    assert r["result"]["isError"] is True
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "error"
    assert text["answer"] is None


def test_ping_and_unknown_method():
    assert _call("ping")["result"] == {}
    r = _call("no_such_method")
    assert r["error"]["code"] == -32601


def test_shutdown():
    assert _call("shutdown")["result"] is None


def test_stdio_roundtrip_handshake_and_list():
    """Spawn the real server over stdio; do initialize + tools/list (offline)."""
    env = {"PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, str(AGENT_DIR / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=env, cwd=str(tempfile.gettempdir()),
    )

    def send(obj):
        data = json.dumps(obj).encode("utf-8")
        proc.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        proc.stdin.flush()

    def recv():
        headers = {}
        line = proc.stdout.readline()
        while line and line not in (b"\r\n", b"\n"):
            k, _, v = line.decode().partition(":")
            headers[k.strip().lower()] = v.strip()
            line = proc.stdout.readline()
        body = proc.stdout.read(int(headers.get("content-length", 0)))
        return json.loads(body.decode("utf-8"))

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t"}}})
        init = recv()
        assert init["result"]["serverInfo"]["name"] == "knowledge-os"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = recv()
        assert tools["result"]["tools"][0]["name"] == "knowledge_search"
        send({"jsonrpc": "2.0", "id": 3, "method": "exit"})
    finally:
        proc.kill()


if __name__ == "__main__":
    for t in (
        test_initialize_handshake, test_tools_list_single_tool,
        test_tools_call_answerable, test_tools_call_knowledge_missing_preserved,
        test_tools_call_unknown_tool, test_tools_call_fail_closed_on_exception,
        test_ping_and_unknown_method, test_shutdown, test_stdio_roundtrip_handshake_and_list,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all MCP server tests passed")