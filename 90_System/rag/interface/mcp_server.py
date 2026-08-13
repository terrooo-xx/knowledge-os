"""Minimal MCP Server exposing the Agent Knowledge Interface (READ-ONLY).

Stdio transport only, Python stdlib, no external MCP SDK / framework.
Exposes a single tool: `knowledge_search` -> knowledge_service.knowledge_search
(Retrieval -> Heuristic Evidence -> LLM Relevance Judge, fail-closed).

Vault root: env KNOWLEDGE_OS_VAULT (fallback: this file's location), never cwd.
stdout is the MCP transport: never print to stdout outside MCP frames.
"""
from __future__ import annotations

import os

# 模型已本地缓存：强制离线加载，避免 sentence-transformers 启动时联网检查 HF hub
# 而卡住（无网络环境下 WinError 10013 + 重试）。setdefault 允许外部显式覆盖。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
import sys
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))

from knowledge_service import knowledge_search  # noqa: E402

SERVER_INFO = {"name": "knowledge-os", "version": "1.0.0"}

TOOL = {
    "name": "knowledge_search",
    "description": (
        "Search the user's personal Knowledge OS (an external engineering knowledge base, NOT "
        "the current project codebase) for reliable engineering knowledge. Call this when the "
        "task involves established technical knowledge, prior engineering experience, or "
        "information that may already exist in the user's knowledge base (e.g. STM32, FreeRTOS, "
        "DMA, CAN, UART, SPI, PID, EKF, sensors, motor control, flight controller, robotics). "
        "It is read-only and returns structured evidence + judge relevance; the answer is "
        "typically synthesized by the caller from the evidence. Use mode=deep only when a full "
        "explanation is explicitly needed. If the result is `knowledge_missing`, do NOT claim "
        "the Knowledge OS contains the answer."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要查询的工程知识问题（中文/英文均可）"},
            "mode": {"type": "string", "enum": ["fast", "deep", "evidence_only"],
                     "description": "fast=默认（结构化证据，无长答案，保留 Judge）；deep=完整解释（含长答案）；evidence_only=同 fast"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 10,
                      "description": "返回的检索片段数量（可选，默认取配置）"},
        },
        "required": ["query"],
    },
}


def _read_frame() -> dict | None:
    headers: dict[str, str] = {}
    line = sys.stdin.buffer.readline()
    while line and line not in (b"\r\n", b"\n", b""):
        text = line.decode("ascii", errors="ignore").strip()
        if ":" in text:
            key, _, value = text.partition(":")
            headers[key.strip().lower()] = value.strip()
        line = sys.stdin.buffer.readline()
    if not line:
        return None
    length = int(headers.get("content-length", 0) or 0)
    body = sys.stdin.buffer.read(length)
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def _write_message(msg: dict) -> None:
    data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    head = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
    sys.stdout.buffer.write(head + data)
    sys.stdout.buffer.flush()


def _jsonrpc_error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _handle(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        client_version = params.get("protocolVersion") or "2024-11-05"
        return {
            "jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": client_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Knowledge OS 只读知识查询。用 knowledge_search 查询工程知识；"
                    "若返回 knowledge_missing，不要声称知识库包含答案。"
                ),
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name != "knowledge_search":
            return _jsonrpc_error(msg_id, -32602, f"unknown tool: {name}")
        try:
            top_k = args.get("top_k")
            mode = args.get("mode", "fast")
            if mode not in ("fast", "deep", "evidence_only"):
                mode = "fast"
            result = knowledge_search(
                str(args.get("query", "")),
                mode=mode,
                use_llm=True,
                top_k=top_k if isinstance(top_k, int) else None,
            )
            return {
                "jsonrpc": "2.0", "id": msg_id, "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0", "id": msg_id, "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "status": "error",
                        "answer": None,
                        "sufficient": False,
                        "reason": f"MCP tool call failed (fail closed): {exc}",
                    }, ensure_ascii=False)}],
                    "isError": True,
                },
            }
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"prompts": []}}
    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}
    return _jsonrpc_error(msg_id, -32601, f"method not found: {method}")


def _warmup() -> None:
    """Load the embedding model and reranker in the background (non-blocking).

    Moves the first-query cold start (~9s BGE) to MCP startup. Safe: BgeEmbedder
    and reranker use per-model locks, so a concurrent first query just waits.
    """
    try:
        from rag_engine.config import load_config, resolve_paths
        from rag_engine.embeddings import create_embedder
        from rag_engine.rerank import _get_reranker
        cfg = resolve_paths(load_config(str(Path(__file__).resolve().parent.parent / "config.yaml")), Path(__file__).resolve().parent.parent.parent.parent)
        create_embedder(cfg).embed(["Knowledge OS warmup"])
        rcfg = cfg.get("reranker", {})
        if rcfg.get("enabled") and rcfg.get("provider") in ("bge", "jina"):
            _get_reranker(rcfg["provider"], rcfg["model"])
    except Exception:
        # warmup 失败不影响 MCP 服务（首次真实查询会自行加载）
        pass


def main() -> None:
    import threading
    threading.Thread(target=_warmup, daemon=True).start()
    while True:
        msg = _read_frame()
        if msg is None:
            break
        if msg.get("method") == "exit":
            break
        reply = _handle(msg)
        if reply is not None:
            _write_message(reply)


if __name__ == "__main__":
    main()
