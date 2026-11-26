#!/usr/bin/env python3
"""大肥鱼 VoiceService · 最小 MCP stdio 服务。

只做两件事：
- voice_speak(text, emotion, speed): 调本地 GPT-SoVITS 生成 WAV
- voice_status(): 看 API、参考音频、RVC 状态

stdout 只输出协议 JSON，日志走 stderr。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import voice_engine  # noqa: E402

SERVER_INFO = {"name": "dafeiyu-voice", "version": "0.1.0"}
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "voice_speak",
        "description": "用本地 GPT-SoVITS 把一段文字合成 WAV；返回文件路径与时长。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "emotion": {
                    "type": "string",
                    "enum": ["neutral", "neutral_2", "happy", "tender", "sad"],
                    "default": "neutral",
                },
                "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0},
                "use_rvc": {
                    "type": "boolean", "default": False,
                    "description": "是否再用 RVC feiyu_v2 做音色转换（需要 RVC 环境和权重）",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "voice_status",
        "description": "检查 GPT-SoVITS API、参考音频与 RVC 是否就绪。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}]}


def call_tool(name: str, args: dict) -> dict:
    if name == "voice_speak":
        result = voice_engine.synthesize(
            str(args["text"]),
            emotion=str(args.get("emotion", "neutral")),
            speed=float(args.get("speed", 1.0)),
            use_rvc=bool(args.get("use_rvc", False)),
        )
        return _text(result)
    if name == "voice_status":
        return _text(voice_engine.status())
    return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}


def handle(request: dict) -> dict | None:
    method = request.get("method")
    req_id = request.get("id")
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}
    elif method in ("notifications/initialized", "notifications/cancelled"):
        return None
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        try:
            result = call_tool(str(params.get("name", "")), params.get("arguments") or {})
        except Exception as exc:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": str(exc)}}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": str(exc)}}), flush=True)
            continue
        response = handle(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
