import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import decay_job  # noqa: E402
import extractor  # noqa: E402


class ExtractorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        self.n = 0

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _event(self, text, role="user"):
        self.n += 1
        event_id, _ = db.add_event(
            self.conn,
            turn_id=f"t-{self.n}",
            occurred_at="2026-11-25T10:00:00.000Z",
            actor="owner",
            role=role,
            content=text,
        )
        return event_id

    def test_extract_preference(self):
        eid = self._event("记住：我喜欢喝乌龙茶。")
        ids = extractor.extract_from_event(self.conn, eid)
        self.assertEqual(len(ids), 1)
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (ids[0],)).fetchone()
        self.assertEqual(row["kind"], "user_preference")
        self.assertEqual(row["status"], "candidate")
        self.assertIn("乌龙茶", row["body"])

    def test_no_cue_no_memory(self):
        eid = self._event("今天天气不错。")
        self.assertEqual(extractor.extract_from_event(self.conn, eid), [])

    def test_duplicate_not_created_twice(self):
        eid = self._event("我喜欢喝乌龙茶。")
        first = extractor.extract_from_event(self.conn, eid)
        second = extractor.extract_from_event(self.conn, eid)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_sensitive_skipped(self):
        eid = self._event("我的密码是 abc123。")
        self.assertEqual(extractor.extract_from_event(self.conn, eid), [])
        n = self.conn.execute("SELECT COUNT(*) AS n FROM memories").fetchone()["n"]
        self.assertEqual(n, 0)

    def test_commitment(self):
        eid = self._event("以后每天提醒我喝水。")
        ids = extractor.extract_from_event(self.conn, eid)
        self.assertEqual(len(ids), 1)
        row = self.conn.execute("SELECT kind FROM memories WHERE id = ?", (ids[0],)).fetchone()
        self.assertEqual(row["kind"], "commitment")


class DecayJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        eid, _ = db.add_event(
            self.conn,
            turn_id="decay-1",
            occurred_at="2025-01-01T00:00:00.000Z",
            actor="owner",
            role="user",
            content="旧事件",
        )
        self.eid = eid

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _memory(self, status="active", half_life=30, age_days=0):
        mid = db.add_memory(
            self.conn, kind="event", body=f"记忆-{age_days}-{status}",
            source_event_ids=[self.eid], fact_owner="observed",
            status=status, half_life_days=half_life,
        )
        old = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat().replace("+00:00", "Z")
        self.conn.execute("UPDATE memories SET created_at = ? WHERE id = ?", (old, mid))
        self.conn.commit()
        return mid

    def test_old_memory_archived(self):
        mid = self._memory(age_days=365)
        archived = decay_job.archive_stale(self.conn)
        self.assertEqual([a["id"] for a in archived], [mid])
        row = self.conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        self.assertEqual(row["status"], "archived")

    def test_fresh_memory_kept(self):
        self._memory(age_days=1)
        self.assertEqual(decay_job.archive_stale(self.conn), [])

    def test_candidate_not_archived(self):
        mid = self._memory(status="candidate", age_days=365)
        self.assertEqual(decay_job.archive_stale(self.conn), [])
        row = self.conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        self.assertEqual(row["status"], "candidate")

    def test_reinforced_memory_survives(self):
        mid = self._memory(age_days=90)
        for _ in range(4):
            db.reinforce(self.conn, mid)
        self.assertEqual(decay_job.archive_stale(self.conn), [])
        row = self.conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        self.assertEqual(row["status"], "active")

    def test_dry_run_does_not_write(self):
        mid = self._memory(age_days=365)
        archived = decay_job.archive_stale(self.conn, dry_run=True)
        self.assertEqual(len(archived), 1)
        row = self.conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        self.assertEqual(row["status"], "active")


if __name__ == "__main__":
    unittest.main(verbosity=2)
