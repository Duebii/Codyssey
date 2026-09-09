"""Local-only static server and the SAME recommendation handler used on Vercel.

Run: python dev_server.py
Only explicitly public files are served. .env, Python source, docs and tests stay private.
"""
import argparse
import logging
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from api.recommend import handler

ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = {"index.html", "01_home_ui_website_landing.png", "02_About_Final.png", "Relax.jpg", "Relax_2.jpeg"}
PUBLIC_TYPES = {"css": {".css"}, "js": {".js"}, "images": {".svg", ".png", ".jpg", ".jpeg", ".webp"}, "audio": {".mp3"}}


def load_local_environment():
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key in {"OPENAI_API_KEY", "OPENAI_MODEL"}:
            os.environ.setdefault(key, value.strip().strip("\"'"))


class LocalHandler(SimpleHTTPRequestHandler, handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/recommend":
            self.send_error(404)
            return
        handler.do_POST(self)

    def send_head(self):
        raw_path = unquote(urlsplit(self.path).path)
        if raw_path == "/api/recommend":
            self.method_not_allowed()
            return None
        relative = raw_path.lstrip("/") or "index.html"
        path = (ROOT / relative).resolve()
        try:
            parts = path.relative_to(ROOT).parts
        except ValueError:
            self.send_error(404)
            return None
        public = relative in PUBLIC_FILES or (len(parts) > 1 and parts[0] in PUBLIC_TYPES and path.suffix in PUBLIC_TYPES[parts[0]])
        if not public or not path.is_file() or any(part.startswith(".") for part in parts):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RE:ST local development server")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    load_local_environment()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), LocalHandler)
    print(f"RE:ST is ready at http://localhost:{args.port}", flush=True)
    print("AI: configured" if os.environ.get("OPENAI_API_KEY") else "AI: not configured; Personal and audio are available.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
