"""Adapter test: LLM answer works against any OpenAI-compatible endpoint."""
from __future__ import annotations

import http.server
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.llm import answer


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps(
            {"choices": [{"message": {"content": "模拟 LLM 回答"}}]}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_openai_compatible_adapter():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cfg = {
            "llm": {
                "provider": "openai_compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "mock-model",
                "api_key_env": "MOCK_LLM_KEY",
                "temperature": 0.2,
            }
        }
        os.environ["MOCK_LLM_KEY"] = "mock"
        out = answer("问题", [{"text": "上下文"}], cfg)
        assert "模拟 LLM 回答" in out
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    test_openai_compatible_adapter()
    print("PASS test_openai_compatible_adapter")