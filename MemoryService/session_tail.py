"""从 DSH 会话日志增量提取对话，写入 Memory v2 的 L3。

- 日志是 `session.v4.jsonl.zstd`，用 Python 3.14 的 `compression.zstd` 整包解压；
- 只取 user/message 与 assistant/message 的 text 块，跳过 reasoning、tool、图片；
- 跳过 system-reminder / 定时提醒等注入消息；
- turn_id = `<session_id>:<seq>`，重复运行不会重复入库；
- 只对用户消息跑候选提取；助手内容只进 L3，不自动变成用户事实。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import db
import extractor

NOISE_PREFIXES = ("<system-reminder>", "[SCHEDULE REMINDER", "[dsh-proactive")
STATE_NAME = "tail_state.json"
DEFAULT_WORKSPACES = (r"D:\大肥鱼",)


def allowed_workspaces() -> set[str]:
    raw = os.environ.get("DFY_MEMORY_WORKSPACES", "")
    items = [x.strip() for x in raw.split(";") if x.strip()] if raw else list(DEFAULT_WORKSPACES)
    return {x.rstrip("\\/").casefold() for x in items}


def _text_of(ev: dict) -> str:
    data = ev.get("data") or {}
    blocks = data.get("content")
    if not isinstance(blocks, list):
        message = data.get("message") or {}
        blocks = message.get("content")
    if not isinstance(blocks, list):
        return ""
    parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p).strip()


def _occurred_at(ev: dict) -> str:
    ms = ev.get("time")
    if isinstance(ms, (int, float)):
        return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return db.utcnow()


def _session_id(events: list[dict], path: Path) -> str:
    for ev in events:
        if ev.get("type") == "session" and ev.get("id"):
            return str(ev["id"])
    return path.parent.name


def iter_events(path: Path) -> list[dict]:
    from compression import zstd

    raw = zstd.decompress(path.read_bytes())
    out = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def ingest_file(
    conn: sqlite3.Connection,
    path: Path,
    *,
    dry_run: bool = False,
    workspaces: set[str] | None = None,
) -> dict:
    events = iter_events(path)
    session_id = _session_id(events, path)
    cwd = next((str(e.get("cwd") or "") for e in events if e.get("type") == "session"), "")
    counts = {"user": 0, "assistant": 0, "skipped": 0, "candidates": 0, "new_events": 0, "skipped_file": 0}
    allowed = allowed_workspaces() if workspaces is None else workspaces
    if cwd and cwd.rstrip("\\/").casefold() not in allowed:
        counts["skipped_file"] = 1
        return counts
    for ev in events:
        etype = ev.get("type")
        if etype not in ("user/message", "assistant/message"):
            continue
        text = _text_of(ev)
        if not text or text.startswith(NOISE_PREFIXES):
            counts["skipped"] += 1
            continue
        role = "user" if etype == "user/message" else "assistant"
        counts[role] += 1
        if dry_run:
            continue
        seq = ev.get("seq")
        event_id, created = db.add_event(
            conn,
            turn_id=f"{session_id}:{seq}",
            occurred_at=_occurred_at(ev),
            actor="owner" if role == "user" else "dafeiyu",
            role=role,
            content=text,
            source_platform="dsh",
            session_id=session_id,
        )
        if created:
            counts["new_events"] += 1
            if role == "user":
                counts["candidates"] += len(extractor.extract_from_event(conn, event_id))
    return counts


def _load_state(root: Path) -> dict:
    p = root / STATE_NAME
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(root: Path, state: dict) -> None:
    (root / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run(root: Path | None = None, *, dry_run: bool = False, limit: int = 0) -> dict:
    root = root or Path.home() / ".dsh" / "sessions"
    state = {} if dry_run else _load_state(Path.home() / ".dsh" / "memory-v2")
    files = sorted(root.rglob("session.v4.jsonl.zstd"), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit:
        files = files[:limit]
    total = {"files": 0, "skipped_files": 0, "user": 0, "assistant": 0, "skipped": 0,
             "candidates": 0, "new_events": 0}
    conn = db.init_db(Path.home() / ".dsh" / "memory-v2" / "memory.db")
    try:
        for path in files:
            st = path.stat()
            key = str(path)
            marker = {"mtime": st.st_mtime, "size": st.st_size}
            if not dry_run and state.get(key) == marker:
                continue
            result = ingest_file(conn, path, dry_run=dry_run)
            for k in ("user", "assistant", "skipped", "candidates", "new_events"):
                total[k] += result[k]
            if result["skipped_file"]:
                total["skipped_files"] += 1
            else:
                total["files"] += 1
            if not dry_run:
                state[key] = marker
        if not dry_run:
            _save_state(Path.home() / ".dsh" / "memory-v2", state)
    finally:
        conn.close()
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    result = run(args.root, dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
