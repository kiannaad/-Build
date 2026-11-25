#!/usr/bin/env python3
"""大肥鱼 Memory v2 · 最小 MCP stdio 服务（零第三方依赖）。

只实现 JSON-RPC 2.0 的 initialize / tools/list / tools/call，
stdout 只输出协议 JSON，日志一律走 stderr。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
import decay_job  # noqa: E402
import digest  # noqa: E402
import extractor  # noqa: E402

SERVER_INFO = {"name": "dafeiyu-memory", "version": "0.1.0"}
PROTOCOL = "2024-11-05"


def db_path() -> Path:
    env = os.environ.get("DSH_MEMORY_DB")
    if env:
        return Path(env)
    return Path.home() / ".dsh" / "memory-v2" / "memory.db"


TOOLS = [
    {
        "name": "memory_recall",
        "description": "按关键词召回长期记忆（只返回 active，restricted 默认排除）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_remember",
        "description": "写入一条记忆候选；必须引用至少一个 L3 事件 id。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "kind": {"type": "string"},
                "source_event_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "tags": {"type": "string"},
                "importance": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "sensitivity": {"type": "string", "enum": ["public_safe", "private", "restricted"]},
                "status": {"type": "string", "enum": ["candidate", "active"]},
                "fact_owner": {"type": "string"},
            },
            "required": ["body", "kind", "source_event_ids"],
        },
    },
    {
        "name": "memory_forget",
        "description": "软删除一条记忆（status=deleted），可恢复。",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory_audit",
        "description": "读取最近的操作审计。",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
        },
    },
    {
        "name": "memory_ingest",
        "description": "把一轮对话写入 L3（turn_id 幂等），并用规则提取 L2 候选。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "turn_id": {"type": "string"},
                "text": {"type": "string"},
                "role": {"type": "string", "enum": ["user", "assistant"], "default": "user"},
                "occurred_at": {"type": "string"},
                "session_id": {"type": "string"},
                "source_platform": {"type": "string"},
            },
            "required": ["turn_id", "text"],
        },
    },
    {
        "name": "memory_promote",
        "description": "把候选记忆提升为 active；应在用户确认后调用。",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory_digest_generate",
        "description": "生成/更新某天的 L1 每日摘要（默认今天，UTC 日期）。",
        "inputSchema": {
            "type": "object",
            "properties": {"day": {"type": "string", "description": "YYYY-MM-DD，默认今天"}},
        },
    },
    {
        "name": "memory_digest_get",
        "description": "读取某天的 L1 每日摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {"day": {"type": "string"}},
            "required": ["day"],
        },
    },
    {
        "name": "memory_core_propose",
        "description": "提出一条 L4 核心记忆候选；需再经 memory_core_confirm 才生效。",
        "inputSchema": {
            "type": "object",
            "properties": {"body": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["body"],
        },
    },
    {
        "name": "memory_core_confirm",
        "description": "确认一条 L4 核心记忆（仅 proposed 可确认）。",
        "inputSchema": {
            "type": "object",
            "properties": {"core_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["core_id"],
        },
    },
    {
        "name": "memory_core_list",
        "description": "列出 L4 核心记忆（默认排除 deleted）。",
        "inputSchema": {
            "type": "object",
            "properties": {"include_deleted": {"type": "boolean", "default": False}},
        },
    },
    {
        "name": "memory_decay",
        "description": "按保持率归档低价值记忆；默认 dry-run，只报告不写入。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.15},
                "min_age_days": {"type": "number", "minimum": 0, "default": 7},
                "dry_run": {"type": "boolean", "default": True},
            },
        },
    },
]


def _text(payload) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": False,
    }


def call_tool(name: str, args: dict) -> dict:
    conn = db.init_db(db_path())
    try:
        if name == "memory_recall":
            return _text({"hits": db.recall(conn, str(args.get("query", "")), limit=int(args.get("limit", 6)))})
        if name == "memory_remember":
            memory_id = db.add_memory(
                conn,
                kind=str(args["kind"]),
                body=str(args["body"]),
                source_event_ids=list(args["source_event_ids"]),
                tags=str(args.get("tags", "")),
                fact_owner=str(args.get("fact_owner", "observed")),
                importance=int(args.get("importance", 3)),
                confidence=float(args.get("confidence", 0.5)),
                sensitivity=str(args.get("sensitivity", "private")),
                status=str(args.get("status", "candidate")),
            )
            return _text({"memory_id": memory_id, "status": args.get("status", "candidate")})
        if name == "memory_forget":
            db.set_memory_status(conn, str(args["memory_id"]), "deleted", str(args.get("reason", "")))
            return _text({"ok": True, "memory_id": args["memory_id"]})
        if name == "memory_audit":
            rows = conn.execute(
                "SELECT action, subject_type, subject_id, detail_json, created_at"
                " FROM memory_audit ORDER BY created_at DESC LIMIT ?",
                (int(args.get("limit", 20)),),
            ).fetchall()
            return _text({"entries": [dict(r) for r in rows]})
        if name == "memory_ingest":
            event_id, created = db.add_event(
                conn,
                turn_id=str(args["turn_id"]),
                occurred_at=str(args.get("occurred_at") or db.utcnow()),
                actor="owner",
                role=str(args.get("role", "user")),
                content=str(args["text"]),
                source_platform=str(args.get("source_platform", "local")),
                session_id=args.get("session_id"),
            )
            candidates = extractor.extract_from_event(conn, event_id)
            return _text({"event_id": event_id, "created": created, "candidate_ids": candidates})
        if name == "memory_promote":
            db.set_memory_status(conn, str(args["memory_id"]), "active", str(args.get("reason", "confirmed")))
            return _text({"ok": True, "memory_id": args["memory_id"], "status": "active"})
        if name == "memory_digest_generate":
            return _text({"digest": digest.generate(conn, args.get("day"))})
        if name == "memory_digest_get":
            return _text({"digest": digest.get(conn, str(args["day"]))})
        if name == "memory_core_propose":
            core_id = db.propose_core(conn, body=str(args["body"]), reason=str(args.get("reason", "")))
            return _text({"core_id": core_id, "status": "proposed"})
        if name == "memory_core_confirm":
            db.confirm_core(conn, str(args["core_id"]), str(args.get("reason", "")))
            return _text({"ok": True, "core_id": args["core_id"], "status": "confirmed"})
        if name == "memory_core_list":
            return _text({"entries": db.list_core(conn, include_deleted=bool(args.get("include_deleted", False)))})
        if name == "memory_decay":
            dry = bool(args.get("dry_run", True))
            archived = decay_job.archive_stale(
                conn,
                threshold=float(args.get("threshold", decay_job.DEFAULT_THRESHOLD)),
                min_age_days=float(args.get("min_age_days", decay_job.DEFAULT_MIN_AGE_DAYS)),
                dry_run=dry,
            )
            return _text({"archived": archived, "dry_run": dry})
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}
    finally:
        conn.close()


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
        except Exception as exc:  # 工具参数/约束错误回 JSON-RPC error，不吞成空结果
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": str(exc)}}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main() -> int:
    # Windows 下 Python 默认按本地代码页写 stdout，MCP 客户端按 UTF-8 解码会乱码。
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
