"""
webhook_server.py — Tiny HTTP server that n8n calls to trigger the pipeline.
Run this on your server alongside pipeline.py.

Usage:
  python webhook_server.py          # Listens on port 8080
  PORT=9000 python webhook_server.py
"""
import os
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pipeline import run_single, run_batch, discover_topics, get_reviewed_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", 8080))
SECRET = os.getenv("WEBHOOK_SECRET", "")   # Optional — set to verify requests


class PipelineHandler(BaseHTTPRequestHandler):

    def _send(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        log.info(f"{self.address_string()} - {fmt % args}")

    def do_POST(self):
        # Auth check
        if SECRET:
            auth = self.headers.get("X-Pipeline-Secret", "")
            if auth != SECRET:
                self._send(401, {"error": "Unauthorised"})
                return

        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/run/discover":
            n = int(body.get("n", 3))

            def task():
                already = get_reviewed_tools()
                topics  = discover_topics(n_topics=n, already_done=already)
                run_batch(topics)

            threading.Thread(target=task, daemon=True).start()
            self._send(202, {"status": "started", "n": n})

        elif self.path == "/run/tool":
            name     = body.get("name")
            category = body.get("category", "general")
            if not name:
                self._send(400, {"error": "Missing 'name' field"})
                return
            topic = {
                "title":       name,
                "topic_type":  category,
                "hook":        "",
                "setting":     "",
                "music_style": "orchestral_documentary",
            }
            threading.Thread(target=run_single, args=(topic,), daemon=True).start()
            self._send(202, {"status": "started", "tool": name})

        else:
            self._send(404, {"error": f"Unknown path: {self.path}"})

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "Not found"})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), PipelineHandler)
    log.info(f"Pipeline webhook server listening on port {PORT}")
    log.info(f"  POST /run/discover  — auto-discover & run N videos")
    log.info(f"  POST /run/tool      — run a specific tool review")
    log.info(f"  GET  /health        — health check")
    server.serve_forever()
