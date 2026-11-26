"""大肥鱼语音桥：给浏览器一个带 CORS 的本地 TTS 入口。

- 127.0.0.1:9881
- POST /speak {text, emotion, speed} -> {url, duration, path}
- GET  /audio/<file> 提供 WAV
- GET  /health

只绑定本机，不对外网开放；文字最长 1200 字。
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import voice_engine  # noqa: E402

HOST = "127.0.0.1"
PORT = 9881
OUT = Path(r"D:\大肥鱼\Voice\output")
MAX_CHARS = 1200
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "DafeiyuVoiceBridge/0.1"

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {"ok": True, "service": "dafeiyu-voice-bridge"})
            return
        if path.startswith("/audio/"):
            name = path[len("/audio/"):]
            if not name or name != Path(name).name or not name.endswith(".wav"):
                self._json(400, {"message": "bad audio name"})
                return
            target = OUT / name
            if not target.is_file():
                self._json(404, {"message": "audio not found"})
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in CORS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {"message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/speak":
            self._json(404, {"message": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 64 * 1024))
            payload = json.loads(raw.decode("utf-8") or "{}")
            text = str(payload.get("text", "")).strip()
            emotion = str(payload.get("emotion", "neutral"))
            speed = float(payload.get("speed", 1.0))
            if not text:
                self._json(400, {"message": "text is empty"})
                return
            if len(text) > MAX_CHARS:
                self._json(400, {"message": f"text too long ({len(text)} > {MAX_CHARS})"})
                return
            result = voice_engine.synthesize(text, emotion=emotion, speed=speed)
            name = Path(result["path"]).name
            self._json(200, {
                "id": name,
                "url": f"http://{HOST}:{PORT}/audio/{name}",
                "duration_sec": result["duration_sec"],
                "emotion": result["emotion"],
                "reference": result["reference"],
                "path": result["path"],
            })
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"message": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[voice-bridge] {fmt % args}", file=sys.stderr, flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[voice-bridge] listening http://{HOST}:{PORT}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
