#!/usr/bin/env python3

import json
import secrets
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from catalog_lib import EXTRACTOR_ARGS, FORMAT, exact_content_length


CHUNK_SIZE = 1024 * 1024


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True


class StreamHandler(BaseHTTPRequestHandler):
    upstream_url = ""
    user_agent = "curl"
    content_length = 0
    content_type = "video/mp4"
    token_path = ""

    def do_HEAD(self):
        if not self._authorized():
            return
        self._send_headers(self.headers.get("Range", ""))

    def do_GET(self):
        if not self._authorized():
            return
        self._proxy()

    def _authorized(self):
        if urlparse(self.path).path == self.token_path:
            return True
        self.send_error(404)
        return False

    def _range_bounds(self, requested_range):
        start = 0
        end = max(0, self.content_length - 1)
        if requested_range.startswith("bytes="):
            parts = requested_range[6:].split("-", 1)
            if parts[0].isdigit():
                start = int(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                end = min(end, int(parts[1]))
        start = max(0, min(start, end))
        return start, end

    def _send_headers(self, requested_range):
        start, end = self._range_bounds(requested_range)
        partial = bool(requested_range)
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", self.content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(max(0, end - start + 1)))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{self.content_length}")
        self.end_headers()

    def _proxy(self):
        requested_range = self.headers.get("Range", "")
        start, end = self._range_bounds(requested_range)
        self._send_headers(requested_range)
        process = None
        try:
            offset = start
            while offset <= end:
                chunk_end = min(end, offset + CHUNK_SIZE - 1)
                process = subprocess.Popen(
                    [
                        "curl",
                        "--fail",
                        "--location",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        "30",
                        "--user-agent",
                        self.user_agent,
                        "--range",
                        f"{offset}-{chunk_end}",
                        self.upstream_url,
                    ],
                    stdout=subprocess.PIPE,
                )
                while chunk := process.stdout.read(256 * 1024):
                    self.wfile.write(chunk)
                if process.wait(timeout=5) != 0:
                    break
                process = None
                offset = chunk_end + 1
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def log_message(self, _format, *_args):
        pass


def resolve(video_url):
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 10,
        "retries": 1,
        "extractor_args": EXTRACTOR_ARGS,
        "format": FORMAT,
    }
    with YoutubeDL(options) as ydl:
        return ydl.extract_info(video_url, download=False)


def main():
    if len(sys.argv) != 2:
        print("usage: stream_proxy.py <youtube-url>", file=sys.stderr)
        return 2

    info = resolve(sys.argv[1])
    size = exact_content_length(info)
    if size <= 0:
        raise RuntimeError("The selected stream did not report an exact size")

    token = secrets.token_urlsafe(24)
    StreamHandler.upstream_url = info["url"]
    StreamHandler.user_agent = info.get("http_headers", {}).get("User-Agent", "curl")
    StreamHandler.content_length = size
    StreamHandler.content_type = "video/webm" if info.get("ext") == "webm" else "video/mp4"
    StreamHandler.token_path = f"/{token}"

    server = LoopbackServer(("127.0.0.1", 0), StreamHandler)
    local_url = f"http://127.0.0.1:{server.server_port}/{token}"
    print(
        json.dumps(
            {
                "status": "ready",
                "id": info.get("id", ""),
                "url": local_url,
                "duration": info.get("duration") or 0,
                "width": info.get("width") or 0,
                "height": info.get("height") or 0,
            }
        ),
        flush=True,
    )

    def stop_server(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
