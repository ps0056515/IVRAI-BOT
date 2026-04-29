"""
Serves the Voice demo UI from `static/` next to this file.
Run alongside server.py (WebSocket). Use an absolute static path so `runpy` / old CWD cannot break it.
"""

import logging
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

log = logging.getLogger("static")

# Always resolve next to this file (not CWD) — required when launched via root `static_server.py` shim
_STATIC_ROOT = (Path(__file__).resolve().parent / "static").resolve()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(_STATIC_ROOT), **kwargs)

    def log_message(self, format, *args):
        log.info(f"{self.address_string()} - {format % args}")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    index = _STATIC_ROOT / "index.html"
    if not index.is_file():
        log.error("Voice UI not found: %s (reinstall or run from repo root).", index)
        sys.exit(1)

    port = int(os.getenv("STATIC_PORT", "8080"))
    log.info("Static root: %s", _STATIC_ROOT)
    server = HTTPServer(("0.0.0.0", port), Handler)
    log.info("Voice demo UI: http://localhost:%s/  (also try http://127.0.0.1:%s/)", port, port)
    server.serve_forever()
