#!/usr/bin/env python3
"""把 Memory v2 导出为「记忆星河」的 galaxy.json。

只读 SQLite；默认排除 sensitivity=restricted。
输出文件只在本机，已加入 .gitignore。
"""

from __future__ import annotations

import array
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "MemoryGalaxy" / "galaxy.json"


def db_path() -> Path:
    env = os.environ.get("DSH_MEMORY_DB")
    if env:
        return Path(env)
    return Path.home() / ".dsh" / "memory-v2" / "memory.db"


def connect() -> sqlite3.Connection:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"memory db not found: {p}")
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def tags_of(raw: str) -> list[str]:
    parts = []
    for piece in (raw or "").replace("，", ",").split(","):
        piece = piece.strip()
        if piece and piece not in parts:
            parts.append(piece)
    return parts


def label(text: str, n: int = 42) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def read_vec(blob: bytes) -> array.array:
    vec = array.array("f")
    vec.frombytes(blob)
    return vec


def cosine(a: array.array, b: array.array) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / math.sqrt(na * nb)


def main() -> int:
    con = connect()
    cur = con.cursor()
    now = datetime.now(timezone.utc).isoformat()
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    tag_nodes: dict[str, str] = {}
    excluded = 0

    memories = list(cur.execute(
        "SELECT id, kind, body, tags, fact_owner, importance, confidence, sensitivity,"
        " created_at, updated_at FROM memories WHERE status='active' ORDER BY importance DESC, created_at"
    ))
    mem_ids = []
    for m in memories:
        if m["sensitivity"] == "restricted":
            excluded += 1
            continue
        mem_ids.append(m["id"])
        nodes.append({
            "id": m["id"],
            "type": "memory",
            "kind": m["kind"],
            "label": label(m["body"]),
            "body": m["body"],
            "tags": tags_of(m["tags"]),
            "fact_owner": m["fact_owner"],
            "importance": m["importance"],
            "confidence": m["confidence"],
            "created_at": m["created_at"],
        })
        node_ids.add(m["id"])
        for tag in tags_of(m["tags"]):
            if tag not in tag_nodes:
                tid = f"tag:{tag}"
                tag_nodes[tag] = tid
                nodes.append({"id": tid, "type": "tag", "label": tag})
                node_ids.add(tid)
            edges.append({"source": m["id"], "target": tag_nodes[tag], "type": "tag"})

    # 核心记忆
    try:
        core = cur.execute(
            "SELECT id, body, confirmed_at FROM core_memories WHERE status='confirmed' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        core = None
    if core:
        nodes.append({
            "id": f"core:{core['id']}",
            "type": "core",
            "label": label(core["body"], 30),
            "body": core["body"],
            "confirmed_at": core["confirmed_at"],
        })
        node_ids.add(f"core:{core['id']}")

    # 事件：只挂到有来源关系的记忆；没有关系的孤儿事件先不画
    rows = list(cur.execute(
        "SELECT e.id, e.content, e.occurred_at, e.role, e.sensitivity,"
        " ms.memory_id, ms.relation"
        " FROM events e JOIN memory_sources ms ON ms.event_id=e.id"
        " ORDER BY e.occurred_at"
    ))
    event_ids: set[str] = set()
    for e in rows:
        if e["sensitivity"] == "restricted":
            excluded += 1
            continue
        eid = e["id"]
        if eid not in event_ids:
            event_ids.add(eid)
            nodes.append({
                "id": eid,
                "type": "event",
                "label": label(e["content"], 56),
                "body": label(e["content"], 220),
                "occurred_at": e["occurred_at"],
                "role": e["role"],
            })
            node_ids.add(eid)
        edges.append({
            "source": e["memory_id"],
            "target": eid,
            "type": "source",
            "relation": e["relation"],
        })

    # 日摘要
    digests = list(cur.execute(
        "SELECT day, summary, mood FROM daily_digests ORDER BY day"
    ))
    for d in digests:
        did = f"digest:{d['day']}"
        nodes.append({
            "id": did,
            "type": "digest",
            "label": d["day"],
            "body": d["summary"],
            "mood": d["mood"],
            "day": d["day"],
        })
        node_ids.add(did)

    # 语义连线：每个记忆取最相似的 top-2，阈值 0.68
    try:
        emb_rows = list(cur.execute(
            "SELECT memory_id, model, vector FROM memory_embeddings"
        ))
    except sqlite3.Error:
        emb_rows = []
    vecs = {}
    for r in emb_rows:
        if r["memory_id"] in node_ids:
            vecs[r["memory_id"]] = read_vec(r["vector"])
    semantic = []
    seen = set()
    for i, a in enumerate(mem_ids):
        if a not in vecs:
            continue
        scored = []
        for b in mem_ids[i + 1:]:
            if b not in vecs:
                continue
            score = cosine(vecs[a], vecs[b])
            if score >= 0.68:
                scored.append((score, b))
        for score, b in sorted(scored, reverse=True)[:2]:
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            semantic.append({
                "source": a,
                "target": b,
                "type": "semantic",
                "weight": round(score, 4),
            })
    edges.extend(semantic)

    # 去重
    dedup = []
    edge_seen = set()
    for e in edges:
        if e["source"] not in node_ids or e["target"] not in node_ids:
            continue
        key = (e["source"], e["target"], e["type"], e.get("relation", ""))
        if key in edge_seen:
            continue
        edge_seen.add(key)
        dedup.append(e)

    payload = {
        "meta": {
            "generated_at": now,
            "source": str(db_path()),
            "memory_count": len(mem_ids),
            "event_count": len(event_ids),
            "tag_count": len(tag_nodes),
            "digest_count": len(digests),
            "core_count": 1 if core else 0,
            "node_count": len(nodes),
            "edge_count": len(dedup),
            "restricted_skipped": excluded,
            "semantic_edges": len(semantic),
        },
        "nodes": nodes,
        "edges": dedup,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["meta"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
