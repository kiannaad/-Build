"""大肥鱼 Memory v2 · 最小存储层。

设计约束（见 Doc/重建/2026-11-25-大肥鱼重建-v1.md 第 5 节）：
- L3 事件是权威，只追加，turn_id 幂等；
- L2 记忆卡必须引用至少一个 L3 事件；
- L4 核心记忆只能经确认/受控晋升；
- 衰减用半衰期，retention = 0.5 ** (age_days / eff_half_life)；
- 只被读取不增加 reinforcement。
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_HALF_LIFE = {
    "event": 30.0,
    "experience": 180.0,
    "interest": 120.0,
    "preference": 120.0,
    "commitment": 30.0,
    "user_fact": 365.0,
    "relationship": 365.0,
    "boundary": 365.0,
    "core": 1e9,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_fts(conn: sqlite3.Connection) -> None:
    """FTS5 优先用 trigram（中文子串），不可用则退 unicode61。"""
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    ).fetchone()
    if not existing:
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE memories_fts USING fts5("
                "memory_id UNINDEXED, body, tags, tokenize='trigram')"
            )
        except sqlite3.OperationalError:
            conn.execute(
                "CREATE VIRTUAL TABLE memories_fts USING fts5("
                "memory_id UNINDEXED, body, tags, tokenize='unicode61')"
            )
    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
          INSERT INTO memories_fts(memory_id, body, tags) VALUES (new.id, new.body, new.tags);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
          DELETE FROM memories_fts WHERE memory_id = old.id;
        END;
        CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE OF body, tags ON memories BEGIN
          DELETE FROM memories_fts WHERE memory_id = old.id;
          INSERT INTO memories_fts(memory_id, body, tags) VALUES (new.id, new.body, new.tags);
        END;
        """
    )


