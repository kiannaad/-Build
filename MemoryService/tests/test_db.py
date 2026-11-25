import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402


class MemoryDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        self.event_id, _ = db.add_event(
            self.conn,
            turn_id="turn-1",
            occurred_at="2026-11-25T08:00:00.000Z",
            actor="owner",
            role="user",
            content="我养了一只橘猫，叫年糕。",
        )

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _memory(self, **kwargs):
        params = dict(
            kind="user_fact",
            body="主人养了一只橘猫，名字叫年糕",
            source_event_ids=[self.event_id],
            fact_owner="explicit_user",
            importance=4,
            confidence=0.9,
            status="active",
        )
        params.update(kwargs)
        return db.add_memory(self.conn, **params)

    def test_event_idempotent(self):
        second, created = db.add_event(
            self.conn,
            turn_id="turn-1",
            occurred_at="2026-11-25T08:00:00.000Z",
            actor="owner",
            role="user",
            content="重复提交",
        )
        self.assertFalse(created)
        self.assertEqual(second, self.event_id)
        count = self.conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        self.assertEqual(count, 1)

    def test_memory_requires_source(self):
        with self.assertRaises(ValueError):
            db.add_memory(self.conn, kind="user_fact", body="无来源", source_event_ids=[])

    def test_recall_with_chinese_keyword(self):
        self._memory()
        hits = db.recall(self.conn, "橘猫")
        self.assertEqual(len(hits), 1)
        self.assertIn("年糕", hits[0]["body"])
        self.assertGreater(hits[0]["score"], 0)

    def test_archive_and_restore(self):
        memory_id = self._memory()
        db.set_memory_status(self.conn, memory_id, "archived", "测试归档")
        self.assertEqual(db.recall(self.conn, "橘猫"), [])
        db.set_memory_status(self.conn, memory_id, "active", "恢复")
        self.assertEqual(len(db.recall(self.conn, "橘猫")), 1)

    def test_forget_excludes(self):
        memory_id = self._memory()
        db.set_memory_status(self.conn, memory_id, "deleted", "用户要求遗忘")
        self.assertEqual(db.recall(self.conn, "橘猫"), [])
        row = self.conn.execute("SELECT status FROM memories WHERE id = ?", (memory_id,)).fetchone()
        self.assertEqual(row["status"], "deleted")

    def test_retention_decays_and_reinforcement_extends(self):
        memory_id = self._memory(half_life_days=30)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
        self.conn.execute("UPDATE memories SET created_at = ? WHERE id = ?", (old, memory_id))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        plain = db.retention(row)
        self.assertAlmostEqual(plain, 0.25, places=2)
        db.reinforce(self.conn, memory_id)
        db.reinforce(self.conn, memory_id)
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        self.assertGreater(db.retention(row), plain)

    def test_restricted_excluded_by_default(self):
        self._memory(sensitivity="restricted", body="私密医疗信息")
        self.assertEqual(db.recall(self.conn, "医疗"), [])
        self.assertEqual(len(db.recall(self.conn, "医疗", include_restricted=True)), 1)

    def test_digest_upsert(self):
        db.upsert_digest(self.conn, day="2026-11-25", summary="第一天", mood="平静")
        db.upsert_digest(self.conn, day="2026-11-25", summary="第一天（改）", mood="开心")
        rows = self.conn.execute("SELECT * FROM daily_digests").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["summary"], "第一天（改）")

    def test_audit_written(self):
        self._memory()
        n = self.conn.execute("SELECT COUNT(*) AS n FROM memory_audit").fetchone()["n"]
        self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
