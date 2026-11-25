"""把人工精选的笔记条目导入记忆库（可重复执行、幂等）。

条目格式见 import/notes_batch1.json：
body / kind / sensitivity / confidence / importance / status / source
只导入 body，不导入原文全文，避免联系方式等敏感信息进库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import db


def _occurred_at(source: str) -> str:
    path = Path(source)
    try:
        ts = path.stat().st_mtime
    except OSError:
        ts = datetime.now(timezone.utc).timestamp()
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def import_entries(conn: sqlite3.Connection, entries: list[dict], *, dry_run: bool = False) -> dict:
    created, skipped = [], []
    for entry in entries:
        body = str(entry["body"]).strip()
        if not body:
            continue
        exists = conn.execute(
            "SELECT 1 FROM memories WHERE body = ? AND status != 'deleted' LIMIT 1", (body,),
        ).fetchone()
        if exists:
            skipped.append(body)
            continue
        item = {
            "body": body,
            "kind": entry["kind"],
            "sensitivity": entry.get("sensitivity", "private"),
            "confidence": float(entry.get("confidence", 0.6)),
            "importance": int(entry.get("importance", 3)),
            "status": entry.get("status", "candidate"),
        }
        if dry_run:
            created.append(item)
            continue
        turn_id = "note:" + hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]
        event_id, _ = db.add_event(
            conn,
            turn_id=turn_id,
            occurred_at=_occurred_at(str(entry.get("source", ""))),
            actor="owner",
            role="user",
            content=body,
            source_platform="notes",
            sensitivity=item["sensitivity"],
            fact_owner="explicit_user",
        )
        memory_id = db.add_memory(
            conn,
            kind=item["kind"],
            body=body,
            source_event_ids=[event_id],
            tags="notes-import",
            fact_owner="explicit_user",
            importance=item["importance"],
            confidence=item["confidence"],
            sensitivity=item["sensitivity"],
            status=item["status"],
        )
        item["memory_id"] = memory_id
        created.append(item)
    return {"created": created, "skipped": skipped, "dry_run": dry_run}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--file", type=Path,
        default=Path(__file__).resolve().parents[1] / "Private" / "notes_batch1.json",
    )
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    entries = json.loads(args.file.read_text(encoding="utf-8"))
    db_path = args.db or Path.home() / ".dsh" / "memory-v2" / "memory.db"
    conn = db.init_db(db_path)
    try:
        result = import_entries(conn, entries, dry_run=args.dry_run)
    finally:
        conn.close()
    print(json.dumps({
        "created": len(result["created"]),
        "skipped": len(result["skipped"]),
        "dry_run": result["dry_run"],
        "items": result["created"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
