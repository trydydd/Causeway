"""Minimal stdlib health-check app — a build-loop test fixture, not an example.

No third-party dependencies, so the container build needs no package index.
Binds 0.0.0.0 so the platform's port mapping can reach it.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8080


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib-mandated name)
        if self.path == "/health":
            self._send(200, b'{"status": "ok"}', "application/json")
        elif self.path == "/":
            self._send(200, b"py-health is running on Causeway.\n", "text/plain")
        else:
            self._send(404, b"not found\n", "text/plain")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep stdout clean for log streaming
        pass


if __name__ == "__main__":
    print(f"py-health listening on 0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
