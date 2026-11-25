"""自动心跳：定期把新会话增量入库，并刷新当天 L1 摘要。

运行在 Memory MCP 服务进程内（daemon 线程），DSH 关闭即随之停止；
不写系统计划任务，也不自动归档（归档仍由用户/模型显式触发）。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import db
import decay_job
import digest
import session_tail

DEFAULT_INTERVAL_MIN = 10


def tick_once() -> dict:
    ingest = session_tail.run()
    today = datetime.now(timezone.utc).date().isoformat()
    conn = db.init_db(Path.home() / ".dsh" / "memory-v2" / "memory.db")
    try:
        digest.generate(conn, today)
        # 只监控不归档：报告哪些记忆已低于保持率阈值，实际归档仍由用户/模型显式触发
        stale = decay_job.archive_stale(conn, dry_run=True)
    finally:
        conn.close()
    return {"ingest": ingest, "digest_day": today, "stale": len(stale)}


def _loop(interval_seconds: int) -> None:
    while True:
        time.sleep(interval_seconds)
        try:
            result = tick_once()
            print(f"[auto-tick] {result}", file=sys.stderr, flush=True)
        except Exception as exc:  # 心跳失败不能杀掉服务
            print(f"[auto-tick] failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def start(interval_minutes: int | None = None) -> threading.Thread | None:
    if os.environ.get("DFY_MEMORY_AUTO_TICK", "1") == "0":
        return None
    minutes = interval_minutes or int(os.environ.get("DFY_MEMORY_AUTO_TICK_MINUTES", DEFAULT_INTERVAL_MIN))
    minutes = max(1, minutes)
    thread = threading.Thread(target=_loop, args=(minutes * 60,), name="dfy-memory-auto-tick", daemon=True)
    thread.start()
    print(f"[auto-tick] started, every {minutes} min", file=sys.stderr, flush=True)
    return thread
