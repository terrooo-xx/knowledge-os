"""Knowledge OS Control Center - local HTTP server (stdlib only).

Serves a single-page UI and a JSON API that calls the service layer.
Run:  python 90_System/control_center/server.py   (default port 8765)
"""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

CTRL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CTRL_DIR))

import service  # noqa: E402

STATIC = CTRL_DIR / "static"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_err(self, code, msg):
        self._send(code, {"ok": False, "message": msg})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8")
                self._send(200, html, "text/html; charset=utf-8")
                return
            if path.startswith("/api/"):
                self._route_api(path)
                return
            self._json_err(404, f"not found: {path}")
        except Exception as exc:
            self._json_err(500, f"server error: {exc}")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/api/sync":
                self._send(200, service.sync_kb())
                return
            if path == "/api/weekly_review/generate":
                self._send(200, service.generate_weekly_review())
                return
            if path == "/api/review/preflight":
                self._send(200, service.preflight_review_candidates(trigger="manual"))
                return
            if path == "/api/query/trace":
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {}
                self._send(200, service.query_trace(payload.get("query", "")))
                return
            if path == "/api/weekly_review/insight":
                self._send(200, service.generate_weekly_insight())
                return
            if path == "/api/rag/evaluation/run":
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {}
                result = service.run_evaluation(
                    limit=payload.get("limit"), mode=payload.get("mode", "fast"))
                self._send(200 if result.get("ok") else 500, result)
                return
            if path == "/api/rag/evaluation/diff":
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {}
                result = service.run_evaluation_diff(
                    before=payload.get("before", ""), after=payload.get("after", ""))
                self._send(200 if result.get("ok") else 500, result)
                return
            if path == "/api/gaps/diagnose":
                self._send(200, service.run_gap_diagnosis())
                return
            if path == "/api/rag/evaluation/verify":
                self._send(200, service.run_baseline_verification())
                return
            m = re.match(r"^/api/source_acquisition/(.+)/verify$", path)
            if m:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {}
                result = service.mark_source_verified(
                    m.group(1), actor=payload.get("actor", "user"))
                self._send(200 if result.get("ok") else 400, result)
                return
            if path.startswith("/api/actions/"):
                self._route_action(path)
                return
            self._json_err(404, f"not found: {path}")
        except Exception as exc:
            self._json_err(500, f"server error: {exc}")

    def _route_api(self, path):
        if path == "/api/dashboard":
            self._send(200, service.dashboard())
        elif path == "/api/actions":
            self._send(200, service.build_actions())
        elif path == "/api/wikis":
            self._send(200, service.list_wikis())
        elif path == "/api/gaps":
            self._send(200, service.list_gaps())
        elif path == "/api/sources":
            self._send(200, service.list_sources())
        elif path == "/api/weekly_review/dashboard":
            self._send(200, service.weekly_review_dashboard())
        elif path == "/api/weekly_review":
            self._send(200, service.weekly_review_list())
        elif path == "/api/project_status":
            self._send(200, service.project_status())
        elif path == "/api/status":
            self._send(200, service.cc_status())
        elif path == "/api/activity":
            self._send(200, service.activity_timeline())
        elif path == "/api/health":
            self._send(200, service.health())
        elif path == "/api/rag/evaluation":
            self._send(200, service.evaluation_latest())
        elif path == "/api/rag/evaluation/diff":
            self._send(200, service.evaluation_diff())
        elif path == "/api/gaps/evaluation":
            self._send(200, service.evaluation_gaps())
        elif path == "/api/source_acquisition":
            self._send(200, service.source_acquisition())
        elif path.startswith("/api/source_acquisition/"):
            source_id = path[len("/api/source_acquisition/"):]
            result = service.source_acquisition_detail(source_id)
            self._send(200 if result.get("ok") else 404, result)
        elif path == "/api/golden_set":
            self._send(200, service.golden_set())
        elif path == "/api/judge_variance":
            self._send(200, service.judge_variance())
        elif path == "/api/rag/evaluation/baseline":
            self._send(200, service.evaluation_baseline())
        elif path == "/api/rag/evaluation/governance":
            self._send(200, service.governance_state())
        elif path.startswith("/api/gaps/evaluation/"):
            gap_id = path[len("/api/gaps/evaluation/"):]
            result = service.evaluation_gap_detail(gap_id)
            self._send(200 if result.get("ok") else 404, result)
        elif path.startswith("/api/rag/evaluation/"):
            run_id = path[len("/api/rag/evaluation/"):]
            result = service.evaluation_report(run_id)
            self._send(200 if result.get("ok") else 404, result)
        elif path.startswith("/api/actions/"):
            action_id = path[len("/api/actions/"):]
            if action_id.endswith("/context"):
                ctx = service.review_context(action_id[: -len("/context")])
                if ctx.get("ok"):
                    self._send(200, ctx)
                else:
                    self._json_err(404, ctx.get("message", "action not found"))
                return
            for a in service.build_actions():
                if a["id"] == action_id:
                    self._send(200, a)
                    return
            self._json_err(404, f"action not found: {action_id}")
        else:
            self._json_err(404, f"api not found: {path}")

    def _route_action(self, path):
        if path == "/api/actions/batch/approve":
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(body)
            except Exception:
                payload = {}
            result = service.batch_approve(
                payload.get("ids", []),
                actor=payload.get("actor", "user"),
                confirm=bool(payload.get("confirm", False)),
            )
            self._send(200 if result.get("ok") else 400, result)
            return
        m = re.match(r"^/api/actions/(.+)/judge$", path)
        if m:
            result = service.run_review_judge(m.group(1))
            self._send(200 if result.get("ok") else 400, result)
            return
        m = re.match(r"^/api/actions/(.+)/(approve|reject|resolve|ignore|reprocess)$", path)
        if not m:
            self._json_err(400, "bad action path")
            return
        action_id = m.group(1)
        decision = m.group(2)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        actor = "user"
        if body:
            try:
                payload = json.loads(body)
                actor = payload.get("actor", "user")
            except Exception:
                pass
        result = service.execute_action(action_id, decision, actor=actor)
        self._send(200 if result.get("ok") else 409, result)


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Knowledge OS Control Center: http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
