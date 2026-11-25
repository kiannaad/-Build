"""L1 每日摘要：只读当天事件与当天新增记忆，不反复总结摘要。

先用规则生成结构化摘要（轮次、候选、激活、承诺），后续可让模型在固定事实上润色。
日期按 occurred_at / created_at 的 UTC 日期前缀归类，避免本地时区边界歧义。
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import db

MAX_SOURCE_EVENTS = 50
DAY_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADING = re.compile(r"^###\s+(BV[0-9A-Za-z]+|\d{6,})")
BILI_TITLE = re.compile(r"^-\s*标题[：:]\s*(.+)$")
DOUYIN_TITLE = re.compile(r"^\*\*(.+?)\*\*\s*·")


def _report_brief(day: str, folders: list[Path]) -> str:
    parts = []
    for label, folder in zip(("B站", "抖音"), folders):
        path = folder / f"{day}.md"
        if not DAY_FILE.match(day) or not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        titles = []
        current = False
        for line in lines:
            stripped = line.strip()
            if HEADING.match(stripped):
                current = True
                continue
            if current:
                m = BILI_TITLE.match(stripped) or DOUYIN_TITLE.match(stripped)
                if m:
                    titles.append(m.group(1).strip())
                current = False
        if titles:
            parts.append(f"{label}推荐 {len(titles)} 条（{'；'.join(titles[:3])}）")
    return "；".join(parts)


def _day(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).date().isoformat()


def generate(
    conn: sqlite3.Connection,
    day: str | None = None,
    report_dirs: list[Path] | None = None,
) -> dict:
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
    folders = report_dirs if report_dirs is not None else [
        Path.home() / ".dsh" / "bili-duty" / "out",
        Path.home() / ".dsh" / "douyin-duty" / "out",
    ]
    brief = _report_brief(day, folders)
    if brief:
        summary += " 日报：" + brief + "。"

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
