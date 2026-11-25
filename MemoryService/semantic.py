"""语义召回：向量相似度 + 与 db.recall 相同的精排。"""

from __future__ import annotations

import sqlite3

import db
import embeddings


def semantic_recall(
    conn: sqlite3.Connection,
    query: str,
    embedder,
    *,
    limit: int = 4,
    include_restricted: bool = False,
    now=None,
) -> list[dict]:
    qvec = embedder.embed(query)
    candidates = embeddings.semantic_candidates(
        conn,
        query_vec=qvec,
        model=embedder.model,
        limit=max(limit * 5, 20),
        include_restricted=include_restricted,
    )
    if not candidates:
        return []
    out: list[dict] = []
    for memory_id, similarity in candidates:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None or row["status"] != "active":
            continue
        rec = db.retention(row, now)
        score = similarity * (
            0.55
            + 0.15 * (int(row["importance"]) / 5.0)
            + 0.10 * float(row["confidence"])
            + 0.10 * rec
            + 0.05 * min(int(row["reinforcement"]) / 5.0, 1.0)
            + 0.05 * 0.5
        )
        out.append({
            "id": memory_id,
            "body": row["body"],
            "similarity": round(similarity, 4),
            "score": round(score, 4),
            "retention": round(rec, 4),
            "importance": row["importance"],
            "confidence": row["confidence"],
            "reinforcement": row["reinforcement"],
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def embed_all(conn: sqlite3.Connection, embedder, *, limit: int = 500) -> int:
    return embeddings.embed_missing(conn, embedder, limit=limit)
