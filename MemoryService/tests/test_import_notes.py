import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import import_notes  # noqa: E402


class ImportNotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.note = self.root / "note.md"
        self.note.write_text("我喜欢民谣。", encoding="utf-8")
        self.entries = [
            {"body": "喜欢民谣", "kind": "user_preference", "sensitivity": "private",
             "confidence": 0.8, "importance": 4, "status": "active", "source": str(self.note)},
            {"body": "容易焦虑", "kind": "user_fact", "sensitivity": "restricted",
             "confidence": 0.6, "importance": 3, "status": "candidate", "source": str(self.note)},
        ]
        self.conn = db.init_db(self.root / "memory.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_import_and_idempotent(self):
        first = import_notes.import_entries(self.conn, self.entries)
        self.assertEqual(len(first["created"]), 2)
        rows = self.conn.execute("SELECT status, sensitivity, tags FROM memories ORDER BY status").fetchall()
        self.assertEqual({r["status"] for r in rows}, {"active", "candidate"})
        self.assertTrue(all(r["tags"] == "notes-import" for r in rows))
        second = import_notes.import_entries(self.conn, self.entries)
        self.assertEqual(len(second["created"]), 0)
        self.assertEqual(len(second["skipped"]), 2)

    def test_dry_run_writes_nothing(self):
        result = import_notes.import_entries(self.conn, self.entries, dry_run=True)
        self.assertEqual(len(result["created"]), 2)
        count = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        self.assertEqual(count, 0)

    def test_missing_status_defaults_to_candidate(self):
        entries = [{"body": "默认候选", "kind": "user_fact", "source": str(self.note)}]
        import_notes.import_entries(self.conn, entries)
        row = self.conn.execute("SELECT status FROM memories WHERE body = '默认候选'").fetchone()
        self.assertEqual(row["status"], "candidate")


if __name__ == "__main__":
    unittest.main(verbosity=2)
