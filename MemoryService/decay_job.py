"""每日衰减任务：重算保持率，低于阈值先归档（可恢复），不物理删除。

L4 核心记忆不在此表，因此天然不衰减；candidate 也不归档，等用户处理。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import db

DEFAULT_THRESHOLD = 0.15
DEFAULT_MIN_AGE_DAYS = 7


def _age_days(memory: sqlite3.Row, now: datetime) -> float:
    anchor = memory["last_reinforced_at"] or memory["created_at"]
    try:
        then = datetime.fromisoformat(str(anchor).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max((now - then).total_seconds() / 86400.0, 0.0)


def archive_stale(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_age_days: float = DEFAULT_MIN_AGE_DAYS,
    dry_run: bool = False,
) -> list[dict]:
    """把保持率低于 threshold 且已过 min_age_days 的 active 记忆归档。"""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute("SELECT * FROM memories WHERE status = 'active'").fetchall()
    archived: list[dict] = []
    for memory in rows:
        age = _age_days(memory, now)
        if age < min_age_days:
            continue
        r = db.retention(memory, now)
        if r >= threshold:
            continue
        archived.append({
            "id": memory["id"],
            "kind": memory["kind"],
            "retention": round(r, 6),
            "age_days": round(age, 2),
        })
        if dry_run:
            continue
        conn.execute(
            "UPDATE memories SET status = 'archived', archived_at = ?, updated_at = ? WHERE id = ?",
            (now.isoformat().replace("+00:00", "Z"), now.isoformat().replace("+00:00", "Z"), memory["id"]),
        )
        db.record_audit(
            conn, "decay_archive", "memory", memory["id"],
            {"retention": round(r, 6), "age_days": round(age, 2), "threshold": threshold},
        )
    if not dry_run:
        conn.commit()
    return archived
