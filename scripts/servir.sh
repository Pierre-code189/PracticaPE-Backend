#!/usr/bin/env bash
# Sirve el frontend de PrácticaPE con el backend de prueba en :8096
set -e
cd "$(dirname "$0")/.."
export PRACTICAPE_DATA_DIR="${PRACTICAPE_DATA_DIR:-/root/.hermes/cache/scratch/pp_test/data}"
export PP_BASE="http://127.0.0.1:8096"
python3 - "$@" <<'PY'
import http.server, json, os, socketserver, sys, urllib.request, urllib.error

BACKEND = os.environ["PP_BASE"]
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)) if False else os.getcwd(), "frontend")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def _proxy(self):
        path = self.path.split("?", 1)[0]
        if "?" in self.path:
            url = BACKEND + path[4:] + "?" + self.path.split("?", 1)[1]
        else:
            url = BACKEND + path[4:]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=self.command)
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        if self.headers.get("Authorization"):
            req.add_header("Authorization", self.headers["Authorization"])
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read(), r.headers.get("content-type", "application/json")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("content-type", "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            status, body, ct = self._proxy()
            self.send_response(status)
            self.send_header("Content-Type", ct)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            status, body, ct = self._proxy()
            self.send_response(status)
            self.send_header("Content-Type", ct)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def do_PATCH(self):
        self.do_POST()

    def log_message(self, *a):
        pass

PORT = int(os.getenv("PORT", "8097"))
with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
    print("frontend en http://127.0.0.1:%d  (API %s)" % (PORT, BACKEND), flush=True)
    httpd.serve_forever()
PY
