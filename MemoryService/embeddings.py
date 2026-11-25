"""向量层：可插拔嵌入后端 + 本地暴力余弦召回。

设计：
- 嵌入模型通过协议注入，测试用假嵌入器，不联网；
- 嵌入记录保存模型 ID、维度、内容哈希，换模型不会混用；
- 数据量小时用 Python 暴力余弦即可，后续可换 sqlite-vec；
- 嵌入失败不阻塞聊天，只标记缺失，后台可补。
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import struct
import urllib.request
from array import array
from datetime import datetime, timezone
from typing import Protocol


class Embedder(Protocol):
    model: str

    def embed(self, text: str) -> list[float]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def save_embedding(conn: sqlite3.Connection, *, memory_id: str, model: str, vec: list[float], text: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO memory_embeddings(memory_id, model, dim, vector, content_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (memory_id, model, len(vec), pack(vec), _hash(text), _now()),
    )
    conn.commit()


def load_embeddings(conn: sqlite3.Connection, model: str) -> dict[str, list[float]]:
    rows = conn.execute(
        "SELECT memory_id, vector FROM memory_embeddings WHERE model = ?", (model,)
    ).fetchall()
    return {r["memory_id"]: unpack(r["vector"]) for r in rows}


def embed_missing(conn: sqlite3.Connection, embedder: Embedder, *, limit: int = 100) -> int:
    """为还没有该模型向量的 active/候选记忆补向量，返回补了几条。"""
    rows = conn.execute(
        """SELECT m.id, m.body FROM memories m
           LEFT JOIN memory_embeddings e ON e.memory_id = m.id AND e.model = ?
           WHERE e.memory_id IS NULL AND m.status != 'deleted' AND m.sensitivity != 'restricted'
           ORDER BY m.created_at DESC LIMIT ?""",
        (embedder.model, limit),
    ).fetchall()
    n = 0
    for row in rows:
        vec = embedder.embed(row["body"])
        save_embedding(conn, memory_id=row["id"], model=embedder.model, vec=vec, text=row["body"])
        n += 1
    return n


def semantic_candidates(
    conn: sqlite3.Connection,
    *,
    query_vec: list[float],
    model: str,
    limit: int = 10,
    include_restricted: bool = False,
) -> list[tuple[str, float]]:
    """对 active 记忆做暴力余弦，返回 [(memory_id, similarity)]。"""
    rows = conn.execute(
        "SELECT id, sensitivity FROM memories WHERE status = 'active'"
    ).fetchall()
    allowed = {
        r["id"] for r in rows if include_restricted or r["sensitivity"] != "restricted"
    }
    vectors = load_embeddings(conn, model)
    scored = [(mid, cosine(query_vec, vec)) for mid, vec in vectors.items() if mid in allowed]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


class OllamaEmbedder:
    """本地 Ollama；默认试图用 bge-m3，没有该模型时调用会报错，不静默降级。"""

    def __init__(self, model: str = "bge-m3", url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.url = url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "input": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/api/embed", data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return list(data["embeddings"][0])


class SiliconFlowEmbedder:
    """硅基流动 OpenAI 兼容 /embeddings；key 只从环境变量读。"""

    def __init__(self, model: str = "BAAI/bge-m3", api_key: str | None = None,
                 url: str = "https://api.siliconflow.cn/v1/embeddings"):
        import os

        self.model = model
        self.url = url
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")

    def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError("缺少 SILICONFLOW_API_KEY")
        payload = json.dumps({"model": self.model, "input": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return list(data["data"][0]["embedding"])
