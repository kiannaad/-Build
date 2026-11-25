import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import digest  # noqa: E402


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _event(self, turn_id, day, role, text):
        eid, _ = db.add_event(
            self.conn, turn_id=turn_id, occurred_at=f"{day}T08:00:00.000Z",
            actor="owner", role=role, content=text, session_id="s-1",
        )
        return eid

    def test_generate_counts_and_todos(self):
        e1 = self._event("d1-u", "2026-11-25", "user", "以后每天提醒我喝水。")
        self._event("d1-a", "2026-11-25", "assistant", "好。")
        self._event("d2-u", "2026-11-26", "user", "第二天。")
        mid = db.add_memory(
            self.conn, kind="commitment", body="每天提醒喝水",
            source_event_ids=[e1], fact_owner="explicit_user", status="active",
        )
        self.conn.execute(
            "UPDATE memories SET created_at='2026-11-25T08:00:00.000Z' WHERE id=?", (mid,)
        )
        self.conn.commit()

        result = digest.generate(self.conn, "2026-11-25")
        self.assertIn("用户 1", result["summary"])
        self.assertIn("助手 1", result["summary"])
        self.assertIn("激活 1", result["summary"])
        self.assertIn("每天提醒喝水", result["todos_json"])
        self.assertTrue(json.loads(result["source_event_ids"]))

    def test_get_missing_returns_none(self):
        self.assertIsNone(digest.get(self.conn, "2020-01-01"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
