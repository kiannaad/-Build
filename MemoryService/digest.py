"""L1 每日摘要：只读当天事件与当天新增记忆，不反复总结摘要。

先用规则生成结构化摘要（轮次、候选、激活、承诺），后续可让模型在固定事实上润色。
日期按 occurred_at / created_at 的 UTC 日期前缀归类，避免本地时区边界歧义。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import db

MAX_SOURCE_EVENTS = 50


def _day(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).date().isoformat()


def generate(conn: sqlite3.Connection, day: str | None = None) -> dict:
    day = day or _day()
    user_n = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE substr(occurred_at,1,10)=? AND role='user'", (day,)
    ).fetchone()["n"]
    assistant_n = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE substr(occurred_at,1,10)=? AND role='assistant'", (day,)
    ).fetchone()["n"]
    sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_id) AS n FROM events WHERE substr(occurred_at,1,10)=? AND session_id IS NOT NULL",
        (day,),
    ).fetchone()["n"]
    candidates = conn.execute(
        "SELECT COUNT(*) AS n FROM memories WHERE substr(created_at,1,10)=? AND status='candidate'", (day,)
    ).fetchone()["n"]
    active = conn.execute(
        "SELECT COUNT(*) AS n FROM memories WHERE substr(created_at,1,10)=? AND status='active'", (day,)
    ).fetchone()["n"]
    commitments = [
        r["body"] for r in conn.execute(
            "SELECT body FROM memories WHERE substr(created_at,1,10)=? AND kind='commitment'"
            " AND status != 'deleted' ORDER BY created_at",
            (day,),
        ).fetchall()
    ]
    event_ids = [
        r["id"] for r in conn.execute(
            "SELECT id FROM events WHERE substr(occurred_at,1,10)=? ORDER BY occurred_at LIMIT ?",
            (day, MAX_SOURCE_EVENTS),
        ).fetchall()
    ]

    summary = (
        f"{day}：用户 {user_n} 条、助手 {assistant_n} 条消息"
        f"（{sessions} 个会话）；新增记忆候选 {candidates} 条，激活 {active} 条。"
    )
    if commitments:
        summary += " 承诺/计划：" + "；".join(commitments[:5]) + "。"

    db.upsert_digest(
        conn,
        day=day,
        summary=summary,
        mood="",
        todos=commitments,
        source_event_ids=event_ids,
    )
    row = conn.execute("SELECT * FROM daily_digests WHERE day=?", (day,)).fetchone()
    return dict(row)


def get(conn: sqlite3.Connection, day: str) -> dict | None:
    row = conn.execute("SELECT * FROM daily_digests WHERE day=?", (day,)).fetchone()
    return dict(row) if row else None
