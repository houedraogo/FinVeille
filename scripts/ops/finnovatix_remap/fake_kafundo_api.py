#!/usr/bin/env python3
"""API Kafundo FIGEE pour la simulation : sert un instantane complet (JSON) avec une pagination DETERMINISTE.
Permet de rejouer la synchro Finnovatix de facon reproductible (l'API reelle pagine de facon instable).
Usage : fake_kafundo_api.py snapshot.json PORT"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

items = sorted(json.load(open(sys.argv[1], encoding="utf-8")), key=lambda i: i["id"])

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.rstrip("/") == "/api/health":
            return self._send({"status": "ok"})
        if u.path.rstrip("/") == "/api/v1/devices":
            q = parse_qs(u.query); page = int(q.get("page", ["1"])[0]); size = min(100, int(q.get("page_size", ["20"])[0]))
            chunk = items[(page - 1) * size: page * size]
            return self._send({"items": chunk, "total": len(items), "page": page, "page_size": size, "pages": -(-len(items) // size)})
        self._send({"detail": "not found"}, 404)

HTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
