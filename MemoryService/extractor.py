"""规则版候选提取器：成功轮次 → L2 候选（candidate），等用户确认后再激活。

先用显式线索（记住 / 喜欢 / 我养了 / 答应…）做高精度提取，避免把每句话都变成记忆。
模型提取作为后续可选层；本模块不调用任何网络。
"""

from __future__ import annotations

import re
import sqlite3

import db

# (正则, 记忆类型, 重要度)
CUE_PATTERNS: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"我(?:很|最|超)?不喜欢(?P<body>.+)"), "user_preference", 3),
    (re.compile(r"我(?:很|最|超)?喜欢(?P<body>.+)"), "user_preference", 3),
    (re.compile(r"我养了(?P<body>.+)"), "user_fact", 4),
    (re.compile(r"我住在(?P<body>.+)"), "user_fact", 4),
    (re.compile(r"我的(?P<body>.+?)是(?P<value>.+)"), "user_fact", 3),
    (re.compile(r"以后(?:都|要|会|每天)?(?P<body>.+)"), "commitment", 4),
    (re.compile(r"答应(?:我|你)?(?P<body>.+)"), "commitment", 4),
    (re.compile(r"记住[：:，,\s]*(?P<body>.+)"), "user_fact", 3),
]

SENSITIVE = re.compile(
    r"密码|口令|验证码|身份证|银行卡|信用卡|私钥|密钥|token|cookie|api[_ ]?key|secret",
    re.IGNORECASE,
)

MAX_BODY = 200


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?\n；;]", text)
    return [p.strip() for p in parts if p.strip()]


def extract_candidates(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    text: str,
    source: str = "user",
) -> list[str]:
    """从一段文本提取候选记忆，返回新建的 memory_id 列表。"""
    created: list[str] = []
    for sentence in _sentences(text):
        if len(sentence) > MAX_BODY:
            sentence = sentence[:MAX_BODY]
        if SENSITIVE.search(sentence):
            continue
        for pattern, kind, importance in CUE_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue
            body = sentence
            if kind == "user_fact" and "value" in match.groupdict() and match.group("value"):
                body = sentence
            exists = conn.execute(
                "SELECT 1 FROM memories WHERE body = ? AND status != 'deleted' LIMIT 1",
                (body,),
            ).fetchone()
            if exists:
                break
            created.append(db.add_memory(
                conn,
                kind=kind,
                body=body,
                source_event_ids=[event_id],
                tags="auto-extract",
                fact_owner="explicit_user" if source == "user" else "assistant_generated",
                importance=importance,
                confidence=0.6,
                sensitivity="private",
                status="candidate",
            ))
            break
    return created


def extract_from_event(conn: sqlite3.Connection, event_id: str) -> list[str]:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise ValueError(f"事件不存在: {event_id}")
    return extract_candidates(conn, event_id=event_id, text=row["content"], source=row["role"])
