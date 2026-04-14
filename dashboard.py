import os
import sys
import json
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from db import init_db, get_stats, get_recent_activities, get_users

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = 5002402843

HTML_PATH = os.path.join(BASE_DIR, "templates", "index.html")


def validate_telegram_init_data(init_data: str) -> dict | None:
    try:
        params = dict(parse_qsl(init_data, strict_parsing=True))
        hash_value = params.pop("hash", None)
        if not hash_value:
            return None
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed_hash, hash_value):
            return None
        return params
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_GET(self):
        init_db()
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/":
            try:
                with open(HTML_PATH, "rb") as f:
                    self.send_html(f.read())
            except FileNotFoundError:
                self.send_html(b"<h1>Template not found</h1>", 500)

        elif path == "/api/stats":
            total_users, total_actions = get_stats()
            self.send_json({"total_users": total_users, "total_actions": total_actions})

        elif path == "/api/users":
            self.send_json(get_users())

        elif path == "/api/activities":
            self.send_json(get_recent_activities(50))

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        init_db()
        path = urlparse(self.path).path.rstrip("/")

        if path == "/api/auth":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            init_data = body.get("initData", "")
            if not TOKEN:
                self.send_json({"ok": False, "error": "Server not configured"}, 500)
                return
            params = validate_telegram_init_data(init_data)
            if not params:
                self.send_json({"ok": False, "error": "Invalid Telegram data"}, 403)
                return
            user_info = json.loads(params.get("user", "{}"))
            if user_info.get("id") != ADMIN_ID:
                self.send_json({"ok": False, "error": "Access denied"}, 403)
                return
            self.send_json({"ok": True})

        else:
            self.send_json({"error": "Not found"}, 404)
