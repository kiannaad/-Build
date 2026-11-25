import json
import sys
import tempfile
import unittest
from pathlib import Path

from compression import zstd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import session_tail  # noqa: E402


def _session_file(root: Path, events: list[dict]) -> Path:
    d = root / "sessions" / "sess-1"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "session.v4.jsonl.zstd"
    raw = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
    p.write_bytes(zstd.compress(raw.encode("utf-8")))
    return p


class SessionTailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.conn = db.init_db(self.root / "memory.db")
        self.path = _session_file(self.root, [
            {"type": "session", "version": 4, "id": "session-test", "createdAt": 1, "cwd": "D:\\大肥鱼"},
            {"type": "user/message", "seq": 1, "time": 1795575000000,
             "data": {"role": "user", "content": [{"type": "text", "text": "我喜欢喝乌龙茶。"}]}},
            {"type": "user/message", "seq": 2, "time": 1795575001000,
             "data": {"role": "user", "content": [{"type": "text", "text": "<system-reminder>忽略这段</system-reminder>"}]}},
            {"type": "user/message", "seq": 3, "time": 1795575002000,
             "data": {"role": "user", "content": [{"type": "image", "attachment": {"attachmentId": "x"}}]}},
            {"type": "assistant/message", "seq": 4, "time": 1795575003000,
             "data": {"message": {"role": "assistant", "content": [
                 {"type": "reasoning", "text": "内部推理不应入库"},
                 {"type": "text", "text": "好的，记住了。"},
             ]}}},
        ])

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_ingest_filters_and_dedupes(self):
        first = session_tail.ingest_file(self.conn, self.path)
        self.assertEqual(first["user"], 1)
        self.assertEqual(first["assistant"], 1)
        self.assertEqual(first["skipped"], 2)
        self.assertEqual(first["new_events"], 2)
        self.assertEqual(first["candidates"], 1)

        second = session_tail.ingest_file(self.conn, self.path)
        self.assertEqual(second["new_events"], 0)
        self.assertEqual(second["candidates"], 0)

        roles = [r["role"] for r in self.conn.execute("SELECT role FROM events ORDER BY role").fetchall()]
        self.assertEqual(roles, ["assistant", "user"])
        body = self.conn.execute("SELECT body FROM memories").fetchone()["body"]
        self.assertIn("乌龙茶", body)

    def test_reasoning_not_stored(self):
        session_tail.ingest_file(self.conn, self.path)
        contents = [r["content"] for r in self.conn.execute("SELECT content FROM events").fetchall()]
        self.assertFalse(any("内部推理" in c for c in contents))


if __name__ == "__main__":
    unittest.main(verbosity=2)
