"""L2 候选提取的模型层（可选），规则层 extractor.py 的补充。

调用方注入 `call_model(prompt) -> str`，便于：
- 本地 Ollama / 远端 API 自由替换；
- 测试用假模型，不联网。
只产出候选（candidate），不直接激活；敏感内容仍由规则层过滤。
"""

from __future__ import annotations

import json
import sqlite3

import db
import extractor

ALLOWED_KINDS = {
    "user_fact", "user_preference", "relationship", "commitment",
    "experience", "interest", "boundary", "assistant_reflection",
}
MAX_ITEMS = 5
MAX_BODY = 200

SYSTEM_PROMPT = """你是记忆提取器。只从下面这条“用户消息”里提取值得长期记住的内容。
规则：
- 只提取用户明确表达的事实、偏好、关系、承诺、边界、经历、兴趣；
- 不提取寒暄、反问、临时情绪、一次性任务；
- 不编造，不把推测写成事实；
- 涉及密码、验证码、身份证、银行卡、Cookie、Token、密钥的内容一律跳过；
- 最多 5 条；没有就返回 []。
只返回 JSON 数组，每项：{"body": "...", "kind": "user_fact|user_preference|relationship|commitment|experience|interest|boundary", "importance": 1-5, "confidence": 0-1}
不要输出解释或 Markdown。"""


def _strip_fence(text: str) -> str:
    text = str(text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_items(raw: str) -> list[dict]:
    text = _strip_fence(raw)
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("memories") or data.get("items") or []
    if not isinstance(data, list):
        return []
    out = []
    for item in data[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        body = str(item.get("body") or "").strip()[:MAX_BODY]
        kind = str(item.get("kind") or "").strip()
        if not body or kind not in ALLOWED_KINDS:
            continue
        if extractor.SENSITIVE.search(body):
            continue
        try:
            importance = int(item.get("importance", 3))
        except (TypeError, ValueError):
            importance = 3
        try:
            confidence = float(item.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence = 0.6
        out.append({
            "body": body,
            "kind": kind,
            "importance": max(1, min(importance, 5)),
            "confidence": max(0.0, min(confidence, 1.0)),
        })
    return out


def extract_with_model(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    call_model,
) -> list[str]:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise ValueError(f"事件不存在: {event_id}")
    if row["role"] != "user":
        return []
    prompt = f"{SYSTEM_PROMPT}\n\n用户消息：\n{row['content']}"
    try:
        raw = call_model(prompt)
    except Exception:
        return []
    created: list[str] = []
    for item in parse_items(raw):
        exists = conn.execute(
            "SELECT 1 FROM memories WHERE body = ? AND status != 'deleted' LIMIT 1",
            (item["body"],),
        ).fetchone()
        if exists:
            continue
        created.append(db.add_memory(
            conn,
            kind=item["kind"],
            body=item["body"],
            source_event_ids=[event_id],
            tags="model-extract",
            fact_owner="explicit_user",
            importance=item["importance"],
            confidence=item["confidence"],
            sensitivity="private",
            status="candidate",
        ))
    return created