def init_db(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _init_fts(conn)
    conn.commit()
    return conn


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM memories_fts")
    rows = conn.execute("SELECT id, body, tags FROM memories").fetchall()
    conn.executemany(
        "INSERT INTO memories_fts(memory_id, body, tags) VALUES (?, ?, ?)",
        [(r["id"], r["body"], r["tags"]) for r in rows],
    )
    conn.commit()


def add_event(
    conn: sqlite3.Connection,
    *,
    turn_id: str,
    occurred_at: str,
    actor: str,
    role: str,
    content: str,
    source_platform: str = "local",
    session_id: str | None = None,
    sensitivity: str = "private",
    fact_owner: str = "observed",
) -> tuple[str, bool]:
    """写入 L3。返回 (event_id, created)；重复 turn_id 返回原 id、created=False。"""
    event_id = "ev-" + uuid.uuid4().hex
    cur = conn.execute(
        """INSERT OR IGNORE INTO events
           (id, turn_id, occurred_at, source_platform, session_id, actor, role,
            content, content_hash, sensitivity, fact_owner, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (event_id, turn_id, occurred_at, source_platform, session_id, actor, role,
         content, _hash(content), sensitivity, fact_owner, utcnow()),
    )
    conn.commit()
    if cur.rowcount == 0:
        row = conn.execute("SELECT id FROM events WHERE turn_id = ?", (turn_id,)).fetchone()
        return row["id"], False
    return event_id, True


def add_memory(
    conn: sqlite3.Connection,
    *,
    kind: str,
    body: str,
    source_event_ids: list[str],
    tags: str = "",
    fact_owner: str = "observed",
    importance: int = 3,
    confidence: float = 0.5,
    sensitivity: str = "private",
    status: str = "candidate",
    half_life_days: float | None = None,
) -> str:
    if not source_event_ids:
        raise ValueError("L2 记忆必须引用至少一个 L3 事件")
    memory_id = "mem-" + uuid.uuid4().hex
    now = utcnow()
    conn.execute(
        """INSERT INTO memories
           (id, kind, body, tags, fact_owner, importance, confidence, sensitivity, status,
            half_life_days, reinforcement, last_reinforced_at, valid_from, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)""",
        (memory_id, kind, body, tags, fact_owner, importance, confidence, sensitivity, status,
         float(half_life_days if half_life_days is not None else DEFAULT_HALF_LIFE.get(kind, 30.0)),
         now, now, now),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO memory_sources(memory_id, event_id) VALUES (?, ?)",
        [(memory_id, eid) for eid in source_event_ids],
    )
    record_audit(conn, "create", "memory", memory_id, {"kind": kind, "sources": source_event_ids})
    conn.commit()
    return memory_id


def set_memory_status(conn: sqlite3.Connection, memory_id: str, status: str, reason: str = "") -> None:
    if status not in {"candidate", "active", "archived", "deleted"}:
        raise ValueError(f"未知状态: {status}")
    now = utcnow()
    conn.execute(
        "UPDATE memories SET status = ?, updated_at = ?, archived_at = ? WHERE id = ?",
        (status, now, now if status == "archived" else None, memory_id),
    )
    record_audit(conn, status, "memory", memory_id, {"reason": reason})
    conn.commit()


def reinforce(conn: sqlite3.Connection, memory_id: str) -> None:
    conn.execute(
        "UPDATE memories SET reinforcement = reinforcement + 1, last_reinforced_at = ?, updated_at = ? WHERE id = ?",
        (utcnow(), utcnow(), memory_id),
    )
    record_audit(conn, "reinforce", "memory", memory_id, {})
    conn.commit()


def retention(memory: sqlite3.Row | dict, now: datetime | None = None) -> float:
    """艾宾浩斯保持率；强化会延长有效半衰期，最多 3 倍。"""
    now = now or datetime.now(timezone.utc)
    anchor = memory["last_reinforced_at"] or memory["created_at"]
    try:
        then = datetime.fromisoformat(str(anchor).replace("Z", "+00:00"))
    except ValueError:
        then = now
    age_days = max((now - then).total_seconds() / 86400.0, 0.0)
    base = float(memory["half_life_days"]) or 30.0
    eff = base * min(1.0 + 0.5 * int(memory["reinforcement"]), 3.0)
    return math.pow(0.5, age_days / eff)


def _candidates(conn: sqlite3.Connection, query: str, limit: int) -> list[tuple[sqlite3.Row, float]]:
    """返回 (memory, similarity)。无向量时用 FTS/LIKE 作为相似度代理。"""
    q = query.strip()
    if not q:
        rows = conn.execute(
            "SELECT * FROM memories WHERE status = 'active' ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [(r, 0.5) for r in rows]
    found: list[sqlite3.Row] = []
    if len(q) >= 3:
        try:
            pattern = '"' + q.replace('"', '""') + '"'
            found = conn.execute(
                """SELECT m.* FROM memories_fts f JOIN memories m ON m.id = f.memory_id
                   WHERE memories_fts MATCH ? AND m.status = 'active'
                   ORDER BY bm25(memories_fts) LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            found = []
    if not found:
        like = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        found = conn.execute(
            """SELECT * FROM memories WHERE status = 'active' AND body LIKE ? ESCAPE '\\'
               ORDER BY updated_at DESC LIMIT ?""",
            (like, limit),
        ).fetchall()
    return [(r, 1.0 / (1.0 + i)) for i, r in enumerate(found)]


def recall(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 6,
    now: datetime | None = None,
    include_restricted: bool = False,
    source_affinity: float = 0.5,
) -> list[dict]:
    """召回：候选 → 过滤 → 精排。返回带 score/retention 的字典列表。"""
    candidates = _candidates(conn, query, max(limit * 5, 20))
    out: list[dict] = []
    for memory, similarity in candidates:
        if memory["status"] != "active":
            continue
        if memory["sensitivity"] == "restricted" and not include_restricted:
            continue
        r = retention(memory, now)
        score = similarity * (
            0.55
            + 0.15 * (int(memory["importance"]) / 5.0)
            + 0.10 * float(memory["confidence"])
            + 0.10 * r
            + 0.05 * min(int(memory["reinforcement"]) / 5.0, 1.0)
            + 0.05 * source_affinity
        )
        out.append({
            "id": memory["id"],
            "kind": memory["kind"],
            "body": memory["body"],
            "tags": memory["tags"],
            "score": round(score, 4),
            "retention": round(r, 4),
            "importance": memory["importance"],
            "confidence": memory["confidence"],
            "reinforcement": memory["reinforcement"],
        })
    # L4：已确认的核心记忆不衰减，相关时优先召回
    q = query.strip().lower()
    cores = conn.execute(
        "SELECT id, body FROM core_memories WHERE status = 'confirmed' ORDER BY created_at DESC"
    ).fetchall()
    for core in cores:
        if q and q not in core["body"].lower():
            continue
        out.append({
            "id": core["id"],
            "kind": "core",
            "body": core["body"],
            "tags": "core",
            "score": 1.0,
            "retention": 1.0,
            "importance": 5,
            "confidence": 1.0,
            "reinforcement": 0,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def upsert_digest(
    conn: sqlite3.Connection,
    *,
    day: str,
    summary: str,
    mood: str = "",
    todos: list[str] | None = None,
    source_event_ids: list[str] | None = None,
) -> None:
    now = utcnow()
    conn.execute(
        """INSERT INTO daily_digests(day, summary, mood, todos_json, source_event_ids, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(day) DO UPDATE SET
             summary = excluded.summary,
             mood = excluded.mood,
             todos_json = excluded.todos_json,
             source_event_ids = excluded.source_event_ids,
             updated_at = excluded.updated_at""",
        (day, summary, mood, json.dumps(todos or [], ensure_ascii=False),
         json.dumps(source_event_ids or [], ensure_ascii=False), now, now),
    )
    record_audit(conn, "digest", "day", day, {"summary_chars": len(summary)})
    conn.commit()


def propose_core(conn: sqlite3.Connection, *, body: str, reason: str = "") -> str:
    """新增一条 L4 核心记忆候选（proposed），必须再经 confirm 才生效。"""
    core_id = "core-" + uuid.uuid4().hex
    now = utcnow()
    conn.execute(
        "INSERT INTO core_memories(id, body, status, version, reason, created_at, updated_at)"
        " VALUES (?, ?, 'proposed', 1, ?, ?, ?)",
        (core_id, body, reason, now, now),
    )
    record_audit(conn, "core_propose", "core", core_id, {"reason": reason})
    conn.commit()
    return core_id


def confirm_core(conn: sqlite3.Connection, core_id: str, reason: str = "") -> None:
    now = utcnow()
    cur = conn.execute(
        "UPDATE core_memories SET status = 'confirmed', confirmed_at = ?, version = version + 1,"
        " reason = ?, updated_at = ? WHERE id = ? AND status = 'proposed'",
        (now, reason, now, core_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"没有可确认的 L4 候选: {core_id}")
    record_audit(conn, "core_confirm", "core", core_id, {"reason": reason})
    conn.commit()


def list_core(conn: sqlite3.Connection, *, include_deleted: bool = False) -> list[dict]:
    sql = "SELECT id, body, status, version, confirmed_at, reason, created_at FROM core_memories"
    if not include_deleted:
        sql += " WHERE status != 'deleted'"
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def record_audit(
    conn: sqlite3.Connection,
    action: str,
    subject_type: str,
    subject_id: str | None,
    detail: dict,
) -> None:
    conn.execute(
        "INSERT INTO memory_audit(id, action, subject_type, subject_id, detail_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("aud-" + uuid.uuid4().hex, action, subject_type, subject_id,
         json.dumps(detail, ensure_ascii=False), utcnow()),
    )
