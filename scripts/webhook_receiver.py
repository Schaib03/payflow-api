"""Tiny webhook receiver for local testing.

Prints every event and checks the PayFlow-Signature header when WEBHOOK_SECRET
is set. Uses only the standard library so it runs anywhere:

    WEBHOOK_SECRET=whsec_... python scripts/webhook_receiver.py
"""

import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ.get("WEBHOOK_SECRET", "")
TOLERANCE = 300


def verify(header, body):
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    timestamp = int(parts.get("t", "0"))
    expected = hmac.new(SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    fresh = abs(time.time() - timestamp) <= TOLERANCE
    return fresh and hmac.compare_digest(expected.hexdigest(), parts.get("v1", ""))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if SECRET and not verify(self.headers.get("PayFlow-Signature", ""), body):
            print("rejected: bad signature")
            self.send_response(400)
            self.end_headers()
            return
        event = json.loads(body)
        print(f"{event['type']} {event['id']} -> {json.dumps(event['data'])[:200]}")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9000"))
    print(f"listening on :{port}, signature check {'on' if SECRET else 'off'}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
